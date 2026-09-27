class Collections(object):
    """
    Provides an interface to Luxir's collection admin endpoints
    (`/collections/_list`, `/collections/_create`, `/collections/_delete`,
    `/collections/{c}/_stats`). Collections also auto-create on first
    write, so `create()` is only needed when you want to install a
    schema up front.
    """

    def __init__(self, client, log):
        self.client = client
        self.logger = log

    def list(self):
        """Returns a list of all collection names on the node."""
        body, _ = self.client.transport.send_request(method="GET", path="collections/_list")
        # Public docs describe the response as "sorted collection names"
        # but don't pin down the field name; assuming `collections`.
        return body["collections"]

    def exists(self, name):
        """Returns True if a collection with this name exists."""
        return name in self.list()

    def create(self, name, schema=None):
        """Creates a new collection, optionally installing a schema before it becomes visible."""
        payload = {"name": name}
        if schema is not None:
            payload["schema"] = schema
        body, _ = self.client.transport.send_request(
            method="POST", path="collections/_create", json_body=payload
        )
        return body

    def delete(self, name):
        """Deletes a collection and its stored data."""
        body, _ = self.client.transport.send_request(
            method="POST", path="collections/_delete", json_body={"name": name}
        )
        return body

    def stats(self, name, segments=False):
        """Returns per-collection statistics. Pass segments=True for segment layout detail."""
        params = {"segments": "true"} if segments else None
        body, _ = self.client.transport.send_request(
            method="GET", path="collections/{}/_stats".format(name), params=params
        )
        return body
