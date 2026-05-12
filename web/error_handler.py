import asyncio
import logging
from anthropic import APIError, RateLimitError, APIConnectionError, InternalServerError

logger = logging.getLogger("socratic_web.error_handler")

MAX_RETRIES_API = 3
MAX_RETRIES_PARSE = 2


async def api_call_with_retry(fn, *args, **kwargs):
    """
    Call an async function with exponential backoff retry for API errors.
    `fn` should be an async callable that returns the API response.
    """
    last_error = None
    for attempt in range(MAX_RETRIES_API):
        try:
            return await fn(*args, **kwargs)
        except RateLimitError as e:
            last_error = e
            wait = _parse_retry_after(e) or (2 ** attempt)
            logger.warning(f"速率限制 (429)，{wait:.0f}s 后重试 ({attempt + 1}/{MAX_RETRIES_API})")
            await asyncio.sleep(wait)
        except (APIConnectionError, InternalServerError) as e:
            last_error = e
            if attempt == MAX_RETRIES_API - 1:
                raise
            wait = 2 ** attempt
            logger.warning(f"API 错误，{wait}s 后重试 ({attempt + 1}/{MAX_RETRIES_API}): {e}")
            await asyncio.sleep(wait)
        except APIError as e:
            raise
    raise last_error


def _parse_retry_after(error: RateLimitError) -> float | None:
    try:
        headers = error.response.headers if hasattr(error, 'response') else {}
        val = headers.get("retry-after") or headers.get("Retry-After")
        if val:
            return float(val)
    except (ValueError, TypeError):
        pass
    return None


def safe_parse_json(text: str, label: str = "response") -> dict | None:
    """Try to extract JSON from Claude's response text."""
    import json
    import re
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to extract from markdown code blocks
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try to find first { ... } block
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    logger.error(f"无法解析 {label} 为 JSON: {text[:200]}...")
    return None
