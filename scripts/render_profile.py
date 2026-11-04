#!/usr/bin/env python3
"""Render the profile frames and link buttons.

Outputs:
  images/profile.svg         wide frame for desktop
  images/profile-mobile.svg  portrait frame for phones (large type)
  images/link-*.svg          link buttons shown under the frame

Live numbers come from the GitHub GraphQL API when GITHUB_TOKEN is set.
The last good fetch is cached in images/stats.json, so the frames still
render (with cached numbers) when the API is unreachable.
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

CYAN, AMBER, PINK, BLUE, GREY = "#3ee6c1", "#ffb547", "#ff5d8f", "#7aa2ff", "#56677a"
LANG_COLORS = [CYAN, AMBER, PINK, BLUE, "#b48cff", GREY]

# Docs, markup and build files that would skew the language mix.
NOT_CODE = {"Roff", "HTML", "CSS", "Makefile", "CMake", "Batchfile", "PowerShell", "Dockerfile",
            "Jupyter Notebook", "TeX", "Markdown", "Linker Script"}

# --------------------------------------------------------------------------- content

NAME = "NIKHIL ROBINSON"
TITLE = "EMBEDDED LINUX & FIRMWARE ENGINEER"
SUBTITLE = "BSP · EDGE AI · IOT · 5+ YEARS"
ROLES = ["SILICON BRING-UP", "EMBEDDED LINUX BSPs", "REAL-TIME FIRMWARE",
         "NPU MODEL DEPLOYMENT", "WIRELESS + OTA", "POWER OPTIMIZATION"]

VENDORS = ["ROCKCHIP", "KNERON", "MILK-V", "NXP i.MX", "RENESAS", "TI",
           "MICROCHIP", "STM32", "NORDIC", "ESP32", "CH32", "AVR"]
IFACES = ["UART", "SPI", "I2C", "CAN", "USB", "I2S", "ETH", "JTAG", "SWD"]
CORES = ["C", "C++", "RUST", "BASH"]

# Die blocks in reading order: 4 columns x 3 rows on desktop, 2 columns x 6 rows on mobile.
# (kicker, title, lines, colour). Lines stay <= 19 chars so they fit both layouts.
# The "cpu" block draws CORES instead of lines.
BLOCKS = [
    ("CPU CLUSTER", None, None, CYAN),
    ("NPU / EDGE AI", "ON-DEVICE AI", ["RKNN · Kneron NPU", "TinyML · OpenCV", "PyTorch · TF → NPU"], PINK),
    ("APP SUBSYSTEM", "LINUX / BSP", ["Rockchip · i.MX", "Milk-V · RKMPP/RGA", "kernel drivers · DT"], BLUE),
    ("BOOT ROM", "BOOT CHAIN", ["U-Boot · OTA · A/B", "Yocto · Buildroot", "provisioning"], AMBER),
    ("SECURE ENCLAVE", "ROOT OF TRUST", ["Secure boot · AES", "Flash encryption", "CRC32 · MD5"], AMBER),
    ("RT CORE", "REAL-TIME", ["FreeRTOS · Zephyr", "nRF Connect SDK", "ESP-IDF · FSP"], CYAN),
    ("DISPLAY", "HMI / GUI", ["LVGL · Qt · Slint", "MCU + Linux GUIs", "touch + display"], PINK),
    ("RF FRONT-END", "WIRELESS", ["Wi-Fi · BLE · LoRa", "LTE · NB-IoT · GSM", "NFC · RFID"], BLUE),
    ("NETWORK STACK", "PROTOCOLS", ["MQTT · TCP · UDP", "HTTP/S · WebSocket", "custom APIs"], CYAN),
    ("MOTION ENGINE", "ROBOTICS", ["ROS 2 · AHRS", "sensor fusion", "navigation"], PINK),
    ("BRING-UP", "FIRST SILICON", ["hardware debugging", "power optimization", "JTAG · SWD"], AMBER),
    ("R&D", "EXPLORING", ["autonomous drones", "GPS-denied nav", "Edge AI on MCUs"], BLUE),
]

BOOT = [
    ('<tspan class="x-dim">BootROM</tspan> secure boot <tspan class="x-ok">OK</tspan> · OTA slot <tspan class="x-ok">B</tspan>', 0),
    ('<tspan class="x-dim">U-Boot</tspan> · <tspan class="x-bl">Image</tspan> + <tspan class="x-bl">nr-26.dtb</tspan>', 0),
    ('<tspan class="x-ts">[0.000]</tspan> Linux · <tspan class="x-hi">Nikhil Robinson NR-26</tspan>', 6),
    ('<tspan class="x-ts">[0.104]</tspan> cpu: C · C++ · Rust · Bash <tspan class="x-ok">up</tspan>', 0),
    ('<tspan class="x-ts">[0.218]</tspan> uart spi i2c can <tspan class="x-ok">bound</tspan>', 0),
    ('<tspan class="x-ts">[0.402]</tspan> rtos: FreeRTOS + Zephyr <tspan class="x-ok">run</tspan>', 0),
    ('<tspan class="x-ts">[0.611]</tspan> rknpu: model <tspan class="x-ok">deployed</tspan>', 0),
    ('<tspan class="x-ts">[0.817]</tspan> wlan0 hci0 <tspan class="x-ok">up</tspan> · mqtt <tspan class="x-ok">ok</tspan>', 0),
    ('<tspan class="x-ts">[1.003]</tspan> pm: low-power idle <tspan class="x-ok">on</tspan>', 0),
    ('<tspan class="x-ok">Welcome to NR-26.</tspan> All systems nominal.', 8),
    ('<tspan class="x-bl">nr-26 login:</tspan> hire_me', 6),
]
LOGIN_CHARS = len("nr-26 login: hire_me ")

TOOLCHAINS = ["e² studio · FSP", "STM32CubeIDE", "MPLAB X", "Code Composer Studio", "nRF Connect SDK", "ESP-IDF",
              "PlatformIO", "GitHub Actions", "GitLab CI", "Bitbucket", "TDD + CI/CD", "Blender"]
TICKER = "  ◆  ".join(TOOLCHAINS + ["SILICON BRING-UP TO CLOUD", "TECHPROGENY.COM"]) + "  ◆  "

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


# --------------------------------------------------------------------------- shared widgets

def odometer(x, y, value, color, begin, size):
    """Rolling digits in a clipped viewport: each column scrolls from 0 to its digit."""
    ch, cw = size * 1.15, size * 0.62
    if value is None:
        return f'<text x="{x}" y="{y + size}" font-size="{size}" class="x-num" fill="{color}">--</text>'
    cols = []
    for i, digit in enumerate(str(value)):
        cx = x + i * cw
        strip = "".join(f'<text x="{cx:.1f}" y="{y + size * 0.95 + k * ch:.1f}" font-size="{size}" class="x-num" fill="{color}">{k}</text>'
                        for k in range(10))
        cols.append(f'<g>{strip}<animateTransform attributeName="transform" type="translate" from="0 0" to="0 {-int(digit) * ch:.1f}" '
                    f'dur="{1.4 + i * 0.25:.2f}s" begin="{begin}s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".2 .7 .2 1"/></g>')
    return (f'<svg x="{x - 2}" y="{y}" width="{len(str(value)) * cw + 8:.0f}" height="{ch:.0f}" overflow="hidden">'
            f'<g transform="translate({2 - x} {-y})">{"".join(cols)}</g></svg>')


def stat_cell(x, y, label, value, color, begin, label_size, num_size):
    return (f'<text x="{x}" y="{y}" class="x-lbl" font-size="{label_size}">{label}</text>'
            + odometer(x, y + label_size * 0.6, value, color, begin, num_size))


def waveform(x, y, w, h, weekly, begin, label_size):
    box = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="#0c1218" stroke="#1a2430"/>'
    if not weekly:
        return box + (f'<text x="{x + w / 2}" y="{y + h / 2 + 4}" class="x-lbl" font-size="{label_size}" '
                      f'text-anchor="middle">AWAITING FIRST SYNC</text>')
    peak = max(weekly) or 1
    step = w / max(len(weekly) - 1, 1)
    pts = " ".join(f"{x + i * step:.1f},{y + h - 4 - (v / peak) * (h - 10):.1f}" for i, v in enumerate(weekly))
    return (box
            + f'<polygon points="{x},{y + h} {pts} {x + w},{y + h}" fill="url(#wavefill)" opacity="0">'
              f'<animate attributeName="opacity" from="0" to="1" dur="1s" begin="{begin + 1.2}s" fill="freeze"/></polygon>'
            + f'<polyline points="{pts}" fill="none" stroke="{CYAN}" stroke-width="2.5" stroke-linejoin="round" '
              f'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1">'
              f'<animate attributeName="stroke-dashoffset" from="1" to="0" dur="2s" begin="{begin}s" fill="freeze"/></polyline>')


def language_bar(x, y, w, languages, begin, legend_size):
    languages = {k: v for k, v in (languages or {}).items() if k not in NOT_CODE}
    if not languages:
        return ""
    total = sum(languages.values())
    ranked = sorted(languages.items(), key=lambda kv: -kv[1])
    top, rest = ranked[:5], sum(v for _, v in ranked[5:])
    if rest:
        top.append(("Other", rest))
    out, cx = [], x
    for i, (_, v) in enumerate(top):
        seg = w * v / total
        out.append(f'<rect x="{cx:.1f}" y="{y}" width="0" height="{legend_size * 0.8:.0f}" fill="{LANG_COLORS[i]}">'
                   f'<animate attributeName="width" from="0" to="{max(seg - 2, 1):.1f}" dur=".6s" '
                   f'begin="{begin + i * 0.15:.2f}s" fill="freeze"/></rect>')
        cx += seg
    cw = legend_size * 0.62
    lx, ly = x, y + legend_size * 2.6
    for i, (name, v) in enumerate(top):
        label = f"{escape(name)} {100 * v / total:.0f}%"
        width = cw * len(label) + legend_size * 1.2
        if lx + width > x + w:
            lx, ly = x, ly + legend_size * 1.7
        out.append(f'<circle cx="{lx + legend_size * 0.35:.1f}" cy="{ly - legend_size * 0.35:.1f}" '
                   f'r="{legend_size * 0.33:.1f}" fill="{LANG_COLORS[i]}"/>'
                   f'<text x="{lx + legend_size * 1.1:.1f}" y="{ly:.1f}" class="x-leg" font-size="{legend_size}">{label}</text>')
        lx += width + legend_size * 1.4
    return "".join(out)


def boot_log(x, y, begin, size, line_h):
    out, ly = [], y
    for i, (line, gap) in enumerate(BOOT):
        ly += gap
        out.append(f'<text x="{x}" y="{ly}" class="x-boot" font-size="{size}" opacity="0">{line}'
                   f'<animate attributeName="opacity" from="0" to="1" dur=".2s" begin="{begin + i * 0.32:.2f}s" fill="freeze"/></text>')
        ly += line_h
    t = begin + len(BOOT) * 0.32
    cx = x + LOGIN_CHARS * size * 0.6
    out.append(f'<rect x="{cx:.0f}" y="{ly - line_h - size * 0.85:.0f}" width="{size * 0.55:.0f}" height="{size:.0f}" fill="{CYAN}" opacity="0">'
               f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.01;.5;.51" dur="1s" begin="{t:.2f}s" repeatCount="indefinite"/></rect>')
    return "".join(out)


def role_cycler(x, y, size):
    n, period = len(ROLES), 2.2
    return "".join(
        f'<text x="{x}" y="{y}" text-anchor="middle" class="x-role" font-size="{size}" opacity="0">▸ {escape(r)} ◂'
        f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;{0.03 / n:.4f};{0.92 / n:.4f};{1 / n:.4f};1" '
        f'dur="{period * n}s" begin="{i * period}s" repeatCount="indefinite"/></text>'
        for i, r in enumerate(ROLES))


def ticker(x, y, size, clip_id):
    width = len(TICKER) * (size * 0.6 + 3)  # char advance + letter-spacing
    return (f'<g clip-path="url(#{clip_id})"><g>'
            f'<text x="{x}" y="{y}" class="x-tick" font-size="{size}">{escape(TICKER * 3)}</text>'
            f'<animateTransform attributeName="transform" type="translate" from="0 0" to="-{width:.0f} 0" dur="45s" repeatCount="indefinite"/>'
            f'</g></g>')


def defs(w, h, extra=""):
    return f'''<defs>
    <linearGradient id="namegrad" x1="0" x2="1">
      <stop offset="0" stop-color="#e6edf3"/><stop offset=".45" stop-color="#e6edf3"/>
      <stop offset=".5" stop-color="{CYAN}"/><stop offset=".55" stop-color="#e6edf3"/><stop offset="1" stop-color="#e6edf3"/>
      <animate attributeName="x1" values="-1;1" dur="4s" repeatCount="indefinite"/>
      <animate attributeName="x2" values="0;2" dur="4s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="wavefill" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="{CYAN}" stop-opacity=".35"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="frame"><rect width="{w}" height="{h}" rx="22"/></clipPath>
    {extra}
  </defs>
  <style>
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }}
    .x-bar  {{ fill: #8b9bb0; letter-spacing: 2px; }}
    .x-name {{ font-weight: 800; letter-spacing: 6px; }}
    .x-sub  {{ fill: #a9b6c4; letter-spacing: 2px; }}
    .x-role {{ fill: {CYAN}; letter-spacing: 2px; font-weight: 700; }}
    .x-ptl  {{ fill: {CYAN}; letter-spacing: 3px; }}
    .x-lbl  {{ fill: #8b9bb0; letter-spacing: 2px; }}
    .x-num  {{ font-weight: 800; }}
    .x-leg  {{ fill: #c9d4df; }}
    .x-boot {{ fill: #d5dee8; white-space: pre; }}
    .x-ts {{ fill: #6b7c91; }} .x-ok {{ fill: {CYAN}; }} .x-hi {{ fill: {PINK}; }} .x-bl {{ fill: {BLUE}; }} .x-dim {{ fill: #8b9bb0; }}
    .x-tick {{ fill: #8b9bb0; letter-spacing: 3px; }}
    .x-pulse {{ animation: xpulse 1.6s ease-in-out infinite; }}
    @keyframes xpulse {{ 50% {{ opacity: .25; }} }}
  </style>'''


def panel(x, y, w, h, title, size, dot=False):
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#0a0e13" stroke="#24313f"/>'
         f'<text x="{x + 22}" y="{y + 30}" class="x-ptl" font-size="{size}">{title}</text>'
         f'<line x1="{x}" y1="{y + 46}" x2="{x + w}" y2="{y + 46}" stroke="#1a2430"/>')
    if dot:
        s += f'<circle cx="{x + w - 24}" cy="{y + 25}" r="5" fill="{CYAN}" class="x-pulse"/>'
    return s


def telemetry(px, py, pw, stats, s):
    """s holds the size knobs: label, num, legend, row, wave_h."""
    col2 = px + 22 + (pw - 44) / 2
    r1, r2 = py + 46 + s["row"] * 0.55, py + 46 + s["row"] * 1.55
    wy = r2 + s["row"] * 1.25
    ly = wy + s["wave_h"] + s["label"] * 3
    return "".join([
        stat_cell(px + 22, r1, "STARS", stats.get("stars"), CYAN, 3.4, s["label"], s["num"]),
        stat_cell(col2, r1, "PUBLIC REPOS", stats.get("repos"), AMBER, 3.6, s["label"], s["num"]),
        stat_cell(px + 22, r2, "FOLLOWERS", stats.get("followers"), PINK, 3.8, s["label"], s["num"]),
        stat_cell(col2, r2, "CONTRIBUTIONS · 1Y", stats.get("contributions"), BLUE, 4.0, s["label"], s["num"]),
        f'<text x="{px + 22}" y="{wy - s["label"] * 0.8:.0f}" class="x-lbl" font-size="{s["label"]}">ACTIVITY · 52 WEEKS</text>',
        waveform(px + 22, wy, pw - 44, s["wave_h"], stats.get("weekly"), 4.2, s["label"]),
        f'<text x="{px + 22}" y="{ly - s["label"] * 0.8:.0f}" class="x-lbl" font-size="{s["label"]}">LANGUAGES</text>',
        language_bar(px + 22, ly, pw - 44, stats.get("languages"), 4.8, s["legend"]),
    ])


def block_body(x, y, w, h, kicker, title, lines, color, k_cls, t_cls, l_cls, k_dy, t_dy, l_dy, lh):
    """Kicker + title + lines, or the CPU core grid when title is None."""
    head = f'<text class="{k_cls}" x="{x + 14}" y="{y + k_dy}" fill="{color}" style="fill:{color}">{escape(kicker)}</text>'
    if title is None:
        cw, gap = (w - 28 - 8) / 2, 8
        chh = min(lh * 2.3, (h - k_dy - 12 - gap - 12) / 2)
        cores = "".join(
            f'<rect class="core m-core" x="{x + 14 + (i % 2) * (cw + gap):.0f}" y="{y + k_dy + 12 + (i // 2) * (chh + gap):.0f}" '
            f'width="{cw:.0f}" height="{chh:.0f}" rx="3" style="animation-delay:{i * .6:.1f}s"/>'
            f'<text class="{t_cls}" x="{x + 14 + (i % 2) * (cw + gap) + cw / 2:.0f}" y="{y + k_dy + 12 + (i // 2) * (chh + gap) + chh / 2 + lh * 0.3:.0f}" '
            f'text-anchor="middle">{c}</text>'
            for i, c in enumerate(CORES))
        return head + cores
    body = "".join(f'<text class="{l_cls}" x="{x + 14}" y="{y + l_dy + i * lh}">{escape(t)}</text>' for i, t in enumerate(lines))
    return head + f'<text class="{t_cls}" x="{x + 14}" y="{y + t_dy}">{escape(title)}</text>' + body


# --------------------------------------------------------------------------- desktop frame

def die_markup():
    src = DIE.read_text()
    n = len(VENDORS)
    step = 780 / n
    top = "".join(
        f'<rect class="pad" x="{90 + i * step:.1f}" y="42" width="{step - 4:.1f}" height="20" rx="2" style="animation-delay:{i * .15:.2f}s"/>'
        f'<text class="pl" x="{90 + i * step + (step - 4) / 2:.1f}" y="56" text-anchor="middle">{escape(v)}</text>'
        for i, v in enumerate(VENDORS))
    step = 780 / len(IFACES)
    bottom = "".join(
        f'<rect class="pad" x="{90 + i * step:.1f}" y="618" width="{step - 6:.1f}" height="20" rx="2" style="animation-delay:{i * .2 + .1:.2f}s"/>'
        f'<text class="pl" x="{90 + i * step + (step - 6) / 2:.1f}" y="632" text-anchor="middle">{v}</text>'
        for i, v in enumerate(IFACES))
    side = "".join(
        f'<rect class="pad" x="{x}" y="{96 + i * 64}" width="16" height="42" rx="2" style="animation-delay:{i * .3 + off:.2f}s"/>'
        for i in range(8) for x, off in ((44, 0), (900, .15)))
    blocks = []
    bw, bh, gap = 186, 160, 12
    for i, (kicker, title, lines, color) in enumerate(BLOCKS):
        r, c = divmod(i, 4)
        x, y = 90 + c * (bw + gap), 90 + r * (bh + gap)
        delay = f"animation-delay:{0.2 + i * 0.18:.2f}s"
        blocks.append(
            f'<rect class="blk" x="{x}" y="{y}" width="{bw}" height="{bh}" rx="4" stroke="{color}" style="{delay}"/>'
            f'<g class="lbl" style="{delay}">'
            + block_body(x, y, bw, bh, kicker, title, lines, color, "k", "t", "s", 24, 52, 80, 22)
            + "</g>")
    for token, val in (("TOP_PADS", top), ("BOTTOM_PADS", bottom), ("SIDE_PADS", side), ("BLOCKS", "".join(blocks))):
        src = src.replace("{{" + token + "}}", val)
    return re.search(r"<svg[^>]*>(.*)</svg>", src, re.S).group(1)


def render_desktop(stats):
    W, H = 1000, 1306
    synced = stats.get("synced", "pending")
    status = f"ONLINE · SYNC {synced}"
    py = 866
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
  aria-label="Nikhil Robinson, Embedded Linux and firmware engineer. Animated profile frame with a chip floorplan of skills, a boot log and live GitHub telemetry.">
  <title>Nikhil Robinson · NR-26</title>
  {defs(W, H, '<clipPath id="tick"><rect x="40" y="1246" width="920" height="44"/></clipPath>')}
  <g clip-path="url(#frame)">
    <rect width="{W}" height="{H}" fill="#070a0e"/>
    <text x="40" y="38" class="x-bar" font-size="13">NR-26 // ENGINEER-ON-CHIP</text>
    <circle cx="{960 - len(status) * 9.8 - 14:.0f}" cy="33" r="5" fill="{CYAN}" class="x-pulse"/>
    <text x="960" y="38" class="x-bar" font-size="13" text-anchor="end">{escape(status)}</text>
    <line x1="40" y1="52" x2="960" y2="52" stroke="#1a2430"/>
    <text x="500" y="100" text-anchor="middle" class="x-name" font-size="42" fill="url(#namegrad)">{NAME}</text>
    <text x="500" y="130" text-anchor="middle" class="x-sub" font-size="15">{escape(TITLE)}</text>
    <text x="500" y="152" text-anchor="middle" class="x-sub" font-size="13">{escape(SUBTITLE)}</text>
    {role_cycler(500, 180, 16)}
    <g transform="translate(40 196) scale(0.9583)">{die_markup()}</g>
    {panel(40, py, 492, 362, "/DEV/TTYS0 · 115200 8N1", 12)}
    {boot_log(62, py + 80, 2.6, 14, 24)}
    {panel(548, py, 412, 362, "TELEMETRY · LIVE FROM GITHUB", 12, dot=True)}
    {telemetry(548, py, 412, stats, dict(label=11, num=30, legend=12, row=58, wave_h=56))}
    <line x1="40" y1="1246" x2="960" y2="1246" stroke="#1a2430"/>
    {ticker(40, 1276, 13, "tick")}
  </g>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="21" fill="none" stroke="#24313f" stroke-width="2"/>
</svg>
'''


# --------------------------------------------------------------------------- mobile frame

def mobile_chip(y0):
    """Portrait chip: vendor pads, 2-column block grid, interface pads. Returns (svg, bottom_y)."""
    out, x0, w = [], 20, 560
    cols, gap = 4, 6
    pw = (w - 44 - (cols - 1) * gap) / cols
    for i, v in enumerate(VENDORS):
        r, c = divmod(i, cols)
        px, py = x0 + 22 + c * (pw + gap), y0 + 62 + r * 44
        out.append(f'<rect class="m-pad" x="{px:.1f}" y="{py}" width="{pw:.1f}" height="36" rx="4" style="animation-delay:{i * .15:.2f}s"/>'
                   f'<text x="{px + pw / 2:.1f}" y="{py + 24}" class="m-pl" text-anchor="middle">{escape(v)}</text>')
    gy = y0 + 62 + -(-len(VENDORS) // cols) * 44 + 18
    bw, bh, bgap = 254, 160, 12
    for idx, (kicker, title, lines, color) in enumerate(BLOCKS):
        r, c = divmod(idx, 2)
        bx, by = x0 + 22 + c * (bw + bgap), gy + r * (bh + bgap)
        out.append(f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur=".5s" begin="{0.3 + idx * 0.18:.2f}s" fill="freeze"/>'
                   f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6" fill="#111a24" stroke="{color}" stroke-width="2"/>'
                   + block_body(bx + 2, by, bw - 4, bh, kicker, title, lines, color, "m-kick", "m-title", "m-line", 28, 62, 94, 25)
                   + "</g>")
    iy = gy + -(-len(BLOCKS) // 2) * (bh + bgap) + 4
    iw = (w - 44 - 8 * 6) / 9
    for i, v in enumerate(IFACES):
        px = x0 + 22 + i * (iw + 6)
        out.append(f'<rect class="m-pad" x="{px:.1f}" y="{iy}" width="{iw:.1f}" height="34" rx="4" style="animation-delay:{i * .2:.2f}s"/>'
                   f'<text x="{px + iw / 2:.1f}" y="{iy + 23}" class="m-pl" text-anchor="middle" style="font-size:13px">{v}</text>')
    bottom = iy + 58
    frame = (f'<rect x="{x0}" y="{y0}" width="{w}" height="{bottom - y0}" rx="12" fill="#0e141b" stroke="#24313f" stroke-width="2"/>'
             f'<text x="{x0 + 22}" y="{y0 + 38}" class="m-kick" fill="{CYAN}">NR-26 · SILICON I WORK ON</text>'
             f'<circle cx="{x0 + w - 26}" cy="{y0 + 32}" r="6" fill="{CYAN}" class="x-pulse"/>'
             f'<rect x="{x0}" y="{y0}" width="{w}" height="90" fill="url(#mscan)" class="m-scan"/>')
    return frame + "".join(out), bottom


def render_mobile(stats):
    W = 600
    synced = stats.get("synced", "pending")
    chip, chip_end = mobile_chip(250)
    by = chip_end + 24
    boot_h = 64 + len(BOOT) * 31 + 40
    ty = by + boot_h + 24
    tele_h = 545
    tk = ty + tele_h + 24
    H = tk + 70
    extra = (f'<clipPath id="mtick"><rect x="20" y="{tk}" width="560" height="50"/></clipPath>'
             f'<linearGradient id="mscan" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>'
             f'<stop offset=".5" stop-color="{CYAN}" stop-opacity=".14"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
  aria-label="Nikhil Robinson, Embedded Linux and firmware engineer. Animated profile with the silicon he works on, a boot log and live GitHub telemetry.">
  <title>Nikhil Robinson · NR-26</title>
  {defs(W, H, extra)}
  <style>
    .m-pad {{ fill: #1a2633; stroke: #2b3d50; animation: mpad 3s ease-in-out infinite; }}
    .m-pl {{ fill: #d5dee8; font-size: 14px; font-weight: 700; letter-spacing: 1px; }}
    .m-kick {{ font-size: 14px; letter-spacing: 2px; font-weight: 700; }}
    .m-title {{ fill: #f0f5fa; font-size: 22px; font-weight: 800; letter-spacing: 1px; }}
    .m-line {{ fill: #c9d4df; font-size: 17px; }}
    .m-core {{ fill: #0d151e; stroke: {CYAN}; animation: mcore 2.4s ease-in-out infinite; }}
    .m-scan {{ animation: mscan 7s linear infinite; }}
    @keyframes mpad {{ 0%,100% {{ fill: #1a2633 }} 50% {{ fill: #2f5a52 }} }}
    @keyframes mcore {{ 0%,100% {{ fill: #0d151e }} 50% {{ fill: #154d44 }} }}
    @keyframes mscan {{ from {{ transform: translateY(0) }} to {{ transform: translateY({chip_end - 340}px) }} }}
  </style>
  <g clip-path="url(#frame)">
    <rect width="{W}" height="{H}" fill="#070a0e"/>
    <text x="24" y="42" class="x-bar" font-size="15">NR-26</text>
    <circle cx="{576 - len("ONLINE") * 11 - 16}" cy="37" r="6" fill="{CYAN}" class="x-pulse"/>
    <text x="576" y="42" class="x-bar" font-size="15" text-anchor="end">ONLINE</text>
    <line x1="24" y1="60" x2="576" y2="60" stroke="#1a2430"/>
    <text x="300" y="122" text-anchor="middle" class="x-name" font-size="40" style="letter-spacing:3px" fill="url(#namegrad)">{NAME}</text>
    <text x="300" y="160" text-anchor="middle" class="x-sub" font-size="18" style="letter-spacing:0">{escape(TITLE)}</text>
    <text x="300" y="188" text-anchor="middle" class="x-sub" font-size="17" style="letter-spacing:1px">{escape(SUBTITLE)}</text>
    {role_cycler(300, 226, 19)}
    {chip}
    {panel(20, by, 560, boot_h, "/DEV/TTYS0 · 115200 8N1", 15)}
    {boot_log(40, by + 86, 2.6, 18, 31)}
    {panel(20, ty, 560, tele_h, f"TELEMETRY · SYNC {escape(synced)}", 15, dot=True)}
    {telemetry(20, ty, 560, stats, dict(label=15, num=44, legend=17, row=92, wave_h=86))}
    <line x1="20" y1="{tk}" x2="580" y2="{tk}" stroke="#1a2430"/>
    {ticker(20, tk + 36, 17, "mtick")}
  </g>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="21" fill="none" stroke="#24313f" stroke-width="2"/>
</svg>
'''


# --------------------------------------------------------------------------- buttons

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
    (IMAGES / "profile.svg").write_text(render_desktop(stats))
    (IMAGES / "profile-mobile.svg").write_text(render_mobile(stats))
    for slug, label, color in BUTTONS:
        (IMAGES / f"link-{slug}.svg").write_text(button(label, color))
    print(f"rendered profile frames (synced: {stats.get('synced', 'never')})")


if __name__ == "__main__":
    main()
