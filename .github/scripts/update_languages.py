import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

TOKEN = os.environ["GH_TOKEN"]
USERNAME = os.environ["GH_USERNAME"]
API_URL = "https://api.github.com/graphql"
MAX_LANGUAGES = 6

# GitHub's linguist colors, used as a fallback when a repository doesn't
# report a color for one of its languages.
FALLBACK_COLOR = "#8B98A5"


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", USERNAME)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    return data


CREATED_QUERY = """
query($login: String!) {
  user(login: $login) { createdAt }
}
"""

COMMIT_LANGUAGES_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      commitContributionsByRepository(maxRepositories: 100) {
        commitCount
        repository {
          nameWithOwner
          isPrivate
          languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
            edges {
              size
              node { name color }
            }
          }
        }
      }
    }
  }
}
"""


def collect_language_weights():
    created = gql(CREATED_QUERY, {"login": USERNAME})["data"]["user"]["createdAt"]
    start_year = int(created[:4])
    now = datetime.now(timezone.utc)

    weights = {}
    colors = {}
    seen_repos = set()

    for year in range(start_year, now.year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = f"{year + 1}-01-01T00:00:00Z" if year < now.year else now.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = gql(COMMIT_LANGUAGES_QUERY, {"login": USERNAME, "from": frm, "to": to})
        cc = data["data"]["user"]["contributionsCollection"]
        for entry in cc["commitContributionsByRepository"]:
            repo = entry["repository"]
            if repo["isPrivate"]:
                continue
            seen_repos.add(repo["nameWithOwner"])
            edges = repo["languages"]["edges"]
            total_size = sum(e["size"] for e in edges)
            if total_size == 0:
                continue
            commit_weight = entry["commitCount"]
            for edge in edges:
                name = edge["node"]["name"]
                share = commit_weight * (edge["size"] / total_size)
                weights[name] = weights.get(name, 0) + share
                colors.setdefault(name, edge["node"]["color"] or FALLBACK_COLOR)

    return weights, colors


def build_svg(langs, palette):
    bg, border, track, label_color, pct_color, title_color = palette
    row_h = 40
    top_pad = 34
    bottom_pad = 18
    height = top_pad + len(langs) * row_h + bottom_pad
    bar_x = 24
    bar_w = 447

    rows = []
    for i, (name, pct, color) in enumerate(langs):
        y = top_pad + i * row_h
        filled = round(bar_w * pct / 100, 1)
        rows.append(f'''
    <circle cx="{bar_x + 5}" cy="{y - 6}" r="5" fill="{color}"/>
    <text x="{bar_x + 18}" y="{y - 2}" font-size="13" font-weight="600" fill="{label_color}">{name}</text>
    <text x="{bar_x + bar_w}" y="{y - 2}" font-size="12" font-weight="600" fill="{pct_color}" text-anchor="end">{pct:.1f}%</text>
    <rect x="{bar_x}" y="{y + 4}" width="{bar_w}" height="7" rx="3.5" fill="{track}"/>
    <rect x="{bar_x}" y="{y + 4}" width="{filled}" height="7" rx="3.5" fill="{color}"/>''')

    return f'''<svg width="495" height="{height}" viewBox="0 0 495 {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Languages used across commits">
  <rect x="1" y="1" width="493" height="{height - 2}" rx="14" fill="{bg}" stroke="{border}" stroke-width="1.5"/>
  <g font-family="'JetBrains Mono','Fira Code',monospace">
    <text x="24" y="24" font-size="12" font-weight="700" letter-spacing="1" fill="{title_color}">LANGUAGES · BY COMMIT ACTIVITY</text>{"".join(rows)}
  </g>
</svg>
'''


def render(weights, colors):
    total = sum(weights.values())
    ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:MAX_LANGUAGES]
    langs = [(name, (w / total) * 100 if total else 0, colors[name]) for name, w in ranked]

    dark_palette = ("#05070D", "#2E9EF7", "#111a2e", "#FFFFFF", "#5EEAD4", "#8B98A5")
    light_palette = ("#F4F7FB", "#0B5FCC", "#dfe7f5", "#17223B", "#0E8F84", "#57606F")

    os.makedirs("assets", exist_ok=True)
    with open("assets/languages.svg", "w") as f:
        f.write(build_svg(langs, dark_palette))
    with open("assets/languages-light.svg", "w") as f:
        f.write(build_svg(langs, light_palette))

    return langs


def main():
    weights, colors = collect_language_weights()
    if not weights:
        weights = {"—": 1}
        colors = {"—": FALLBACK_COLOR}
    langs = render(weights, colors)
    print("Updated language breakdown: " + ", ".join(f"{n} {p:.1f}%" for n, p, _ in langs))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
