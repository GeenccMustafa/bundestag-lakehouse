import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from ingestion.client import DipClient

FIXTURES = Path(__file__).parent / "fixtures" / "dip"


@pytest.fixture
def vorgang_page() -> dict[str, Any]:
    return json.loads((FIXTURES / "vorgang_page1.json").read_text())


class FakeDip:
    """Serves scripted responses and records every request it receives."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError(f"unexpected request: {request.url}")
        return self.responses.pop(0)


def page(documents: list[dict[str, Any]], cursor: str) -> httpx.Response:
    return httpx.Response(200, json={"numFound": 999, "cursor": cursor, "documents": documents})


@pytest.fixture
def make_client() -> Callable[[FakeDip], tuple[DipClient, list[float]]]:
    def factory(fake: FakeDip, **kwargs: Any) -> tuple[DipClient, list[float]]:
        sleeps: list[float] = []
        client = DipClient(
            "test-key",
            "https://dip.test/api/v1",
            transport=httpx.MockTransport(fake),
            sleep=sleeps.append,
            **kwargs,
        )
        return client, sleeps

    return factory
