import json
import os
import urllib.request
from datetime import datetime, timezone

TOKEN = os.environ["GH_TOKEN"]
USERNAME = os.environ["GH_USERNAME"]
API_URL = "https://api.github.com/graphql"
REQUEST_TIMEOUT = 30
FALLBACK_COLOR = "#8B98A5"


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", USERNAME)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
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


def merged_prs_by_repo():
    """Merged PRs authored by USERNAME, grouped by public repo owned by someone else.

    Returns {nameWithOwner: {"count": int, "url": str}}.
    """
    search_query = f"author:{USERNAME} is:pr is:merged"
    repos = {}
    after = None
    while True:
        data = gql(MERGED_PRS_QUERY, {"q": search_query, "after": after})["data"]["search"]
        for node in data["nodes"]:
            repo = node["repository"]
            if repo["isPrivate"] or repo["owner"]["login"].lower() == USERNAME.lower():
                continue
            name = repo["nameWithOwner"]
            entry = repos.setdefault(name, {"count": 0, "url": repo["url"]})
            entry["count"] += 1
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]
    return repos


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
        contributions(first: 100) {
          nodes { commitCount }
        }
        repository {
          isPrivate
          owner { login }
          languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
            edges { size node { name color } }
          }
        }
      }
    }
  }
}
"""


def commit_language_weights():
    """Language mix derived from real commit history, weighted by commit count
    per repo and each language's byte share within that repo.

    commitCount lives on the individual CreatedCommitContribution nodes (one per
    day with activity), not directly on CommitContributionsByRepository, so it's
    summed across contributions.nodes rather than read as a single field.

    Returns (weights, colors): {language: weighted_share}, {language: linguist_color}.
    """
    created = gql(CREATED_QUERY, {"login": USERNAME})["data"]["user"]["createdAt"]
    start_year = int(created[:4])
    now = datetime.now(timezone.utc)

    weights = {}
    colors = {}
    for year in range(start_year, now.year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = f"{year + 1}-01-01T00:00:00Z" if year < now.year else now.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = gql(COMMIT_LANGUAGES_QUERY, {"login": USERNAME, "from": frm, "to": to})
        cc = data["data"]["user"]["contributionsCollection"]
        for entry in cc["commitContributionsByRepository"]:
            repo = entry["repository"]
            if repo["isPrivate"] or repo["owner"]["login"].lower() == USERNAME.lower():
                continue
            commit_count = sum(n["commitCount"] for n in entry["contributions"]["nodes"])
            edges = repo["languages"]["edges"]
            total_size = sum(e["size"] for e in edges)
            if total_size == 0:
                continue
            for edge in edges:
                name = edge["node"]["name"]
                share = commit_count * (edge["size"] / total_size)
                weights[name] = weights.get(name, 0) + share
                colors.setdefault(name, edge["node"]["color"] or FALLBACK_COLOR)
    return weights, colors
