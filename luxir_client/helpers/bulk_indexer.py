class BulkIndexer(object):
    """
    Batches documents into bounded update() calls instead of one HTTP
    request per document, or one huge request for a large list (Luxir's
    default max request body is 32MB).

    Example::

        with BulkIndexer(client, "books", batch_size=500) as bulk:
            for doc in docs:
                bulk.add(doc)
        # remaining docs are flushed and committed automatically on exit
    """

    def __init__(self, client, collection, batch_size=500, commit_every_batch=False):
        """
        :param client: A LuxirClient instance.
        :param str collection: Collection to index into.
        :param int batch_size: Number of documents to buffer before sending a batch.
        :param bool commit_every_batch: If True, each batch is committed as it's
            sent. If False (default), batches are sent uncommitted for
            throughput and only committed on close()/context-manager exit.
        """
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.client = client
        self.collection = collection
        self.batch_size = batch_size
        self.commit_every_batch = commit_every_batch
        self._buffer = []
        self.docs_sent = 0
        self.batches_sent = 0

    def add(self, doc):
        """Buffers a single document, flushing automatically once batch_size is reached."""
        self._buffer.append(doc)
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def add_many(self, docs):
        """Buffers an iterable of documents."""
        for doc in docs:
            self.add(doc)

    def flush(self, commit=None):
        """
        Sends whatever's currently buffered as one update() call.

        :param commit: Overrides commit_every_batch for this flush. Same
            semantics as LuxirClient.index()'s commit param.

        Returns None if there was nothing buffered to send.
        """
        if not self._buffer:
            return None
        commit_opt = self.commit_every_batch if commit is None else commit
        batch, self._buffer = self._buffer, []
        result = self.client.index(self.collection, batch, commit=commit_opt)
        self.docs_sent += len(batch)
        self.batches_sent += 1
        return result

    def close(self, commit=True):
        """Flushes any remaining buffered documents, committing by default."""
        return self.flush(commit=commit)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # Only auto-flush on a clean exit. If the caller's loop raised, we
        # don't know whether the buffered docs are in a valid state, so
        # leave them buffered for the caller to inspect or flush manually.
        if exc_type is None:
            self.close(commit=True)
        return False
