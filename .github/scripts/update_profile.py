import math
import os
import sys

from lib import FALLBACK_COLOR, commit_language_weights, merged_prs_by_repo

MAX_REPOS = 10
MAX_LANGUAGES = 6


def corner_brackets(width, height, color, opacity=0.9, inset=18, arm=18, stroke_width=2.2):
    """The sci-fi corner-frame accent used on the banner, reused across cards
    so the page reads as one system instead of banner-plus-plain-boxes."""
    x0, y0 = inset, inset
    x1, y1 = width - inset, height - inset
    return f'''<g stroke="{color}" stroke-opacity="{opacity}" stroke-width="{stroke_width}" fill="none">
    <path d="M{x0},{y0 + arm} L{x0},{y0} L{x0 + arm},{y0}"/>
    <path d="M{x1 - arm},{y0} L{x1},{y0} L{x1},{y0 + arm}"/>
    <path d="M{x0},{y1 - arm} L{x0},{y1} L{x0 + arm},{y1}"/>
    <path d="M{x1 - arm},{y1} L{x1},{y1} L{x1},{y1 - arm}"/>
  </g>'''


def glow_filter_defs(filter_id="glow", std_deviation=3):
    return f'''<filter id="{filter_id}" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="{std_deviation}" result="blur"/>
    <feMerge>
      <feMergeNode in="blur"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>'''


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
        # Only the leading language gets the glow treatment - a full row of
        # glowing bars would just be noise, one hero bar reads as emphasis.
        glow = ' filter="url(#glow)"' if i == 0 else ""
        rows.append(f'''
    <circle cx="{bar_x + 5}" cy="{y - 6}" r="5" fill="{color}"/>
    <text x="{bar_x + 18}" y="{y - 2}" font-size="13" font-weight="600" fill="{label_color}">{name}</text>
    <text x="{bar_x + bar_w}" y="{y - 2}" font-size="12" font-weight="600" fill="{pct_color}" text-anchor="end">{pct:.1f}%</text>
    <rect x="{bar_x}" y="{y + 4}" width="{bar_w}" height="7" rx="3.5" fill="{track}"/>
    <rect x="{bar_x}" y="{y + 4}" width="{filled}" height="7" rx="3.5" fill="{color}"{glow}/>''')

    return f'''<svg width="495" height="{height}" viewBox="0 0 495 {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Languages used across commits">
  <defs>{glow_filter_defs()}</defs>
  <rect x="1" y="1" width="493" height="{height - 2}" rx="14" fill="{bg}" stroke="{border}" stroke-width="1.5"/>
  {corner_brackets(495, height, border, opacity=0.5, inset=10, arm=12)}
  <g font-family="'JetBrains Mono','Fira Code',monospace">
    <text x="24" y="24" font-size="12" font-weight="700" letter-spacing="1" fill="{title_color}">LANGUAGES · BY COMMIT ACTIVITY</text>{"".join(rows)}
  </g>
</svg>
'''


MIN_LANGUAGE_PCT = 1.0


def render_language_cards(weights, colors):
    total = sum(weights.values())
    ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)

    langs = []
    for name, w in ranked:
        pct = (w / total) * 100 if total else 0
        # Drop incidental languages (a stray Dockerfile/Makefile in an
        # otherwise Rust repo, etc.) once at least one real entry is in,
        # so the card doesn't pad itself out with noise near 0%.
        if langs and pct < MIN_LANGUAGE_PCT:
            break
        langs.append((name, pct, colors[name]))
        if len(langs) >= MAX_LANGUAGES:
            break

    dark_palette = ("#05070D", "#2E9EF7", "#111a2e", "#FFFFFF", "#5EEAD4", "#8B98A5")
    light_palette = ("#F4F7FB", "#0B5FCC", "#dfe7f5", "#17223B", "#0E8F84", "#57606F")

    os.makedirs("assets", exist_ok=True)
    with open("assets/languages.svg", "w") as f:
        f.write(build_language_svg(langs, dark_palette))
    with open("assets/languages-light.svg", "w") as f:
        f.write(build_language_svg(langs, light_palette))

    return langs


def build_chip(x, label, palette, delay):
    bg, border, text_color = palette
    char_w = 8.6
    pad = 18
    width = round(pad * 2 + len(label) * char_w)
    svg = f'''
  <g transform="translate({x},0)">
    <rect width="{width}" height="40" rx="20" fill="{bg}" stroke="{border}" stroke-width="1.2">
      <animate attributeName="stroke-opacity" values="1;0.4;1" dur="3s" begin="{delay}s" repeatCount="indefinite"/>
    </rect>
    <text x="{width / 2}" y="26" text-anchor="middle" font-family="'JetBrains Mono','Fira Code',monospace" font-size="13" font-weight="700" fill="{text_color}">{label}</text>
  </g>'''
    return svg, width


