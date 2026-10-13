#!/usr/bin/env python3
"""Review only JavaScript assets publicly linked by the authorized homepage.

Strict hostname allowlist, two assets maximum, 1 MiB read limit per asset,
no request parameters or payloads, no crawling, no login, no saving source
or printing credential values to public CI logs.
"""
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

HOST = "zedoneexam.site"
ALLOWED = {HOST, "www." + HOST}
UA = {"User-Agent": "OwnerSecurityClientAssetReview/1.0"}
MAX_BYTES = 1048576

class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
    def handle_starttag(self, tag, attrs):
        if tag == "script":
            url = dict(attrs).get("src")
            if url:
                self.refs.append(url)

class ScopedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        u = urllib.parse.urlsplit(newurl)
        if u.scheme != "https" or u.hostname not in ALLOWED:
            raise ValueError("Cross-origin redirect denied")
        return super().redirect_request(request, fp, code, msg, headers, newurl)

OPENER = urllib.request.build_opener(ScopedRedirects())

def read_public(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or p.hostname not in ALLOWED:
        raise ValueError("Out of scope URL")
    request = urllib.request.Request(url, headers=UA)
    with OPENER.open(request, timeout=12) as res:
        if res.status != 200:
            raise ValueError("Non-200 response")
        return res.read(MAX_BYTES + 1)

def run():
    try:
        home = read_public("https://" + HOST + "/")
    except (OSError, ssl.SSLError, urllib.error.URLError, ValueError) as exc:
        print("Homepage unreachable for client review:", type(exc).__name__)
        return 1
    parser = Scripts()
    parser.feed(home[:MAX_BYTES].decode("utf-8", "replace"))
    urls = []
    for src in parser.refs:
        u = urllib.parse.urlsplit(urllib.parse.urljoin("https://" + HOST + "/", src))
        if u.scheme != "https" or u.hostname not in ALLOWED:
            continue
        if u.path.lower().endswith((".js", ".mjs")):
            full = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, u.query, ""))
            if full not in urls:
                urls.append(full)
        if len(urls) == 2:
            break

    checked = 0
    truncated = 0
    map_references = 0
    literal_key_markers = 0
    exposed_key_like_assignments = 0
    for url in urls:
        try:
            buf = read_public(url)
        except (OSError, ssl.SSLError, urllib.error.URLError, ValueError) as exc:
            print("One public client asset unavailable:", type(exc).__name__)
            continue
        checked += 1
        if len(buf) > MAX_BYTES:
            truncated += 1
            buf = buf[:MAX_BYTES]
        data = buf.decode("utf-8", "replace")
        if "sourceMappingURL=" in data:
            map_references += 1
        # Heuristics only. No potential secret values are printed or persisted.
        literal_key_markers += len(re.findall(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data))
        exposed_key_like_assignments += len(re.findall(
            r"""(?i)(?:secret|api[_-]?key|private[_-]?key|access[_-]?token)\s*[:=]\s*['"][-_a-z0-9./+=]{24,}['"]""",
            data,
        ))
    print("Public first-party JavaScript assets referenced:", len(urls))
    print("First-party JavaScript assets reviewed:", checked)
    print("Assets exceeding 1 MiB read cap:", truncated)
    print("Assets containing sourceMappingURL hints:", map_references)
    print("Private-key PEM markers:", literal_key_markers)
    print("Potential embedded long key-like assignments (manual validation needed):", exposed_key_like_assignments)
    if literal_key_markers or exposed_key_like_assignments:
        print("ACTION: Review source privately, rotate any confirmed exposed keys; never post values to issues/logs.")
    return 0 if checked else 1

if __name__ == "__main__":
    sys.exit(run())
