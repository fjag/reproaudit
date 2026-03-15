from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

import anthropic


class LLMClient:
    """Thin wrapper around the Anthropic SDK for ReproAudit."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: Optional[str] = None):
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def complete(self, prompt: str, *, max_tokens: int = 4096, system: Optional[str] = None) -> str:
        """Send a prompt and return the text response."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        msg = self._client.messages.create(**kwargs)
        return msg.content[0].text

    def complete_with_tool(
        self,
        prompt: str,
        tool_name: str,
        tool_description: str,
        input_schema: Dict[str, Any],
        *,
        max_tokens: int = 4096,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a prompt and force the model to call a single tool (structured output).

        Returns the tool input dict.
        """
        tool = {
            "name": tool_name,
            "description": tool_description,
            "input_schema": input_schema,
        }
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": tool_name},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        msg = self._client.messages.create(**kwargs)
        for block in msg.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input
        raise RuntimeError("LLM did not return expected tool call")

    def complete_batch(
        self,
        prompts: List[str],
        *,
        max_tokens: int = 2048,
        system: Optional[str] = None,
    ) -> List[str]:
        """Run multiple prompts sequentially. Returns responses in order."""
        return [self.complete(p, max_tokens=max_tokens, system=system) for p in prompts]
