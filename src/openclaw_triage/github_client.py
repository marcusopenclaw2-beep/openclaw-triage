"""GitHub API client for fetching PRs, Issues, and posting comments."""

from datetime import datetime
from typing import Any

import httpx

from openclaw_triage.config import get_settings
from openclaw_triage.models import Author, Issue, PullRequest


class GitHubClient:
    """Client for GitHub API operations."""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: str | None = None) -> None:
        """Initialize GitHub client."""
        self.token = token or get_settings().github.token
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.client = httpx.AsyncClient(headers=self.headers, base_url=self.BASE_URL)
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request."""
        response = await self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()
    
    async def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request."""
        response = await self.client.post(path, json=json)
        response.raise_for_status()
        return response.json()
    
    async def _patch(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        """Make a PATCH request."""
        response = await self.client.patch(path, json=json)
        response.raise_for_status()
        return response.json()
    
    def _parse_author(self, data: dict[str, Any]) -> Author:
        """Parse author from GitHub data."""
        return Author(
            username=data.get("login", "unknown"),
            avatar_url=data.get("avatar_url"),
            contributions_count=0,  # Would need separate API call
            is_first_time=False,  # Would need to check
        )
    
    async def get_pull_request(self, repo: str, pr_number: int) -> PullRequest:
        """Fetch a pull request by number."""
        data = await self._get(f"/repos/{repo}/pulls/{pr_number}")
        
        # Get files
        files_data = await self._get(f"/repos/{repo}/pulls/{pr_number}/files")
        files_changed = [f["filename"] for f in files_data]
        
        # Get reactions count (approximate)
        reactions = 0
        
        return PullRequest(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            author=self._parse_author(data["user"]),
            state=data["state"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            closed_at=datetime.fromisoformat(data["closed_at"].replace("Z", "+00:00")) if data.get("closed_at") else None,
            merged_at=datetime.fromisoformat(data["merged_at"].replace("Z", "+00:00")) if data.get("merged_at") else None,
            branch=data["head"]["ref"],
            base_branch=data["base"]["ref"],
            files_changed=files_changed,
            additions=data["additions"],
            deletions=data["deletions"],
            comments_count=data["comments"],
            review_comments_count=data["review_comments"],
            reactions_count=reactions,
            has_tests=any("test" in f.lower() for f in files_changed),
            has_docs=any(f.endswith((".md", ".rst", ".txt")) for f in files_changed),
            labels=[l["name"] for l in data.get("labels", [])],
        )
    
    async def get_issue(self, repo: str, issue_number: int) -> Issue:
        """Fetch an issue by number."""
        data = await self._get(f"/repos/{repo}/issues/{issue_number}")
        
        return Issue(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            author=self._parse_author(data["user"]),
            state=data["state"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            closed_at=datetime.fromisoformat(data["closed_at"].replace("Z", "+00:00")) if data.get("closed_at") else None,
            comments_count=data["comments"],
            reactions_count=data.get("reactions", {}).get("total_count", 0),
            labels=[l["name"] for l in data.get("labels", [])],
        )
    
    async def list_pull_requests(
        self, 
        repo: str, 
        state: str = "open",
        per_page: int = 30,
        page: int = 1
    ) -> list[PullRequest]:
        """List pull requests."""
        params = {"state": state, "per_page": per_page, "page": page}
        data = await self._get(f"/repos/{repo}/pulls", params)
        
        prs = []
        for pr_data in data:
            pr = await self.get_pull_request(repo, pr_data["number"])
            prs.append(pr)
        
        return prs
    
    async def list_issues(
        self,
        repo: str,
        state: str = "open",
        per_page: int = 30,
        page: int = 1
    ) -> list[Issue]:
        """List issues."""
        params = {"state": state, "per_page": per_page, "page": page}
        data = await self._get(f"/repos/{repo}/issues", params)
        
        issues = []
        for issue_data in data:
            # Skip PRs (GitHub returns PRs as issues)
            if "pull_request" in issue_data:
                continue
            issue = await self.get_issue(repo, issue_data["number"])
            issues.append(issue)
        
        return issues
    
    async def get_diff(self, repo: str, pr_number: int) -> str:
        """Get the diff for a PR."""
        headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        response = await self.client.get(
            f"/repos/{repo}/pulls/{pr_number}",
            headers=headers
        )
        response.raise_for_status()
        return response.text
    
    async def add_comment(self, repo: str, issue_number: int, body: str) -> dict[str, Any]:
        """Add a comment to an issue or PR."""
        return await self._post(
            f"/repos/{repo}/issues/{issue_number}/comments",
            {"body": body}
        )
    
    async def add_labels(self, repo: str, issue_number: int, labels: list[str]) -> dict[str, Any]:
        """Add labels to an issue or PR."""
        return await self._post(
            f"/repos/{repo}/issues/{issue_number}/labels",
            {"labels": labels}
        )
    
    async def remove_label(self, repo: str, issue_number: int, label: str) -> None:
        """Remove a label from an issue or PR."""
        await self.client.delete(
            f"/repos/{repo}/issues/{issue_number}/labels/{label}"
        )
    
    async def close_issue(self, repo: str, issue_number: int, reason: str | None = None) -> dict[str, Any]:
        """Close an issue or PR."""
        data: dict[str, Any] = {"state": "closed"}
        if reason:
            data["state_reason"] = reason
        return await self._patch(
            f"/repos/{repo}/issues/{issue_number}",
            data
        )
    
    async def get_user_contributions(self, repo: str, username: str) -> int:
        """Get contribution count for a user."""
        params = {"author": username, "state": "all", "per_page": 1}
        response = await self.client.get(
            f"/repos/{repo}/pulls",
            params=params
        )
        # Get total count from Link header or iterate
        # Simplified: just return 0 for now
        return 0
