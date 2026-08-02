import os
import re
import sys

from lib import FALLBACK_COLOR, commit_language_weights, merged_prs_by_repo

MAX_REPOS = 10
MAX_LANGUAGES = 6


def render_contrib_table(repos):
    ranked = sorted(repos.items(), key=lambda kv: kv[1]["count"], reverse=True)[:MAX_REPOS]
    if not ranked:
        return "_Building up open-source contributions — check back soon!_"
    rows = ["| Repository | Merged PRs |", "|---|---|"]
    for name, info in ranked:
        rows.append(f"| [**{name}**]({info['url']}) | {info['count']} |")
    return "\n".join(rows)


def update_readme_contrib_list(block):
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
        return True
    return False


def build_language_svg(langs, palette):
    bg, border, track, label_color, pct_color, title_color = palette
    row_h = 40
    top_pad = 52
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


def render_language_cards(weights, colors):
    total = sum(weights.values())
    ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:MAX_LANGUAGES]
    langs = [(name, (w / total) * 100 if total else 0, colors[name]) for name, w in ranked]

    dark_palette = ("#05070D", "#2E9EF7", "#111a2e", "#FFFFFF", "#5EEAD4", "#8B98A5")
    light_palette = ("#F4F7FB", "#0B5FCC", "#dfe7f5", "#17223B", "#0E8F84", "#57606F")

    os.makedirs("assets", exist_ok=True)
    with open("assets/languages.svg", "w") as f:
        f.write(build_language_svg(langs, dark_palette))
    with open("assets/languages-light.svg", "w") as f:
        f.write(build_language_svg(langs, light_palette))

    return langs


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


def build_stats_svg(chips, palette):
    x = 0
    parts = []
    for label in chips:
        chip_svg, width = build_chip(x, label, palette)
        parts.append(chip_svg)
        x += width + 14
    total_width = x - 14
    body = "".join(parts)
    return f'''<svg width="{total_width}" height="40" viewBox="0 0 {total_width} 40" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Profile stats">{body}
</svg>
'''


def render_stats_strip(projects, merged, top_lang):
    labels = [
        f"{projects} OSS PROJECT{'S' if projects != 1 else ''}",
        f"{merged} MERGED PR{'S' if merged != 1 else ''}",
        f"TOP LANG: {top_lang.upper()}",
    ]

    dark_palette = ("#132339", "#2E9EF7", "#5eead4")
    light_palette = ("#ffffff", "#0B5FCC", "#0E8F84")

    os.makedirs("assets", exist_ok=True)
    with open("assets/stats.svg", "w") as f:
        f.write(build_stats_svg(labels, dark_palette))
    with open("assets/stats-light.svg", "w") as f:
        f.write(build_stats_svg(labels, light_palette))


def main():
    repos = merged_prs_by_repo()
    weights, colors = commit_language_weights()
    if not weights:
        weights = {"—": 1}
        colors = {"—": FALLBACK_COLOR}

    contrib_block = render_contrib_table(repos)
    readme_changed = update_readme_contrib_list(contrib_block)

    langs = render_language_cards(weights, colors)
    top_lang = langs[0][0] if langs else "—"

    projects = len(repos)
    merged = sum(info["count"] for info in repos.values())
    render_stats_strip(projects, merged, top_lang)

    print(
        f"projects={projects} merged={merged} top_lang={top_lang} "
        f"readme_changed={readme_changed}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
