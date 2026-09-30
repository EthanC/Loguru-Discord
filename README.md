<h1 align="center">Loguru-Discord</h1>

<p align="center">
  <a href="https://pypi.org/project/loguru-discord/"><img src="https://img.shields.io/pypi/v/loguru-discord" alt="PyPI version"></a>
  <a href="https://pypi.org/project/loguru-discord/"><img src="https://img.shields.io/pypi/pyversions/loguru-discord" alt="Supported Python versions"></a>
  <a href="https://github.com/EthanC/Loguru-Discord/actions/workflows/workflow.yaml"><img src="https://img.shields.io/github/actions/workflow/status/ethanc/loguru-discord/workflow.yaml" alt="Build status"></a>
  <a href="https://codecov.io/gh/ethanc/loguru-discord"><img src="https://codecov.io/gh/ethanc/loguru-discord/branch/main/graph/badge.svg" alt="Coverage report"></a>
  <a href="https://pypi.org/project/loguru-discord/"><img src="https://img.shields.io/pypi/dm/loguru-discord" alt="PyPI downloads"></a>
</p>

<p align="center"><strong>Forward Loguru logs to Discord webhooks.</strong></p>

Loguru-Discord is a lightweight sink for [Loguru](https://github.com/Delgan/loguru) that forwards logs to [Discord](https://discord.com/) via the Webhook API.

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

```bash
uv add loguru-discord
```

Alternatively, install with pip:

```bash
pip install loguru-discord
```

### Quick Start

Replace the placeholder with your Discord webhook URL:

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

## Documentation

See the [documentation](https://loguru-discord.e3n.im/) for more examples and configuration options.

## Releases

Loguru-Discord loosely follows [Semantic Versioning](https://semver.org/) for consistent, predictable releases.

## Contributing

See the contributor guide to report bugs, propose features, or work on documentation.

-   See [`CONTRIBUTING.md`](https://github.com/EthanC/Loguru-Discord/blob/main/.github/CONTRIBUTING.md) for guidelines.
-   See [Issues](https://github.com/EthanC/Loguru-Discord/issues) for known bugs and feature requests.

## Acknowledgments

This project is not affiliated with or endorsed by Loguru or Discord in any way.
