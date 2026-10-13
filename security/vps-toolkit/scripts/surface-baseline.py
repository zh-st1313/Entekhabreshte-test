#!/usr/bin/env python3
"""Low-impact public web-surface audit, strictly confined to zedoneexam.site.

No login attempts, fuzzing, exploitation, crawling, file downloads, or
subdomain/IP discovery. Uses a bounded number of HTTP requests. Prints
high-level findings only, never page content, IPs, cookies, or secrets.
"""
import json
import ssl
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

HOST = "zedoneexam.site"
ALLOWED = {HOST, "www." + HOST}
TIMEOUT = 8
MAX_BYTES = 262144
MAX_SCRIPTS = 2
SECURITY = (
    "strict-transport-security", "content-security-policy",
    "x-content-type-options", "referrer-policy", "permissions-policy",
    "x-frame-options",
)

class HTMLAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.form_count = 0
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "script" and d.get("src"):
            self.scripts.append(d["src"])
        if tag == "form":
            self.form_count += 1

class ScopeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.hostname not in ALLOWED or parsed.scheme != "https":
            raise ValueError("Redirect outside approved HTTPS scope")
        return super().redirect_request(request, fp, code, msg, headers, newurl)

OPENER = urllib.request.build_opener(ScopeRedirects())

def request(url, method="HEAD", read_html=False, headers=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED:
        raise ValueError("Request outside HTTPS allowlist")
    req = urllib.request.Request(
        url, method=method,
        headers={"User-Agent": "AuthorizedOwnerBaseline/1.0", **(headers or {})},
    )
    try:
        res = OPENER.open(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        res = exc
    with res:
        status = res.status
        hdrs = res.headers
        body = res.read(MAX_BYTES) if read_html and method == "GET" else b""
        return status, hdrs, body

def safely(label, fn):
    try:
        return fn()
    except (OSError, TimeoutError, ValueError, ssl.SSLError, urllib.error.URLError) as exc:
        print(label + ": unavailable (" + type(exc).__name__ + ")")
        return None

def report():
    try:
        ips = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
        print("DNS resolution:", "ok" if ips else "failed")
    except OSError as exc:
        print("DNS resolution: unavailable (" + type(exc).__name__ + ")")
        return 1

    def tlscheck():
        with socket.create_connection((HOST, 443), TIMEOUT) as raw:
            with ssl.create_default_context().wrap_socket(raw, server_hostname=HOST) as tls:
                return tls.version()
    tls = safely("TLS", tlscheck)
    print("TLS certificate verification:", "passed" if tls else "not confirmed")
    if tls:
        print("Negotiated TLS protocol:", tls)

    response = safely("Homepage", lambda: request("https://" + HOST + "/", method="GET", read_html=True))
    if not response:
        return 1
    status, headers, body = response
    print("Homepage HTTP status:", status)
    missing = [name for name in SECURITY if not headers.get(name)]
    print("Header coverage:", str(len(SECURITY) - len(missing)) + "/" + str(len(SECURITY)))
    print("Absent headers (review relevance):", ", ".join(missing) if missing else "none")
    raw_cookies = headers.get_all("Set-Cookie") or []
    print("Set-Cookie count:", len(raw_cookies))
    if raw_cookies:
        print("Cookies missing Secure flag:", sum(not any(x.strip().lower() == "secure" for x in c.split(";")[1:]) for c in raw_cookies))
        print("Cookies missing HttpOnly flag:", sum(not any(x.strip().lower() == "httponly" for x in c.split(";")[1:]) for c in raw_cookies))
        print("Cookies missing SameSite attribute:", sum(not any(x.strip().lower().startswith("samesite=") for x in c.split(";")[1:]) for c in raw_cookies))

    origin = "https://" + HOST
    cors = safely("CORS OPTIONS", lambda: request(
        origin + "/", method="OPTIONS",
        headers={"Origin": "https://security-audit.invalid", "Access-Control-Request-Method": "GET"}))
    if cors:
        _status, h, _ = cors
        allow = h.get("Access-Control-Allow-Origin", "")
        creds = (h.get("Access-Control-Allow-Credentials") or "").lower()
        print("CORS test-origin reflected:", allow == "https://security-audit.invalid")
        print("CORS wildcard:", allow == "*")
        print("CORS allows credentials:", creds == "true")

    for path in ("/.well-known/security.txt", "/robots.txt"):
        result = safely("Public metadata " + path, lambda p=path: request(origin + p))
        if result:
            print("Public metadata " + path + ":", result[0])

    parsed = HTMLAssets()
    ctype = headers.get("Content-Type", "")
    if "text/html" in ctype.lower():
        parsed.feed(body.decode("utf-8", "replace"))
        print("HTML forms visible:", parsed.form_count)
        print("External JS script references:", len(parsed.scripts))
    else:
        print("Homepage not delivered with text/html Content-Type")

    checked = 0
    candidates = 0
    for script in parsed.scripts:
        if checked >= MAX_SCRIPTS:
            break
        src = urllib.parse.urljoin(origin + "/", script)
        u = urllib.parse.urlsplit(src)
        if u.hostname not in ALLOWED or u.scheme != "https":
            continue
        suffix = u.path.lower()
        if not (suffix.endswith(".js") or suffix.endswith(".mjs")):
            continue
        # Probe only first two same-origin JS sourcemaps, headers only.
        url = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path + ".map", "", ""))
        checked += 1
        result = safely("Source-map metadata", lambda p=url: request(p))
        if result:
            code, h, _ = result
            ctype = (h.get("Content-Type") or "").lower()
            if code == 200 and ("json" in ctype or "octet-stream" in ctype):
                candidates += 1
    print("Same-origin source-map HEAD probes:", checked)
    print("Possible public source-map files (verify privately):", candidates)
    return 0 if tls and status < 500 else 1

if __name__ == "__main__":
    sys.exit(report())
