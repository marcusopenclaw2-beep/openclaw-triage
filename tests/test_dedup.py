"""Tests for deduplication engine."""

import pytest
from datetime import datetime, timezone

from openclaw_triage.dedup import DeduplicationEngine
from openclaw_triage.models import PullRequest, Author, Issue


@pytest.fixture
def dedup_engine():
    """Create a deduplication engine for testing."""
    return DeduplicationEngine()


@pytest.fixture
def sample_pr():
    """Create a sample PR for testing."""
    return PullRequest(
        number=1,
        title="Add user authentication",
        body="This PR adds OAuth2 authentication support",
        author=Author(username="alice", contributions_count=10),
        state="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        branch="feature/auth",
        base_branch="main",
        files_changed=["auth.ts", "login.tsx"],
        additions=100,
        deletions=20,
        has_tests=True,
        has_docs=True,
    )


@pytest.fixture
def similar_pr():
    """Create a similar PR for testing."""
    return PullRequest(
        number=2,
        title="Implement user login with OAuth",
        body="Adding OAuth2 login functionality for users",
        author=Author(username="bob", contributions_count=5),
        state="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        branch="feature/oauth-login",
        base_branch="main",
        files_changed=["auth.ts", "oauth.ts"],
        additions=120,
        deletions=15,
        has_tests=True,
        has_docs=False,
    )


@pytest.fixture
def different_pr():
    """Create a different PR for testing."""
    return PullRequest(
        number=3,
        title="Fix CSS styling on mobile",
        body="Update responsive styles for mobile devices",
        author=Author(username="carol", contributions_count=20),
        state="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        branch="fix/mobile-css",
        base_branch="main",
        files_changed=["styles.css", "mobile.scss"],
        additions=50,
        deletions=30,
        has_tests=False,
        has_docs=False,
    )


@pytest.mark.asyncio
async def test_detect_similar_prs(dedup_engine, sample_pr, similar_pr):
    """Test that similar PRs are detected."""
    result = await dedup_engine.analyze_pr(sample_pr, [similar_pr])
    
    assert len(result.similar_items) > 0
    assert result.similar_items[0].item_number == similar_pr.number
    assert result.similar_items[0].similarity_score > 0.5


@pytest.mark.asyncio
async def test_different_prs_not_duplicate(dedup_engine, sample_pr, different_pr):
    """Test that different PRs are not marked as duplicates."""
    result = await dedup_engine.analyze_pr(sample_pr, [different_pr])
    
    # Should not be marked as duplicate
    assert not result.is_duplicate
    
    # Similarity should be low
    if result.similar_items:
        assert result.similar_items[0].similarity_score < 0.8


@pytest.mark.asyncio
async def test_duplicate_detection_threshold(dedup_engine, sample_pr, similar_pr):
    """Test duplicate detection with high similarity."""
    # Create a very similar PR
    very_similar = similar_pr.model_copy()
    very_similar.number = 4
    very_similar.title = sample_pr.title  # Same title
    very_similar.body = sample_pr.body  # Same body
    
    result = await dedup_engine.analyze_pr(sample_pr, [very_similar])
    
    # With same title and body, should be marked duplicate
    assert result.is_duplicate or result.similar_items[0].similarity_score > 0.8


@pytest.mark.asyncio
async def test_issue_deduplication(dedup_engine):
    """Test issue deduplication."""
    issue1 = Issue(
        number=1,
        title="Bug: Login not working",
        body="Users cannot log in with OAuth",
        author=Author(username="user1"),
        state="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    issue2 = Issue(
        number=2,
        title="Login broken after update",
        body="OAuth login fails with error",
        author=Author(username="user2"),
        state="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    result = await dedup_engine.analyze_issue(issue1, [issue2])
    
    assert len(result.similar_items) > 0
    assert result.similar_items[0].similarity_score > 0.5
