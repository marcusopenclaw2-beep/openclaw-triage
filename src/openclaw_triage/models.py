"""Data models for PRs, Issues, and analysis results."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PRIssueType(str, Enum):
    """Type of item being analyzed."""
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"


class AnalysisStatus(str, Enum):
    """Status of analysis."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Author(BaseModel):
    """GitHub author information."""
    
    username: str
    avatar_url: str | None = None
    contributions_count: int = 0
    is_first_time: bool = False


class PullRequest(BaseModel):
    """Pull request data."""
    
    number: int
    title: str
    body: str | None = None
    author: Author
    state: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    merged_at: datetime | None = None
    
    # Content
    branch: str
    base_branch: str
    files_changed: list[str] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    
    # Engagement
    comments_count: int = 0
    review_comments_count: int = 0
    reactions_count: int = 0
    
    # Quality signals
    has_tests: bool = False
    has_docs: bool = False
    test_coverage: float | None = None
    
    # Labels
    labels: list[str] = Field(default_factory=list)
    
    def to_text(self) -> str:
        """Convert to text for embedding."""
        return f"""Title: {self.title}
Description: {self.body or ""}
Files changed: {', '.join(self.files_changed)}
Author: {self.author.username}
Labels: {', '.join(self.labels)}
"""


class Issue(BaseModel):
    """Issue data."""
    
    number: int
    title: str
    body: str | None = None
    author: Author
    state: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    
    # Engagement
    comments_count: int = 0
    reactions_count: int = 0
    
    # Labels
    labels: list[str] = Field(default_factory=list)
    
    # Linked PRs
    linked_prs: list[int] = Field(default_factory=list)
    
    def to_text(self) -> str:
        """Convert to text for embedding."""
        return f"""Title: {self.title}
Description: {self.body or ""}
Author: {self.author.username}
Labels: {', '.join(self.labels)}
"""


class DuplicateMatch(BaseModel):
    """A potential duplicate match."""
    
    item_number: int
    item_type: PRIssueType
    similarity_score: float
    title: str
    url: str
    reason: str


class DeduplicationResult(BaseModel):
    """Result of deduplication analysis."""
    
    is_duplicate: bool
    confidence: float
    canonical_item: DuplicateMatch | None = None
    similar_items: list[DuplicateMatch] = Field(default_factory=list)
    analysis_summary: str = ""


class BasePRScore(BaseModel):
    """Score breakdown for base PR detection."""
    
    chronological_score: float = Field(ge=0, le=1)
    quality_score: float = Field(ge=0, le=1)
    engagement_score: float = Field(ge=0, le=1)
    author_score: float = Field(ge=0, le=1)
    completeness_score: float = Field(ge=0, le=1)
    
    # Weighted total
    total_score: float = Field(ge=0, le=1)


class BaseDetectionResult(BaseModel):
    """Result of base PR detection."""
    
    is_base_candidate: bool
    score: BasePRScore
    reasoning: str
    competing_prs: list[int] = Field(default_factory=list)
    recommendation: str = ""


class CodeReviewFinding(BaseModel):
    """A single finding from code review."""
    
    severity: str  # critical, high, medium, low, info
    category: str  # security, performance, style, logic, testing, docs
    file: str | None = None
    line: int | None = None
    message: str
    suggestion: str | None = None


class DeepReviewResult(BaseModel):
    """Result of deep code review."""
    
    summary: str
    findings: list[CodeReviewFinding] = Field(default_factory=list)
    
    # Scores
    overall_quality: float = Field(ge=0, le=1)
    test_coverage_assessment: str = ""
    security_risk: str = "low"  # low, medium, high, critical
    breaking_changes: list[str] = Field(default_factory=list)
    
    # Action items
    action_items: list[str] = Field(default_factory=list)


class VisionAlignmentResult(BaseModel):
    """Result of vision alignment check."""
    
    alignment_score: float = Field(ge=0, le=1)
    status: str  # aligned, needs_discussion, misaligned
    
    # Analysis
    fits_vision: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    
    # Recommendation
    recommendation: str = ""
    suggested_changes: list[str] = Field(default_factory=list)


class TriageResult(BaseModel):
    """Complete triage result for a PR or Issue."""
    
    item_type: PRIssueType
    item_number: int
    repository: str
    
    # Analysis results
    status: AnalysisStatus
    deduplication: DeduplicationResult | None = None
    base_detection: BaseDetectionResult | None = None
    deep_review: DeepReviewResult | None = None
    vision_alignment: VisionAlignmentResult | None = None
    
    # Metadata
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: int = 0
    error_message: str | None = None
    
    # Summary for maintainers
    executive_summary: str = ""
    priority: str = "normal"  # low, normal, high, urgent
    recommended_action: str = ""
