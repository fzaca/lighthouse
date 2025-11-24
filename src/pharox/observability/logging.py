from __future__ import annotations

import logging
import random
from typing import Callable, Dict, Optional

from pharox.models import AcquireEventPayload, ReleaseEventPayload


class StructuredLogger:
    """Emit structured logs for acquisition and release callbacks."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
        sample_rate: float = 1.0,
        include_pool_stats: bool = True,
        random_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        if not 0 <= sample_rate <= 1:
            raise ValueError("sample_rate must be between 0 and 1.")
        self._logger = logger or logging.getLogger("pharox")
        self._sample_rate = sample_rate
        self._include_pool_stats = include_pool_stats
        self._random_fn = random_fn or random.random

    def handle_acquire(self, payload: AcquireEventPayload) -> None:
        """Emit an acquisition log if sampling allows."""
        if not self._should_emit():
            return
        self._logger.info(
            "pharox.acquire",
            extra=self._build_acquire_payload(payload),
        )

    def handle_release(self, payload: ReleaseEventPayload) -> None:
        """Emit a release log if sampling allows."""
        if not self._should_emit():
            return
        self._logger.info(
            "pharox.release",
            extra=self._build_release_payload(payload),
        )

    def _build_acquire_payload(
        self, payload: AcquireEventPayload
    ) -> Dict[str, object]:
        lease = payload.lease
        filters = (
            payload.filters.model_dump(
                exclude={"predicate"}, exclude_none=True
            )
            if payload.filters
            else None
        )

        return {
            "event": "pharox.acquire",
            "pool": payload.pool_name,
            "consumer": payload.consumer_name,
            "selector": payload.selector.value,
            "status": "hit" if lease else "miss",
            "duration_ms": payload.duration_ms,
            "lease_id": lease.id if lease else None,
            "proxy_id": lease.proxy_id if lease else None,
            "started_at": payload.started_at.isoformat(),
            "completed_at": payload.completed_at.isoformat(),
            "filters": filters,
            **self._pool_stats_payload(payload.pool_stats),
        }

    def _build_release_payload(
        self, payload: ReleaseEventPayload
    ) -> Dict[str, object]:
        lease = payload.lease
        return {
            "event": "pharox.release",
            "pool": payload.pool_name,
            "lease_id": lease.id,
            "proxy_id": lease.proxy_id,
            "consumer_id": lease.consumer_id,
            "status": "released",
            "released_at": payload.released_at.isoformat(),
            "lease_duration_ms": payload.lease_duration_ms,
            **self._pool_stats_payload(payload.pool_stats),
        }

    def _pool_stats_payload(self, pool_stats) -> Dict[str, object]:
        if not self._include_pool_stats or pool_stats is None:
            return {}
        return {
            "pool_stats": {
                "pool": pool_stats.pool_name,
                "total_proxies": pool_stats.total_proxies,
                "active_proxies": pool_stats.active_proxies,
                "available_proxies": pool_stats.available_proxies,
                "leased_proxies": pool_stats.leased_proxies,
                "total_leases": pool_stats.total_leases,
                "collected_at": pool_stats.collected_at.isoformat(),
            }
        }

    def _should_emit(self) -> bool:
        if self._sample_rate >= 1:
            return True
        return self._random_fn() < self._sample_rate
