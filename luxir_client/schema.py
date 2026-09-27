class Schema(object):
    """
    Provides an interface to Luxir's schema API (`/collections/{c}/_schema`).
    Luxir infers types from field naming conventions (e.g. `_t`, `_i`, `_s`)
    so declaring a schema up front is optional.
    """

    def __init__(self, client):
        self.client = client

    def get(self, collection, resolved=False):
        """
        Returns the collection's schema. Pass resolved=True to expand
        inheritance/templates into physical field representations.
        """
        params = {"view": "resolved"} if resolved else None
        body, _ = self.client.transport.send_request(
            method="GET", path="collections/{}/_schema".format(collection), params=params
        )
        return body

    def set_fields(self, collection, fields):
        """
        Adds/updates the given field definitions, leaving other fields
        untouched (mode=set, the server default).
        """
        body, _ = self.client.transport.send_request(
            method="POST",
            path="collections/{}/_schema".format(collection),
            json_body={"fields": fields},
        )
        return body

    def replace_all(self, collection, schema):
        """Replaces the collection's entire schema."""
        body, _ = self.client.transport.send_request(
            method="POST",
            path="collections/{}/_schema".format(collection),
            params={"mode": "replace_all"},
            json_body=schema,
        )
        return body

    def does_field_exist(self, collection, field_name):
        """Returns True if `field_name` is declared in the collection's schema."""
        schema = self.get(collection)
        return field_name in schema.get("fields", {})
