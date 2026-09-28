"""Draws the GitHub stats card in the profile README (assets/stats-dark.svg and assets/stats-light.svg).

Self-hosted so the README never shows a broken image when a shared stats service is down.
Runs daily from .github/workflows/stats.yml; locally: GITHUB_TOKEN=$(gh auth token) python3 .github/scripts/stats.py
"""

import json
import os
import urllib.request
from html import escape
from pathlib import Path

USER = "TRUPALIX9"
OUT = Path(__file__).resolve().parents[2] / "assets"

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      totalCount
      nodes { languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } }
    }
    contributionsCollection {
      contributionCalendar { totalContributions }
      totalCommitContributions
      totalPullRequestContributions
      restrictedContributionsCount
    }
  }
}
"""

THEMES = {
    "dark": {"bg": "#0D1117", "border": "#30363D", "text": "#E6EDF3", "muted": "#8B949E", "accent": "#4ADE80", "track": "#21262D"},
    "light": {"bg": "#FFFFFF", "border": "#D0D7DE", "text": "#1F2328", "muted": "#59636E", "accent": "#16A34A", "track": "#EAEEF2"},
}

FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"


def fetch():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN (or GH_TOKEN).")
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.load(res)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]["user"]


def top_languages(user, n=6):
    sizes, colors = {}, {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8B949E"
    total = sum(sizes.values()) or 1
    ranked = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [(name, size / total, colors[name]) for name, size in ranked]


def card(user, t):
    cc = user["contributionsCollection"]
    stats = [
        ("Commits", cc["totalCommitContributions"]),
        ("Pull requests", cc["totalPullRequestContributions"]),
        ("Private contributions", cc["restrictedContributionsCount"]),
        ("Public repos", user["repositories"]["totalCount"]),
    ]
    stats = [(label, value) for label, value in stats if value > 0]
    langs = top_languages(user)
    total = cc["contributionCalendar"]["totalContributions"]

    w, h = 840, 270
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title">',
        f'<title id="title">{USER} on GitHub: {total:,} contributions in the last year</title>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>',
        f'<g font-family="{FONT}">',
        # Headline number.
        f'<text x="32" y="78" font-size="52" font-weight="700" fill="{t["accent"]}">{total:,}</text>',
        f'<text x="32" y="106" font-size="17" fill="{t["muted"]}">contributions in the last year</text>',
    ]
    # Stats in a 2×2 grid under the headline, left half only.
    for i, (label, value) in enumerate(stats):
        x = 32 + (i % 2) * 200
        y = 160 + (i // 2) * 62
        out.append(f'<text x="{x}" y="{y}" font-size="28" font-weight="700" fill="{t["text"]}">{value:,}</text>')
        out.append(f'<text x="{x}" y="{y + 22}" font-size="14" fill="{t["muted"]}">{escape(label)}</text>')
    out.append(f'<line x1="440" y1="28" x2="440" y2="{h - 28}" stroke="{t["border"]}"/>')

    # Top languages: a stacked bar and a legend, on the right.
    lx, lw = 470, 338
    out.append(f'<text x="{lx}" y="46" font-size="15" font-weight="600" fill="{t["text"]}">Top languages · public repos</text>')
    out.append(f'<rect x="{lx}" y="60" width="{lw}" height="10" rx="5" fill="{t["track"]}"/>')
    out.append(f'<clipPath id="bar"><rect x="{lx}" y="60" width="{lw}" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">')
    x = lx
    for name, share, color in langs:
        seg = lw * share
        out.append(f'<rect x="{x:.1f}" y="60" width="{seg + 0.5:.1f}" height="10" fill="{color}"/>')
        x += seg
    out.append("</g>")
    for i, (name, share, color) in enumerate(langs):
        cx = lx + (i % 2) * 175
        cy = 100 + (i // 2) * 30
        out.append(f'<circle cx="{cx + 6}" cy="{cy - 5}" r="6" fill="{color}"/>')
        out.append(f'<text x="{cx + 20}" y="{cy}" font-size="15" fill="{t["text"]}">{escape(name)} <tspan fill="{t["muted"]}">{share * 100:.1f}%</tspan></text>')

    out.append(f'<text x="{lx}" y="{h - 26}" font-size="12" fill="{t["muted"]}">Updated daily from the GitHub API</text>')
    out.append("</g></svg>")
    return "\n".join(out)


def main():
    user = fetch()
    OUT.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        (OUT / f"stats-{name}.svg").write_text(card(user, theme) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
