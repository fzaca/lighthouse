"""SQLAlchemy table definitions for the PostgreSQL adapter template."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from pharox.models import LeaseStatus, ProxyProtocol, ProxyStatus

metadata = MetaData()

pool_table = Table(
    "proxy_pool",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", String(128), nullable=False, unique=True),
    Column("description", Text),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

consumer_table = Table(
    "consumer",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", String(128), nullable=False, unique=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

proxy_table = Table(
    "proxy",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column(
        "pool_id",
        UUID(as_uuid=True),
        ForeignKey("proxy_pool.id"),
        nullable=False,
    ),
    Column("host", String(255), nullable=False),
    Column("port", Integer, nullable=False),
    Column(
        "protocol",
        Enum(ProxyProtocol, name="proxy_protocol", native_enum=False),
        nullable=False,
    ),
    Column(
        "status",
        Enum(ProxyStatus, name="proxy_status", native_enum=False),
        nullable=False,
        server_default=text(f"'{ProxyStatus.INACTIVE.value}'"),
    ),
    Column("credentials", JSON),
    Column("source", String(255)),
    Column("country", String(8)),
    Column("city", String(128)),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("isp", String(255)),
    Column("asn", Integer),
    Column("max_concurrency", Integer),
    Column(
        "current_leases",
        Integer,
        nullable=False,
        server_default=text("0"),
    ),
    Column(
        "checked_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

lease_table = Table(
    "lease",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column(
        "proxy_id",
        UUID(as_uuid=True),
        ForeignKey("proxy.id"),
        nullable=False,
    ),
    Column(
        "pool_id",
        UUID(as_uuid=True),
        ForeignKey("proxy_pool.id"),
        nullable=False,
    ),
    Column(
        "consumer_id",
        UUID(as_uuid=True),
        ForeignKey("consumer.id"),
        nullable=False,
    ),
    Column("pool_name", String(128), nullable=False),
    Column(
        "status",
        Enum(LeaseStatus, name="lease_status", native_enum=False),
        nullable=False,
        server_default=text(f"'{LeaseStatus.ACTIVE.value}'"),
    ),
    Column(
        "acquired_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("released_at", DateTime(timezone=True)),
)
