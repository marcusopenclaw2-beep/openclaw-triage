"""LLM client for AI-powered analysis."""

import os
from typing import Any

import httpx


class LLMClient:
    """Client for LLM API calls."""
    
    def __init__(
        self, 
        provider: str = "anthropic",
        api_key: str | None = None,
    ) -> None:
        """Initialize LLM client.
        
        Args:
            provider: LLM provider (anthropic, openai)
            api_key: API key (or from env var)
        """
        self.provider = provider
        
        if provider == "anthropic":
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            self.base_url = "https://api.anthropic.com/v1"
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
            )
        elif provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.base_url = "https://api.openai.com/v1"
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                }
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Get completion from LLM.
        
        Args:
            prompt: The prompt to send
            model: Model to use (provider-specific)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        if self.provider == "anthropic":
            return await self._anthropic_complete(
                prompt, model or "claude-3-5-sonnet-20241022", max_tokens, temperature
            )
        elif self.provider == "openai":
            return await self._openai_complete(
                prompt, model or "gpt-4", max_tokens, temperature
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def _anthropic_complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Complete using Anthropic API."""
        response = await self.client.post(
            "/messages",
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]
    
    async def _openai_complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Complete using OpenAI API."""
        response = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
