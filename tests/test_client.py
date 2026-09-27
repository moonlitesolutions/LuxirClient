import json
from unittest.mock import patch

import pytest
import requests

from luxir_client import LuxirClient
from luxir_client.exceptions import (
    AlreadyExistsError,
    ConnectionError as LuxirConnectionError,
    LuxirError,
    NotFoundError,
)


class FakeResponse(object):
    def __init__(self, text, status_code=200, url="http://localhost:9400/"):
        self.text = text
        self.status_code = status_code
        self.url = url


def make_client(**kwargs):
    return LuxirClient(host="http://localhost:9400", **kwargs)


def test_search_single_json_object():
    client = make_client()
    body = {
        "found": 2,
        "docs": [{"id": "b2", "title_t": "Dune Messiah", "_score_": 0.67}],
    }
    with patch.object(requests.Session, "request", return_value=FakeResponse(json.dumps(body))):
        res = client.search("books", {"query": "title_t:dune", "get_number": True, "get_scores": True})

    assert res.get_num_found() == 2
    assert res.get_results_count() == 1
    assert res.get_docs()[0]["id"] == "b2"
    assert res.get_scores() == {"b2": 0.67}


def test_search_multiline_ndjson_merges_docs():
    client = make_client()
    lines = "\n".join(
        [
            json.dumps({"docs": [{"id": "b1"}]}),
            json.dumps({"docs": [{"id": "b2"}]}),
            json.dumps({"found": 2}),
        ]
    )
    with patch.object(requests.Session, "request", return_value=FakeResponse(lines)):
        res = client.search("books", {"query": "*"})

    assert [d["id"] for d in res.get_docs()] == ["b1", "b2"]
    assert res.get_num_found() == 2


def test_index_and_delete_by_id():
    client = make_client()
    with patch.object(requests.Session, "request", return_value=FakeResponse(json.dumps({"status": "ok"}))) as m:
        client.index("books", [{"id": "b1", "title_t": "Dune"}])
        args, kwargs = m.call_args
        assert kwargs["data"] == json.dumps({"docs": [{"id": "b1", "title_t": "Dune"}], "commit": {}})

    with patch.object(requests.Session, "request", return_value=FakeResponse(json.dumps({"status": "ok"}))) as m:
        client.delete_by_id("books", "b1")
        args, kwargs = m.call_args
        assert kwargs["data"] == json.dumps({"delete_ids": ["b1"], "commit": {}})


def test_error_envelope_maps_to_typed_exception():
    client = make_client()
    envelope = {
        "request_id": "abc",
        "error": {"kind": "not_found", "code": "collection_missing", "message": "no such collection"},
    }
    with patch.object(requests.Session, "request", return_value=FakeResponse(json.dumps(envelope), status_code=404)):
        with pytest.raises(NotFoundError) as exc_info:
            client.search("missing", {"query": "*"})
    assert exc_info.value.request_id == "abc"
    assert exc_info.value.code == "collection_missing"


def test_already_exists_error():
    client = make_client()
    envelope = {"error": {"kind": "already_exists", "message": "collection exists"}}
    with patch.object(requests.Session, "request", return_value=FakeResponse(json.dumps(envelope), status_code=409)):
        with pytest.raises(AlreadyExistsError):
            client.collections.create("books")


def test_unrecognized_error_kind_falls_back_to_base_class():
    client = make_client()
    envelope = {"error": {"kind": "something_new", "message": "??"}}
    with patch.object(requests.Session, "request", return_value=FakeResponse(json.dumps(envelope), status_code=500)):
        with pytest.raises(LuxirError):
            client.health()


def test_connection_error_fails_over_to_second_host():
    client = LuxirClient(host=["http://down:9400", "http://localhost:9400"])
    ok_body = json.dumps({"status": "ok"})

    def side_effect(*args, **kwargs):
        url = args[1] if len(args) > 1 else kwargs.get("url")
        if "down" in url:
            raise requests.exceptions.ConnectionError("no route to host")
        return FakeResponse(ok_body, url=url)

    with patch.object(requests.Session, "request", side_effect=side_effect):
        assert client.health() == {"status": "ok"}


def test_connection_error_raised_when_all_hosts_down():
    client = LuxirClient(host="http://down:9400")
    with patch.object(requests.Session, "request", side_effect=requests.exceptions.ConnectionError("boom")):
        with pytest.raises(LuxirConnectionError):
            client.health()


def test_collections_list_exists():
    client = make_client()
    body = json.dumps({"collections": ["books", "movies"]})
    with patch.object(requests.Session, "request", return_value=FakeResponse(body)):
        assert client.collections.list() == ["books", "movies"]
        assert client.collections.exists("books") is True
        assert client.collections.exists("nope") is False


def test_schema_does_field_exist():
    client = make_client()
    body = json.dumps({"fields": {"title": {"type": "text"}, "year": "int"}})
    with patch.object(requests.Session, "request", return_value=FakeResponse(body)):
        assert client.schema.does_field_exist("books", "title") is True
        assert client.schema.does_field_exist("books", "missing_field") is False


def test_get_found_and_not_found():
    client = make_client()
    found_body = json.dumps({"docs": [{"id": "b1", "title_t": "Dune"}]})
    with patch.object(requests.Session, "request", return_value=FakeResponse(found_body)):
        doc = client.get("books", "b1")
    assert doc["id"] == "b1"

    empty_body = json.dumps({"docs": []})
    with patch.object(requests.Session, "request", return_value=FakeResponse(empty_body)):
        with pytest.raises(NotFoundError):
            client.get("books", "missing")
