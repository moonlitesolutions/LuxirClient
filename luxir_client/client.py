import logging

from .collections import Collections
from .exceptions import NotFoundError
from .response import LuxirResponse
from .schema import Schema
from .transport import TransportRequests


class LuxirClient(object):
    """
    Creates a new LuxirClient.

    :param host: Location of the Luxir HTTP API, e.g. 'http://localhost:9400'.
        Can also be a list of hosts; the client fails over to the next one
        if a host is unreachable.
    :param transport: Transport class to use. Defaults to the `requests`-based
        HTTP transport.
    :param bool devel: Enables more verbose debug logging.
    """

    def __init__(self, host="http://localhost:9400", transport=TransportRequests, devel=False, log=None, **kwargs):
        self.host = host
        self.devel = devel
        self.logger = log or logging.getLogger(__package__)
        self.transport = transport(self, host=host, devel=devel, **kwargs)
        self.schema = Schema(self)
        self.collections = Collections(self, self.logger)

    def health(self):
        """Returns the `/health` liveness payload."""
        body, _ = self.transport.send_request(method="GET", path="health")
        return body

    def stats(self, collection=None, segments=False):
        """Returns node-wide stats, or per-collection stats if `collection` is given."""
        if collection is not None:
            return self.collections.stats(collection, segments=segments)
        body, _ = self.transport.send_request(method="GET", path="_stats")
        return body

    def search_raw(self, collection, query, **params):
        """
        :param str collection: Collection to search.
        :param query: Either a query-language string or a structured query dict,
            e.g. {'query': 'title_t:dune', 'limit': 10, 'get_number': True}.

        Sends a search request and returns the raw parsed response dict.
        """
        body, _ = self.transport.send_request(
            method="POST",
            path="collections/{}/_search".format(collection),
            json_body=query,
            params=params or None,
        )
        return body

    def search(self, collection, query, **params):
        """Same as search_raw, but wraps the result in a LuxirResponse."""
        return LuxirResponse(self.search_raw(collection, query, **params))

    def update(self, collection, docs=None, delete_ids=None, commit=None, **kwargs):
        """
        :param str collection: Collection to update.
        :param list docs: List of dicts to index/upsert.
        :param list delete_ids: List of document ids to delete.
        :param dict commit: Commit options, e.g. {} for defaults. Omit to
            leave the write uncommitted.

        Sends a single bounded update request. Collections auto-create on
        first write.
        """
        payload = dict(kwargs)
        if docs is not None:
            payload["docs"] = docs
        if delete_ids is not None:
            payload["delete_ids"] = delete_ids
        if commit is not None:
            payload["commit"] = commit
        body, _ = self.transport.send_request(
            method="POST", path="collections/{}/_update".format(collection), json_body=payload
        )
        return body

    def index(self, collection, docs, commit=True, **kwargs):
        """
        :param str collection: Collection to index into.
        :param list docs: List of dicts, e.g. [{'id': 'b1', 'title_t': 'Dune'}].
        :param commit: Commit options dict, or True/False to shorthand
            "commit with defaults" / "don't commit".

        Convenience wrapper over update() for the common indexing case.
        """
        commit_opt = {} if commit is True else (None if commit is False else commit)
        return self.update(collection, docs=docs, commit=commit_opt, **kwargs)

    def delete_by_id(self, collection, ids, commit=True):
        """
        :param str collection: Collection to delete from.
        :param ids: A single document id, or a list of ids.
        """
        if isinstance(ids, str):
            ids = [ids]
        commit_opt = {} if commit is True else (None if commit is False else commit)
        return self.update(collection, delete_ids=ids, commit=commit_opt)

    def get(self, collection, doc_id):
        """
        :param str collection: Collection to look up.
        :param doc_id: Id of the document to retrieve.

        Luxir has no dedicated realtime-get endpoint; this is sugar over
        search() filtered to a single id. Raises NotFoundError if missing.
        """
        doc_id_str = str(doc_id)
        expr = 'id:"{}"'.format(doc_id_str) if " " in doc_id_str else "id:{}".format(doc_id_str)
        res = self.search(collection, {"query": expr, "limit": 1})
        docs = res.get_docs()
        if docs:
            return docs[0]
        raise NotFoundError("Document '{}' not found in collection '{}'".format(doc_id, collection))
