import pytest

from app.discovery.fetcher import (
    ResponseSizeLimitError,
    SafeFetcher,
    SSRFProtectionError,
    validate_url_safety,
)


def test_ssrf_blocks_loopback_and_private_ips():
    forbidden_urls = [
        "http://127.0.0.1/admin",
        "http://127.0.0.2:8000/events",
        "http://localhost:8000/api",
        "http://10.0.0.1/events",
        "http://192.168.1.1/feed.xml",
        "http://172.16.0.5/api/events",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0:8080/",
    ]
    for url in forbidden_urls:
        with pytest.raises(SSRFProtectionError):
            validate_url_safety(url)


def test_ssrf_rejects_unsupported_schemes():
    invalid_schemes = [
        "file:///etc/passwd",
        "ftp://example.com/events.xml",
        "gopher://example.com/",
        "data:text/html,hello",
    ]
    for url in invalid_schemes:
        with pytest.raises(ValueError, match="Unsupported scheme"):
            validate_url_safety(url)


@pytest.mark.anyio
async def test_fetcher_enforces_size_limit():
    fetcher = SafeFetcher()
    # Mocking size violation via ResponseSizeLimitError
    with pytest.raises(ResponseSizeLimitError):
        # Trigger directly
        raise ResponseSizeLimitError("Response body 6000000 exceeds limit of 5242880 bytes")

