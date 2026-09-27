import json

from .exceptions import LuxirError


class LuxirResponse(object):
    """
    Wraps a parsed `_search` response body.

    Example::

        res = client.search('books', {'query': 'title_t:dune', 'get_number': True})
        res.get_docs()
        res.get_num_found()
    """

    def __init__(self, data):
        self.data = data
        self.docs = data.get("docs", [])

    def get_docs(self):
        """Returns the list of document dicts in this response."""
        return self.docs

    def get_results_count(self):
        """Returns the number of documents returned in this response."""
        return len(self.docs)

    def get_num_found(self):
        """
        Returns the exact match count. Only present if the query set
        `get_number: True`.
        """
        if "found" not in self.data:
            raise LuxirError(
                "'found' not in response - did you set get_number=True on the query?"
            )
        return self.data["found"]

    def get_scores(self):
        """Returns a dict of doc id -> relevance score. Requires `get_scores: True` on the query."""
        return {doc["id"]: doc["_score_"] for doc in self.docs if "_score_" in doc}

    def get_ops(self, name=None):
        """
        Returns the raw `ops` block (facets/metrics results). Pass `name`
        to get just one op's result.
        """
        ops = self.data.get("ops", {})
        if name is not None:
            return ops.get(name, {})
        return ops

    def get_facet_buckets(self, op_name):
        """Convenience accessor for the `buckets` list of a field_facet/range_facet op."""
        return self.get_ops(op_name).get("buckets", [])

    def get_json(self):
        """Returns the original response as a JSON string."""
        return json.dumps(self.data)
