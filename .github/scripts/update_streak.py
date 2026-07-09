import json
import os
import urllib.request
import sys
from datetime import datetime, timedelta, timezone

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


CREATED_QUERY = """
query($login: String!) {
  user(login: $login) { createdAt }
}
"""

CALENDAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def fmt(d):
    return d.strftime("%b %-d")


def build_svg(total, total_range, current, current_date, longest, longest_range, palette):
    bg, border, ring, fire, num_color, side_color, label_color, streak_label, date_color = palette
    return f'''<svg width="495" height="150" viewBox="0 0 495 150" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub Streak">
  <rect x="1" y="1" width="493" height="148" rx="14" fill="{bg}" stroke="{border}" stroke-width="1.5"/>
  <line x1="165" y1="30" x2="165" y2="120" stroke="{border}" stroke-opacity="0.4" stroke-width="1"/>
  <line x1="330" y1="30" x2="330" y2="120" stroke="{border}" stroke-opacity="0.4" stroke-width="1"/>

  <g font-family="'JetBrains Mono','Fira Code',monospace" text-anchor="middle">
    <text x="82" y="60" font-size="32" font-weight="700" fill="{side_color}">{total}</text>
    <text x="82" y="85" font-size="12" fill="{label_color}">Total Contributions</text>
    <text x="82" y="103" font-size="11" fill="{date_color}">{total_range}</text>

    <g transform="translate(247.5,55)">
      <circle r="30" fill="none" stroke="{ring}" stroke-width="3"/>
      <path d="M0 -14 C 5 -6 8 -2 4 4 C 6 1 7 -2 5 -6 C 8 -3 9 3 4 8 C 8 6 10 0 8 -4 C 10 0 10 6 4 10 C -4 10 -8 4 -6 -2 C -7 2 -6 4 -4 6 C -8 3 -8 -3 -4 -8 C -6 -5 -6 -2 -5 1 C -8 -3 -7 -9 0 -14 Z" fill="{fire}"/>
      <text y="5" font-size="20" font-weight="700" fill="{num_color}" text-anchor="middle">{current}</text>
    </g>
    <text x="247.5" y="105" font-size="12" font-weight="600" fill="{streak_label}">Current Streak</text>
    <text x="247.5" y="123" font-size="11" fill="{date_color}">{current_date}</text>

    <text x="413" y="60" font-size="32" font-weight="700" fill="{side_color}">{longest}</text>
    <text x="413" y="85" font-size="12" fill="{label_color}">Longest Streak</text>
    <text x="413" y="103" font-size="11" fill="{date_color}">{longest_range}</text>
  </g>
</svg>
'''


def main():
    created = gql(CREATED_QUERY, {"login": USERNAME})["data"]["user"]["createdAt"]
    created_date = datetime.strptime(created[:10], "%Y-%m-%d").date()
    start_year = created_date.year
    now = datetime.now(timezone.utc)
    today = now.date()

    day_map = {}
    total_contributions = 0
    for year in range(start_year, now.year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = f"{year + 1}-01-01T00:00:00Z" if year < now.year else now.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = gql(CALENDAR_QUERY, {"login": USERNAME, "from": frm, "to": to})
        cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        total_contributions += cal["totalContributions"]
        for week in cal["weeks"]:
            for day in week["contributionDays"]:
                day_map[day["date"]] = day["contributionCount"]

    # current streak (grace period: if today has 0 so far, start counting from yesterday)
    cursor = today
    if day_map.get(cursor.isoformat(), 0) == 0:
        cursor = cursor - timedelta(days=1)
    current_streak = 0
    current_end = None
    while day_map.get(cursor.isoformat(), 0) > 0:
        if current_streak == 0:
            current_end = cursor
        current_streak += 1
        cursor -= timedelta(days=1)
    current_start = cursor + timedelta(days=1) if current_streak > 0 else None

    # longest streak (chronological scan)
    longest = 0
    longest_start = longest_end = None
    run = 0
    run_start = None
    for date_str in sorted(day_map):
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if day_map[date_str] > 0:
            if run == 0:
                run_start = date
            run += 1
            if run > longest:
                longest = run
                longest_start = run_start
                longest_end = date
        else:
            run = 0

    total_range = f"{fmt(created_date)} - Present"
    current_date_label = fmt(current_end) if current_streak > 0 else "—"
    longest_range = f"{fmt(longest_start)} - {fmt(longest_end)}" if longest > 0 else "—"

    dark_palette = ("#05070D", "#2E9EF7", "#5EEAD4", "#A78BFA", "#FFFFFF", "#FFFFFF", "#8B98A5", "#5EEAD4", "#5B6577")
    light_palette = ("#F4F7FB", "#0B5FCC", "#0E8F84", "#6D4FD1", "#17223B", "#17223B", "#57606F", "#0E8F84", "#7A8699")

    os.makedirs("assets", exist_ok=True)
    with open("assets/streak.svg", "w") as f:
        f.write(build_svg(total_contributions, total_range, current_streak, current_date_label, longest, longest_range, dark_palette))
    with open("assets/streak-light.svg", "w") as f:
        f.write(build_svg(total_contributions, total_range, current_streak, current_date_label, longest, longest_range, light_palette))

    print(f"total={total_contributions} current={current_streak} longest={longest}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
