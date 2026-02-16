"""Deep code review using LLM analysis."""

import json
from typing import TYPE_CHECKING

from openclaw_triage.config import get_settings
from openclaw_triage.models import (
    CodeReviewFinding,
    DeepReviewResult,
    PullRequest,
)

if TYPE_CHECKING:
    from openclaw_triage.llm_client import LLMClient


class DeepReviewer:
    """Performs deep code review using LLM analysis."""
    
    def __init__(self, llm_client: "LLMClient | None" = None) -> None:
        """Initialize the deep reviewer."""
        self.config = get_settings().review
        self.llm = llm_client
    
    async def review(self, pr: PullRequest, diff_content: str | None = None) -> DeepReviewResult:
        """Perform deep review of a PR.
        
        Args:
            pr: The PR to review
            diff_content: Optional raw diff content
            
        Returns:
            DeepReviewResult with detailed findings
        """
        if not self.llm:
            # Return basic review without LLM
            return self._basic_review(pr)
        
        # Build the prompt
        prompt = self._build_review_prompt(pr, diff_content)
        
        # Call LLM
        response = await self.llm.complete(
            prompt=prompt,
            model=self.config.llm_model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        
        # Parse the response
        return self._parse_review_response(response, pr)
    
    def _build_review_prompt(self, pr: PullRequest, diff_content: str | None) -> str:
        """Build the review prompt."""
        prompt = f"""You are an expert code reviewer analyzing a pull request. Provide a thorough, actionable review.

## PR Information

Title: {pr.title}
Description: {pr.body or "No description provided"}
Author: {pr.author.username} ({"first-time contributor" if pr.author.is_first_time else f"{pr.author.contributions_count} contributions"})
Files Changed: {len(pr.files_changed)}
Additions: {pr.additions}
Deletions: {pr.deletions}
Has Tests: {"Yes" if pr.has_tests else "No"}
Has Docs: {"Yes" if pr.has_docs else "No"}

"""
        
        if diff_content:
            prompt += f"""## Diff Content

```diff
{diff_content[:8000]}  # Truncate if too long
```

"""
        
        prompt += """## Review Instructions

Analyze this PR and provide:

1. **Summary**: A concise summary of what this PR does and its overall quality

2. **Findings**: List specific issues found, categorized by:
   - severity: critical, high, medium, low, info
   - category: security, performance, style, logic, testing, docs
   - Include file/line references when possible
   - Provide specific, actionable suggestions

3. **Overall Quality Score**: 0.0-1.0 rating

4. **Test Coverage Assessment**: Brief evaluation of test coverage

5. **Security Risk**: low, medium, high, or critical

6. **Breaking Changes**: List any breaking changes

7. **Action Items**: Prioritized list of what needs to be addressed

Format your response as JSON:

```json
{
  "summary": "...",
  "findings": [
    {
      "severity": "high",
      "category": "security",
      "file": "path/to/file.ts",
      "line": 42,
      "message": "Description of issue",
      "suggestion": "How to fix it"
    }
  ],
  "overall_quality": 0.75,
  "test_coverage_assessment": "...",
  "security_risk": "medium",
  "breaking_changes": ["..."],
  "action_items": ["..."]
}
```

Be thorough but concise. Focus on issues that actually matter, not nitpicks."""
        
        return prompt
    
    def _parse_review_response(self, response: str, pr: PullRequest) -> DeepReviewResult:
        """Parse LLM response into structured result."""
        try:
            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            # Parse findings
            findings = [
                CodeReviewFinding(**f) for f in data.get("findings", [])
            ]
            
            return DeepReviewResult(
                summary=data.get("summary", "No summary provided"),
                findings=findings,
                overall_quality=data.get("overall_quality", 0.5),
                test_coverage_assessment=data.get("test_coverage_assessment", ""),
                security_risk=data.get("security_risk", "low"),
                breaking_changes=data.get("breaking_changes", []),
                action_items=data.get("action_items", []),
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback to basic review with error note
            return DeepReviewResult(
                summary=f"Error parsing LLM response: {e}. Raw response: {response[:500]}...",
                findings=[],
                overall_quality=0.5,
                test_coverage_assessment="Unable to assess",
                security_risk="unknown",
                breaking_changes=[],
                action_items=["Review manually - automated analysis failed"],
            )
    
    def _basic_review(self, pr: PullRequest) -> DeepReviewResult:
        """Generate basic review without LLM."""
        findings = []
        action_items = []
        
        # Check for tests
        if not pr.has_tests:
            findings.append(CodeReviewFinding(
                severity="medium",
                category="testing",
                message="No tests detected",
                suggestion="Add unit tests for new functionality",
            ))
            action_items.append("Add tests")
        
        # Check for docs
        if not pr.has_docs:
            findings.append(CodeReviewFinding(
                severity="low",
                category="docs",
                message="No documentation updates",
                suggestion="Update documentation if user-facing changes",
            ))
        
        # Check size
        total_lines = pr.additions + pr.deletions
        if total_lines > 1000:
            findings.append(CodeReviewFinding(
                severity="medium",
                category="style",
                message=f"Large PR ({total_lines} lines changed)",
                suggestion="Consider breaking into smaller PRs",
            ))
            action_items.append("Consider splitting PR")
        
        # Check description
        if not pr.body or len(pr.body) < 50:
            findings.append(CodeReviewFinding(
                severity="low",
                category="docs",
                message="Brief or missing description",
                suggestion="Add more context about the changes",
            ))
        
        # Calculate quality score
        quality = 0.7
        if pr.has_tests:
            quality += 0.15
        if pr.has_docs:
            quality += 0.1
        if total_lines < 500:
            quality += 0.05
        
        return DeepReviewResult(
            summary=f"Basic automated review for PR #{pr.number}. {len(findings)} finding(s).",
            findings=findings,
            overall_quality=min(quality, 1.0),
            test_coverage_assessment="Tests present" if pr.has_tests else "No tests detected",
            security_risk="unknown",
            breaking_changes=[],
            action_items=action_items if action_items else ["Ready for human review"],
        )
