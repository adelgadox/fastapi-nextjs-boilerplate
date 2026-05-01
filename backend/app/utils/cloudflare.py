"""
Cloudflare integration utilities.

- get_client_ip: reads the real visitor IP from CF-Connecting-IP (set by
  Cloudflare on every proxied request), falling back to X-Forwarded-For and
  then request.client.host for local/non-proxied environments.

- is_cloudflare_ip: validates that a connecting IP belongs to Cloudflare's
  published ranges (https://www.cloudflare.com/ips/). Used by
  CloudflareOnlyMiddleware when CLOUDFLARE_ONLY=true.
"""

import ipaddress
from fastapi import Request

# Cloudflare published IP ranges — last updated 2026-04
# Source: https://www.cloudflare.com/ips-v4 + https://www.cloudflare.com/ips-v6
_CF_RANGES: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    # IPv4
    ipaddress.ip_network("103.21.244.0/22"),
    ipaddress.ip_network("103.22.200.0/22"),
    ipaddress.ip_network("103.31.4.0/22"),
    ipaddress.ip_network("104.16.0.0/13"),
    ipaddress.ip_network("104.24.0.0/14"),
    ipaddress.ip_network("108.162.192.0/18"),
    ipaddress.ip_network("131.0.72.0/22"),
    ipaddress.ip_network("141.101.64.0/18"),
    ipaddress.ip_network("162.158.0.0/15"),
    ipaddress.ip_network("172.64.0.0/13"),
    ipaddress.ip_network("173.245.48.0/20"),
    ipaddress.ip_network("188.114.96.0/20"),
    ipaddress.ip_network("190.93.240.0/20"),
    ipaddress.ip_network("197.234.240.0/22"),
    ipaddress.ip_network("198.41.128.0/17"),
    # IPv6
    ipaddress.ip_network("2400:cb00::/32"),
    ipaddress.ip_network("2606:4700::/32"),
    ipaddress.ip_network("2803:f800::/32"),
    ipaddress.ip_network("2405:b500::/32"),
    ipaddress.ip_network("2405:8100::/32"),
    ipaddress.ip_network("2a06:98c0::/29"),
    ipaddress.ip_network("2c0f:f248::/32"),
]


def get_client_ip(request: Request) -> str:
    """Return the real visitor IP address.

    Priority:
    1. CF-Connecting-IP  — set by Cloudflare, cannot be spoofed when proxied
    2. X-Forwarded-For   — first entry (original client), set by most proxies
    3. request.client.host — direct connection (local dev / non-proxied)
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "unknown"


def is_cloudflare_ip(ip: str) -> bool:
    """Return True if *ip* belongs to a known Cloudflare IP range."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in network for network in _CF_RANGES)
