"""Lightweight API without heavy ML dependencies for serverless."""

import os
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from openclaw_triage.config import get_settings
from openclaw_triage.github_client import GitHubClient
from openclaw_triage.llm_client import LLMClient
from openclaw_triage.models import (
    AnalysisStatus,
    BaseDetectionResult,
    BasePRScore,
    DeepReviewResult,
    DeduplicationResult,
    PRIssueType,
    TriageResult,
    VisionAlignmentResult,
)

app = FastAPI(
    title="OpenClaw Triage API (Lightweight)",
    description="AI-powered PR/Issue triage - lightweight version",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzePRRequest(BaseModel):
    repo: str
    pr_number: int


@app.get("/")
async def root():
    return {"status": "ok", "service": "openclaw-triage", "version": "0.1.0"}


@app.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "healthy",
        "mode": "lightweight",
        "github_token_set": bool(settings.github.token),
    }


@app.post("/analyze/pr")
async def analyze_pr(request: AnalyzePRRequest):
    """Analyze a PR using lightweight heuristics (no embeddings)."""
    settings = get_settings()
    
    if not settings.github.token:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN not configured")
    
    github = GitHubClient()
    
    try:
        # Fetch PR
        pr = await github.get_pull_request(request.repo, request.pr_number)
        
        # Lightweight analysis (no heavy ML)
        result = TriageResult(
            item_type=PRIssueType.PULL_REQUEST,
            item_number=request.pr_number,
            repository=request.repo,
            status=AnalysisStatus.COMPLETED,
            deduplication=DeduplicationResult(
                is_duplicate=False,
                confidence=0.0,
                analysis_summary="Lightweight mode - deduplication requires full deployment",
            ),
            base_detection=BaseDetectionResult(
                is_base_candidate=pr.has_tests and pr.has_docs,
                score=BasePRScore(
                    chronological_score=0.5,
                    quality_score=0.7 if pr.has_tests else 0.4,
                    engagement_score=min(pr.comments_count / 10, 1.0),
                    author_score=0.5,
                    completeness_score=0.7 if pr.has_docs else 0.4,
                    total_score=0.6 if (pr.has_tests and pr.has_docs) else 0.5,
                ),
                reasoning="Lightweight heuristic analysis",
                recommendation="Review manually or deploy full version for AI analysis",
            ),
            deep_review=DeepReviewResult(
                summary=f"Lightweight analysis for PR #{request.pr_number}",
                overall_quality=0.7 if pr.has_tests else 0.5,
                test_coverage_assessment="Has tests" if pr.has_tests else "No tests detected",
                security_risk="unknown",
                action_items=["Deploy full version for complete analysis"] if not pr.has_tests else [],
            ),
            vision_alignment=VisionAlignmentResult(
                alignment_score=0.7,
                status="needs_discussion",
                recommendation="Lightweight mode - full vision check requires AI",
            ),
            executive_summary=f"{'✅' if pr.has_tests else '⚠️'} Tests: {'yes' if pr.has_tests else 'no'} | {'✅' if pr.has_docs else '⚠️'} Docs: {'yes' if pr.has_docs else 'no'} | Size: {pr.additions + pr.deletions} lines",
            priority="high" if (pr.has_tests and pr.has_docs) else "normal",
            recommended_action="Review PR" + (" - looks good" if (pr.has_tests and pr.has_docs) else " - consider adding tests/docs"),
        )
        
        await github.close()
        return result
        
    except Exception as e:
        await github.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/github")
async def github_webhook(request: dict):
    """Handle GitHub webhook events."""
    event_type = request.get("headers", {}).get("X-GitHub-Event", "unknown")
    
    # Lightweight response
    return {
        "status": "received",
        "event": event_type,
        "message": "Lightweight mode - deploy full version for automatic analysis",
    }
