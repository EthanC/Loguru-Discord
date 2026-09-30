# How to Contribute

Contributions to this project are gladly accepted, there are a just a few guidelines that need to be followed.

## Reporting Issues

Bugs and feature requests should be directed to the [GitHub Issue Tracker](https://github.com/EthanC/Loguru-Discord/issues).

If reporting a bug, please try and provide as much context as possible such as your operating system, Python version, and anything else that might be relevant to the bug. Security related bugs should also be reported in the Issue Tracker, or if they are more sensitive, Direct Messaged to [@Mxtive on Twitter](https://twitter.com/Mxtive) or `lacking` on Discord.

For feature requests, please explain what you're trying to do and how the requested feature would help you do that.

## Submitting a Contribution

1. It's generally best to start by opening a new Issue describing the bug or feature you're intending to fix. Even if you think it's relatively minor, it's helpful to know what people are working on. Mention in the initial Issue that you are planning to work on that bug or feature so that it can be assigned to you.
2. Follow the normal process of [Forking](https://help.github.com/articles/fork-a-repo) the repository, then setup a new Branch to work in. It's important that each group of changes be done in separate Branches in order to ensure that a Pull Request only includes the commits related to that bug or feature.
3. Use [Ruff](https://docs.astral.sh/ruff/) to format and lint Python code. Run `uv run ruff format .` and `uv run ruff check .` before submitting changes.
4. Any significant changes should almost always be accompanied by tests. The project already has good test coverage, so look at some of the existing tests if you're unsure how to go about it.
5. Do your best to have [well-formed Commit messages](http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html) for each change. This provides consistency throughout the project, and ensures that Commit messages are able to be formatted properly by various git tools.
6. Finally, push the Commits to your Fork and submit a [Pull Request](https://help.github.com/articles/creating-a-pull-request). Please do not use Force-Push on Pull Requests in this repository, as it makes it more difficult for reviewers to see what has changed since the last code review.

## Local Development

Install [uv](https://docs.astral.sh/uv/) and sync the locked development dependencies:

```console
uv sync --locked --dev
```

Run the library checks:

```console
uv run ruff format --check .
uv run ruff check .
uv run python -m pytest
uv build
```

The test suite requires 100% branch coverage. CI also runs it on Python 3.11 through 3.14 with tox.

## Documentation

The site uses [Zensical](https://zensical.org/) and [mkdocstrings-python](https://mkdocstrings.github.io/python/). Edit `docs/index.md` for usage examples and the Google-style docstrings in `loguru_discord/sink.py` and `loguru_discord/intercept.py` for API descriptions. The reference pages select the public classes from those modules. Keep `sink.pyi` aligned with the runtime constructor when changing parameters.

Preview the site locally:

```console
uv run zensical serve
```

Build it from scratch:

```console
uv run zensical build --clean
```

Check all three pages, search, images, navigation, and code blocks at desktop and mobile widths. Confirm that signatures and parameter descriptions agree with the implementation. Generated files in `site/` are ignored by Git.

Pull requests and pushes to `main` build the documentation and upload a Pages artifact. A separate deployment job publishes that artifact on pushes to `main`, using the `github-pages` environment.

### Publishing Setup

Repository administrators configure [Settings > Pages](https://github.com/EthanC/Loguru-Discord/settings/pages) with **GitHub Actions** as the source and `loguru-discord.e3n.im` as the custom domain. The DNS CNAME record must point `loguru-discord.e3n.im` to `ethanc.github.io`. Enable **Enforce HTTPS** after GitHub provisions the certificate, and use `https://loguru-discord.e3n.im/` as the repository website URL.

`docs/CNAME` is included in the site, but Actions-based Pages deployments use the custom domain saved in the repository settings. The file alone does not configure the domain.
