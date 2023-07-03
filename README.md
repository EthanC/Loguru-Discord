# Loguru-Discord

Lightweight, easy-to-use [Discord](https://discord.com/) sink for [Loguru](https://github.com/Delgan/loguru).

<p align="center">
    <img src="https://i.imgur.com/aS7wt4c.png" draggable="false">
</p>

## Usage

Construct a handler with your preferred options, then add a new sink to Loguru.

### Installation

Support is guaranteed only for Python 3.11 or greater.

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

logger.add(
    DiscordSink(
        "https://discord.com/api/webhooks/00000000/XXXXXXXX",
        embed=True
    ),
    level="WARNING",
)

try:
    value: float = 1 / 0
except Exception as ex:
    logger.error("Lorem ipsum dolor sit amet.", e=ex)
```

## Customization

Upon constructing your handler, the following optional customizations are available via keyword arguments.

-   **Username**: Username to use for the Discord Webhook message.
-   **Avatar**: Image URL to use for the Discord Webhook message.
-   **Embed**: Toggle whether to use plain codeblock formatting or rich embeds.
-   **Trace**: Toggle whether or not to include tracebacks (where available).

## Releases

Loguru-Discord follows [Semantic Versioning](https://semver.org/) for tagging releases of the project.

Changelogs can be found on the [Releases](https://github.com/EthanC/Loguru-Discord/releases) page in the [Keep a Changelog](https://keepachangelog.com/) format.

## Contributing

Bug fixes and optimizations are always welcome. See [`CONTRIBUTING.md`](https://github.com/EthanC/CallofDuty.py/blob/master/.github/CONTRIBUTING.md) for details.
