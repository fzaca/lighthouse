from __future__ import annotations

from typing import Any, Optional

from pharox.models import AcquireEventPayload, ReleaseEventPayload

try:  # pragma: no cover - optional dependency
    from opentelemetry import trace as _otel_trace

    _HAS_OTEL = True
except ImportError:  # pragma: no cover
    _HAS_OTEL = False


class TracingRecorder:
    """
    Acquire/release callbacks that emit OpenTelemetry spans.

    Requires ``opentelemetry-api`` to be installed. When the library is not
    present the callbacks become no-ops, so you can register them
    unconditionally and enable tracing just by installing the extra.

    Parameters
    ----------
    tracer_name:
        Instrumentation scope name passed to ``get_tracer``.
    tracer:
        Supply an explicit tracer instance instead of the global one.
        Useful in tests or when you manage the ``TracerProvider`` manually.

    Examples
    --------
    >>> from pharox import ProxyManager
    >>> from pharox.observability import TracingRecorder
    >>> recorder = TracingRecorder()
    >>> manager = ProxyManager(storage=...)
    >>> manager.register_acquire_callback(recorder.handle_acquire)
    >>> manager.register_release_callback(recorder.handle_release)
    """

    def __init__(
        self,
        tracer_name: str = "pharox",
        tracer: Optional[Any] = None,
    ) -> None:
        if tracer is not None:
            self._tracer: Optional[Any] = tracer
        elif _HAS_OTEL:
            self._tracer = _otel_trace.get_tracer(tracer_name)
        else:
            self._tracer = None

    def handle_acquire(self, payload: AcquireEventPayload) -> None:
        """Emit a ``pharox.acquire`` span for an acquisition attempt."""
        if self._tracer is None:
            return
        with self._tracer.start_as_current_span("pharox.acquire") as span:
            span.set_attribute("pharox.pool", payload.pool_name)
            span.set_attribute("pharox.consumer", payload.consumer_name)
            span.set_attribute("pharox.hit", payload.lease is not None)
            span.set_attribute("pharox.duration_ms", payload.duration_ms)

    def handle_release(self, payload: ReleaseEventPayload) -> None:
        """Emit a ``pharox.release`` span for a lease release."""
        if self._tracer is None:
            return
        with self._tracer.start_as_current_span("pharox.release") as span:
            span.set_attribute("pharox.pool", payload.pool_name or "")
            if payload.lease_duration_ms is not None:
                span.set_attribute(
                    "pharox.lease_duration_ms", payload.lease_duration_ms
                )