def build_stats_svg(chips, palette):
    x = 0
    parts = []
    for i, label in enumerate(chips):
        chip_svg, width = build_chip(x, label, palette, delay=i * 0.4)
        parts.append(chip_svg)
        x += width + 14
    total_width = x - 14
    body = "".join(parts)
    return f'''<svg width="{total_width}" height="40" viewBox="0 0 {total_width} 40" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Profile stats">{body}
</svg>
'''


def build_orbit_svg(ranked, palette):
    bg, border, line_color, node_fill, center_color, label_color, count_color = palette
    width, height = 700, 520
    cx, cy = width / 2, height / 2 + 14
    radius = 190
    n = len(ranked)
    max_count = max((info["count"] for _, info in ranked), default=1)

    lines = []
    nodes = []
    for i, (name, info) in enumerate(ranked):
        angle = -math.pi / 2 + (2 * math.pi * i / n) if n else 0
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        node_r = 7 + (info["count"] / max_count) * 9
        clearance = node_r + 9  # keep the label clear of the node's own circle

        if x > cx + 4:
            anchor, dx = "start", clearance
        elif x < cx - 4:
            anchor, dx = "end", -clearance
        else:
            anchor, dx = "middle", 0

        # Stack the two label lines outward from the node, not just downward -
        # a node sitting above center needs its count line further up, not
        # dropped back down into the node it's meant to clear.
        if y < cy - 4:
            name_y, count_y = y - clearance - 14, y - clearance
        elif y > cy + 4:
            name_y, count_y = y + clearance + 12, y + clearance + 27
        else:
            name_y, count_y = y + 4, y + 19

        short_name = name.split("/")[-1]
        count_label = f"{info['count']} PR{'s' if info['count'] != 1 else ''}"

        lines.append(
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="{line_color}" stroke-width="1.2" stroke-dasharray="3 4" opacity="0.6">'
            f'<animate attributeName="stroke-dashoffset" values="0;-14" dur="{1.6 + i * 0.15:.1f}s" repeatCount="indefinite"/>'
            f"</line>"
        )
        nodes.append(f'''
    <circle cx="{x:.1f}" cy="{y:.1f}" r="{node_r:.1f}" fill="{bg}" stroke="{node_fill}" stroke-width="2"/>
    <circle cx="{x:.1f}" cy="{y:.1f}" r="{max(node_r - 3, 2):.1f}" fill="{node_fill}" opacity="0.85">
      <animate attributeName="opacity" values="0.85;0.5;0.85" dur="2.4s" begin="{i * 0.25:.2f}s" repeatCount="indefinite"/>
    </circle>
    <text x="{x + dx:.1f}" y="{name_y:.1f}" text-anchor="{anchor}" font-size="13" font-weight="600" fill="{label_color}">{short_name}</text>
    <text x="{x + dx:.1f}" y="{count_y:.1f}" text-anchor="{anchor}" font-size="10" fill="{count_color}">{count_label}</text>''')

    return f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Open source contribution network">
  <defs>{glow_filter_defs()}</defs>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="18" fill="{bg}" stroke="{border}" stroke-width="1.5"/>
  {corner_brackets(width, height, node_fill, opacity=0.5)}
  <text x="24" y="34" font-family="'JetBrains Mono','Fira Code',monospace" font-size="12" font-weight="700" letter-spacing="1" fill="{label_color}" opacity="0.7">OPEN SOURCE · CONTRIBUTION NETWORK</text>
  <g font-family="'JetBrains Mono','Fira Code',monospace">
    {"".join(lines)}
    <circle cx="{cx:.1f}" cy="{cy:.1f}" r="34" fill="{bg}" stroke="{center_color}" stroke-width="2.5" filter="url(#glow)"/>
    <text x="{cx:.1f}" y="{cy + 5:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="{center_color}">YOU</text>
    {"".join(nodes)}
  </g>
</svg>
'''


def render_contrib_orbit(repos):
    ranked = sorted(repos.items(), key=lambda kv: kv[1]["count"], reverse=True)[:MAX_REPOS]

    dark_palette = ("#05070D", "#2E9EF7", "#2E9EF7", "#5eead4", "#5eead4", "#FFFFFF", "#8B98A5")
    light_palette = ("#F4F7FB", "#0B5FCC", "#0B5FCC", "#0E8F84", "#0E8F84", "#17223B", "#57606F")

    os.makedirs("assets", exist_ok=True)
    if ranked:
        with open("assets/orbit.svg", "w") as f:
            f.write(build_orbit_svg(ranked, dark_palette))
        with open("assets/orbit-light.svg", "w") as f:
            f.write(build_orbit_svg(ranked, light_palette))
    return ranked


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

    ranked_repos = render_contrib_orbit(repos)

    langs = render_language_cards(weights, colors)
    top_lang = langs[0][0] if langs else "—"

    projects = len(repos)
    merged = sum(info["count"] for info in repos.values())
    render_stats_strip(projects, merged, top_lang)

    print(
        f"projects={projects} merged={merged} top_lang={top_lang} "
        f"orbit_nodes={len(ranked_repos)}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
