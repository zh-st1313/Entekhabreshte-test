#!/usr/bin/env python3
"""Bounded, non-invasive security inventory for one owner-authorized website.

Only public HTML, browser-linked JavaScript, and standard discovery documents.
No brute force, exploitation, vulnerability payloads, credential attempts,
directory guessing, or requests to discovered APIs. Do not log raw content.
"""
from __future__ import annotations

import hashlib
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

HOST = "zedoneexam.site"
HTTPS_ORIGIN = "https://" + HOST
SCOPE = {HOST, "www." + HOST}
HEADERS = {"User-Agent": "ZedOneOwnerSecurityReview/1.0"}
MAX_PAGE = 512 * 1024
MAX_JS = 768 * 1024
MAX_SCRIPTS = 2


class ScopeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        u = urllib.parse.urlsplit(newurl)
        if u.scheme != "https" or u.hostname not in SCOPE or u.port not in (None, 443):
            raise ValueError("Out-of-scope redirect blocked")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


HTTPS_OPENER = urllib.request.build_opener(ScopeRedirect)
PLAIN_OPENER = urllib.request.build_opener(NoRedirect)


def fetch(url, limit=MAX_PAGE, method="GET", http_probe=False):
    u = urllib.parse.urlsplit(url)
    if http_probe:
        if url != "http://" + HOST + "/" or method != "HEAD":
            raise ValueError("HTTP probe restricted")
    elif u.scheme != "https" or u.hostname not in SCOPE or u.port not in (None, 443):
        raise ValueError("Request outside allowlist")
    opener = PLAIN_OPENER if http_probe else HTTPS_OPENER
    req = urllib.request.Request(url, method=method, headers=HEADERS)
    try:
        res = opener.open(req, timeout=9)
    except urllib.error.HTTPError as error:
        res = error
    with res:
        status = res.status
        header = res.headers
        body = res.read(limit + 1) if method == "GET" else b""
    return status, header, body[:limit], len(body) > limit


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.links = []
        self.form_count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.scripts.append(attrs["src"])
        elif tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        elif tag == "form":
            self.form_count += 1


def is_html(body, headers):
    ctype = (headers.get("Content-Type") or "").lower()
    prefix = body[:256].lower().lstrip()
    return "text/html" in ctype or b"<html" in prefix or b"<!doctype html" in prefix


def main():
    try:
        status, h, homepage, truncated = fetch(HTTPS_ORIGIN + "/")
    except (OSError, ValueError, ssl.SSLError) as exc:
        print("Homepage: unable to inspect", type(exc).__name__)
        return 1
    if status >= 500:
        print("Homepage: server error", status)
        return 1
    print("Homepage HTTP status:", status)
    print("Homepage HTML:", is_html(homepage, h))
    print("Homepage sample truncated:", truncated)
    print("Runtime technology header disclosed:", bool(h.get("X-Powered-By")))
    print("Frame protections present:", bool(h.get("X-Frame-Options") or "frame-ancestors" in (h.get("Content-Security-Policy") or "").lower()))

    try:
        code, headers, _body, _cut = fetch("http://" + HOST + "/", method="HEAD", http_probe=True)
        location = headers.get("Location", "")
        redirected = (code in (301, 302, 303, 307, 308)
                      and urllib.parse.urlsplit(location).scheme == "https"
                      and urllib.parse.urlsplit(location).hostname in SCOPE)
        print("Plain HTTP redirects to HTTPS:", redirected)
        print("Plain HTTP response status:", code)
    except (OSError, ValueError) as exc:
        print("Plain HTTP redirect check: unavailable", type(exc).__name__)

    parser = Links()
    if is_html(homepage, h):
        parser.feed(homepage.decode("utf-8", "replace"))
    print("Public HTML links:", len(parser.links))
    print("Public HTML forms:", parser.form_count)
    print("Browser-linked scripts:", len(parser.scripts))
    login_paths = []
    for item in parser.links:
        target = urllib.parse.urlsplit(urllib.parse.urljoin(HTTPS_ORIGIN + "/", item))
        if target.scheme != "https" or target.hostname not in SCOPE:
            continue
        if re.search(r"/(login|signin|sign-in|auth)(?:/|$)", target.path, re.I):
            clean = urllib.parse.urlunsplit((target.scheme, target.netloc, target.path, "", ""))
            if clean not in login_paths:
                login_paths.append(clean)
    print("Publicly linked sign-in pages:", len(login_paths))

    for name, path, signature in (
        ("robots.txt", "/robots.txt", b"user-agent:"),
        ("security.txt", "/.well-known/security.txt", b"contact:"),
        ("sitemap.xml", "/sitemap.xml", b"<urlset"),
    ):
        try:
            code, meta, body, _cut = fetch(HTTPS_ORIGIN + path, limit=8192)
            low = body.lower()
            semantically_valid = code == 200 and signature in low and not is_html(body, meta)
            app_shell = code == 200 and is_html(body, meta)
            print(name + " response code:", code)
            print(name + " format looks valid:", semantically_valid)
            print(name + " returned HTML app shell:", app_shell)
        except (OSError, ssl.SSLError, ValueError) as exc:
            print(name + " probe: unavailable", type(exc).__name__)

    try:
        path = "/__owner_security_review_no_file_20261013__.txt"
        code, meta, body, _cut = fetch(HTTPS_ORIGIN + path, limit=MAX_PAGE)
        homepage_hash = hashlib.sha256(homepage).digest()
        unknown_hash = hashlib.sha256(body).digest()
        print("Unknown .txt path HTTP status:", code)
        print("Unknown .txt path returns HTML:", is_html(body, meta))
        print("Unknown .txt path exactly matches homepage:", homepage_hash == unknown_hash)
    except (OSError, ValueError, ssl.SSLError) as exc:
        print("404 fallback check: unavailable", type(exc).__name__)

    total_js = 0
    api_hint_assets = 0
    auth_hint_assets = 0
    asset_skipped = 0
    for src in parser.scripts:
        if total_js >= MAX_SCRIPTS:
            break
        p = urllib.parse.urlsplit(urllib.parse.urljoin(HTTPS_ORIGIN + "/", src))
        if p.scheme != "https" or p.hostname not in SCOPE or not p.path.lower().endswith((".js", ".mjs")):
            continue
        url = urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))
        try:
            code, meta, body, cut = fetch(url, limit=MAX_JS)
        except (OSError, ValueError, ssl.SSLError):
            asset_skipped += 1
            continue
        if code != 200 or cut:
            asset_skipped += 1
            continue
        text = body.decode("utf-8", "replace")
        total_js += 1
        if re.search(r"/api/|/graphql\b|/v[12]/", text, re.I):
            api_hint_assets += 1
        if re.search(r"/login\b|/signin\b|/auth/|authorization|bearer\b", text, re.I):
            auth_hint_assets += 1
    print("Client scripts statically analyzed:", total_js)
    print("Scripts containing possible API route hints:", api_hint_assets)
    print("Scripts containing authentication vocabulary:", auth_hint_assets)
    print("Skipped/truncated client assets:", asset_skipped)
    print("Note: route hints are not evidence of reachable or vulnerable APIs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
