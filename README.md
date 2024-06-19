# Loguru-Discord

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/loguru-discord?label=Python) ![PyPI - Status](https://img.shields.io/pypi/status/loguru-discord?label=PyPI%20Status) ![PyPI - Downloads](https://img.shields.io/pypi/dm/loguru-discord?label=PyPI%20Downloads)

Lightweight sink for [Loguru](https://github.com/Delgan/loguru) that sends logs to [Discord](https://discord.com/) via webhook.

<p align="center">
    <img src="https://i.imgur.com/aS7wt4c.png" draggable="false">
</p>

## Usage

Construct a handler with your preferred options, then add a new sink to Loguru.

### Installation

Support is guaranteed only for Python 3.12 or greater.

Once this requirement is met, simply install via your package manager of choice.

```
pip install loguru-discord
```

### Example

The following code is a complete example which demonstrates:

-   Constructing a handler
-   Adding the handler as a Loguru sink
-   Catching an exception and firing a log

```py
from loguru import logger
from loguru_discord import DiscordSink

logger.add(DiscordSink("https://discord.com/api/webhooks/00000000/XXXXXXXX"))

try:
    value: float = 1 / 0
except Exception as e:
    logger.opt(exception=e).error("Lorem ipsum dolor sit amet")
```

## Customization

Upon constructing your handler, the following optional customizations are available via keyword arguments.

-   **Username**: Username to use for the Discord Webhook message.
-   **Avatar**: Image URL to use for the Discord Webhook message.
-   **Embed**: Toggle whether to use plain codeblock formatting or rich embeds.
-   **Truncate**: Toggle whether to trim lengthy logs instead of uploading as a file.
-   **Suppress**: Prevent specific Exception types from being sent to Discord.

## Releases

Loguru-Discord follows [Semantic Versioning](https://semver.org/) for tagging releases of the project.

## Contributing

Bug fixes and optimizations are always welcome. See [`CONTRIBUTING.md`](https://github.com/EthanC/Loguru-Discord/blob/master/.github/CONTRIBUTING.md) for details.
