from __future__ import annotations
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, TypeVar

import anthropic
from anthropic import Timeout

T = TypeVar("T")

# Default timeout: 120 seconds for connect, 300 seconds for read (LLM responses can be slow)
DEFAULT_TIMEOUT = Timeout(connect=120.0, read=300.0, write=120.0, pool=120.0)


class LLMClient:
    """Thin wrapper around the Anthropic SDK for ReproAudit."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: Optional[str] = None,
        timeout: Optional[Timeout] = None,
    ):
        self.model = model
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            timeout=timeout or DEFAULT_TIMEOUT,
        )

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
        parallel: bool = False,
        max_workers: int = 4,
    ) -> List[str]:
        """Run multiple prompts. Returns responses in order.

        Args:
            prompts: List of prompts to process.
            max_tokens: Maximum tokens per response.
            system: Optional system prompt.
            parallel: If True, run requests concurrently using threads.
            max_workers: Maximum number of parallel workers (default: 4).
        """
        if not parallel:
            return [self.complete(p, max_tokens=max_tokens, system=system) for p in prompts]

        results: List[Optional[str]] = [None] * len(prompts)

        def _process(idx: int, prompt: str) -> tuple[int, str]:
            return idx, self.complete(prompt, max_tokens=max_tokens, system=system)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_process, i, p) for i, p in enumerate(prompts)]
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result

        return [r or "" for r in results]

    def map_parallel(
        self,
        items: List[T],
        process_fn: Callable[[T], Any],
        max_workers: int = 4,
    ) -> List[Any]:
        """Execute a function on multiple items in parallel.

        Args:
            items: List of items to process.
            process_fn: Function to apply to each item.
            max_workers: Maximum number of parallel workers.

        Returns:
            Results in the same order as input items.
        """
        results: List[Any] = [None] * len(items)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {executor.submit(process_fn, item): i for i, item in enumerate(items)}
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = e

        return results
