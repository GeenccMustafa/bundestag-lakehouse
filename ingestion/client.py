"""HTTP client for the DIP API: auth, cursor paging, retries with backoff."""

import logging
import random
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class DipApiError(RuntimeError):
    """Non-retryable API error (bad request, invalid key, not found) or retries exhausted."""


@dataclass(frozen=True)
class Page:
    number: int  # 1-based
    params: dict[str, str]  # query params of the request, excluding the API key
    status_code: int
    body: bytes  # response body exactly as received
    documents: list[dict[str, Any]]
    cursor: str


class DipClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://search.dip.bundestag.de/api/v1",
        *,
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 5,
        backoff_base: float = 1.0,
        backoff_max: float = 60.0,
        page_delay: float = 0.2,
        timeout: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url,
            # Header, not ?apikey=, so the key never shows up in logged URLs.
            headers={
                "Authorization": f"ApiKey {api_key}",
                "Accept": "application/json",
                "User-Agent": "bundestag-lakehouse (+https://github.com/GeenccMustafa/bundestag-lakehouse)",
            },
            timeout=timeout,
            transport=transport,
        )
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._page_delay = page_delay
        self._sleep = sleep

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "DipClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def iter_pages(self, entity: str, params: Mapping[str, str] | None = None) -> Iterator[Page]:
        """Yield every page of a list endpoint.

        The DIP API signals the end of a result set by returning the same cursor that was
        sent, so paging stops on an unchanged cursor (not on numFound or an empty page).
        """
        base_params = dict(params or {})
        cursor: str | None = None
        number = 0
        while True:
            request_params = dict(base_params)
            if cursor is not None:
                request_params["cursor"] = cursor
            response = self._get(f"/{entity}", request_params)
            payload = response.json()
            next_cursor = payload["cursor"]
            documents = payload.get("documents", [])
            is_last = cursor is not None and next_cursor == cursor
            # The terminal page is normally empty; keep it only if it unexpectedly has data.
            if documents or not is_last:
                number += 1
                yield Page(
                    number=number,
                    params=request_params,
                    status_code=response.status_code,
                    body=response.content,
                    documents=documents,
                    cursor=next_cursor,
                )
            if is_last:
                return
            cursor = next_cursor
            if self._page_delay:
                self._sleep(self._page_delay)

    def _get(self, path: str, params: dict[str, str]) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise DipApiError(f"GET {path} failed after {attempt + 1} attempts") from exc
                delay = self._backoff(attempt, None)
                log.warning("GET %s: %s, retrying in %.1fs", path, exc, delay)
                self._sleep(delay)
                continue

            if response.status_code < 400:
                return response
            if response.status_code not in RETRYABLE_STATUS:
                raise DipApiError(f"GET {path} -> {response.status_code}: {response.text[:300]}")
            if attempt == self._max_retries:
                raise DipApiError(
                    f"GET {path} -> {response.status_code} after {attempt + 1} attempts"
                )
            delay = self._backoff(attempt, response.headers.get("Retry-After"))
            log.warning("GET %s -> %d, retrying in %.1fs", path, response.status_code, delay)
            self._sleep(delay)
        raise AssertionError("unreachable")

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        if retry_after and retry_after.isdigit():
            return min(float(retry_after), self._backoff_max)
        # Exponential backoff with full jitter.
        cap = min(self._backoff_max, self._backoff_base * 2**attempt)
        return random.uniform(0, cap)  # noqa: S311 - jitter, not cryptography
