"""Base PR detection - identifies foundational PRs that others build upon."""

from datetime import datetime
from typing import TYPE_CHECKING

from openclaw_triage.config import get_settings
from openclaw_triage.models import (
    BaseDetectionResult,
    BasePRScore,
    PullRequest,
)

if TYPE_CHECKING:
    from openclaw_triage.github_client import GitHubClient


class BaseDetector:
    """Detects which PR is the 'base' among competing implementations."""
    
    def __init__(self, github_client: "GitHubClient | None" = None) -> None:
        """Initialize the base detector."""
        self.config = get_settings().base_detection
        self.github = github_client
    
    async def analyze(
        self, 
        pr: PullRequest, 
        competing_prs: list[PullRequest]
    ) -> BaseDetectionResult:
        """Analyze if this PR is the base among competing implementations.
        
        Args:
            pr: The PR to analyze
            competing_prs: Other PRs addressing the same issue/problem
            
        Returns:
            BaseDetectionResult with scoring and recommendation
        """
        all_prs = [pr] + [p for p in competing_prs if p.number != pr.number]
        
        # Calculate scores for all PRs
        scored_prs = []
        for p in all_prs:
            scores = await self._calculate_scores(p, all_prs)
            scored_prs.append((p, scores))
        
        # Sort by total score
        scored_prs.sort(key=lambda x: x[1].total_score, reverse=True)
        
        # Is this PR the base?
        is_base = scored_prs[0][0].number == pr.number
        pr_scores = next(s for p, s in scored_prs if p.number == pr.number)
        
        # Get competing PR numbers
        competing_numbers = [p.number for p, _ in scored_prs[1:]]
        
        # Generate reasoning
        reasoning = self._generate_reasoning(pr, pr_scores, scored_prs, is_base)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(pr, is_base, scored_prs)
        
        return BaseDetectionResult(
            is_base_candidate=is_base and pr_scores.total_score >= self.config.min_quality_score,
            score=pr_scores,
            reasoning=reasoning,
            competing_prs=competing_numbers,
            recommendation=recommendation,
        )
    
    async def _calculate_scores(
        self, 
        pr: PullRequest, 
        all_prs: list[PullRequest]
    ) -> BasePRScore:
        """Calculate all score components for a PR."""
        
        # Chronological score: earlier is better
        chronological = self._score_chronological(pr, all_prs)
        
        # Quality score: tests, docs, clean code
        quality = self._score_quality(pr)
        
        # Engagement score: discussion, reactions
        engagement = self._score_engagement(pr)
        
        # Author score: reputation, track record
        author = await self._score_author(pr)
        
        # Completeness score: does it fully solve the problem?
        completeness = self._score_completeness(pr)
        
        # Calculate weighted total
        total = (
            chronological * self.config.weight_chronological +
            quality * self.config.weight_quality +
            engagement * self.config.weight_engagement +
            author * self.config.weight_author +
            completeness * self.config.weight_completeness
        )
        
        return BasePRScore(
            chronological_score=chronological,
            quality_score=quality,
            engagement_score=engagement,
            author_score=author,
            completeness_score=completeness,
            total_score=total,
        )
    
    def _score_chronological(self, pr: PullRequest, all_prs: list[PullRequest]) -> float:
        """Score based on being first to address the issue."""
        if len(all_prs) <= 1:
            return 1.0
        
        # Sort by creation time
        sorted_prs = sorted(all_prs, key=lambda p: p.created_at)
        
        # Find position of this PR
        for i, p in enumerate(sorted_prs):
            if p.number == pr.number:
                position = i
                break
        else:
            return 0.5
        
        # Score: 1.0 for first, decreasing for later
        # Use exponential decay so being first matters a lot
        import math
        return math.exp(-0.5 * position)
    
    def _score_quality(self, pr: PullRequest) -> float:
        """Score based on code quality signals."""
        scores = []
        
        # Has tests
        if pr.has_tests:
            scores.append(1.0)
        else:
            scores.append(0.3)
        
        # Has documentation
        if pr.has_docs:
            scores.append(1.0)
        else:
            scores.append(0.5)
        
        # Test coverage (if available)
        if pr.test_coverage is not None:
            scores.append(min(pr.test_coverage / self.config.min_test_coverage, 1.0))
        
        # Reasonable size (not too big, not too small)
        total_lines = pr.additions + pr.deletions
        if 10 <= total_lines <= 500:
            scores.append(1.0)
        elif total_lines < 10:
            scores.append(0.5)  # Too small
        elif total_lines < 1000:
            scores.append(0.8)  # Getting big
        else:
            scores.append(0.5)  # Too big
        
        return sum(scores) / len(scores) if scores else 0.5
    
    def _score_engagement(self, pr: PullRequest) -> float:
        """Score based on community engagement."""
        # Total engagement
        total = pr.comments_count + pr.review_comments_count + pr.reactions_count
        
        # Normalize: 10+ interactions is "high engagement"
        if total >= 20:
            return 1.0
        elif total >= 10:
            return 0.8
        elif total >= 5:
            return 0.6
        elif total >= 1:
            return 0.4
        else:
            return 0.2
    
    async def _score_author(self, pr: PullRequest) -> float:
        """Score based on author reputation."""
        # Use author's contribution count
        contributions = pr.author.contributions_count
        
        if contributions >= 50:
            return 1.0
        elif contributions >= 20:
            return 0.9
        elif contributions >= 10:
            return 0.8
        elif contributions >= 5:
            return 0.7
        elif contributions >= 1:
            return 0.6
        else:
            # First-time contributor
            return 0.4 if not pr.author.is_first_time else 0.3
    
    def _score_completeness(self, pr: PullRequest) -> float:
        """Score based on solution completeness."""
        scores = []
        
        # Has description
        if pr.body and len(pr.body) > 100:
            scores.append(1.0)
        elif pr.body:
            scores.append(0.6)
        else:
            scores.append(0.3)
        
        # Addresses multiple files if needed
        if len(pr.files_changed) >= 3:
            scores.append(1.0)
        elif len(pr.files_changed) >= 2:
            scores.append(0.8)
        else:
            scores.append(0.6)
        
        # Not a draft
        # Note: We'd need to add is_draft to PullRequest model
        scores.append(1.0)  # Placeholder
        
        return sum(scores) / len(scores) if scores else 0.5
    
    def _generate_reasoning(
        self,
        pr: PullRequest,
        scores: BasePRScore,
        all_scored: list[tuple[PullRequest, BasePRScore]],
        is_base: bool
    ) -> str:
        """Generate human-readable reasoning."""
        parts = []
        
        if is_base:
            parts.append(f"PR #{pr.number} scores highest ({scores.total_score:.2f}) among {len(all_scored)} competing PRs.")
        else:
            winner = all_scored[0][0]
            parts.append(
                f"PR #{pr.number} scores {scores.total_score:.2f}, "
                f"below #{winner.number} ({all_scored[0][1].total_score:.2f})."
            )
        
        # Highlight strengths
        strengths = []
        if scores.chronological_score >= 0.8:
            strengths.append("early submission")
        if scores.quality_score >= 0.8:
            strengths.append("high code quality")
        if scores.engagement_score >= 0.8:
            strengths.append("strong community engagement")
        if scores.author_score >= 0.8:
            strengths.append("experienced contributor")
        if scores.completeness_score >= 0.8:
            strengths.append("complete solution")
        
        if strengths:
            parts.append(f"Strengths: {', '.join(strengths)}.")
        
        # Highlight weaknesses
        weaknesses = []
        if scores.chronological_score < 0.5:
            weaknesses.append("late submission")
        if scores.quality_score < 0.5:
            weaknesses.append("quality concerns")
        if scores.engagement_score < 0.5:
            weaknesses.append("low engagement")
        if scores.author_score < 0.5:
            weaknesses.append("new contributor")
        if scores.completeness_score < 0.5:
            weaknesses.append("incomplete solution")
        
        if weaknesses:
            parts.append(f"Concerns: {', '.join(weaknesses)}.")
        
        return " ".join(parts)
    
    def _generate_recommendation(
        self,
        pr: PullRequest,
        is_base: bool,
        all_scored: list[tuple[PullRequest, BasePRScore]]
    ) -> str:
        """Generate actionable recommendation."""
        if is_base:
            if len(all_scored) > 1:
                others = ", ".join(f"#{p.number}" for p, _ in all_scored[1:])
                return (
                    f"This appears to be the base PR. Consider merging this one and "
                    f"closing {others} as duplicates."
                )
            else:
                return "This is the primary implementation. Ready for final review."
        else:
            winner = all_scored[0][0]
            return (
                f"Consider closing this in favor of #{winner.number} which scores higher. "
                f"Alternatively, identify what this PR does better and suggest "
                f"incorporating those improvements into the base PR."
            )
