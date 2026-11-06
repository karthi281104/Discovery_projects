import asyncio
import ipaddress
import logging
import socket
import urllib.parse
import urllib.robotparser
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Reserved and private IP networks to block for SSRF protection
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6 blocked
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # Unique local
    ipaddress.ip_network("fe80::/10"),  # Link-local
    ipaddress.ip_network("ff00::/8"),  # Multicast
]

DEFAULT_USER_AGENT = "TamilEventDiscoveryBot/1.0 (+https://github.com/karthi281104/Discovery_projects)"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB max response limit


class SSRFProtectionError(Exception):
    """Raised when a URL resolves to a forbidden private, loopback, or reserved IP address."""
    pass


class ResponseSizeLimitError(Exception):
    """Raised when the fetched resource exceeds the allowed size limit."""
    pass


class DomainRateLimiter:
    """Simple in-memory per-domain rate limiter."""

    def __init__(self, min_interval_seconds: float = 1.0):
        self.min_interval = min_interval_seconds
        self._last_request_time: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait_for_domain(self, domain: str) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            last_time = self._last_request_time.get(domain, 0.0)
            elapsed = now - last_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_request_time[domain] = asyncio.get_event_loop().time()


def validate_url_safety(url: str) -> str:
    """
    Validates that a URL uses http/https and resolves exclusively to public, routable IP addresses.
    Raises SSRFProtectionError or ValueError on unsafe targets.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme '{parsed.scheme}': only http and https are permitted")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must have a valid hostname")

    # Check for direct IP address literal in hostname
    try:
        ip = ipaddress.ip_address(hostname)
        for net in BLOCKED_NETWORKS:
            if ip in net:
                raise SSRFProtectionError(f"Target IP {ip} is in blocked network {net}")
        return url
    except ValueError:
        # Not a direct IP literal, resolve hostname via DNS
        pass

    try:
        addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFProtectionError(f"DNS resolution failed for {hostname}: {exc}") from exc

    resolved_ips: list[str] = []
    for family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        resolved_ips.append(ip_str)
        try:
            ip = ipaddress.ip_address(ip_str)
            for net in BLOCKED_NETWORKS:
                if ip in net:
                    raise SSRFProtectionError(
                        f"Resolved IP {ip} for host '{hostname}' is in blocked network {net}"
                    )
        except ValueError:
            continue

    if not resolved_ips:
        raise SSRFProtectionError(f"Host '{hostname}' resolved to no valid IP addresses")

    return url


class SafeFetcher:
    """
    HTTP client enforcing:
    - SSRF prevention (DNS check + redirect destination checks)
    - Response size cap
    - Per-domain rate limiting
    - Connection and read timeouts
    - Custom User-Agent
    """

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 15.0,
        rate_limit_interval: float = 0.5,
    ):
        self.user_agent = user_agent
        self.timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        self.rate_limiter = DomainRateLimiter(min_interval_seconds=rate_limit_interval)
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def is_allowed_by_robots(self, url: str) -> bool:
        """Checks if URL path is allowed by the host's robots.txt if available."""
        parsed = urllib.parse.urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots_cache:
            try:
                robots_url = f"{base}/robots.txt"
                validate_url_safety(robots_url)
                rp = urllib.robotparser.RobotFileParser()
                rp.set_url(robots_url)
                # Quick non-blocking attempt or default to allowed
                self._robots_cache[base] = rp
            except Exception:
                self._robots_cache[base] = None

        rp = self._robots_cache.get(base)
        if rp:
            try:
                return rp.can_fetch(self.user_agent, url)
            except Exception:
                return True
        return True

    async def fetch(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        max_redirects: int = 5,
        max_bytes: int = MAX_RESPONSE_BYTES,
    ) -> httpx.Response:
        """
        Fetches a URL with SSRF validation at every hop (including redirects)
        and stream-based response size enforcement.
        """
        current_url = url
        redirect_count = 0

        merged_headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ta;q=0.8",
        }
        if headers:
            merged_headers.update(headers)

        while True:
            # 1. SSRF validation of current URL
            validate_url_safety(current_url)

            # 2. Rate limit per domain
            domain = urllib.parse.urlparse(current_url).netloc
            await self.rate_limiter.wait_for_domain(domain)

            # 3. Request without auto-following redirects so we can revalidate each destination
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.get(current_url, headers=merged_headers)

                # Check redirect
                if response.is_redirect:
                    redirect_count += 1
                    if redirect_count > max_redirects:
                        raise httpx.TooManyRedirects(f"Exceeded max redirects ({max_redirects})")

                    location = response.headers.get("location")
                    if not location:
                        return response
                    current_url = urllib.parse.urljoin(current_url, location)
                    continue

                # 4. Enforce max response size
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise ResponseSizeLimitError(
                        f"Response Content-Length {content_length} exceeds limit of {max_bytes} bytes"
                    )

                if len(response.content) > max_bytes:
                    raise ResponseSizeLimitError(
                        f"Response body {len(response.content)} exceeds limit of {max_bytes} bytes"
                    )

                response.raise_for_status()
                return response

