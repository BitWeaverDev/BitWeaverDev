import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

TOKEN = os.environ["GH_TOKEN"]
USERNAME = os.environ["GH_USERNAME"]
API_URL = "https://api.github.com/graphql"
MAX_REPOS = 10


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

CONTRIB_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      commitContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner url description stargazerCount isFork isPrivate owner { login } }
      }
      pullRequestContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner url description stargazerCount isFork isPrivate owner { login } }
      }
    }
  }
}
"""


def main():
    created = gql(CREATED_QUERY, {"login": USERNAME})["data"]["user"]["createdAt"]
    start_year = int(created[:4])
    now = datetime.now(timezone.utc)

    repos = {}
    for year in range(start_year, now.year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = f"{year + 1}-01-01T00:00:00Z" if year < now.year else now.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = gql(CONTRIB_QUERY, {"login": USERNAME, "from": frm, "to": to})
        cc = data["data"]["user"]["contributionsCollection"]
        for bucket in ("commitContributionsByRepository", "pullRequestContributionsByRepository"):
            for entry in cc[bucket]:
                repo = entry["repository"]
                if repo["isPrivate"]:
                    continue
                if repo["owner"]["login"].lower() == USERNAME.lower():
                    continue
                repos[repo["nameWithOwner"]] = repo

    ranked = sorted(repos.values(), key=lambda r: r["stargazerCount"], reverse=True)[:MAX_REPOS]

    if ranked:
        lines = []
        for r in ranked:
            desc = f" — {r['description']}" if r.get("description") else ""
            lines.append(f"- [{r['nameWithOwner']}]({r['url']}){desc}")
        block = "\n".join(lines)
    else:
        block = "_Building up open-source contributions — check back soon!_"

    with open("README.md", encoding="utf-8") as f:
        readme = f.read()

    new_readme = re.sub(
        r"(<!-- CONTRIB-LIST:START -->)(.*?)(<!-- CONTRIB-LIST:END -->)",
        lambda m: f"{m.group(1)}\n{block}\n{m.group(3)}",
        readme,
        flags=re.DOTALL,
    )

    if new_readme != readme:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(new_readme)
        print(f"Updated with {len(ranked)} repositories.")
    else:
        print("No changes.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
