"""netfetch.py - safe HTTP GET for advisory sources.

Stdlib only; Python 3.8+.

Trust controls: HTTPS only, the host must be in the allowlist of sources.json (also for
every redirect), response size is capped, fetched bytes are only ever parsed as data.
"""

import hashlib
import socket
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from sources import USER_AGENT, _AllowlistRedirect

DEFAULT_MAX_BYTES = 20 * 1024 * 1024


class FetchError(Exception):
    pass


def host_of(url):
    return (urlparse(url).hostname or "").lower()


def fetch(url, allowed_hosts, max_bytes=DEFAULT_MAX_BYTES, timeout=30, headers=None, retries=2):
    """GET a URL. Returns (bytes, sha256 hex, final url). Raises FetchError."""
    if not url.startswith("https://"):
        raise FetchError("refused: not https: %s" % url)
    if host_of(url) not in allowed_hosts:
        raise FetchError("refused: host '%s' is not allowlisted" % host_of(url))
    opener = urllib.request.build_opener(_AllowlistRedirect(set(allowed_hosts)))
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json, text/xml, text/html;q=0.8, */*;q=0.5"}
    hdrs.update(headers or {})
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with opener.open(req, timeout=timeout) as resp:
                data = resp.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise FetchError("response larger than %d bytes: %s" % (max_bytes, url))
                return data, hashlib.sha256(data).hexdigest(), resp.geturl()
        except urllib.error.HTTPError as exc:
            last = "HTTP %d" % exc.code
            if exc.code != 429 and exc.code < 500:
                break
        except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as exc:
            last = str(getattr(exc, "reason", exc))
        if attempt < retries:
            time.sleep(2 * (attempt + 1))
    raise FetchError("%s: %s" % (url, last))
