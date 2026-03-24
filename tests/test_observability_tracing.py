"""Tests for TracingRecorder."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock
from uuid import uuid4

from pharox.models import AcquireEventPayload, Lease, ReleaseEventPayload
from pharox.observability.tracing import TracingRecorder


def _make_lease() -> Lease:
    now = datetime.now(timezone.utc)
    return Lease(
        proxy_id=uuid4(),
        consumer_id=uuid4(),
        pool_id=uuid4(),
        pool_name="pool-a",
        acquired_at=now,
        expires_at=now + timedelta(seconds=60),
    )


def _make_acquire_payload(*, hit: bool = True) -> AcquireEventPayload:
    now = datetime.now(timezone.utc)
    lease: Optional[Lease] = _make_lease() if hit else None
    return AcquireEventPayload(
        lease=lease,
        pool_name="pool-a",
        consumer_name="bot",
        started_at=now,
        completed_at=now,
        duration_ms=5,
    )


def _make_release_payload() -> ReleaseEventPayload:
    return ReleaseEventPayload(
        lease=_make_lease(), pool_name="pool-a", lease_duration_ms=100
    )


def test_tracing_recorder_noop_without_tracer() -> None:
    """TracingRecorder is a no-op when no tracer is provided and OTel is absent."""
    recorder = TracingRecorder(tracer=None)
    # Should not raise even without OTel installed
    recorder.handle_acquire(_make_acquire_payload())
    recorder.handle_release(_make_release_payload())


def test_handle_acquire_calls_span() -> None:
    """handle_acquire opens a span and sets expected attributes."""
    mock_span = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_span)
    mock_cm.__exit__ = MagicMock(return_value=False)

    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value = mock_cm

    recorder = TracingRecorder(tracer=mock_tracer)
    payload = _make_acquire_payload(hit=True)
    recorder.handle_acquire(payload)

    mock_tracer.start_as_current_span.assert_called_once_with("pharox.acquire")
    mock_span.set_attribute.assert_any_call("pharox.pool", "pool-a")
    mock_span.set_attribute.assert_any_call("pharox.consumer", "bot")
    mock_span.set_attribute.assert_any_call("pharox.hit", True)
    mock_span.set_attribute.assert_any_call("pharox.duration_ms", 5)


def test_handle_acquire_miss_sets_hit_false() -> None:
    """handle_acquire sets pharox.hit=False when no lease was returned."""
    mock_span = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_span)
    mock_cm.__exit__ = MagicMock(return_value=False)

    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value = mock_cm

    recorder = TracingRecorder(tracer=mock_tracer)
    recorder.handle_acquire(_make_acquire_payload(hit=False))

    mock_span.set_attribute.assert_any_call("pharox.hit", False)


def test_handle_release_calls_span() -> None:
    """handle_release opens a span and sets pool and duration attributes."""
    mock_span = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_span)
    mock_cm.__exit__ = MagicMock(return_value=False)

    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value = mock_cm

    recorder = TracingRecorder(tracer=mock_tracer)
    recorder.handle_release(_make_release_payload())

    mock_tracer.start_as_current_span.assert_called_once_with("pharox.release")
    mock_span.set_attribute.assert_any_call("pharox.pool", "pool-a")
    mock_span.set_attribute.assert_any_call("pharox.lease_duration_ms", 100)
