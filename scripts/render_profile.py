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

# A dmesg-style stream that scrolls forever. (message, tag) with tag in {"OK", "WARN", ""}.
LOG = [
    ("bootrom: signature verified", "OK"),
    ("ddr: training passed, first try", "OK"),
    ("i2c-1: 0x68 ACK. writing this down.", ""),
    ("uart: 115200 8N1, the one true baud", ""),
    ("pinmux: schematic says 13", ""),
    ("pinmux: scope says 14. scope wins.", "WARN"),
    ("watchdog: fed. still alive.", "OK"),
    ("heisenbug: gone after adding printf", "WARN"),
    ("heisenbug: printf stays. forever.", ""),
    ("errata rev F outranks the datasheet", ""),
    ("bisect: 7 steps. culprit: me, 2023", ""),
    ("thermal: 61°C, within spec", "OK"),
    ("ota: slot B healthy, A on standby", "OK"),
    ("analyzer: 3 of 4 probes alive", "WARN"),
    ("pm: sleep current in µA range", "OK"),
    ("dmesg: 0 errors. suspicious.", "WARN"),
    ("kernel: hello from userspace", ""),
    ("ready. ship it.", "OK"),
    ("reboot: see you at 0.000", ""),
]

TOOLCHAINS = ["e² studio", "STM32CubeIDE", "MPLAB X", "Code Composer Studio", "PlatformIO", "GitHub Actions", "GitLab CI", "Bitbucket", "TDD + CI/CD", "Blender"]
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


