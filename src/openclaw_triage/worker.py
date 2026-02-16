"""Background worker for batch processing and queue handling."""

import asyncio
import json
import os
from datetime import datetime

from openclaw_triage.config import get_settings
from openclaw_triage.github_client import GitHubClient
from openclaw_triage.llm_client import LLMClient
from openclaw_triage.orchestrator import TriageOrchestrator


class Worker:
    """Background worker for processing triage jobs."""
    
    def __init__(self) -> None:
        """Initialize worker."""
        self.settings = get_settings()
        self.github = GitHubClient()
        
        # Initialize LLM if API key available
        self.llm = None
        if os.getenv("ANTHROPIC_API_KEY"):
            self.llm = LLMClient(provider="anthropic")
        elif os.getenv("OPENAI_API_KEY"):
            self.llm = LLMClient(provider="openai")
        
        self.orchestrator = TriageOrchestrator(
            github_client=self.github,
            llm_client=self.llm,
        )
    
    async def run_batch_analysis(self, repo: str, limit: int = 50) -> dict:
        """Run batch analysis on open PRs.
        
        Args:
            repo: Repository to analyze
            limit: Max PRs to analyze
            
        Returns:
            Summary of results
        """
        print(f"Starting batch analysis for {repo}")
        print(f"Limit: {limit} PRs")
        
        # Get open PRs
        prs = await self.github.list_pull_requests(repo, state="open", per_page=limit)
        print(f"Found {len(prs)} open PRs")
        
        results = []
        duplicates = []
        base_candidates = []
        
        for i, pr in enumerate(prs, 1):
            print(f"\nAnalyzing PR #{pr.number} ({i}/{len(prs)})...")
            
            try:
                result = await self.orchestrator.triage_pr(
                    repo=repo,
                    pr_number=pr.number,
                    enable_dedup=True,
                    enable_base_detection=True,
                    enable_review=self.llm is not None,
                    enable_vision=self.llm is not None,
                )
                
                results.append(result)
                
                # Track interesting findings
                if result.deduplication and result.deduplication.is_duplicate:
                    duplicates.append({
                        "pr": pr.number,
                        "duplicate_of": result.deduplication.canonical_item.item_number,
                        "confidence": result.deduplication.confidence,
                    })
                
                if result.base_detection and result.base_detection.is_base_candidate:
                    base_candidates.append({
                        "pr": pr.number,
                        "score": result.base_detection.score.total_score,
                        "competing": result.base_detection.competing_prs,
                    })
                
                # Post comment if configured
                if os.getenv("POST_COMMENTS", "false").lower() == "true":
                    comment = self._format_comment(result)
                    await self.github.add_comment(repo, pr.number, comment)
                    print(f"  Posted comment on PR #{pr.number}")
                
            except Exception as e:
                print(f"  Error analyzing PR #{pr.number}: {e}")
                continue
        
        # Generate summary
        summary = {
            "repo": repo,
            "analyzed_at": datetime.utcnow().isoformat(),
            "total_prs": len(prs),
            "duplicates_found": len(duplicates),
            "base_candidates": len(base_candidates),
            "duplicates": duplicates,
            "base_candidates_details": base_candidates,
        }
        
        print("\n" + "="*50)
        print("BATCH ANALYSIS COMPLETE")
        print("="*50)
        print(f"Total PRs analyzed: {summary['total_prs']}")
        print(f"Duplicates found: {summary['duplicates_found']}")
        print(f"Base candidates: {summary['base_candidates']}")
        
        if duplicates:
            print("\nDuplicates:")
            for d in duplicates:
                print(f"  PR #{d['pr']} -> #{d['duplicate_of']} ({d['confidence']:.0%})")
        
        if base_candidates:
            print("\nBase candidates:")
            for b in base_candidates:
                print(f"  PR #{b['pr']} (score: {b['score']:.0%})")
        
        return summary
    
    def _format_comment(self, result) -> str:
        """Format result as GitHub comment."""
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
        
        if result.deep_review:
            lines.extend([
                "### Code Review",
                f"Quality: {result.deep_review.overall_quality:.0%}",
                f"Security: {result.deep_review.security_risk}",
                "",
            ])
            
            if result.deep_review.findings:
                lines.append("**Findings:**")
                for finding in result.deep_review.findings[:5]:
                    lines.append(f"- {finding.severity.upper()}: {finding.message}")
                lines.append("")
        
        return "\n".join(lines)
    
    async def close(self) -> None:
        """Clean up resources."""
        await self.orchestrator.close()


async def main() -> None:
    """Main worker entry point."""
    import sys
    
    worker = Worker()
    
    try:
        # Check command line args
        if len(sys.argv) > 1 and sys.argv[1] == "batch":
            repo = sys.argv[2] if len(sys.argv) > 2 else "openclaw/openclaw"
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50
            
            await worker.run_batch_analysis(repo, limit)
        else:
            # Default: run batch on openclaw/openclaw
            await worker.run_batch_analysis("openclaw/openclaw", 20)
    
    finally:
        await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
