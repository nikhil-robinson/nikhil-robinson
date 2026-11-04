#!/usr/bin/env python3
"""Render the profile frame (images/profile.svg) and link buttons.

Live numbers come from the GitHub GraphQL API when GITHUB_TOKEN is set.
The last good fetch is cached in images/stats.json, so the frame still
renders (with the cached numbers) when the API is unreachable.
"""

import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

USER = os.environ.get("PROFILE_USER", "nikhil-robinson")
ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "images"
CACHE = IMAGES / "stats.json"
DIE = ROOT / "scripts" / "parts" / "die.svg"

W, H = 1000, 1170
CYAN, AMBER, PINK, BLUE, GREY = "#3ee6c1", "#ffb547", "#ff5d8f", "#7aa2ff", "#56677a"
# Docs, markup and build files that would skew the language mix.
NOT_CODE = {"Roff", "HTML", "CSS", "Makefile", "CMake", "Batchfile", "PowerShell", "Dockerfile",
            "Jupyter Notebook", "TeX", "Markdown", "Linker Script"}
LANG_COLORS = [CYAN, AMBER, PINK, BLUE, "#b48cff", GREY]

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount } }
      }
    }
  }
}
"""


# --------------------------------------------------------------------------- data

def fetch_stats(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-renderer"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    u = payload["data"]["user"]
    repos = u["repositories"]
    sizes = {}
    for node in repos["nodes"]:
        for edge in node["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    return {
        "stars": sum(n["stargazerCount"] for n in repos["nodes"]),
        "repos": repos["totalCount"],
        "followers": u["followers"]["totalCount"],
        "contributions": cal["totalContributions"],
        "weekly": [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cal["weeks"]],
        "languages": sizes,
        "synced": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
    }


def load_stats():
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        try:
            stats = fetch_stats(token)
            CACHE.write_text(json.dumps(stats, indent=2) + "\n")
            return stats
        except Exception as exc:  # keep rendering from cache
            print(f"warning: live fetch failed, using cache: {exc}", file=sys.stderr)
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {}


# --------------------------------------------------------------------------- pieces

def odometer(x, y, value, color, begin):
    """Rolling digits: each column scrolls from 0 to its digit."""
    if value is None:
        return f'<text x="{x}" y="{y + 26}" class="x-num" fill="{color}">--</text>'
    out, cw, ch = [], 19, 34
    for i, ch_digit in enumerate(str(value)):
        d = int(ch_digit)
        cx = x + i * cw
        strip = "".join(f'<text x="{cx}" y="{y + 27 + k * ch}" class="x-num" fill="{color}">{k}</text>' for k in range(10))
        out.append(
            f'<g>{strip}<animateTransform attributeName="transform" type="translate" from="0 0" to="0 {-d * ch}" '
            f'dur="{1.4 + i * 0.25:.2f}s" begin="{begin}s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".2 .7 .2 1"/></g>'
        )
    return "".join(out)


def stat_cell(x, y, label, value, color, begin):
    # odometer digits are clipped per cell by a clipPath sized to the digit row
    return (
        f'<g><text x="{x}" y="{y}" class="x-lbl">{label}</text>'
        f'<svg x="{x - 2}" y="{y + 8}" width="190" height="36" overflow="hidden">'
        f'{odometer(2, 0, value, color, begin)}</svg></g>'
    )


def waveform(x, y, w, h, weekly, begin):
    if not weekly:
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="#0c1218" stroke="#1a2430"/>'
                f'<text x="{x + w / 2}" y="{y + h / 2 + 4}" class="x-lbl" text-anchor="middle">AWAITING FIRST SYNC</text>')
    peak = max(weekly) or 1
    step = w / max(len(weekly) - 1, 1)
    pts = " ".join(f"{x + i * step:.1f},{y + h - 4 - (v / peak) * (h - 10):.1f}" for i, v in enumerate(weekly))
    area = f"{x},{y + h} {pts} {x + w},{y + h}"
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="#0c1218" stroke="#1a2430"/>'
        f'<polygon points="{area}" fill="url(#wavefill)" opacity="0">'
        f'<animate attributeName="opacity" from="0" to="1" dur="1s" begin="{begin + 1.2}s" fill="freeze"/></polygon>'
        f'<polyline points="{pts}" fill="none" stroke="{CYAN}" stroke-width="2" stroke-linejoin="round" '
        f'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" filter="url(#xglow)">'
        f'<animate attributeName="stroke-dashoffset" from="1" to="0" dur="2s" begin="{begin}s" fill="freeze"/></polyline>'
    )


def language_bar(x, y, w, languages, begin):
    if not languages:
        return ""
    languages = {k: v for k, v in languages.items() if k not in NOT_CODE}
    total = sum(languages.values()) or 1
    ranked = sorted(languages.items(), key=lambda kv: -kv[1])
    top, rest = ranked[:5], sum(v for _, v in ranked[5:])
    if rest:
        top.append(("Other", rest))
    out, cx = [], x
    for i, (name, v) in enumerate(top):
        seg = w * v / total
        out.append(
            f'<rect x="{cx:.1f}" y="{y}" width="0" height="10" fill="{LANG_COLORS[i]}">'
            f'<animate attributeName="width" from="0" to="{max(seg - 2, 1):.1f}" dur=".6s" begin="{begin + i * 0.15:.2f}s" fill="freeze"/></rect>'
        )
        cx += seg
    lx, ly = x, y + 32
    for i, (name, v) in enumerate(top):
        label = f"{escape(name)} {100 * v / total:.0f}%"
        if lx + 7.4 * len(label) + 16 > x + w:
            lx, ly = x, ly + 20
        out.append(f'<circle cx="{lx + 4}" cy="{ly - 4}" r="4" fill="{LANG_COLORS[i]}"/>'
                   f'<text x="{lx + 14}" y="{ly}" class="x-leg">{label}</text>')
        lx += 7.4 * len(label) + 26
    return "".join(out)


BOOT = [
    ('<tspan class="x-dim">BootROM</tspan> secure boot <tspan class="x-ok">OK</tspan> · flash enc <tspan class="x-ok">ON</tspan>', 0),
    ('<tspan class="x-dim">U-Boot 2026.10</tspan> · loading <tspan class="x-bl">Image</tspan> + <tspan class="x-bl">nr-26.dtb</tspan>', 0),
    ('<tspan class="x-ts">[0.000]</tspan> Linux 6.x · <tspan class="x-hi">Nikhil Robinson NR-26</tspan>', 6),
    ('<tspan class="x-ts">[0.104]</tspan> cpu: C · C++ · Rust · Bash <tspan class="x-ok">up</tspan>', 0),
    ('<tspan class="x-ts">[0.218]</tspan> spi i2c uart i2s can usb <tspan class="x-ok">bound</tspan>', 0),
    ('<tspan class="x-ts">[0.402]</tspan> remoteproc0: FreeRTOS + Zephyr <tspan class="x-ok">run</tspan>', 0),
    ('<tspan class="x-ts">[0.611]</tspan> npu0: vision pipeline <tspan class="x-ok">ready</tspan>', 0),
    ('<tspan class="x-ts">[0.817]</tspan> rf: wifi0 ble0 lora0 lte0 <tspan class="x-ok">up</tspan>', 0),
    ('<tspan class="x-ts">[1.003]</tspan> ros2: fusion + navigation <tspan class="x-ok">online</tspan>', 0),
    ('<tspan class="x-ok">Welcome to NR-26.</tspan> All systems nominal.', 8),
    ('<tspan class="x-bl">nr-26 login:</tspan> hire_me', 6),
]


def boot_log(x, y, begin):
    out, ly = [], y
    for i, (line, gap) in enumerate(BOOT):
        ly += gap
        out.append(f'<text x="{x}" y="{ly}" class="x-boot" opacity="0">{line}'
                   f'<animate attributeName="opacity" from="0" to="1" dur=".2s" begin="{begin + i * 0.32:.2f}s" fill="freeze"/></text>')
        ly += 23
    cursor_t = begin + len(BOOT) * 0.32
    out.append(f'<rect x="{x + 172}" y="{ly - 23 - 13}" width="8" height="16" fill="{CYAN}" opacity="0">'
               f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.01;.5;.51" dur="1s" begin="{cursor_t:.2f}s" repeatCount="indefinite"/></rect>')
    return "".join(out)


def die_markup():
    src = DIE.read_text()
    body = re.search(r"<svg[^>]*>(.*)</svg>", src, re.S).group(1)
    body = re.sub(r"<title>.*?</title>", "", body, flags=re.S)
    return body


TICKER = ("TREAT FIRMWARE LIKE PRODUCTION SOFTWARE  ◆  READ THE DATASHEET, THEN THE ERRATA  ◆  "
          "TEST IT LIKE IT'S GOING TO SPACE  ◆  NIKHIL@TECHPROGENY.COM  ◆  TECHPROGENY.COM  ◆  ")


# --------------------------------------------------------------------------- frame

def render(stats):
    synced = stats.get("synced", "pending")
    px, py, pw = 548, 726, 412  # telemetry panel
    tele = "".join([
        stat_cell(px + 22, py + 64, "STARS", stats.get("stars"), CYAN, 3.4),
        stat_cell(px + 222, py + 64, "PUBLIC REPOS", stats.get("repos"), AMBER, 3.6),
        stat_cell(px + 22, py + 128, "FOLLOWERS", stats.get("followers"), PINK, 3.8),
        stat_cell(px + 222, py + 128, "CONTRIBUTIONS · 1Y", stats.get("contributions"), BLUE, 4.0),
        f'<text x="{px + 22}" y="{py + 196}" class="x-lbl">ACTIVITY · 52 WEEKS</text>',
        waveform(px + 22, py + 206, pw - 44, 58, stats.get("weekly"), 4.2),
        f'<text x="{px + 22}" y="{py + 290}" class="x-lbl">LANGUAGES</text>',
        language_bar(px + 22, py + 300, pw - 44, stats.get("languages"), 4.8),
    ])

    roles = ["SILICON BRING-UP", "SECURE BOOT CHAINS", "KERNEL DRIVERS", "EMBEDDED LINUX", "REAL-TIME FIRMWARE", "EDGE AI + ROBOTICS"]
    n = len(roles)
    role_svg = "".join(
        f'<text x="500" y="146" text-anchor="middle" class="x-role" opacity="0">▸ {r} ◂'
        f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;{0.03 / n:.4f};{0.92 / n:.4f};{1 / n:.4f};1" '
        f'dur="{2.2 * n}s" begin="{i * 2.2}s" repeatCount="indefinite"/></text>'
        for i, r in enumerate(roles)
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
  aria-label="Nikhil Robinson, embedded systems engineer working on System-on-Chip platforms. Animated profile frame with chip floorplan, boot log and live GitHub telemetry.">
  <title>Nikhil Robinson · NR-26</title>
  <defs>
    <linearGradient id="namegrad" x1="0" x2="1">
      <stop offset="0" stop-color="#e6edf3"/><stop offset=".45" stop-color="#e6edf3"/>
      <stop offset=".5" stop-color="{CYAN}"/><stop offset=".55" stop-color="#e6edf3"/><stop offset="1" stop-color="#e6edf3"/>
      <animate attributeName="x1" values="-1;1" dur="4s" repeatCount="indefinite"/>
      <animate attributeName="x2" values="0;2" dur="4s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="wavefill" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="{CYAN}" stop-opacity=".35"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
    </linearGradient>
    <filter id="xglow" x="-10%" y="-50%" width="120%" height="200%">
      <feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="frame"><rect width="{W}" height="{H}" rx="22"/></clipPath>
    <clipPath id="tick"><rect x="40" y="1102" width="920" height="40"/></clipPath>
  </defs>
  <style>
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }}
    .x-bar  {{ fill: #8b9bb0; font-size: 13px; letter-spacing: 2px; }}
    .x-name {{ font-size: 50px; font-weight: 800; letter-spacing: 8px; }}
    .x-sub  {{ fill: #8b9bb0; font-size: 15px; letter-spacing: 4px; }}
    .x-role {{ fill: {CYAN}; font-size: 15px; letter-spacing: 3px; font-weight: 700; }}
    .x-ptl  {{ fill: {CYAN}; font-size: 12px; letter-spacing: 3px; }}
    .x-lbl  {{ fill: #6b7c91; font-size: 11px; letter-spacing: 2px; }}
    .x-num  {{ font-size: 30px; font-weight: 800; }}
    .x-leg  {{ fill: #a9b6c4; font-size: 12px; }}
    .x-boot {{ fill: #c9d4df; font-size: 13.5px; white-space: pre; }}
    .x-ts {{ fill: {GREY}; }} .x-ok {{ fill: {CYAN}; }} .x-hi {{ fill: {PINK}; }} .x-bl {{ fill: {BLUE}; }} .x-dim {{ fill: #6b7c91; }}
    .x-tick {{ fill: #6b7c91; font-size: 13px; letter-spacing: 3px; }}
    .x-pulse {{ animation: xpulse 1.6s ease-in-out infinite; }}
    @keyframes xpulse {{ 50% {{ opacity: .25; }} }}
  </style>

  <g clip-path="url(#frame)">
    <rect width="{W}" height="{H}" fill="#070a0e"/>

    <!-- header -->
    <text x="40" y="38" class="x-bar">NR-26 // ENGINEER-ON-CHIP</text>
    <circle cx="{960 - len("ONLINE · SYNC " + synced) * 9.8 - 14:.0f}" cy="33" r="5" fill="{CYAN}" class="x-pulse"/>
    <text x="960" y="38" class="x-bar" text-anchor="end">ONLINE · SYNC {escape(synced)}</text>
    <line x1="40" y1="52" x2="960" y2="52" stroke="#1a2430"/>
    <text x="500" y="96" text-anchor="middle" class="x-name" fill="url(#namegrad)" style="font-size:40px">NIKHIL ROBINSON</text>
    <text x="500" y="122" text-anchor="middle" class="x-sub" style="font-size:12px">EMBEDDED SYSTEMS ENGINEER · SYSTEM-ON-CHIP</text>
    {role_svg}

    <!-- die -->
    <g transform="translate(40 166) scale(0.9583)">{die_markup()}</g>

    <!-- boot log panel -->
    <rect x="40" y="{py}" width="492" height="356" rx="10" fill="#0a0e13" stroke="#24313f"/>
    <text x="62" y="{py + 30}" class="x-ptl">/DEV/TTYS0 · 115200 8N1</text>
    <line x1="40" y1="{py + 44}" x2="532" y2="{py + 44}" stroke="#1a2430"/>
    {boot_log(62, py + 78, 2.6)}

    <!-- telemetry panel -->
    <rect x="{px}" y="{py}" width="{pw}" height="356" rx="10" fill="#0a0e13" stroke="#24313f"/>
    <text x="{px + 22}" y="{py + 30}" class="x-ptl">TELEMETRY · LIVE FROM GITHUB</text>
    <circle cx="{px + pw - 24}" cy="{py + 26}" r="4" fill="{CYAN}" class="x-pulse"/>
    <line x1="{px}" y1="{py + 44}" x2="{px + pw}" y2="{py + 44}" stroke="#1a2430"/>
    {tele}

    <!-- ticker -->
    <line x1="40" y1="1098" x2="960" y2="1098" stroke="#1a2430"/>
    <g clip-path="url(#tick)">
      <g>
        <text x="40" y="1127" class="x-tick">{escape(TICKER * 2)}</text>
        <animateTransform attributeName="transform" type="translate" from="0 0" to="-{len(TICKER) * 10.8:.0f} 0" dur="40s" repeatCount="indefinite"/>
      </g>
    </g>
  </g>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="21" fill="none" stroke="#24313f" stroke-width="2"/>
</svg>
'''


BUTTONS = [
    ("linkedin", "LINKEDIN", BLUE),
    ("email", "EMAIL", CYAN),
    ("website", "TECHPROGENY", CYAN),
    ("youtube", "YOUTUBE", PINK),
    ("instagram", "INSTAGRAM", PINK),
    ("fiverr", "FIVERR", AMBER),
    ("coffee", "BUY ME A COFFEE", AMBER),
]


def button(label, color):
    w = 48 + len(label) * 9
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} 40" width="{w}" height="40" role="img" aria-label="{label}">
  <rect x="1" y="1" width="{w - 2}" height="38" rx="8" fill="#0a0e13" stroke="{color}" stroke-opacity=".7"/>
  <circle cx="18" cy="20" r="4" fill="{color}"><animate attributeName="opacity" values="1;.3;1" dur="2s" repeatCount="indefinite"/></circle>
  <text x="32" y="25" fill="#e6edf3" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="13" font-weight="700" letter-spacing="1.5">{label}</text>
</svg>
'''


def main():
    stats = load_stats()
    (IMAGES / "profile.svg").write_text(render(stats))
    for slug, label, color in BUTTONS:
        (IMAGES / f"link-{slug}.svg").write_text(button(label, color))
    print(f"rendered images/profile.svg (synced: {stats.get('synced', 'never')})")


if __name__ == "__main__":
    main()
