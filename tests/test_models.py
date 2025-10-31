from uuid import uuid4

import pytest

from lighthouse.models import (
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
