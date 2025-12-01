# Loguru-Discord

![Python](https://img.shields.io/badge/Python-3-blue?logo=python&logoColor=white)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/ethanc/loguru-discord/workflow.yaml)
![PyPI Downloads](https://img.shields.io/pypi/dm/loguru-discord)
[![Coverage Report](https://codecov.io/gh/ethanc/loguru-discord/branch/main/graph/badge.svg)](https://codecov.io/gh/ethanc/loguru-discord)

Loguru-Discord is a lightweight sink for [Loguru](https://github.com/Delgan/loguru) that forwards logs to [Discord](https://discord.com/) via the Webhook API.

## Features

-   Plug-and-play adoption with your existing logging structure
-   Highly configurable presentation, from usernames and avatars to rich formatting and truncation
-   Fully type-hinted for an excellent developer experience
-   Native and performant Webhook API interaction powered by [Clyde](https://github.com/EthanC/Clyde)

![Preview](/assets/readme_example.png)

## Getting Started

### Installation

> [!IMPORTANT]
> Loguru-Discord requires Python 3.11 or later.

Install with [uv](https://github.com/astral-sh/uv) (recommended):

```
uv add loguru-discord
```

Alternatively, install with pip:

```
pip install loguru-discord
```

### Handler

You can integrate Loguru-Discord in just two lines:

```py
from loguru_discord import DiscordSink

logger.add(DiscordSink("https://discord.com/api/webhooks/00000000/XXXXXXXX"))
```

All configuration is handled on `DiscordSink` via optional keyword arguments.

| **Argument**  | **Description**                                                      | **Default**                    |
|---------------|----------------------------------------------------------------------|--------------------------------|
| `webhook_url` | Discord Webhook URL to forward log events to.                        | N/A (Required)                 |
| `username`    | String to use for the Webhook username.                              | `None` (Determined by Discord) |
| `avatar_url`  | Image URL to use for the Webhook avatar.                             | `None` (Determined by Discord) |
| `rich`        | Toggle whether to use Discord Components.                            | `False`                        |
| `suppress`    | List of Exception types to not forward to Discord.                   | `None`                         |

### Example

Here’s a complete, end-to-end example using Loguru-Discord:

```py
from loguru import logger
from loguru_discord import DiscordSink

# Construct the Discord handler
sink: DiscordSink = DiscordSink("https://discord.com/api/webhooks/00000000/XXXXXXXX")

# Add the sink to Loguru
logger.add(sink)

# Log an exception
try:
    value: float = 1 / 0
except Exception as e:
    logger.opt(exception=e).error("Lorem ipsum dolor sit amet")
```

## Releases

Loguru-Discord loosely follows [Semantic Versioning](https://semver.org/) for consistent, predictable releases.

## Contributing

Contributions are welcome—whether it’s fixing bugs or adding new features.

-   See [`CONTRIBUTING.md`](/.github/CONTRIBUTING.md) for guidelines.
-   See [Issues](https://github.com/EthanC/Loguru-Discord/issues) for known bugs and feature requests.

## Acknowledgments

This project is not affiliated with or endorsed by Loguru or Discord in any way.
