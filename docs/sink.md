# DiscordSink

`DiscordSink` is a standard-library `logging.Handler`. Its constructor updates any supplied default avatar synchronously; each record calls Clyde's `execute()` synchronously. Formatting, thread targeting, exception suppression, and oversized-message attachments are shared with [AsyncDiscordSink](async_sink.md).

## Queuing and failures

Use `logger.add(sink, enqueue=True)` to move delivery to Loguru's background queue worker. Queue writes can block when the pipe is full. `logger.complete()` waits for queued delivery; handler removal waits for the worker to stop. These operations remain synchronous.

Avatar preparation and modification errors propagate from the constructor. Delivery exceptions, including Clyde's `RateLimitExceeded` and `RequestDeadlineExceeded`, reach Loguru's error handling. With the default `catch=True`, Loguru reports the error to stderr; `catch=False` propagates synchronous delivery errors to the caller. Keep `catch=True` for queued delivery so an exception does not terminate Loguru's queue worker.

`request_policy=None` selects five-second connection and ten-second read timeouts, three rate-limit retries, and a 30-second transport budget. The policy is applied to both delivery and avatar modification. Synchronous network timeouts and retry budgets do not provide wall-clock cancellation of DNS resolution or an active response. See [transport limits](transport.md).

## API reference

::: loguru_discord.sink
    options:
      members:
        - DiscordSink
