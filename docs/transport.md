# Transport limits

Both sinks accept `request_policy: clyde.RequestPolicy | None`. `None` selects the sink's finite defaults, applied to message delivery and default-avatar modification:

| Field | Default | Meaning |
| --- | --- | --- |
| `connect_timeout` | `5.0` | Seconds available to establish a connection |
| `read_timeout` | `10.0` | Seconds of read inactivity |
| `max_rate_limit_retries` | `3` | Retries after the initial HTTP 429 response |
| `total_timeout` | `30.0` | Seconds across transport initialization, delivery, and retry waits |

Three retries allow four attempts. Clyde retries only HTTP 429 responses. Other HTTP errors and network failures propagate without retrying, including ambiguous POST failures. Each message or avatar operation gets its own budget.

```python
from clyde import RequestPolicy
from loguru_discord import AsyncDiscordSink, DiscordSink

policy = RequestPolicy(
    connect_timeout=2.0, read_timeout=5.0, max_rate_limit_retries=1, total_timeout=15.0
)
sync_sink = DiscordSink(
    "https://discord.com/api/webhooks/00000000/XXXXXXXX", request_policy=policy
)
async_sink = AsyncDiscordSink(
    "https://discord.com/api/webhooks/00000000/XXXXXXXX", request_policy=policy
)
```

Explicit policies are forwarded unchanged. In a custom `RequestPolicy`, `None` connection/read fields inherit niquests' method defaults, and `None` retry/total fields are unbounded. `RequestPolicy()` therefore opts out of the sink's finite retry and total defaults. Clyde validates policy values at construction.

## Deadlines and preparation

For **synchronous delivery**, Clyde clamps network timeouts to the remaining budget and checks the budget around requests and retry waits. These are network/retry bounds, not a hard wall-clock cancellation guarantee. DNS resolution or an active response that keeps producing data can outlast the budget. Timing out an external thread wait does not cancel an HTTP request already running in that thread. The synchronous sink's avatar file reading and encoding also block the calling thread.

For **async delivery**, Clyde enforces a cancellable total deadline, uses native async HTTP and retry sleeps, and awaits response/session cleanup. External cancellation remains `asyncio.CancelledError`. Cleanup can finish after the deadline.

Clyde's transport budget starts after payload preparation. Message serialization and avatar reading/encoding are outside that budget. The async sink additionally applies the policy's `total_timeout` around startup, covering avatar preparation and modification together. Expiry of this caller-level startup timeout raises Python's `TimeoutError`; Clyde's transport deadline raises `RequestDeadlineExceeded`. Cancelling avatar preparation stops awaiting the worker thread and prevents a subsequent HTTP request, but does not stop work already running in the thread.

## Errors and accounting

- `clyde.RateLimitExceeded` is a `niquests.HTTPError`. It retains the final `.response` and exact `.attempts` count.
- `clyde.RequestDeadlineExceeded` is a `niquests.Timeout`, distinct from connection/read timeouts.
- Other failures retain their niquests exception types. Invalid policies raise `ValueError`.
- External async cancellation propagates as `asyncio.CancelledError` after cleanup.

`DiscordSink` propagates delivery errors to Loguru's configured `catch` handling and propagates avatar errors from its constructor. `AsyncDiscordSink` reports delivery errors through `on_error` or stderr, counts each failed record as terminal, and continues processing. Startup errors propagate to the caller. Shutdown timeout or cancellation accounts for unfinished accepted records as failures and releases drain waiters.

See Clyde's [transport contract](https://clyde.e3n.im/transport/) for its request-policy validation, retry-delay handling, and cleanup semantics.
