# AsyncDiscordSink

`AsyncDiscordSink` implements Loguru's stream-sink protocol. `write()` admits a formatted record into a bounded buffer; one worker calls Clyde's `execute_async()` in acceptance order. Delivery failures count as terminal records, and the worker continues with subsequent messages.

## Initialization and ownership

The constructor configures and validates the webhook without HTTP or avatar file reads. Start explicitly with `await sink.start()`, or use an async context manager:

```python
from pathlib import Path

from loguru import logger
from loguru_discord import AsyncDiscordSink


async def main():
    async with AsyncDiscordSink(
        "https://discord.com/api/webhooks/00000000/XXXXXXXX",
        avatar=Path("avatar.png"),
        rich=True,
    ) as sink:
        handler_id = logger.add(sink, enqueue=False)
        try:
            logger.info("Application started")
            await logger.complete()
        finally:
            logger.remove(handler_id)
```

Startup uses `modify_async()` for any supplied default avatar. Clyde reads and encodes file and bytes avatars off the event loop. The sink applies the policy's total timeout to startup, including avatar preparation. File, image, HTTP, and timeout errors propagate from `start()`. Failed or cancelled startup closes the sink; create another instance to retry. Concurrent startup calls share one initialization.

The starting event loop owns all lifecycle coroutines: `start()`, `complete()`, and `aclose()`. Calls from another loop raise `RuntimeError`. Logging admission and `stop()` are thread-safe. Start before adding the sink, remove its Loguru handler before leaving its context, and close before the owning event loop exits. A stopped sink rejects new records and cannot restart.

## Admission and overflow

| Option | Default | Meaning |
| --- | --- | --- |
| `max_pending` | `1000` | Accepted but unfinished records, including active delivery |
| `max_buffer_bytes` | `16 * 1024 * 1024` | UTF-8 bytes of pending formatted text and level names |
| `shutdown_timeout` | `30.0` | Seconds available for graceful draining |
| `request_policy` | Finite default policy | Connection/read, rate-limit retry, and delivery limits |

The limits are checked under a short admission lock before scheduling event-loop work, including records logged from other threads. The buffer drops the newest record when either limit is reached. Worker notifications are coalesced: overload cannot create a task or callback for every record. The buffer retains text, level information, and a timestamp, without retaining the original Loguru record, traceback frames, or bound objects.

Both sinks share payload formatting and attachment fallback. Loguru supplies stream sinks with a trailing newline for ordinary formatted records; the async sink preserves that newline. `logger.opt(raw=True)` passes raw text without adding one. Neither path strips user-supplied trailing newlines.

`enqueue=False` is deliberate. Adding Loguru's `enqueue=True` places its pipe-backed queue ahead of the sink's bounded admission and can introduce blocking backpressure and synchronous completion/removal waits.

## Statistics and error reporting

`sink.statistics` returns an immutable snapshot:

- `sent`: deliveries that completed successfully.
- `failed`: failed deliveries and accepted records abandoned during shutdown.
- `dropped`: records rejected by overflow limits.
- `pending`: accepted records without a terminal result, including active delivery.
- `buffered_bytes`: UTF-8 text and level-name bytes for pending records.

Suppressed records are skipped before admission and do not increment these counters. Completion means a record has reached a terminal result; it does not guarantee successful Discord delivery.

Supply `on_error` to observe errors outside the logging pipeline:

```python
import sys

from loguru_discord import AsyncDiscordSink, BufferOverflowError


def report(error: Exception) -> None:
    if isinstance(error, BufferOverflowError):
        sys.stderr.write(f"Discord log buffer dropped {error.dropped} records\n")
    else:
        sys.stderr.write(f"Discord delivery failed: {type(error).__name__}\n")


sink = AsyncDiscordSink(
    "https://discord.com/api/webhooks/00000000/XXXXXXXX", on_error=report
)
```

The synchronous callback runs on the owning loop outside admission locks. Keep it short and non-blocking. Overflow errors aggregate drops since the previous notification. Delivery callbacks receive the original exception, including Clyde's retry-exhaustion and deadline errors. An expired shutdown budget reports `TimeoutError`, then unfinished accepted records become failures. With no callback, errors go directly to stderr. Callback exceptions go to stderr and do not stop the worker. Stderr reporting is best-effort: an absent, closed, or failing stream does not interrupt delivery or completion accounting. Delivery and callback-generated logging are guarded against feedback into this sink and interception.

## Draining and shutdown

`await sink.complete()` captures the accepted-record boundary when its coroutine starts running. It waits for those records to reach success, failure, or abandonment. Later producers do not extend the wait. `await logger.complete()` calls this hook through Loguru. Cancelling a drain waiter leaves delivery running.

`stop()`, including Loguru's call during `logger.remove()`, stops admission and initiates shutdown without waiting. `await sink.aclose()` waits for a graceful drain within `shutdown_timeout`. On timeout, the sink cancels active delivery, counts unfinished accepted records as failed, releases drain waiters, and awaits transport cleanup. Cleanup can finish after the budget expires. Timeout or cancellation prevents any further queued delivery from starting, including when Clyde is already cleaning up an expired request. Repeated and concurrent close calls share shutdown.

Cancellation during `start()` or `aclose()` cancels active async work and propagates `asyncio.CancelledError` after cleanup. Cancellation of avatar preparation prevents a subsequent HTTP request, but cannot interrupt the file-reading/encoding thread already running. [Transport limits](transport.md) describes deadlines and exception types.

The non-blocking guarantee covers this sink's network delivery, retry waits, avatar reads, admission, and lifecycle waits. Other Loguru handlers, user formatting/filter callbacks, and `on_error` callbacks must also suit the application's latency requirements.

## API reference

::: loguru_discord.async_sink
    options:
      members:
        - AsyncDiscordSink
        - DeliveryStatistics
        - BufferOverflowError
