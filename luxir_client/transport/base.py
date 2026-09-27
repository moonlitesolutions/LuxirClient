import logging

from ..exceptions import ConnectionError as LuxirConnectionError


class TransportBase(object):
    """
    Base Transport Class. Subclasses implement `setup()` and `_send()`;
    this class handles multi-host failover and stays wire-format agnostic.
    """

    def __init__(self, client, host="http://localhost:9400", devel=False, **kwargs):
        self.logger = logging.getLogger(str(__package__))
        self.client = client
        self.host = host if isinstance(host, list) else [host]
        self.devel = devel
        self.setup(**kwargs)

    def setup(self, **kwargs):
        """
        Hook for subclasses to set up sessions/channels/etc.
        """

    def _retry(function):
        def inner(self, *args, **kwargs):
            last_exception = None
            for host in self.host:
                try:
                    return function(self, host, *args, **kwargs)
                except LuxirConnectionError as e:
                    self.logger.warning("Couldn't reach %s: %s", host, e)
                    last_exception = e
            if last_exception is not None:
                raise last_exception

        return inner

    @_retry
    def send_request(self, host, **kwargs):
        return self._send(host, **kwargs)

    def _send(self, host, **kwargs):
        raise NotImplementedError
