#!/usr/bin/env python3
"""Replace the legacy Star History embed with the repository-owned SVG."""

from pathlib import Path

README = Path("README.md")
LEGACY = """## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=antoinebou12/uml-mcp&type=Date)](https://star-history.com/#antoinebou12/uml-mcp&Date)
"""
REPLACEMENT = """## Star History

[![GitHub Star History](docs/assets/star-history.svg)](https://github.com/antoinebou12/uml-mcp/stargazers)

_Updated daily by GitHub Actions from GitHub's timestamped stargazer API. The refresh job prefers the optional `STAR_HISTORY_TOKEN` repository secret and safely falls back to the per-run `GITHUB_TOKEN`._
"""


def main() -> None:
    text = README.read_text(encoding="utf-8")
    if REPLACEMENT in text:
        print("README Star History section is already migrated")
        return
    if LEGACY not in text:
        raise SystemExit("Legacy Star History block was not found; refusing a blind README edit")
    README.write_text(text.replace(LEGACY, REPLACEMENT), encoding="utf-8")
    print("Migrated README Star History section")


if __name__ == "__main__":
    main()
