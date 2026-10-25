import httpx
import pytest

from ingestion.client import DipApiError
from tests.conftest import FakeDip, page


def test_pages_until_cursor_stops_changing(make_client, vorgang_page) -> None:
    docs = vorgang_page["documents"]
    fake = FakeDip([page(docs[:2], "c1"), page(docs[2:], "c2"), page([], "c2")])
    client, _ = make_client(fake)

    pages = list(client.iter_pages("vorgang", {"f.wahlperiode": "21"}))

    assert [p.number for p in pages] == [1, 2]
    assert [len(p.documents) for p in pages] == [2, 1]
    assert len(fake.requests) == 3
    # Follow-up requests repeat the original params and add the previous cursor.
    assert "cursor" not in fake.requests[0].url.params
    assert fake.requests[1].url.params["cursor"] == "c1"
    assert fake.requests[2].url.params["cursor"] == "c2"
    assert all(r.url.params["f.wahlperiode"] == "21" for r in fake.requests)


def test_empty_result_set_yields_one_empty_page(make_client) -> None:
    fake = FakeDip([page([], "c0"), page([], "c0")])
    client, _ = make_client(fake)

    pages = list(client.iter_pages("person"))

    assert len(pages) == 1
    assert pages[0].documents == []


def test_api_key_sent_in_header_not_url(make_client) -> None:
    fake = FakeDip([page([], "c"), page([], "c")])
    client, _ = make_client(fake)

    list(client.iter_pages("person"))

    request = fake.requests[0]
    assert request.headers["Authorization"] == "ApiKey test-key"
    assert "test-key" not in str(request.url)


def test_body_kept_byte_exact(make_client) -> None:
    raw = b'{"numFound": 1, "cursor": "c", "documents": [{"id": "1", "titel": "\\u00e4"}]}'
    fake = FakeDip([httpx.Response(200, content=raw), page([], "c")])
    client, _ = make_client(fake)

    first = next(iter(client.iter_pages("vorgang")))

    assert first.body == raw


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retries_transient_errors(make_client, status) -> None:
    fake = FakeDip([httpx.Response(status), httpx.Response(status), page([], "c"), page([], "c")])
    client, sleeps = make_client(fake, page_delay=0)

    pages = list(client.iter_pages("vorgang"))

    assert len(pages) == 1
    assert len(sleeps) == 2


def test_honours_retry_after(make_client) -> None:
    fake = FakeDip(
        [httpx.Response(429, headers={"Retry-After": "7"}), page([], "c"), page([], "c")]
    )
    client, sleeps = make_client(fake, page_delay=0)

    list(client.iter_pages("vorgang"))

    assert sleeps == [7.0]


def test_backoff_grows_and_is_capped(make_client) -> None:
    fake = FakeDip([httpx.Response(503)] * 4 + [page([], "c"), page([], "c")])
    client, sleeps = make_client(fake, page_delay=0, backoff_base=1, backoff_max=3)

    list(client.iter_pages("vorgang"))

    caps = [1, 2, 3, 3]
    assert all(0 <= s <= cap for s, cap in zip(sleeps, caps, strict=True))


@pytest.mark.parametrize("status", [400, 401, 404])
def test_client_errors_are_not_retried(make_client, status) -> None:
    fake = FakeDip([httpx.Response(status, json={"code": status, "message": "nope"})])
    client, sleeps = make_client(fake)

    with pytest.raises(DipApiError, match=str(status)):
        list(client.iter_pages("vorgang"))
    assert sleeps == []
    assert len(fake.requests) == 1


def test_gives_up_after_max_retries(make_client) -> None:
    fake = FakeDip([httpx.Response(503)] * 3)
    client, sleeps = make_client(fake, max_retries=2)

    with pytest.raises(DipApiError, match="after 3 attempts"):
        list(client.iter_pages("vorgang"))
    assert len(sleeps) == 2


def test_retries_network_errors(make_client) -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom", request=request)
        return page([], "c")

    client, sleeps = make_client(flaky, page_delay=0)

    assert len(list(client.iter_pages("vorgang"))) == 1
    assert len(sleeps) == 1


def test_waits_between_pages(make_client) -> None:
    fake = FakeDip([page([{"id": "1"}], "c1"), page([{"id": "2"}], "c2"), page([], "c2")])
    client, sleeps = make_client(fake, page_delay=0.5)

    list(client.iter_pages("vorgang"))

    assert sleeps == [0.5, 0.5]
