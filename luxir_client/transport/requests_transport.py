import json
import time

import requests

from .base import TransportBase
from ..exceptions import ConnectionError as LuxirConnectionError
from ..exceptions import error_from_envelope, LuxirError


class TransportRequests(TransportBase):
    """
    Transport that talks to Luxir's HTTP API using the `requests` library.
    """

    def setup(self, auth=None, **kwargs):
        self.session = requests.session()
        if auth:
            self.session.auth = auth

    def _send(self, host, method="GET", path="", params=None, json_body=None, headers=None, **kwargs):
        if not host.endswith("/"):
            host += "/"
        url = host + path.lstrip("/")

        if headers is None:
            headers = {"content-type": "application/json"}

        data = json.dumps(json_body) if json_body is not None else None

        self.logger.debug("Sending %s %s params=%s", method, url, params)

        start = time.time()
        try:
            res = self.session.request(method, url, params=params, data=data, headers=headers)
        except requests.exceptions.RequestException as e:
            raise LuxirConnectionError("Couldn't connect to {}: {}".format(url, e))
        duration = time.time() - start
        self.logger.debug("Request to %s completed in %.3fs", url, duration)

        body = self._parse_body(res.text) if res.text else {}

        if body.get("error"):
            error_from_envelope(body)

        if not (200 <= res.status_code < 300):
            raise LuxirError(
                "HTTP {} from {}: {}".format(res.status_code, url, res.text[:500]),
            )

        return body, {"url": res.url}

    def _parse_body(self, text):
        """
        Luxir's `_search` responses are NDJSON (one or more JSON objects,
        potentially chunked); every other endpoint returns a single JSON
        object. The exact NDJSON line framing isn't pinned down in the
        public docs, so this merges defensively: `docs` arrays across
        lines are concatenated, other top-level keys take the last value
        seen.
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        merged = {}
        docs = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            if "docs" in chunk:
                docs.extend(chunk.pop("docs"))
            merged.update(chunk)
        if docs:
            merged["docs"] = docs
        return merged
