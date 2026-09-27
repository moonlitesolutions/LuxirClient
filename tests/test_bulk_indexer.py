import json
from unittest.mock import patch

import pytest
import requests

from luxir_client import LuxirClient
from luxir_client.helpers import BulkIndexer


class FakeResponse(object):
    def __init__(self, text, status_code=200, url="http://localhost:9400/"):
        self.text = text
        self.status_code = status_code
        self.url = url


def make_client():
    return LuxirClient(host="http://localhost:9400")


def sent_bodies(mock_request):
    return [json.loads(call.kwargs["data"]) for call in mock_request.call_args_list]


def test_add_flushes_automatically_at_batch_size():
    client = make_client()
    bulk = BulkIndexer(client, "books", batch_size=2)
    ok = FakeResponse(json.dumps({"status": "ok"}))

    with patch.object(requests.Session, "request", return_value=ok) as m:
        bulk.add({"id": "1"})
        assert m.call_count == 0  # buffered, not yet flushed
        bulk.add({"id": "2"})
        assert m.call_count == 1  # batch_size reached, auto-flushed

    bodies = sent_bodies(m)
    assert bodies[0]["docs"] == [{"id": "1"}, {"id": "2"}]
    assert "commit" not in bodies[0]  # commit_every_batch defaults to False
    assert bulk.docs_sent == 2
    assert bulk.batches_sent == 1


def test_add_many_respects_batch_size_across_calls():
    client = make_client()
    bulk = BulkIndexer(client, "books", batch_size=3)
    ok = FakeResponse(json.dumps({"status": "ok"}))

    with patch.object(requests.Session, "request", return_value=ok) as m:
        bulk.add_many([{"id": "1"}, {"id": "2"}])
        assert m.call_count == 0
        bulk.add_many([{"id": "3"}, {"id": "4"}])
        assert m.call_count == 1  # flushed once at 3, one doc left buffered

    bodies = sent_bodies(m)
    assert bodies[0]["docs"] == [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    assert bulk._buffer == [{"id": "4"}]


def test_manual_flush_and_close():
    client = make_client()
    bulk = BulkIndexer(client, "books", batch_size=100)
    ok = FakeResponse(json.dumps({"status": "ok"}))

    with patch.object(requests.Session, "request", return_value=ok) as m:
        bulk.add({"id": "1"})
        assert bulk.flush() is not None
        assert m.call_count == 1
        assert bulk.flush() is None  # nothing buffered, no-op
        assert m.call_count == 1

        bulk.add({"id": "2"})
        bulk.close(commit=True)

    bodies = sent_bodies(m)
    assert "commit" not in bodies[0]
    assert bodies[1]["commit"] == {}
    assert bulk.batches_sent == 2


def test_context_manager_flushes_and_commits_on_clean_exit():
    client = make_client()
    ok = FakeResponse(json.dumps({"status": "ok"}))

    with patch.object(requests.Session, "request", return_value=ok) as m:
        with BulkIndexer(client, "books", batch_size=100) as bulk:
            bulk.add({"id": "1"})
            bulk.add({"id": "2"})
            assert m.call_count == 0  # under batch_size, nothing sent yet

    bodies = sent_bodies(m)
    assert len(bodies) == 1
    assert bodies[0]["docs"] == [{"id": "1"}, {"id": "2"}]
    assert bodies[0]["commit"] == {}  # close() commits by default


def test_context_manager_does_not_flush_on_exception():
    client = make_client()
    ok = FakeResponse(json.dumps({"status": "ok"}))

    with patch.object(requests.Session, "request", return_value=ok) as m:
        with pytest.raises(ValueError):
            with BulkIndexer(client, "books", batch_size=100) as bulk:
                bulk.add({"id": "1"})
                raise ValueError("boom")

    assert m.call_count == 0
    assert bulk._buffer == [{"id": "1"}]


def test_commit_every_batch_true():
    client = make_client()
    bulk = BulkIndexer(client, "books", batch_size=1, commit_every_batch=True)
    ok = FakeResponse(json.dumps({"status": "ok"}))

    with patch.object(requests.Session, "request", return_value=ok) as m:
        bulk.add({"id": "1"})

    bodies = sent_bodies(m)
    assert bodies[0]["commit"] == {}


def test_invalid_batch_size_raises():
    client = make_client()
    with pytest.raises(ValueError):
        BulkIndexer(client, "books", batch_size=0)
