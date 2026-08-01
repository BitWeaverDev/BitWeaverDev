import json
import os
import re
import sys
import urllib.request

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


MERGED_PRS_QUERY = """
query($q: String!, $after: String) {
  search(query: $q, type: ISSUE, first: 100, after: $after) {
    nodes {
      ... on PullRequest {
        repository { nameWithOwner url isPrivate owner { login } }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def merged_pr_counts_by_repo():
    search_query = f"author:{USERNAME} is:pr is:merged"
    counts = {}
    urls = {}
    after = None
    while True:
        data = gql(MERGED_PRS_QUERY, {"q": search_query, "after": after})["data"]["search"]
        for node in data["nodes"]:
            repo = node["repository"]
            if repo["isPrivate"]:
                continue
            if repo["owner"]["login"].lower() == USERNAME.lower():
                continue
            name = repo["nameWithOwner"]
            counts[name] = counts.get(name, 0) + 1
            urls[name] = repo["url"]
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]
    return counts, urls


def main():
    counts, urls = merged_pr_counts_by_repo()
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:MAX_REPOS]

    if ranked:
        rows = ["| Repository | Merged PRs |", "|---|---|"]
        for name, count in ranked:
            rows.append(f"| [**{name}**]({urls[name]}) | {count} |")
        block = "\n".join(rows)
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
