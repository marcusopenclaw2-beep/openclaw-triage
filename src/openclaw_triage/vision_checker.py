"""Vision alignment checker - ensures PRs align with project vision."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from openclaw_triage.config import get_settings
from openclaw_triage.models import (
    PullRequest,
    VisionAlignmentResult,
)

if TYPE_CHECKING:
    from openclaw_triage.llm_client import LLMClient


DEFAULT_VISION = """# OpenClaw Vision

## Mission
OpenClaw is a personal AI assistant that you run on your own devices. It answers you on the channels you already use.

## Core Principles

1. **Personal First**: Single-user focus, not multi-tenant
2. **Local-First**: Runs on your devices, not just cloud
3. **Privacy**: Your data stays yours
4. **Multi-Channel**: Works where you already communicate
5. **Extensible**: Skills-based architecture

## What We Build

- Gateway control plane for sessions, channels, tools
- Multi-channel inbox (WhatsApp, Telegram, Slack, etc.)
- Voice capabilities (wake + talk mode)
- Live Canvas for visual workspace
- Skills platform for extensibility

## What We Avoid

- Multi-tenant SaaS features
- Heavy cloud dependencies
- Complex enterprise features
- Breaking changes without migration paths
"""


class VisionChecker:
    """Checks if PRs align with project vision."""
    
    def __init__(self, llm_client: "LLMClient | None" = None) -> None:
        """Initialize the vision checker."""
        self.config = get_settings().vision
        self.llm = llm_client
        self._vision_doc: str | None = None
    
    def _load_vision(self) -> str:
        """Load vision document."""
        if self._vision_doc is not None:
            return self._vision_doc
        
        vision_path = Path(self.config.vision_doc_path)
        if vision_path.exists():
            self._vision_doc = vision_path.read_text()
        else:
            self._vision_doc = DEFAULT_VISION
        
        return self._vision_doc
    
    async def check(self, pr: PullRequest, diff_summary: str | None = None) -> VisionAlignmentResult:
        """Check if a PR aligns with project vision.
        
        Args:
            pr: The PR to check
            diff_summary: Optional summary of code changes
            
        Returns:
            VisionAlignmentResult with alignment analysis
        """
        vision = self._load_vision()
        
        if not self.llm:
            return self._basic_check(pr, vision)
        
        prompt = self._build_check_prompt(pr, vision, diff_summary)
        
        response = await self.llm.complete(
            prompt=prompt,
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.1,
        )
        
        return self._parse_response(response, pr)
    
    def _build_check_prompt(
        self, 
        pr: PullRequest, 
        vision: str,
        diff_summary: str | None
    ) -> str:
        """Build the vision check prompt."""
        prompt = f"""You are a maintainer reviewing a PR against the project vision. Assess alignment.

## Project Vision

{vision}

## PR Information

Title: {pr.title}
Description: {pr.body or "No description"}
Files Changed: {', '.join(pr.files_changed)}
Labels: {', '.join(pr.labels)}

"""
        
        if diff_summary:
            prompt += f"""## Changes Summary

{diff_summary}

"""
        
        prompt += """## Assessment Instructions

Analyze this PR against the project vision:

1. **Alignment Score**: 0.0-1.0 (1.0 = perfectly aligned)

2. **Status**: 
   - "aligned" - fits vision well
   - "needs_discussion" - has some concerns
   - "misaligned" - strays from vision

3. **What Fits**: List aspects that align with vision

4. **Concerns**: List any deviations or concerns

5. **Recommendation**: Clear recommendation

6. **Suggested Changes**: Specific changes to improve alignment

Format as JSON:

```json
{
  "alignment_score": 0.85,
  "status": "aligned",
  "fits_vision": ["..."],
  "concerns": ["..."],
  "recommendation": "...",
  "suggested_changes": ["..."]
}
```

Be objective and constructive."""
        
        return prompt
    
    def _parse_response(self, response: str, pr: PullRequest) -> VisionAlignmentResult:
        """Parse LLM response."""
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found")
            
            data = json.loads(response[json_start:json_end])
            
            return VisionAlignmentResult(
                alignment_score=data.get("alignment_score", 0.5),
                status=data.get("status", "needs_discussion"),
                fits_vision=data.get("fits_vision", []),
                concerns=data.get("concerns", []),
                recommendation=data.get("recommendation", "Review manually"),
                suggested_changes=data.get("suggested_changes", []),
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            return VisionAlignmentResult(
                alignment_score=0.5,
                status="needs_discussion",
                fits_vision=[],
                concerns=[f"Parse error: {e}"],
                recommendation="Manual review required",
                suggested_changes=[],
            )
    
    def _basic_check(self, pr: PullRequest, vision: str) -> VisionAlignmentResult:
        """Basic vision check without LLM."""
        fits = []
        concerns = []
        
        # Simple keyword matching
        title_lower = pr.title.lower()
        body_lower = (pr.body or "").lower()
        combined = title_lower + " " + body_lower
        
        # Positive signals
        if any(k in combined for k in ["personal", "local", "privacy", "channel", "skill"]):
            fits.append("Appears to support core principles")
        
        if "test" in combined:
            fits.append("Includes testing")
        
        # Concern signals
        if any(k in combined for k in ["saas", "enterprise", "multi-tenant", "cloud-only"]):
            concerns.append("May introduce non-personal features")
        
        if pr.additions + pr.deletions > 2000:
            concerns.append("Large change - review carefully for scope creep")
        
        # Score
        score = 0.7
        if fits:
            score += 0.1 * len(fits)
        if concerns:
            score -= 0.15 * len(concerns)
        
        score = max(0.0, min(1.0, score))
        
        # Status
        if score >= self.config.alignment_threshold:
            status = "aligned"
        elif score <= self.config.auto_reject_threshold:
            status = "misaligned"
        else:
            status = "needs_discussion"
        
        return VisionAlignmentResult(
            alignment_score=score,
            status=status,
            fits_vision=fits if fits else ["No strong signals either way"],
            concerns=concerns,
            recommendation="Automated basic check - human review recommended",
            suggested_changes=[],
        )