def boot_stream(px, py, pw, ph, size, lh, clip_id):
    """LOG as an endless upward-scrolling stream inside a panel body."""
    top, n = py + 48, len(LOG)
    lines, t = [], 0.0
    for i in range(2 * n):  # two copies so the loop is seamless
        msg, tag = LOG[i % n]
        t = (i % n) * 0.4137 + (i % n) ** 1.3 * 0.05
        tag_svg = {"OK": ' <tspan class="x-ok">[ OK ]</tspan>', "WARN": ' <tspan class="x-wr">[WARN]</tspan>'}.get(tag, "")
        lines.append(f'<text x="{px + 22}" y="{top + 14 + size + i * lh:.1f}" class="x-boot" font-size="{size}">'
                     f'<tspan class="x-ts">[{t:7.3f}]</tspan> {escape(msg)}{tag_svg}</text>')
    fade = 40
    return (f'<g clip-path="url(#{clip_id})"><g>{"".join(lines)}'
            f'<animateTransform attributeName="transform" type="translate" from="0 0" to="0 {-n * lh}" '
            f'dur="{n * 0.85:.1f}s" repeatCount="indefinite"/></g>'
            f'<rect x="{px}" y="{top}" width="{pw}" height="{fade}" fill="url(#fadedown)"/>'
            f'<rect x="{px}" y="{py + ph - fade}" width="{pw}" height="{fade}" fill="url(#fadeup)"/></g>')


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
    <linearGradient id="fadedown" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#0a0e13"/><stop offset="1" stop-color="#0a0e13" stop-opacity="0"/></linearGradient>
    <linearGradient id="fadeup" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#0a0e13" stop-opacity="0"/><stop offset="1" stop-color="#0a0e13"/></linearGradient>
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
    .x-ts {{ fill: #6b7c91; }} .x-ok {{ fill: {CYAN}; }} .x-hi {{ fill: {PINK}; }} .x-bl {{ fill: {BLUE}; }} .x-wr {{ fill: {AMBER}; }} .x-dim {{ fill: #8b9bb0; }}
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
        stat_cell(px + 22, r1, "STARS", stats.get("stars"), CYAN, 0.3, s["label"], s["num"]),
        stat_cell(col2, r1, "PUBLIC REPOS", stats.get("repos"), AMBER, 0.45, s["label"], s["num"]),
        stat_cell(px + 22, r2, "FOLLOWERS", stats.get("followers"), PINK, 0.6, s["label"], s["num"]),
        stat_cell(col2, r2, "CONTRIBUTIONS · 1Y", stats.get("contributions"), BLUE, 0.75, s["label"], s["num"]),
        f'<text x="{px + 22}" y="{wy - s["label"] * 0.8:.0f}" class="x-lbl" font-size="{s["label"]}">ACTIVITY · 52 WEEKS</text>',
        waveform(px + 22, wy, pw - 44, s["wave_h"], stats.get("weekly"), 0.4, s["label"]),
        f'<text x="{px + 22}" y="{ly - s["label"] * 0.8:.0f}" class="x-lbl" font-size="{s["label"]}">LANGUAGES</text>',
        language_bar(px + 22, ly, pw - 44, stats.get("languages"), 0.8, s["legend"]),
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
        blocks.append(
            f'<rect class="blk" x="{x}" y="{y}" width="{bw}" height="{bh}" rx="4" stroke="{color}"/>'
            + block_body(x, y, bw, bh, kicker, title, lines, color, "k", "t", "s", 24, 52, 80, 22))
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
  {defs(W, H, f'<clipPath id="tick"><rect x="40" y="1246" width="920" height="44"/></clipPath><clipPath id="bootclip"><rect x="40" y="{py + 47}" width="492" height="{362 - 48}"/></clipPath>')}
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
    {panel(40, py, 492, 362, "DMESG -W · LIVE", 12, dot=True)}
    {boot_stream(40, py, 492, 362, 14, 24, "bootclip")}
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
    """Portrait chip package: leads on all sides, pin-1 mark, seal ring, die grid,
    bond pads, bus lines and the block grid. Returns (svg, bottom_y)."""
    out, x0, w = [], 44, 512          # package body; leads stick out 18px on each side
    pad_cols, gap = 4, 6
    inner_x, inner_w = x0 + 22, w - 44
    pw = (inner_w - (pad_cols - 1) * gap) / pad_cols
    vend_y = y0 + 70
    for i, v in enumerate(VENDORS):
        r, c = divmod(i, pad_cols)
        px, py = inner_x + c * (pw + gap), vend_y + r * 42
        out.append(f'<rect class="m-pad" x="{px:.1f}" y="{py}" width="{pw:.1f}" height="34" rx="3" style="animation-delay:{i * .15:.2f}s"/>'
                   f'<text x="{px + pw / 2:.1f}" y="{py + 23}" class="m-pl" text-anchor="middle">{escape(v)}</text>')
    gy = vend_y + -(-len(VENDORS) // pad_cols) * 42 + 22
    bgap = 14
    bw, bh = (inner_w - bgap) / 2, 160
    rows = -(-len(BLOCKS) // 2)
    grid_h = rows * bh + (rows - 1) * bgap
    # bus: one vertical spine between the columns, one horizontal run between each row
    cx = inner_x + bw + bgap / 2
    bus = [f"M{cx:.1f} {gy - 10} V{gy + grid_h + 10}"]
    bus += [f"M{inner_x - 8} {gy + r * (bh + bgap) - bgap / 2:.1f} H{inner_x + inner_w + 8}" for r in range(1, rows)]
    out.append(f'<path d="{" ".join(bus)}" class="m-bus"/>'
               f'<path d="{bus[0]}" class="m-flow"/>'
               + "".join(f'<path d="{b}" class="m-flow" style="animation-duration:{1.6 + k * .3:.1f}s"/>' for k, b in enumerate(bus[1:])))
    for idx, (kicker, title, lines, color) in enumerate(BLOCKS):
        r, c = divmod(idx, 2)
        bx, by = inner_x + c * (bw + bgap), gy + r * (bh + bgap)
        out.append(f'<rect x="{bx:.1f}" y="{by}" width="{bw:.1f}" height="{bh}" rx="5" fill="#111a24" stroke="{color}" stroke-width="2"/>'
                   + block_body(bx, by, bw, bh, kicker, title, lines, color, "m-kick", "m-title", "m-line", 28, 62, 94, 25))
    iy = gy + grid_h + 22
    iw = (inner_w - 8 * 5) / 9
    for i, v in enumerate(IFACES):
        px = inner_x + i * (iw + 5)
        out.append(f'<rect class="m-pad" x="{px:.1f}" y="{iy}" width="{iw:.1f}" height="32" rx="3" style="animation-delay:{i * .2:.2f}s"/>'
                   f'<text x="{px + iw / 2:.1f}" y="{iy + 21}" class="m-pl" text-anchor="middle" style="font-size:12px;letter-spacing:0">{v}</text>')
    bottom = iy + 70
    h = bottom - y0
    # leads
    leads = []
    for yy in range(y0 + 30, bottom - 20, 30):
        leads.append(f'<rect x="{x0 - 18}" y="{yy}" width="18" height="12" rx="1.5" class="m-lead"/>'
                     f'<rect x="{x0 + w}" y="{yy}" width="18" height="12" rx="1.5" class="m-lead"/>')
    for xx in range(x0 + 30, x0 + w - 20, 30):
        leads.append(f'<rect x="{xx}" y="{y0 - 18}" width="12" height="18" rx="1.5" class="m-lead"/>'
                     f'<rect x="{xx}" y="{bottom}" width="12" height="18" rx="1.5" class="m-lead"/>')
    body = (f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="10" fill="#0e141b" stroke="#24313f" stroke-width="2"/>'
            f'<rect x="{x0 + 10}" y="{y0 + 10}" width="{w - 20}" height="{h - 20}" rx="6" fill="url(#mgrid)" stroke="#1f3142" stroke-width="2" stroke-dasharray="6 4"/>'
            f'<circle cx="{x0 + w / 2}" cy="{y0}" r="14" fill="#070a0e" stroke="#24313f" stroke-width="2"/>'
            f'<rect x="{x0 + w / 2 - 16}" y="{y0 - 20}" width="32" height="20" fill="#070a0e"/>'
            f'<circle cx="{x0 + 30}" cy="{y0 + 30}" r="7" fill="#24313f"/>'
            f'<text x="{x0 + 46}" y="{y0 + 36}" class="m-kick" fill="{CYAN}">NR-26</text>'
            f'<text x="{x0 + w - 22}" y="{y0 + 36}" class="m-kick" fill="#6b7c91" text-anchor="end">SILICON I WORK ON</text>'
            f'<text x="{x0 + w / 2}" y="{bottom - 20}" class="m-mark" text-anchor="middle">NR-26 · REV C · NIKHIL ROBINSON</text>'
            f'<rect x="{x0 + 10}" y="{y0}" width="{w - 20}" height="90" fill="url(#mscan)" class="m-scan"/>')
    return "".join(leads) + body + "".join(out), bottom + 18


def render_mobile(stats):
    W = 600
    synced = stats.get("synced", "pending")
    chip, chip_end = mobile_chip(270)
    by = chip_end + 24
    boot_h = 420
    ty = by + boot_h + 24
    tele_h = 545
    tk = ty + tele_h + 24
    H = tk + 70
    extra = (f'<clipPath id="mtick"><rect x="20" y="{tk}" width="560" height="50"/></clipPath>'
             f'<clipPath id="mboot"><rect x="20" y="{by + 47}" width="560" height="{boot_h - 48}"/></clipPath>'
             f'<pattern id="mgrid" width="14" height="14" patternUnits="userSpaceOnUse"><path d="M14 0H0V14" fill="none" stroke="#16202b"/></pattern>'
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
    .m-title {{ fill: #f0f5fa; font-size: 21px; font-weight: 800; letter-spacing: 1px; }}
    .m-line {{ fill: #c9d4df; font-size: 17px; }}
    .m-core {{ fill: #0d151e; stroke: {CYAN}; animation: mcore 2.4s ease-in-out infinite; }}
    .m-scan {{ animation: mscan 7s linear infinite; }}
    .m-lead {{ fill: #7d8a99; }}
    .m-mark {{ fill: #6b7c91; font-size: 12px; letter-spacing: 2px; font-weight: 700; }}
    .m-bus {{ fill: none; stroke: #1f3142; stroke-width: 6; stroke-linecap: round; }}
    .m-flow {{ fill: none; stroke: {CYAN}; stroke-width: 2; stroke-dasharray: 4 18; stroke-linecap: round; opacity: .7; animation: mflow 1.4s linear infinite; }}
    @keyframes mflow {{ to {{ stroke-dashoffset: -44 }} }}
    @keyframes mpad {{ 0%,100% {{ fill: #1a2633 }} 50% {{ fill: #2f5a52 }} }}
    @keyframes mcore {{ 0%,100% {{ fill: #0d151e }} 50% {{ fill: #154d44 }} }}
    @keyframes mscan {{ from {{ transform: translateY(0) }} to {{ transform: translateY({chip_end - 380}px) }} }}
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
    {panel(20, by, 560, boot_h, "DMESG -W · LIVE", 15, dot=True)}
    {boot_stream(20, by, 560, boot_h, 16, 28, "mboot")}
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


# Dark palette -> light palette. Every colour in the frames is a literal hex from the
# dark theme, so the light variant is a straight one-pass substitution.
LIGHT = {
    "#070a0e": "#f6f8fa", "#0a0e13": "#ffffff", "#0e141b": "#eef2f6", "#111a24": "#ffffff",
    "#0c1218": "#f6f8fa", "#0d151e": "#eef7f4", "#154d44": "#c6eee3", "#1a2633": "#e3e9ef",
    "#2f5a52": "#b5e4d7", "#16202b": "#e2e8ee", "#1f3142": "#d2dbe4", "#1a2430": "#dde3ea",
    "#24313f": "#c9d2dc", "#2b3d50": "#bcc6d1",
    "#e6edf3": "#1f2328", "#f0f5fa": "#1f2328", "#d5dee8": "#24292f", "#c9d4df": "#2f363d",
    "#b4c0cc": "#424a53", "#a9b6c4": "#57606a", "#8b9bb0": "#59636e", "#6b7c91": "#6e7781",
    "#56677a": "#8c959f",
    CYAN: "#0a8f73", AMBER: "#b35900", PINK: "#cf2261", BLUE: "#2f5bd3", "#b48cff": "#7c4dcc",
}


def to_light(svg):
    return re.sub("|".join(re.escape(k) for k in LIGHT), lambda m: LIGHT[m.group(0)], svg)


def write_pair(name, svg):
    (IMAGES / f"{name}.svg").write_text(svg)
    (IMAGES / f"{name}-light.svg").write_text(to_light(svg))


def main():
    stats = load_stats()
    write_pair("profile", render_desktop(stats))
    write_pair("profile-mobile", render_mobile(stats))
    for slug, label, color in BUTTONS:
        write_pair(f"link-{slug}", button(label, color))
    print(f"rendered profile frames (synced: {stats.get('synced', 'never')})")


if __name__ == "__main__":
    main()
