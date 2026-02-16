"""Tests for base detector."""

import pytest
from datetime import datetime, timezone, timedelta

from openclaw_triage.base_detector import BaseDetector
from openclaw_triage.models import PullRequest, Author


@pytest.fixture
def detector():
    """Create a base detector for testing."""
    return BaseDetector()


@pytest.fixture
def now():
    """Current time for testing."""
    return datetime.now(timezone.utc)


@pytest.fixture
def base_pr(now):
    """Create a high-quality base PR."""
    return PullRequest(
        number=1,
        title="Add feature X",
        body="Complete implementation of feature X with tests and docs",
        author=Author(username="alice", contributions_count=50),
        state="open",
        created_at=now - timedelta(hours=2),  # First
        updated_at=now,
        branch="feature/x",
        base_branch="main",
        files_changed=["src/x.ts", "tests/x.test.ts", "docs/x.md"],
        additions=200,
        deletions=50,
        comments_count=5,
        review_comments_count=3,
        has_tests=True,
        has_docs=True,
        test_coverage=0.85,
    )


@pytest.fixture
def competing_pr(now):
    """Create a competing PR (later, lower quality)."""
    return PullRequest(
        number=2,
        title="Feature X implementation",
        body="Add feature X",
        author=Author(username="bob", contributions_count=5),
        state="open",
        created_at=now,  # Later
        updated_at=now,
        branch="feature/x-alt",
        base_branch="main",
        files_changed=["src/x.ts"],
        additions=150,
        deletions=20,
        comments_count=1,
        review_comments_count=0,
        has_tests=False,
        has_docs=False,
        test_coverage=None,
    )


@pytest.mark.asyncio
async def test_base_pr_detection(detector, base_pr, competing_pr):
    """Test that the better PR is identified as base."""
    result = await detector.analyze(base_pr, [competing_pr])
    
    assert result.is_base_candidate
    assert result.score.total_score > 0.6
    assert competing_pr.number in result.competing_prs


@pytest.mark.asyncio
async def test_competing_pr_not_base(detector, base_pr, competing_pr):
    """Test that competing PR is not marked as base."""
    result = await detector.analyze(competing_pr, [base_pr])
    
    assert not result.is_base_candidate
    assert base_pr.number in result.competing_prs


@pytest.mark.asyncio
async def test_chronological_scoring(detector, now):
    """Test that earlier PRs score higher chronologically."""
    early_pr = PullRequest(
        number=1,
        title="Early PR",
        body="First",
        author=Author(username="a"),
        state="open",
        created_at=now - timedelta(hours=2),
        updated_at=now,
        branch="a",
        base_branch="main",
        files_changed=["a.ts"],
        additions=10,
        deletions=0,
    )
    
    late_pr = PullRequest(
        number=2,
        title="Late PR",
        body="Second",
        author=Author(username="b"),
        state="open",
        created_at=now,
        updated_at=now,
        branch="b",
        base_branch="main",
        files_changed=["b.ts"],
        additions=10,
        deletions=0,
    )
    
    early_result = await detector.analyze(early_pr, [late_pr])
    late_result = await detector.analyze(late_pr, [early_pr])
    
    assert early_result.score.chronological_score > late_result.score.chronological_score


@pytest.mark.asyncio
async def test_quality_scoring(detector, now):
    """Test quality scoring."""
    good_pr = PullRequest(
        number=1,
        title="Good PR",
        body="Well tested",
        author=Author(username="a"),
        state="open",
        created_at=now,
        updated_at=now,
        branch="a",
        base_branch="main",
        files_changed=["a.ts", "a.test.ts"],
        additions=100,
        deletions=10,
        has_tests=True,
        has_docs=True,
        test_coverage=0.9,
    )
    
    poor_pr = PullRequest(
        number=2,
        title="Poor PR",
        body="No tests",
        author=Author(username="b"),
        state="open",
        created_at=now,
        updated_at=now,
        branch="b",
        base_branch="main",
        files_changed=["b.ts"],
        additions=500,  # Too big
        deletions=0,
        has_tests=False,
        has_docs=False,
        test_coverage=None,
    )
    
    good_result = await detector.analyze(good_pr, [poor_pr])
    poor_result = await detector.analyze(poor_pr, [good_pr])
    
    assert good_result.score.quality_score > poor_result.score.quality_score
