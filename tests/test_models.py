from uuid import uuid4

import pytest

from pharox.models import (
    Proxy,
    ProxyCredentials,
    ProxyProtocol,
    ProxyStatus,
)


@pytest.mark.parametrize(
    "host,expected",
    [
        ("203.0.113.10", "http://203.0.113.10:8080"),
        ("2001:db8::1", "http://[2001:db8::1]:8080"),
    ],
)
def test_proxy_url_handles_ipv6(host: str, expected: str) -> None:
    """Ensure Proxy.url produces valid URLs for IPv4 and IPv6 hosts."""
    proxy = Proxy(
        host=host,
        port=8080,
        protocol=ProxyProtocol.HTTP,
        pool_id=uuid4(),
        status=ProxyStatus.ACTIVE,
    )

    assert proxy.url == expected


def test_proxy_url_with_credentials_ipv4() -> None:
    """Ensure IPv4 URLs include URL-encoded credentials without brackets."""
    proxy = Proxy(
        host="203.0.113.5",
        port=3128,
        protocol=ProxyProtocol.HTTP,
        pool_id=uuid4(),
        status=ProxyStatus.ACTIVE,
        credentials=ProxyCredentials(user="user name", password="p@ss word"),
    )

    assert proxy.url == "http://user+name:p%40ss+word@203.0.113.5:3128"


def test_proxy_url_with_credentials_and_ipv6() -> None:
    """Ensure IPv6 URLs include credentials and brackets."""
    proxy = Proxy(
        host="2001:db8::2",
        port=1080,
        protocol=ProxyProtocol.SOCKS5,
        pool_id=uuid4(),
        status=ProxyStatus.ACTIVE,
        credentials=ProxyCredentials(user="user", password="p@ss"),
    )

    assert proxy.url == "socks5://user:p%40ss@[2001:db8::2]:1080"
