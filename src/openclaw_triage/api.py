"""FastAPI server for OpenClaw Triage webhook and API."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from openclaw_triage.config import get_settings
from openclaw_triage.github_client import GitHubClient
from openclaw_triage.llm_client import LLMClient
from openclaw_triage.orchestrator import TriageOrchestrator
from openclaw_triage.models import TriageResult


# Global instances
orchestrator: TriageOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global orchestrator
    
    # Startup
    settings = get_settings()
    github = GitHubClient()
    llm = None
    
    if os.getenv("ANTHROPIC_API_KEY"):
        llm = LLMClient(provider="anthropic")
    elif os.getenv("OPENAI_API_KEY"):
        llm = LLMClient(provider="openai")
    
    orchestrator = TriageOrchestrator(github_client=github, llm_client=llm)
    
    yield
    
    # Shutdown
    if orchestrator:
        await orchestrator.close()


app = FastAPI(
    title="OpenClaw Triage API",
    description="AI-powered PR/Issue triage for OpenClaw",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzePRRequest(BaseModel):
    """Request to analyze a PR."""
    repo: str
    pr_number: int
    enable_dedup: bool = True
    enable_base_detection: bool = True
    enable_review: bool = True
    enable_vision: bool = True


class AnalyzeIssueRequest(BaseModel):
    """Request to analyze an Issue."""
    repo: str
    issue_number: int
    enable_dedup: bool = True


class BatchRequest(BaseModel):
    """Request for batch analysis."""
    repo: str
    limit: int = 10


@app.get("/")
async def root():
    """Health check."""
    return {
        "status": "ok",
        "service": "openclaw-triage",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    settings = get_settings()
    return {
        "status": "healthy",
        "github_token_set": bool(settings.github.token),
        "llm_available": orchestrator and orchestrator.llm is not None,
    }


@app.post("/analyze/pr", response_model=TriageResult)
async def analyze_pr(request: AnalyzePRRequest):
    """Analyze a single PR."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    result = await orchestrator.triage_pr(
        repo=request.repo,
        pr_number=request.pr_number,
        enable_dedup=request.enable_dedup,
        enable_base_detection=request.enable_base_detection,
        enable_review=request.enable_review,
        enable_vision=request.enable_vision,
    )
    
    return result


@app.post("/analyze/issue", response_model=TriageResult)
async def analyze_issue(request: AnalyzeIssueRequest):
    """Analyze a single Issue."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    result = await orchestrator.triage_issue(
        repo=request.repo,
        issue_number=request.issue_number,
        enable_dedup=request.enable_dedup,
    )
    
    return result


@app.post("/analyze/batch")
async def analyze_batch(request: BatchRequest, background_tasks: BackgroundTasks):
    """Start batch analysis (runs in background)."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # For now, just return accepted
    # In production, this would queue the job
    return {
        "status": "accepted",
        "repo": request.repo,
        "limit": request.limit,
        "message": "Batch analysis queued",
    }


@app.post("/webhook/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events."""
    settings = get_settings()
    
    # Verify signature if secret is configured
    if settings.github.webhook_secret:
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing signature")
        # TODO: Verify signature
    
    event_type = request.headers.get("X-GitHub-Event")
    payload = await request.json()
    
    if event_type == "pull_request":
        action = payload.get("action")
        if action in ["opened", "synchronize", "reopened"]:
            # Trigger analysis
            repo = payload["repository"]["full_name"]
            pr_number = payload["pull_request"]["number"]
            
            if orchestrator:
                result = await orchestrator.triage_pr(repo, pr_number)
                
                # Post comment if configured
                if os.getenv("POST_COMMENTS", "false").lower() == "true":
                    await orchestrator.github.add_comment(
                        repo, pr_number, format_comment(result)
                    )
                
                return {"status": "analyzed", "pr": pr_number}
    
    elif event_type == "issues":
        action = payload.get("action")
        if action == "opened":
            repo = payload["repository"]["full_name"]
            issue_number = payload["issue"]["number"]
            
            if orchestrator:
                result = await orchestrator.triage_issue(repo, issue_number)
                return {"status": "analyzed", "issue": issue_number}
    
    return {"status": "ignored", "event": event_type}


def format_comment(result: TriageResult) -> str:
    """Format triage result as GitHub comment."""
    lines = [
        "## 🤖 Triage Analysis",
        "",
        f"**Executive Summary:** {result.executive_summary}",
        f"**Priority:** {result.priority.upper()}",
        f"**Recommended Action:** {result.recommended_action}",
        "",
    ]
    
    if result.deduplication and result.deduplication.is_duplicate:
        lines.extend([
            "### ⚠️ Duplicate Detected",
            f"Likely duplicate of #{result.deduplication.canonical_item.item_number}",
            "",
        ])
    
    if result.base_detection and result.base_detection.is_base_candidate:
        lines.extend([
            "### ⭐ Base PR Candidate",
            f"Score: {result.base_detection.score.total_score:.0%}",
            "",
        ])
    
    return "\n".join(lines)


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
