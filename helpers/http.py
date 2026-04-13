"""
Shared HTTP utilities for datos-es-mcp clients.

Features:
  - Exponential backoff retry (up to 3 attempts, delays 1s → 2s → 4s)
  - Retries on: connection errors, timeouts, HTTP 429/500/502/503/504
  - Structured error logging with per-client prefix labels
"""

import asyncio
import logging
from typing import Any

import httpx

from helpers.logging import MAIN_LOGGER_NAME

logger = logging.getLogger(MAIN_LOGGER_NAME)

_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float = 20.0,
    log_prefix: str = "",
    **kwargs: Any,
) -> Any:
    """
    Fetch a URL and return parsed JSON, with exponential backoff retry.

    Retries up to 3 times on transient failures (connection errors, timeouts,
    HTTP 429/500/502/503/504) with delays of 1s, 2s, 4s.

    Args:
        client: An httpx.AsyncClient to use for the request.
        url: The URL to fetch.
        timeout: Request timeout in seconds (default 20s).
        log_prefix: Label for log messages (e.g. "INE API", "BdE API").
        **kwargs: Additional keyword arguments forwarded to client.get().

    Returns:
        Parsed JSON response (dict or list).

    Raises:
        httpx.HTTPError: On non-retryable HTTP errors or after all retries
            are exhausted.
        httpx.ConnectError / httpx.TimeoutException: After all retries fail.
    """
    prefix = f"{log_prefix} " if log_prefix else ""
    last_exc: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.debug("%sGET %s (attempt %d/%d)", prefix, url, attempt, _MAX_RETRIES)
            resp = await client.get(url, timeout=timeout, **kwargs)

            if resp.status_code in _RETRY_STATUS_CODES and attempt < _MAX_RETRIES:
                delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "%sHTTP %d for %s — retrying in %.0fs (attempt %d/%d)",
                    prefix,
                    resp.status_code,
                    url,
                    delay,
                    attempt,
                    _MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                continue

            resp.raise_for_status()
            return resp.json()

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "%sTransient error for %s: %s — retrying in %.0fs (attempt %d/%d)",
                    prefix,
                    url,
                    exc,
                    delay,
                    attempt,
                    _MAX_RETRIES,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "%sAll %d attempts failed for %s: %s",
                    prefix,
                    _MAX_RETRIES,
                    url,
                    exc,
                )
                raise

        except httpx.HTTPStatusError as exc:
            logger.error("%sHTTP error for %s: %s", prefix, url, exc)
            raise

    # Unreachable in practice, but satisfies type checkers
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Unexpected exit from retry loop for {url}")  # pragma: no cover
