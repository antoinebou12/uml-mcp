#!/usr/bin/env python3
"""Generate a static SVG of this repository's cumulative GitHub star history.

The GitHub stargazers API returns ``starred_at`` timestamps when requested with the
star media type.  The script intentionally stores only timestamps in the generated
artifact, never usernames or access tokens.
"""

from __future__ import annotations

import html
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API_VERSION = "2026-03-10"
DEFAULT_REPOSITORY = "antoinebou12/uml-mcp"
OUTPUT = Path("docs/assets/star-history.svg")
WIDTH = 960
HEIGHT = 520
MARGIN_LEFT = 72
MARGIN_RIGHT = 36
MARGIN_TOP = 54
MARGIN_BOTTOM = 74


def _request_json(url: str, token: str) -> tuple[Any, dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github.star+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "uml-mcp-star-history",
        "X-GitHub-Api-Version": API_VERSION,
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return payload, dict(response.headers.items())


def _candidate_tokens() -> list[str]:
    tokens: list[str] = []
    for name in ("STAR_HISTORY_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value and value not in tokens:
            tokens.append(value)
    if not tokens:
        raise RuntimeError(
            "No GitHub token is available. Set STAR_HISTORY_TOKEN or GITHUB_TOKEN."
        )
    return tokens


def fetch_stargazer_dates(repository: str) -> list[datetime]:
    """Return all star timestamps, preferring STAR_HISTORY_TOKEN when configured."""
    owner, repo = repository.split("/", 1)
    last_error: Exception | None = None

    for token in _candidate_tokens():
        try:
            dates: list[datetime] = []
            page = 1
            while True:
                url = (
                    f"https://api.github.com/repos/{owner}/{repo}/stargazers"
                    f"?per_page=100&page={page}"
                )
                payload, _headers = _request_json(url, token)
                if not isinstance(payload, list):
                    raise TypeError("Unexpected GitHub stargazers response shape")

                for item in payload:
                    if not isinstance(item, dict) or not item.get("starred_at"):
                        raise RuntimeError(
                            "GitHub did not return starred_at timestamps; "
                            "the token may not have permission to list stargazers."
                        )
                    dates.append(datetime.fromisoformat(item["starred_at"]))

                if len(payload) < 100:
                    return sorted(dates)
                page += 1
        except HTTPError as exc:
            last_error = exc
            if exc.code not in (401, 403, 404):
                raise
        except Exception as exc:  # noqa: BLE001 - try github.token after an unusable repo secret
            last_error = exc

    raise RuntimeError(
        "Unable to read timestamped stargazers with the configured GitHub tokens"
    ) from last_error


def _nice_max(value: int) -> int:
    if value <= 10:
        return 10
    magnitude = 10 ** (len(str(value)) - 1)
    for multiplier in (1, 2, 5, 10):
        candidate = multiplier * magnitude
        if candidate >= value:
            return candidate
    return value


def _fmt_date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def render_svg(repository: str, dates: list[datetime]) -> str:
    now = datetime.now(UTC)
    if dates:
        start = min(dates[0] - timedelta(days=1), now - timedelta(days=1))
    else:
        start = now - timedelta(days=30)
    end = max(now, dates[-1] if dates else now)
    if end <= start:
        end = start + timedelta(days=1)

    plot_width = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    plot_height = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    duration = max((end - start).total_seconds(), 1.0)
    y_max = _nice_max(max(len(dates), 1))

    def x_for(value: datetime) -> float:
        return MARGIN_LEFT + ((value - start).total_seconds() / duration) * plot_width

    def y_for(count: int) -> float:
        return MARGIN_TOP + plot_height - (count / y_max) * plot_height

    points: list[tuple[float, float]] = [(x_for(start), y_for(0))]
    for index, starred_at in enumerate(dates, start=1):
        points.append((x_for(starred_at), y_for(index)))
    points.append((x_for(end), y_for(len(dates))))
    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)

    grid_lines: list[str] = []
    y_labels: list[str] = []
    for i in range(6):
        count = round(y_max * i / 5)
        y = y_for(count)
        grid_lines.append(
            f'<line class="grid" x1="{MARGIN_LEFT}" y1="{y:.2f}" '
            f'x2="{WIDTH - MARGIN_RIGHT}" y2="{y:.2f}" />'
        )
        y_labels.append(
            f'<text class="axis-label" x="{MARGIN_LEFT - 12}" y="{y + 4:.2f}" '
            f'text-anchor="end">{count}</text>'
        )

    x_labels: list[str] = []
    for i in range(6):
        ratio = i / 5
        value = start + (end - start) * ratio
        x = MARGIN_LEFT + plot_width * ratio
        x_labels.append(
            f'<text class="axis-label" x="{x:.2f}" y="{HEIGHT - 34}" '
            f'text-anchor="middle">{value.strftime("%Y-%m")}</text>'
        )

    escaped_repo = html.escape(repository)
    updated = now.strftime("%Y-%m-%d %H:%M UTC")
    current_count = len(dates)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">Star history for {escaped_repo}</title>
  <desc id="desc">Cumulative GitHub stars over time. Current count: {current_count}.</desc>
  <style>
    :root {{ color-scheme: light dark; }}
    .background {{ fill: #ffffff; }}
    .grid {{ stroke: #d0d7de; stroke-width: 1; }}
    .axis {{ stroke: #57606a; stroke-width: 1.2; }}
    .axis-label {{ fill: #57606a; font: 13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .title {{ fill: #1f2328; font: 600 22px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .subtitle {{ fill: #57606a; font: 14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .line {{ fill: none; stroke: #0969da; stroke-width: 3.5; stroke-linejoin: round; stroke-linecap: round; }}
    .dot {{ fill: #0969da; stroke: #ffffff; stroke-width: 2; }}
    @media (prefers-color-scheme: dark) {{
      .background {{ fill: #0d1117; }}
      .grid {{ stroke: #30363d; }}
      .axis {{ stroke: #8b949e; }}
      .axis-label, .subtitle {{ fill: #8b949e; }}
      .title {{ fill: #f0f6fc; }}
      .line {{ stroke: #58a6ff; }}
      .dot {{ fill: #58a6ff; stroke: #0d1117; }}
    }}
  </style>
  <rect class="background" width="100%" height="100%" rx="8" />
  <text class="title" x="{MARGIN_LEFT}" y="31">GitHub Star History</text>
  <text class="subtitle" x="{WIDTH - MARGIN_RIGHT}" y="31" text-anchor="end">{escaped_repo} · {current_count} stars</text>
  {"".join(grid_lines)}
  <line class="axis" x1="{MARGIN_LEFT}" y1="{MARGIN_TOP}" x2="{MARGIN_LEFT}" y2="{MARGIN_TOP + plot_height}" />
  <line class="axis" x1="{MARGIN_LEFT}" y1="{MARGIN_TOP + plot_height}" x2="{WIDTH - MARGIN_RIGHT}" y2="{MARGIN_TOP + plot_height}" />
  {"".join(y_labels)}
  {"".join(x_labels)}
  <polyline class="line" points="{polyline}" />
  <circle class="dot" cx="{points[-1][0]:.2f}" cy="{points[-1][1]:.2f}" r="5" />
  <text class="subtitle" x="{MARGIN_LEFT}" y="{HEIGHT - 8}">Updated {updated} from GitHub's timestamped stargazer API</text>
</svg>
'''


def main() -> None:
    repository = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY)
    dates = fetch_stargazer_dates(repository)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_svg(repository, dates), encoding="utf-8")
    print(f"Generated {OUTPUT} with {len(dates)} star timestamps")


if __name__ == "__main__":
    main()
