"""HTTP client for the DIP API: auth, cursor paging, retries with backoff.

The client is deliberately polite: requests are sequential, pages are spaced out by a short
delay, transient errors are retried with exponential backoff and jitter, and anything that looks
like the DIP bot challenge stops the run instead of hammering the server.
"""

import logging
import random
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
"""HTTP status codes that are retried; every other non-2xx status fails immediately."""


class DipApiError(RuntimeError):
    """A request to the DIP API failed for good.

    Raised for non-retryable responses (400 bad parameter, 401 missing or expired key,
    404 unknown id), for redirects (including the bot challenge), and when retries are
    exhausted.
    """


@dataclass(frozen=True)
class Page:
    """One page of a DIP list endpoint, as returned by `DipClient.iter_pages`.

    Attributes:
        number: 1-based position of the page within the result set.
        params: Query parameters of the request, including the cursor but never the API key.
        status_code: HTTP status of the response.
        body: Response body exactly as received; this is what Bronze stores.
        documents: The parsed ``documents`` array (up to 100 records).
        cursor: Cursor returned with this page, to be sent with the next request.
    """

    number: int
    params: dict[str, str]
    status_code: int
    body: bytes
    documents: list[dict[str, Any]]
    cursor: str


class DipClient:
    """Read-only client for the DIP API list endpoints.

    Use it as a context manager so the underlying connection pool is closed::

        with DipClient(api_key) as client:
            for page in client.iter_pages("vorgang", {"f.wahlperiode": "21"}):
                ...

    Args:
        api_key: DIP API key. Sent as ``Authorization: ApiKey <key>``, never in the URL.
        base_url: API base URL.
        transport: Optional httpx transport; tests pass an ``httpx.MockTransport``.
        max_retries: Retries per request after the first attempt.
        backoff_base: Base delay in seconds for exponential backoff.
        backoff_max: Upper bound in seconds for any single wait, including ``Retry-After``.
        page_delay: Pause in seconds between consecutive pages.
        timeout: Per-request timeout in seconds.
        sleep: Function used to wait; injectable so tests run instantly.
    """

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
        """Close the HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> "DipClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def iter_pages(self, entity: str, params: Mapping[str, str] | None = None) -> Iterator[Page]:
        """Yield every page of a list endpoint, following the cursor.

        Every follow-up request repeats `params` and adds the cursor of the previous
        response. The DIP API signals the end of a result set by returning the cursor that
        was sent, so paging stops on an unchanged cursor, not on ``numFound`` or on an empty
        page. The (normally empty) terminal page is not yielded.

        Args:
            entity: List endpoint name, e.g. ``"vorgang"`` (see `ingestion.ENTITIES`).
            params: Filter parameters such as ``f.aktualisiert.start``.

        Yields:
            Pages in API order, numbered from 1.

        Raises:
            DipApiError: If a request fails for good (see `DipApiError`).
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
        """GET `path`, retrying network errors and `RETRYABLE_STATUS` responses."""
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

            if response.is_success:
                return response
            if response.is_redirect and "challenge" in response.headers.get("location", ""):
                # The DIP front end answers suspected bots with a redirect to a browser
                # challenge. Retrying quickly makes it worse; stop and let the next run try.
                raise DipApiError(
                    f"GET {path} was redirected to a bot challenge; back off and retry later"
                )
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
        """Seconds to wait before retry number `attempt` (0-based).

        Honours a numeric ``Retry-After`` header; otherwise uses exponential backoff with
        full jitter. Both are capped at ``backoff_max``.
        """
        if retry_after and retry_after.isdigit():
            return min(float(retry_after), self._backoff_max)
        # Exponential backoff with full jitter.
        cap = min(self._backoff_max, self._backoff_base * 2**attempt)
        return random.uniform(0, cap)  # noqa: S311 - jitter, not cryptography
