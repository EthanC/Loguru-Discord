# Loguru-Discord

<p align="center">
  <a href="https://pypi.org/project/loguru-discord/"><img src="https://img.shields.io/pypi/v/loguru-discord" alt="PyPI version"></a>
  <a href="https://pypi.org/project/loguru-discord/"><img src="https://img.shields.io/pypi/pyversions/loguru-discord" alt="Supported Python versions"></a>
  <a href="https://github.com/EthanC/Loguru-Discord/actions/workflows/workflow.yaml"><img src="https://img.shields.io/github/actions/workflow/status/ethanc/loguru-discord/workflow.yaml" alt="Build status"></a>
  <a href="https://codecov.io/gh/ethanc/loguru-discord"><img src="https://codecov.io/gh/ethanc/loguru-discord/branch/main/graph/badge.svg" alt="Coverage report"></a>
  <a href="https://pypi.org/project/loguru-discord/"><img src="https://img.shields.io/pypi/dm/loguru-discord" alt="PyPI downloads"></a>
</p>

Loguru-Discord is a lightweight sink for [Loguru](https://github.com/Delgan/loguru) that forwards logs to [Discord](https://discord.com/) via the Webhook API.

[Documentation](https://loguru-discord.e3n.im/) includes examples and the [DiscordSink](https://loguru-discord.e3n.im/sink/) and [Intercept](https://loguru-discord.e3n.im/intercept/) API references.

## Features

-   Plug-and-play adoption with your existing logging structure
-   Configurable usernames, avatars, rich formatting, and attachments for oversized messages
-   Fully type-hinted for an excellent developer experience
-   Native and performant Webhook API interaction powered by [Clyde](https://github.com/EthanC/Clyde)
-   Opt-in interception of standard library logging events, unified under Loguru

![Preview](https://raw.githubusercontent.com/EthanC/Loguru-Discord/main/assets/readme_example.png)

## Getting Started

### Installation

> [!IMPORTANT]
> Loguru-Discord requires Python 3.11 or later.

Install with [uv](https://github.com/astral-sh/uv) (recommended):

```console
uv add loguru-discord
```

Alternatively, install with pip:

```console
pip install loguru-discord
```

### Handler

Replace the placeholder with your Discord webhook URL:

```py
from loguru import logger
from loguru_discord import DiscordSink

logger.add(DiscordSink("https://discord.com/api/webhooks/00000000/XXXXXXXX"))
logger.info("Application started")
```

All configuration is handled on `DiscordSink` via optional keyword arguments.

| **Argument**          | **Description**                                                      | **Default**                    |
|-----------------------|----------------------------------------------------------------------|--------------------------------|
| `webhook_url`         | Discord Webhook URL to forward log events to.                        | N/A (Required)                 |
| `thread_id`           | Thread within the Webhook's channel to forward log events to.        | `None`                         |
| `username`            | String to use for the Webhook username.                              | `None` (Determined by Discord) |
| `avatar_url`          | Image URL to use for the Webhook avatar.                             | `None` (Determined by Discord) |
| `rich`                | Use Discord Components V2 with a heading, colors, and timestamps.    | `False`                        |
| `critical_color`      | CRITICAL accent color when `rich=True`.                              | `"000000"`                     |
| `error_color`         | ERROR accent color when `rich=True`.                                 | `"D22D39"`                     |
| `warning_color`       | WARNING accent color when `rich=True`.                               | `"CE9C5C"`                     |
| `success_color`       | SUCCESS accent color when `rich=True`.                               | `"43A25A"`                     |
| `info_color`          | INFO accent color when `rich=True`.                                  | `"FFFFFF"`                     |
| `debug_color`         | DEBUG accent color when `rich=True`.                                 | `"5865F2"`                     |
| `trace_color`         | TRACE accent color when `rich=True`.                                 | `None` (No accent color)        |
| `intercept`           | Route standard-library logging through Loguru.                       | `False`                        |
| `intercept_level_map` | Map custom log levels to Loguru log levels.                          | `None`                         |
| `suppress`            | Exception types (including subclasses) whose records are skipped.   | `None`                         |

### Accent colors

Pass hexadecimal strings or integers to override individual log-level colors:

```py
logger.add(
    DiscordSink(
        "https://discord.com/api/webhooks/00000000/XXXXXXXX",
        rich=True,
        error_color="FF0000",
        warning_color=0xFFAA00,
        trace_color="808080",
    )
)
```

Every color argument accepts `None` to disable that level's accent color, for example `info_color=None`. Omitted arguments keep their defaults. TRACE has no accent color by default.

### Threads

Pass `thread_id` to send logs to an existing thread within the Webhook's channel:

```py
logger.add(
    DiscordSink(
        "https://discord.com/api/webhooks/00000000/XXXXXXXX",
        thread_id="123456789012345678",
    )
)
```

A supplied `thread_id` takes precedence over a `thread_id` query parameter in the Webhook URL. When the argument is `None`, any `thread_id` query parameter in the URL is used. See Discord's [Execute Webhook documentation](https://docs.discord.com/developers/resources/webhook#execute-webhook) for thread requirements.

### Long messages

Plain output that exceeds Discord's 2,000-character content limit, including Markdown code-block fences, is sent as a `message.txt` attachment. With `rich=True`, the sink uses the same attachment fallback when the body, level heading, and timestamps exceed the 4,000-character Components V2 text limit, including Markdown formatting.

The attachment contains the complete formatted log record, including any traceback, encoded as UTF-8 without Markdown code-block fences. Oversized rich records use a plain webhook payload without Components V2 flags. Subsequent records that fit the limit retain rich formatting.

### Standard-library logging

Set `intercept=True` on `DiscordSink`, or call `Intercept.setup()` separately, to send standard-library logging records through Loguru. Setup replaces and closes existing root logging handlers and sets the root logging level to `0`. Named loggers retain their own levels and handlers and must propagate to the root logger to reach the interceptor.

See the [logging interception example](https://loguru-discord.e3n.im/#standard-library-logging) for custom level mapping and setup details.

### Example

This example uses rich output, as shown in the preview:

```py
from loguru import logger
from loguru_discord import DiscordSink

# Construct the Discord handler
sink: DiscordSink = DiscordSink(
    "https://discord.com/api/webhooks/00000000/XXXXXXXX", rich=True
)

# Add the sink to Loguru
logger.add(sink)

# Log an exception
try:
    value: float = 1 / 0
except Exception as e:
    logger.opt(exception=e).error("Calculation failed")
```

## Releases

Loguru-Discord loosely follows [Semantic Versioning](https://semver.org/) for consistent, predictable releases.

## Contributing

See the contributor guide to report bugs, propose features, or work on documentation.

-   See [`CONTRIBUTING.md`](https://github.com/EthanC/Loguru-Discord/blob/main/.github/CONTRIBUTING.md) for guidelines.
-   See [Issues](https://github.com/EthanC/Loguru-Discord/issues) for known bugs and feature requests.

## Acknowledgments

This project is not affiliated with or endorsed by Loguru or Discord in any way.
