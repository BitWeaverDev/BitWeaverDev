import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

TOKEN = os.environ["GH_TOKEN"]
USERNAME = os.environ["GH_USERNAME"]
API_URL = "https://api.github.com/graphql"


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


MERGED_PRS_QUERY = """
query($q: String!, $after: String) {
  search(query: $q, type: ISSUE, first: 100, after: $after) {
    nodes {
      ... on PullRequest {
        repository { nameWithOwner isPrivate owner { login } }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

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
          isPrivate
          languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
            edges { size node { name } }
          }
        }
      }
    }
  }
}
"""


def merged_pr_stats():
    search_query = f"author:{USERNAME} is:pr is:merged"
    repos = set()
    total = 0
    after = None
    while True:
        data = gql(MERGED_PRS_QUERY, {"q": search_query, "after": after})["data"]["search"]
        for node in data["nodes"]:
            repo = node["repository"]
            if repo["isPrivate"] or repo["owner"]["login"].lower() == USERNAME.lower():
                continue
            repos.add(repo["nameWithOwner"])
            total += 1
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]
    return len(repos), total


def top_language():
    created = gql(CREATED_QUERY, {"login": USERNAME})["data"]["user"]["createdAt"]
    start_year = int(created[:4])
    now = datetime.now(timezone.utc)

    weights = {}
    for year in range(start_year, now.year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = f"{year + 1}-01-01T00:00:00Z" if year < now.year else now.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = gql(COMMIT_LANGUAGES_QUERY, {"login": USERNAME, "from": frm, "to": to})
        cc = data["data"]["user"]["contributionsCollection"]
        for entry in cc["commitContributionsByRepository"]:
            repo = entry["repository"]
            if repo["isPrivate"]:
                continue
            edges = repo["languages"]["edges"]
            total_size = sum(e["size"] for e in edges)
            if total_size == 0:
                continue
            for edge in edges:
                name = edge["node"]["name"]
                share = entry["commitCount"] * (edge["size"] / total_size)
                weights[name] = weights.get(name, 0) + share

    if not weights:
        return "—"
    return max(weights.items(), key=lambda kv: kv[1])[0]


def build_chip(x, label, palette):
    bg, border, text_color = palette
    char_w = 8.6
    pad = 18
    width = round(pad * 2 + len(label) * char_w)
    svg = f'''
  <g transform="translate({x},0)">
    <rect width="{width}" height="40" rx="20" fill="{bg}" stroke="{border}" stroke-width="1.2"/>
    <text x="{width / 2}" y="26" text-anchor="middle" font-family="'JetBrains Mono','Fira Code',monospace" font-size="13" font-weight="700" fill="{text_color}">{label}</text>
  </g>'''
    return svg, width


def build_svg(chips, palette):
    bg, border, text_color = palette
    x = 0
    parts = []
    for label in chips:
        chip_svg, width = build_chip(x, label, (bg, border, text_color))
        parts.append(chip_svg)
        x += width + 14
    total_width = x - 14
    body = "".join(parts)
    return f'''<svg width="{total_width}" height="40" viewBox="0 0 {total_width} 40" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Profile stats">{body}
</svg>
'''


def main():
    projects, merged = merged_pr_stats()
    lang = top_language().upper()

    labels = [
        f"{projects} OSS PROJECT{'S' if projects != 1 else ''}",
        f"{merged} MERGED PR{'S' if merged != 1 else ''}",
        f"TOP LANG: {lang}",
    ]

    dark_palette = ("#132339", "#2E9EF7", "#5eead4")
    light_palette = ("#ffffff", "#0B5FCC", "#0E8F84")

    os.makedirs("assets", exist_ok=True)
    with open("assets/stats.svg", "w") as f:
        f.write(build_svg(labels, dark_palette))
    with open("assets/stats-light.svg", "w") as f:
        f.write(build_svg(labels, light_palette))

    print(f"projects={projects} merged={merged} top_lang={lang}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
