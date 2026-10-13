#!/usr/bin/env python3
"""Heuristic-only review of publicly shipped JavaScript auth architecture.

No form submissions or API requests. Never logs source text, URL paths,
credential-like literals or tokens. Pattern absence does not prove safety.
"""
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ORIGIN = "https://zedoneexam.site"
HOSTS = {"zedoneexam.site", "www.zedoneexam.site"}
MAX_ASSET_SIZE = 1024 * 1024
UA = {"User-Agent": "OwnerAuthArchitectureReview/1.0"}

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        if tag == "script":
            s = dict(attrs).get("src")
            if s:
                self.scripts.append(s)

class ScopedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        u = urllib.parse.urlsplit(newurl)
        if u.scheme != "https" or u.hostname not in HOSTS or u.port not in (None, 443):
            raise ValueError("Redirect out of scope")
        return super().redirect_request(request, fp, code, msg, headers, newurl)

OPENER = urllib.request.build_opener(ScopedRedirects())

def read(url, limit):
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.hostname not in HOSTS or u.port not in (None, 443):
        raise ValueError("Invalid target")
    req = urllib.request.Request(url, headers=UA)
    with OPENER.open(req, timeout=10) as response:
        if response.status != 200:
            raise ValueError("Unexpected HTTP response")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Asset exceeds bounded read limit")
    return data.decode("utf-8", "replace")

DETECTORS = {
    "browser_local_storage": r"\blocalStorage\b",
    "browser_session_storage": r"\bsessionStorage\b",
    "document_cookie_access": r"\bdocument\.cookie\b",
    "bearer_token_handling": r"\bBearer\b|Authorization",
    "firebase_client_sdk": r"firebase(?:app|auth)?|firebaseapp\.com",
    "supabase_client_sdk": r"supabase",
    "auth0_or_clerk": r"auth0|clerk",
    "explicit_jwt_reference": r"\bJWT\b|jwtDecode|jwt-decode",
    "fetch_or_xhr": r"\bfetch\s*\(|XMLHttpRequest|\.axios\b",
    "csrf_token_reference": r"csrf|xsrf",
}

def main():
    try:
        homepage = read(ORIGIN + "/", 512 * 1024)
    except (OSError, ValueError, ssl.SSLError, urllib.error.URLError) as exc:
        print("Homepage unavailable:", type(exc).__name__)
        return 1
    parser = LinkParser()
    parser.feed(homepage)
    assets = []
    for source in parser.scripts:
        u = urllib.parse.urlsplit(urllib.parse.urljoin(ORIGIN + "/", source))
        if u.hostname not in HOSTS or u.scheme != "https" or not u.path.endswith((".js", ".mjs")):
            continue
        url = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, u.query, ""))
        if url not in assets:
            assets.append(url)
        if len(assets) >= 2:
            break
    contents = []
    for asset in assets:
        try:
            contents.append(read(asset, MAX_ASSET_SIZE))
        except (OSError, ValueError, ssl.SSLError, urllib.error.URLError):
            pass
    print("Reviewed first-party browser scripts:", len(contents))
    if not contents:
        return 1
    for name, pattern in DETECTORS.items():
        present = any(bool(re.search(pattern, js, re.I)) for js in contents)
        print(name.replace("_", " ") + " signal:", present)
    print("All results are non-conclusive static indicators, not vulnerability findings.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
