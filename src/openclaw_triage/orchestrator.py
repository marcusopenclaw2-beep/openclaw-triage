"""Main triage orchestrator that coordinates all analysis components."""

import time
from datetime import datetime

from openclaw_triage.base_detector import BaseDetector
from openclaw_triage.config import get_settings
from openclaw_triage.dedup import DeduplicationEngine
from openclaw_triage.deep_reviewer import DeepReviewer
from openclaw_triage.github_client import GitHubClient
from openclaw_triage.llm_client import LLMClient
from openclaw_triage.models import (
    AnalysisStatus,
    PRIssueType,
    TriageResult,
)
from openclaw_triage.vision_checker import VisionChecker


class TriageOrchestrator:
    """Orchestrates the complete triage pipeline."""
    
    def __init__(
        self,
        github_client: GitHubClient | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        """Initialize the triage orchestrator."""
        self.config = get_settings()
        self.github = github_client or GitHubClient()
        self.llm = llm_client
        
        # Initialize components
        self.dedup = DeduplicationEngine()
        self.base_detector = BaseDetector(self.github)
        self.reviewer = DeepReviewer(self.llm)
        self.vision_checker = VisionChecker(self.llm)
    
    async def triage_pr(
        self,
        repo: str,
        pr_number: int,
        enable_dedup: bool = True,
        enable_base_detection: bool = True,
        enable_review: bool = True,
        enable_vision: bool = True,
    ) -> TriageResult:
        """Run complete triage on a PR.
        
        Args:
            repo: Repository in format "owner/repo"
            pr_number: PR number
            enable_*: Toggle specific analyses
            
        Returns:
            Complete TriageResult
        """
        start_time = time.time()
        
        try:
            # Fetch PR data
            pr = await self.github.get_pull_request(repo, pr_number)
            pr.repository = repo  # Set for URL generation
            
            result = TriageResult(
                item_type=PRIssueType.PULL_REQUEST,
                item_number=pr_number,
                repository=repo,
                status=AnalysisStatus.IN_PROGRESS,
            )
            
            # 1. Deduplication
            if enable_dedup:
                # Get recent PRs for comparison
                recent_prs = await self.github.list_pull_requests(repo, state="open", per_page=50)
                result.deduplication = await self.dedup.analyze_pr(pr, recent_prs)
            
            # 2. Base Detection (only if duplicates found)
            if enable_base_detection and result.deduplication and result.deduplication.similar_items:
                competing = [
                    p for p in recent_prs 
                    if any(p.number == m.item_number for m in result.deduplication.similar_items)
                ]
                result.base_detection = await self.base_detector.analyze(pr, competing)
            
            # 3. Deep Review
            if enable_review:
                diff = await self.github.get_diff(repo, pr_number)
                result.deep_review = await self.reviewer.review(pr, diff)
            
            # 4. Vision Alignment
            if enable_vision:
                diff_summary = None
                if result.deep_review:
                    diff_summary = result.deep_review.summary[:500]
                result.vision_alignment = await self.vision_checker.check(pr, diff_summary)
            
            # Generate executive summary
            result.executive_summary = self._generate_executive_summary(result)
            result.priority = self._determine_priority(result)
            result.recommended_action = self._determine_action(result)
            
            result.status = AnalysisStatus.COMPLETED
            result.processing_time_ms = int((time.time() - start_time) * 1000)
            
            return result
            
        except Exception as e:
            return TriageResult(
                item_type=PRIssueType.PULL_REQUEST,
                item_number=pr_number,
                repository=repo,
                status=AnalysisStatus.FAILED,
                error_message=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
    
    async def triage_issue(
        self,
        repo: str,
        issue_number: int,
        enable_dedup: bool = True,
    ) -> TriageResult:
        """Run triage on an Issue."""
        start_time = time.time()
        
        try:
            issue = await self.github.get_issue(repo, issue_number)
            issue.repository = repo
            
            result = TriageResult(
                item_type=PRIssueType.ISSUE,
                item_number=issue_number,
                repository=repo,
                status=AnalysisStatus.IN_PROGRESS,
            )
            
            if enable_dedup:
                recent_issues = await self.github.list_issues(repo, state="open", per_page=50)
                result.deduplication = await self.dedup.analyze_issue(issue, recent_issues)
            
            result.executive_summary = self._generate_issue_summary(result)
            result.priority = self._determine_issue_priority(issue, result)
            result.recommended_action = self._determine_issue_action(result)
            
            result.status = AnalysisStatus.COMPLETED
            result.processing_time_ms = int((time.time() - start_time) * 1000)
            
            return result
            
        except Exception as e:
            return TriageResult(
                item_type=PRIssueType.ISSUE,
                item_number=issue_number,
                repository=repo,
                status=AnalysisStatus.FAILED,
                error_message=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def _generate_executive_summary(self, result: TriageResult) -> str:
        """Generate executive summary for maintainers."""
        parts = []
        
        # Deduplication
        if result.deduplication:
            if result.deduplication.is_duplicate:
                parts.append(f"🔁 Likely duplicate of #{result.deduplication.canonical_item.item_number}")
            elif result.deduplication.similar_items:
                parts.append(f"📎 {len(result.deduplication.similar_items)} similar PR(s) found")
            else:
                parts.append("✅ No duplicates detected")
        
        # Base detection
        if result.base_detection:
            if result.base_detection.is_base_candidate:
                parts.append("⭐ Base PR candidate")
            else:
                parts.append(f"📊 Base score: {result.base_detection.score.total_score:.2f}")
        
        # Review
        if result.deep_review:
            quality = result.deep_review.overall_quality
            emoji = "🟢" if quality >= 0.8 else "🟡" if quality >= 0.6 else "🔴"
            parts.append(f"{emoji} Quality: {quality:.0%}")
            
            if result.deep_review.security_risk in ("high", "critical"):
                parts.append(f"🚨 Security: {result.deep_review.security_risk}")
            
            if result.deep_review.breaking_changes:
                parts.append(f"⚠️ Breaking changes: {len(result.deep_review.breaking_changes)}")
        
        # Vision
        if result.vision_alignment:
            alignment = result.vision_alignment.alignment_score
            if alignment >= 0.8:
                parts.append("✨ Vision aligned")
            elif alignment <= 0.4:
                parts.append("❌ Vision concerns")
            else:
                parts.append(f"🤔 Vision: {alignment:.0%}")
        
        return " | ".join(parts) if parts else "Analysis complete"
    
    def _generate_issue_summary(self, result: TriageResult) -> str:
        """Generate summary for issue."""
        if result.deduplication:
            if result.deduplication.is_duplicate:
                return f"🔁 Duplicate of #{result.deduplication.canonical_item.item_number}"
            elif result.deduplication.similar_items:
                return f"📎 {len(result.deduplication.similar_items)} similar issue(s)"
        return "✅ No duplicates detected"
    
    def _determine_priority(self, result: TriageResult) -> str:
        """Determine priority based on analysis."""
        # Critical: security issues
        if result.deep_review and result.deep_review.security_risk in ("high", "critical"):
            return "urgent"
        
        # High: breaking changes or vision misalignment
        if result.deep_review and result.deep_review.breaking_changes:
            return "high"
        
        if result.vision_alignment and result.vision_alignment.status == "misaligned":
            return "high"
        
        # High: base PR candidate
        if result.base_detection and result.base_detection.is_base_candidate:
            return "high"
        
        # Low: duplicate
        if result.deduplication and result.deduplication.is_duplicate:
            return "low"
        
        return "normal"
    
    def _determine_issue_priority(self, issue, result: TriageResult) -> str:
        """Determine priority for issue."""
        # Check labels
        urgent_labels = ["bug", "critical", "security", "urgent"]
        if any(l.lower() in urgent_labels for l in issue.labels):
            return "high"
        
        # Duplicate is lower priority
        if result.deduplication and result.deduplication.is_duplicate:
            return "low"
        
        return "normal"
    
    def _determine_action(self, result: TriageResult) -> str:
        """Determine recommended action."""
        actions = []
        
        if result.deduplication and result.deduplication.is_duplicate:
            actions.append("Close as duplicate")
        
        if result.base_detection and result.base_detection.is_base_candidate:
            actions.append("Prioritize for review")
        
        if result.deep_review:
            if result.deep_review.security_risk in ("high", "critical"):
                actions.append("Security review required")
            
            if result.deep_review.action_items:
                actions.append(f"Address {len(result.deep_review.action_items)} finding(s)")
        
        if result.vision_alignment:
            if result.vision_alignment.status == "misaligned":
                actions.append("Vision discussion needed")
            elif result.vision_alignment.suggested_changes:
                actions.append("Consider suggested changes")
        
        return "; ".join(actions) if actions else "Ready for review"
    
    def _determine_issue_action(self, result: TriageResult) -> str:
        """Determine action for issue."""
        if result.deduplication and result.deduplication.is_duplicate:
            return "Close and redirect to canonical issue"
        return "Triage to appropriate maintainer"
    
    async def close(self) -> None:
        """Clean up resources."""
        await self.github.close()
        if self.llm:
            await self.llm.close()
