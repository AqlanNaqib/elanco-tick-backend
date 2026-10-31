"""Tests for retrying the Elanco API, using a fake server instead of the real one."""
import httpx
import pytest

from app import elanco_client
from app.elanco_client import UpstreamError, get_json


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(elanco_client.time, "sleep", lambda seconds: None)


def fake_client(*responses):
    """A client whose server replies with these responses, in order."""
    replies = iter(responses)

    def handler(request):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    return httpx.Client(base_url="https://fake", transport=httpx.MockTransport(handler))


def test_retries_rate_limit_and_server_error_then_succeeds():
    client = fake_client(httpx.Response(429), httpx.Response(500),
                         httpx.Response(200, json={"ok": True}))
    assert get_json(client, "/stats") == {"ok": True}


def test_retries_network_errors():
    client = fake_client(httpx.ConnectError("down"), httpx.Response(200, json=[]))
    assert get_json(client, "/tick-sightings") == []


def test_404_is_not_retried():
    client = fake_client(httpx.Response(404))
    with pytest.raises(UpstreamError, match="404"):
        get_json(client, "/tick-sightings/nope")


def test_gives_up_after_three_attempts():
    client = fake_client(httpx.Response(500), httpx.Response(500), httpx.Response(500))
    with pytest.raises(UpstreamError, match="3 attempts"):
        get_json(client, "/stats")