#!/usr/bin/env python3
"""Non-invasive HTTPS baseline for an explicitly allow-listed domain.

Checks DNS, certificate verification and one HTTP HEAD response. No crawling,
authentication attempts, fuzzing, payloads, exploits or privileged operations.
Do not publish detailed findings from production targets in a public repository.
"""
import argparse
import datetime
import json
import socket
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ALLOWED_HOST = "zedoneexam.site"
SECURITY_HEADERS = (
    "strict-transport-security",
    "content-security-policy",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
)

class SameSiteRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in (ALLOWED_HOST, "www." + ALLOWED_HOST):
            raise ValueError("redirect outside authorized HTTPS scope")
        return super().redirect_request(request, fp, code, msg, headers, newurl)

def run(host, timeout):
    if host != ALLOWED_HOST:
        raise ValueError("Host not on explicit authorized allowlist")
    report = {
        "host": host, "dns_ok": False, "tls_verified": False,
        "cert_days_remaining": None, "http_status": None,
        "headers_present": {}, "errors": [],
    }
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        report["dns_ok"] = bool(addresses)
    except (OSError, ValueError) as exc:
        report["errors"].append("dns:" + type(exc).__name__)
        return report

    try:
        with socket.create_connection((host, 443), timeout=timeout) as connection:
            with ssl.create_default_context().wrap_socket(connection, server_hostname=host) as tls:
                report["tls_verified"] = True
                expiry = tls.getpeercert().get("notAfter")
                if expiry:
                    epoch = ssl.cert_time_to_seconds(expiry)
                    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
                    report["cert_days_remaining"] = int((epoch - now) // 86400)
    except (OSError, ssl.SSLError, ValueError) as exc:
        report["errors"].append("tls:" + type(exc).__name__)
        return report

    request = urllib.request.Request("https://" + host + "/", method="HEAD",
                                     headers={"User-Agent": "OwnerSecurityBaseline/1.0"})
    opener = urllib.request.build_opener(SameSiteRedirects())
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc  # An HTTP 4xx/5xx still carries useful response headers.
    except (OSError, ValueError, urllib.error.URLError) as exc:
        report["errors"].append("http:" + type(exc).__name__)
        return report
    with response:
        report["http_status"] = response.status
        report["headers_present"] = {name: bool(response.headers.get(name))
                                     for name in SECURITY_HEADERS}
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=ALLOWED_HOST)
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--output", default="audit-results.json")
    args = parser.parse_args()
    if args.timeout < 1 or args.timeout > 15:
        parser.error("timeout must be between 1 and 15 seconds")
    try:
        report = run(args.host, args.timeout)
    except ValueError as exc:
        parser.error(str(exc))
    with open(args.output, "w", encoding="utf-8") as destination:
        json.dump(report, destination, indent=2)
    # Minimal public-CI output: detailed findings stay on the ephemeral runner.
    total = len(SECURITY_HEADERS)
    found = sum(report["headers_present"].values())
    print(f"DNS reachable: {report['dns_ok']}")
    print(f"TLS certificate verified: {report['tls_verified']}")
    print(f"HTTP response received: {report['http_status'] is not None}")
    print(f"Security-header coverage: {found}/{total}")
    if report["errors"]:
        print("Baseline incomplete; review connectivity and runner configuration.")
    return 0 if report["dns_ok"] and report["tls_verified"] and report["http_status"] is not None else 1

if __name__ == "__main__":
    raise SystemExit(main())
