"""
Claude API client wrapper with retry logic, rate limiting, and structured output.
"""

import json
import re
import time
from typing import Any

from anthropic import Anthropic, APIError, RateLimitError
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


class ClaudeClient:
    """Wrapper around Anthropic's Python SDK with retry and rate-limit handling."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        self.client = Anthropic(api_key=api_key)  # reads ANTHROPIC_API_KEY from env if None
        self.model = model

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Send a prompt to Claude and return the text response."""
        return self._call_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """Send a prompt to Claude and parse the response as JSON.

        Handles markdown-fenced JSON blocks (```json ... ```) automatically.
        Uses temperature 0 for deterministic structured output.
        """
        raw = self._call_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=0,
        )
        return self._parse_json(raw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Call the API with exponential-backoff retries."""
        backoff = INITIAL_BACKOFF

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                console.log(
                    f"[bold cyan]Claude API[/] attempt {attempt}/{MAX_RETRIES}  "
                    f"model={self.model}  max_tokens={max_tokens}  temp={temperature}"
                )
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                text: str = response.content[0].text
                console.log(
                    f"[bold green]✓[/] Response received  "
                    f"tokens_in={response.usage.input_tokens}  "
                    f"tokens_out={response.usage.output_tokens}"
                )
                return text

            except RateLimitError as exc:
                retry_after = _extract_retry_after(exc)
                wait = retry_after if retry_after else backoff
                console.log(
                    f"[bold yellow]Rate limited[/] — waiting {wait:.1f}s before retry"
                )
                time.sleep(wait)
                backoff *= 2

            except APIError as exc:
                if attempt == MAX_RETRIES:
                    console.log(f"[bold red]✗ API error after {MAX_RETRIES} retries:[/] {exc}")
                    raise
                console.log(
                    f"[bold yellow]API error (attempt {attempt})[/] {exc} — "
                    f"retrying in {backoff:.1f}s"
                )
                time.sleep(backoff)
                backoff *= 2

        # Should never reach here, but satisfy type checker
        raise RuntimeError("Exhausted retries without a response")  # pragma: no cover

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Extract and parse JSON from Claude's response, stripping markdown fences."""
        # Try to find a fenced JSON block first
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        json_str = match.group(1).strip() if match else text.strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse JSON from Claude response: {exc}\n"
                f"Raw response:\n{text[:500]}"
            ) from exc


def _extract_retry_after(exc: RateLimitError) -> float | None:
    """Try to read a Retry-After header from a RateLimitError."""
    try:
        headers = exc.response.headers  # type: ignore[union-attr]
        val = headers.get("retry-after")
        if val is not None:
            return float(val)
    except Exception:
        pass
    return None
