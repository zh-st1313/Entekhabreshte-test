#!/usr/bin/env python3
"""Detect severe credential patterns only in publicly linked browser bundles.

Reads up to two first-party JavaScript files. No credentials are printed,
persisted, used, or tested. No authenticated API calls occur. This is a
heuristic check and cannot prove the absence of secrets.
"""
import base64
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://zedoneexam.site"
HOSTS = {"zedoneexam.site", "www.zedoneexam.site"}
MAX_BYTES = 1048576

class JsAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []
    def handle_starttag(self, tag, attrs):
        if tag == "script":
            s = dict(attrs).get("src")
            if s:
                self.sources.append(s)

class ScopeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        p = urllib.parse.urlsplit(newurl)
        if p.scheme != "https" or p.hostname not in HOSTS:
            raise ValueError("Outside allowlist")
        return super().redirect_request(request, fp, code, msg, headers, newurl)

opener = urllib.request.build_opener(ScopeRedirect)

def read(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or p.hostname not in HOSTS:
        raise ValueError("Outside allowlist")
    req = urllib.request.Request(url, headers={"User-Agent": "ZedOneOwnerCredentialHygiene/1.0"})
    with opener.open(req, timeout=12) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Asset exceeds size cap")
    return data.decode("utf-8", "replace")

def role(jwt_payload):
    try:
        payload = base64.urlsafe_b64decode(jwt_payload + "=" * (-len(jwt_payload) % 4))
        data = json.loads(payload.decode("utf-8"))
        return str(data.get("role", ""))
    except (ValueError, UnicodeError, TypeError):
        return ""

def main():
    try:
        home = read(BASE + "/")
        parser = JsAssets()
        parser.feed(home)
        files = []
        for s in parser.sources:
            url = urllib.parse.urljoin(BASE + "/", s)
            p = urllib.parse.urlsplit(url)
            if p.scheme == "https" and p.hostname in HOSTS and p.path.lower().endswith((".js", ".mjs")):
                if url not in files:
                    files.append(url)
            if len(files) == 2:
                break
        contents = []
        for file in files:
            try:
                contents.append(read(file))
            except (OSError, ValueError, ssl.SSLError, urllib.error.URLError):
                continue
    except (OSError, ValueError, ssl.SSLError, urllib.error.URLError) as exc:
        print("Public bundle audit unavailable:", type(exc).__name__)
        return 1
    print("Public JavaScript assets reviewed:", len(contents))
    if not contents:
        return 1
    elevated_roles = 0
    publishable_keys = 0
    secret_key_candidates = 0
    for content in contents:
        publishable_keys += len(re.findall(r"sb_publishable_[A-Za-z0-9_-]{12,}", content))
        secret_key_candidates += len(re.findall(r"sb_secret_[A-Za-z0-9_-]{12,}", content))
        jwt_candidates = re.findall(r"(eyJ[A-Za-z0-9_-]{10,})\.(eyJ[A-Za-z0-9_-]{10,})\.([A-Za-z0-9_-]{8,})", content)
        for _head, payload, _sig in jwt_candidates[:50]:
            if role(payload) in ("service_role", "supabase_admin"):
                elevated_roles += 1
    print("Supabase publishable-key presence:", publishable_keys > 0)
    print("Sensitive Supabase secret-key pattern detected:", secret_key_candidates > 0)
    print("Elevated-role JWT pattern detected:", elevated_roles > 0)
    if elevated_roles or secret_key_candidates:
        print("URGENT: Inspect the published assets privately and rotate any confirmed exposed privileged key.")
    print("No keys, project IDs, JWT payloads, or asset paths were logged.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
