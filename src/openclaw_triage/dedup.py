"""Deduplication engine using embeddings and vector similarity."""

import hashlib
from typing import TYPE_CHECKING

import numpy as np
from sentence_transformers import SentenceTransformer

from openclaw_triage.config import get_settings
from openclaw_triage.models import (
    DeduplicationResult,
    DuplicateMatch,
    Issue,
    PRIssueType,
    PullRequest,
)

if TYPE_CHECKING:
    from openclaw_triage.storage.vector_store import VectorStore


class DeduplicationEngine:
    """Engine for detecting duplicate PRs and Issues."""
    
    def __init__(self, vector_store: "VectorStore | None" = None) -> None:
        """Initialize the deduplication engine."""
        self.config = get_settings().dedup
        self.model = SentenceTransformer(self.config.embedding_model)
        self.vector_store = vector_store
        self._embedding_cache: dict[str, np.ndarray] = {}
    
    def _get_cache_key(self, text: str) -> str:
        """Get cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _embed(self, text: str) -> np.ndarray:
        """Get embedding for text with caching."""
        cache_key = self._get_cache_key(text)
        if cache_key not in self._embedding_cache:
            embedding = self.model.encode(text, convert_to_numpy=True)
            self._embedding_cache[cache_key] = embedding
        return self._embedding_cache[cache_key]
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    async def analyze_pr(
        self, 
        pr: PullRequest, 
        candidate_prs: list[PullRequest] | None = None
    ) -> DeduplicationResult:
        """Analyze a PR for duplicates.
        
        Args:
            pr: The PR to analyze
            candidate_prs: Optional list of candidate PRs to compare against
            
        Returns:
            DeduplicationResult with duplicate detection results
        """
        pr_text = pr.to_text()
        pr_embedding = self._embed(pr_text)
        
        similar_items: list[DuplicateMatch] = []
        
        # Check against provided candidates
        if candidate_prs:
            for candidate in candidate_prs:
                if candidate.number == pr.number:
                    continue
                    
                candidate_text = candidate.to_text()
                candidate_embedding = self._embed(candidate_text)
                similarity = self._cosine_similarity(pr_embedding, candidate_embedding)
                
                if similarity >= self.config.similarity_threshold - 0.1:  # Lower threshold for candidates
                    similar_items.append(DuplicateMatch(
                        item_number=candidate.number,
                        item_type=PRIssueType.PULL_REQUEST,
                        similarity_score=similarity,
                        title=candidate.title,
                        url=f"https://github.com/{pr.repository}/pull/{candidate.number}",
                        reason=self._generate_reason(pr, candidate, similarity),
                    ))
        
        # Check against vector store if available
        if self.vector_store:
            store_matches = await self.vector_store.similarity_search(
                embedding=pr_embedding.tolist(),
                threshold=self.config.similarity_threshold - 0.1,
                limit=self.config.max_candidates,
                exclude_id=f"pr_{pr.number}",
            )
            
            for match in store_matches:
                if not any(m.item_number == match["number"] for m in similar_items):
                    similar_items.append(DuplicateMatch(
                        item_number=match["number"],
                        item_type=PRIssueType.PULL_REQUEST,
                        similarity_score=match["score"],
                        title=match["title"],
                        url=match["url"],
                        reason=f"Vector similarity: {match['score']:.2f}",
                    ))
        
        # Sort by similarity
        similar_items.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Determine if duplicate
        is_duplicate = False
        canonical_item = None
        
        if similar_items:
            best_match = similar_items[0]
            if best_match.similarity_score >= self.config.similarity_threshold:
                is_duplicate = True
                canonical_item = best_match
        
        return DeduplicationResult(
            is_duplicate=is_duplicate,
            confidence=best_match.similarity_score if similar_items else 0.0,
            canonical_item=canonical_item,
            similar_items=similar_items[:5],  # Top 5 similar
            analysis_summary=self._generate_summary(pr, is_duplicate, similar_items),
        )
    
    async def analyze_issue(
        self, 
        issue: Issue,
        candidate_issues: list[Issue] | None = None
    ) -> DeduplicationResult:
        """Analyze an Issue for duplicates."""
        issue_text = issue.to_text()
        issue_embedding = self._embed(issue_text)
        
        similar_items: list[DuplicateMatch] = []
        
        if candidate_issues:
            for candidate in candidate_issues:
                if candidate.number == issue.number:
                    continue
                    
                candidate_text = candidate.to_text()
                candidate_embedding = self._embed(candidate_text)
                similarity = self._cosine_similarity(issue_embedding, candidate_embedding)
                
                if similarity >= self.config.similarity_threshold - 0.1:
                    similar_items.append(DuplicateMatch(
                        item_number=candidate.number,
                        item_type=PRIssueType.ISSUE,
                        similarity_score=similarity,
                        title=candidate.title,
                        url=f"https://github.com/{issue.repository}/issues/{candidate.number}",
                        reason=self._generate_issue_reason(issue, candidate, similarity),
                    ))
        
        # Check vector store
        if self.vector_store:
            store_matches = await self.vector_store.similarity_search(
                embedding=issue_embedding.tolist(),
                threshold=self.config.similarity_threshold - 0.1,
                limit=self.config.max_candidates,
                exclude_id=f"issue_{issue.number}",
            )
            
            for match in store_matches:
                if not any(m.item_number == match["number"] for m in similar_items):
                    similar_items.append(DuplicateMatch(
                        item_number=match["number"],
                        item_type=PRIssueType.ISSUE,
                        similarity_score=match["score"],
                        title=match["title"],
                        url=match["url"],
                        reason=f"Vector similarity: {match['score']:.2f}",
                    ))
        
        similar_items.sort(key=lambda x: x.similarity_score, reverse=True)
        
        is_duplicate = False
        canonical_item = None
        
        if similar_items:
            best_match = similar_items[0]
            if best_match.similarity_score >= self.config.similarity_threshold:
                is_duplicate = True
                canonical_item = best_match
        
        return DeduplicationResult(
            is_duplicate=is_duplicate,
            confidence=best_match.similarity_score if similar_items else 0.0,
            canonical_item=canonical_item,
            similar_items=similar_items[:5],
            analysis_summary=self._generate_issue_summary(issue, is_duplicate, similar_items),
        )
    
    def _generate_reason(self, pr: PullRequest, candidate: PullRequest, similarity: float) -> str:
        """Generate human-readable reason for similarity."""
        reasons = []
        
        # Check title similarity
        pr_words = set(pr.title.lower().split())
        candidate_words = set(candidate.title.lower().split())
        title_overlap = len(pr_words & candidate_words) / max(len(pr_words), len(candidate_words))
        
        if title_overlap > 0.5:
            reasons.append("similar title")
        
        # Check file overlap
        common_files = set(pr.files_changed) & set(candidate.files_changed)
        if common_files:
            reasons.append(f"touches same files: {', '.join(list(common_files)[:3])}")
        
        # Check timing
        time_diff = abs((pr.created_at - candidate.created_at).total_seconds())
        if time_diff < 86400:  # Less than 24 hours
            reasons.append("opened around the same time")
        
        if not reasons:
            reasons.append(f"semantic similarity: {similarity:.2f}")
        
        return "; ".join(reasons)
    
    def _generate_issue_reason(self, issue: Issue, candidate: Issue, similarity: float) -> str:
        """Generate human-readable reason for issue similarity."""
        reasons = []
        
        # Check title similarity
        issue_words = set(issue.title.lower().split())
        candidate_words = set(candidate.title.lower().split())
        title_overlap = len(issue_words & candidate_words) / max(len(issue_words), len(candidate_words))
        
        if title_overlap > 0.5:
            reasons.append("similar title")
        
        # Check label overlap
        common_labels = set(issue.labels) & set(candidate.labels)
        if common_labels:
            reasons.append(f"shared labels: {', '.join(common_labels)}")
        
        if not reasons:
            reasons.append(f"semantic similarity: {similarity:.2f}")
        
        return "; ".join(reasons)
    
    def _generate_summary(
        self, 
        pr: PullRequest, 
        is_duplicate: bool, 
        similar_items: list[DuplicateMatch]
    ) -> str:
        """Generate analysis summary."""
        if is_duplicate:
            canonical = similar_items[0]
            return (
                f"PR #{pr.number} appears to be a duplicate of #{canonical.item_number} "
                f"(similarity: {canonical.similarity_score:.2f}). "
                f"Consider closing this PR and focusing on the original."
            )
        elif similar_items:
            return (
                f"PR #{pr.number} has {len(similar_items)} similar PR(s) but appears to be "
                f"a distinct implementation. Review for potential consolidation."
            )
        else:
            return f"PR #{pr.number} appears to be unique with no similar PRs found."
    
    def _generate_issue_summary(
        self, 
        issue: Issue, 
        is_duplicate: bool, 
        similar_items: list[DuplicateMatch]
    ) -> str:
        """Generate analysis summary for issue."""
        if is_duplicate:
            canonical = similar_items[0]
            return (
                f"Issue #{issue.number} appears to be a duplicate of #{canonical.item_number} "
                f"(similarity: {canonical.similarity_score:.2f}). "
                f"Consider closing and redirecting to the original."
            )
        elif similar_items:
            return (
                f"Issue #{issue.number} has {len(similar_items)} similar issue(s). "
                f"Review for potential duplicates."
            )
        else:
            return f"Issue #{issue.number} appears to be unique with no similar issues found."
