#!/usr/bin/env python3
"""One-shot, low-impact TCP reachability probe of the owner-authorized domain.

Checks ten explicitly listed common ports, once each, no service banners,
no login, no exploitation, no retries, no subdomain or IP discovery.
Network middleboxes/CDNs can make results unrepresentative of origin VPS.
"""
import socket
import sys

TARGET = "zedoneexam.site"
PORTS = (22, 80, 443, 8080, 8443, 3306, 5432, 6379, 27017, 9200)

def main():
    reachable = []
    for port in PORTS:
        try:
            with socket.create_connection((TARGET, port), timeout=1.5):
                reachable.append(port)
        except OSError:
            pass
    print("TCP ports checked:", len(PORTS))
    print("TCP connect successes:", len(reachable))
    print("Public web TCP 80 reachable:", 80 in reachable)
    print("Public web TCP 443 reachable:", 443 in reachable)
    print("Non-web service ports reachable:", len([p for p in reachable if p not in (80, 443)]))
    print("Caution: results may reflect a reverse proxy/CDN, not the origin VPS.")
    return 0 if 443 in reachable else 1

if __name__ == "__main__":
    sys.exit(main())
