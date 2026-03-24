---
title: OpenTelemetry Integration
description: Emit traces and spans from Pharox via the OpenTelemetry SDK.
---
# OpenTelemetry Integration

Pharox ships with Prometheus metrics out of the box, but you can layer
OpenTelemetry traces on top by hooking into the acquire/release callbacks.

## Prerequisites

```bash
pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
```

## Basic Setup

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("pharox")
```

## Acquire Callback

Register a callback that opens a span for every proxy acquisition:

```python
from pharox import ProxyManager
from pharox.models import AcquireEventPayload

def otel_acquire_callback(payload: AcquireEventPayload) -> None:
    status = "hit" if payload.lease else "miss"
    with tracer.start_as_current_span("pharox.acquire") as span:
        span.set_attribute("pharox.pool", payload.pool_name)
        span.set_attribute("pharox.consumer", payload.consumer_name or "")
        span.set_attribute("pharox.status", status)
        span.set_attribute("pharox.duration_ms", payload.duration_ms)

manager = ProxyManager(storage=...)
manager.register_acquire_callback(otel_acquire_callback)
```

## Release Callback

```python
from pharox.models import ReleaseEventPayload

def otel_release_callback(payload: ReleaseEventPayload) -> None:
    with tracer.start_as_current_span("pharox.release") as span:
        span.set_attribute("pharox.pool", payload.pool_name)
        span.set_attribute("pharox.lease_duration_ms", payload.lease_duration_ms)

manager.register_release_callback(otel_release_callback)
```

## Propagating an Existing Span Context

If the calling code already holds an active span, the callbacks run inside that
context automatically — the `with tracer.start_as_current_span(...)` call will
create a child span of whatever is current in the calling thread.

For explicit propagation across thread boundaries (e.g. when using
`acquire_proxy_with_retry_async` via `asyncio.to_thread`):

```python
from opentelemetry.context import attach, detach
from opentelemetry.propagate import extract

def otel_acquire_callback(payload: AcquireEventPayload) -> None:
    # carrier is set by your async caller before handing off to the thread
    token = attach(extract(carrier={}))
    try:
        with tracer.start_as_current_span("pharox.acquire"):
            ...
    finally:
        detach(token)
```

## Notes

- Pharox callbacks are **synchronous**. If your OTLP exporter is async-only,
  wrap the export in `asyncio.run_coroutine_threadsafe` or use a synchronous
  exporter.
- For high-throughput workers, prefer the `BatchSpanProcessor` over
  `SimpleSpanProcessor` to avoid blocking the acquire path.
- Combine with `PrometheusMetricsRecorder` — both can be registered as callbacks
  on the same manager instance.
