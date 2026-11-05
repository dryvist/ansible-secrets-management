"""Loopback ports for the OpenBao dev servers the tests start.

Each pytest-xdist worker draws from its own 100-port slice of 20000-29999, keyed on
PYTEST_XDIST_WORKER, so concurrent workers never choose the same port. A port is
returned only after a bind check confirms it is free.
"""

import os
import socket

_RANGE_START = 20000
_PORTS_PER_WORKER = 100
_WORKER_SLOTS = 100


def _worker_slot() -> int:
    # pytest-xdist names workers gw0, gw1, ...; a run without xdist has no name.
    worker = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
    return int(worker.removeprefix("gw")) % _WORKER_SLOTS


def loopback_port() -> int:
    """Return a port free on 127.0.0.1 from this worker's slice."""
    start = _RANGE_START + _worker_slot() * _PORTS_PER_WORKER
    for port in range(start, start + _PORTS_PER_WORKER):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(
        f"no free loopback port in {start}-{start + _PORTS_PER_WORKER - 1}"
    )
