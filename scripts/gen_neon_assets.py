#!/usr/bin/env python3
"""
Build the animated SVG art for the profile README.

Everything here is pure SMIL. GitHub strips <script> and ignores CSS :hover in
markdown, so an image that reacts to the cursor is not possible on a README.
What *is* possible is motion that never stops: gradients whose stop-colours
cycle, a highlight that sweeps across the letters, packets that travel down a
wire. That is what these files do, so the page is alive the moment it loads
rather than waiting for a hover that GitHub will never deliver.

Each piece is emitted twice, once tuned for GitHub's light theme and once for
dark, and the README shows one of them with #gh-light-mode-only /
#gh-dark-mode-only.

    python scripts/gen_neon_assets.py     # writes assets/neon-*.svg

No dependencies.
"""

from __future__ import annotations

import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets"

# The four accents every gradient rotates through: cyan, violet, pink, lime.
# Listed once; the loop back to the first colour is added where it is needed.
NEON = ["#22d3ee", "#8b5cf6", "#f472b6", "#c3f53c"]
# Same hues, darkened enough to stay legible on GitHub's white.
NEON_LIGHT = ["#0891b2", "#7c3aed", "#db2777", "#65a30d"]

FONT = "'Segoe UI', SF Pro Display, Helvetica Neue, Arial, sans-serif"
MONO = "'JetBrains Mono', SFMono-Regular, Consolas, monospace"


class Theme:
    def __init__(self, dark: bool):
        self.dark = dark
        self.neon = NEON if dark else NEON_LIGHT
        self.ink = "#f8fafc" if dark else "#0f172a"
        self.muted = "#64748b" if dark else "#94a3b8"
        self.grid = "#ffffff" if dark else "#0f172a"
        self.grid_op = 0.07 if dark else 0.06
        self.suffix = "dark" if dark else "light"


def cycling_stops(theme: Theme, dur: str, phase: int = 0) -> str:
    """Three gradient stops whose colours rotate, offset from one another."""
    out = []
    for i, off in enumerate(("0%", "50%", "100%")):
        k = (i + phase) % 4
        seq = theme.neon[k:] + theme.neon[:k]
        seq = seq + [seq[0]]  # close the loop so the cycle is seamless
        out.append(
            f'<stop offset="{off}" stop-color="{seq[0]}">'
            f'<animate attributeName="stop-color" values="{";".join(seq)}" '
            f'dur="{dur}" repeatCount="indefinite"/></stop>'
        )
    return "".join(out)


def svg(w: int, h: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" fill="none" role="img">{body}</svg>\n'
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Hero wordmark
# ─────────────────────────────────────────────────────────────────────────────
def hero(theme: Theme) -> str:
    W, H = 1200, 300
    parts = []

    parts.append(
        "<defs>"
        f'<linearGradient id="ink" x1="0" y1="0" x2="1" y2="0">{cycling_stops(theme, "9s")}'
        '<animateTransform attributeName="gradientTransform" type="translate" '
        'values="-0.35 0;0.35 0;-0.35 0" dur="14s" repeatCount="indefinite"/>'
        "</linearGradient>"
        f'<linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">{cycling_stops(theme, "7s", 2)}</linearGradient>'
        '<linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#ffffff" stop-opacity="0"/>'
        f'<stop offset="50%" stop-color="#ffffff" stop-opacity="{0.55 if theme.dark else 0.35}"/>'
        '<stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>'
        "</linearGradient>"
        '<mask id="letters">'
        f'<text x="600" y="150" text-anchor="middle" font-family="{FONT}" '
        'font-size="82" font-weight="700" letter-spacing="2" fill="#fff">'
        "SAHIL CHHILLAR</text>"
        "</mask>"
        "</defs>"
    )

    # Receding horizon grid.
    for i in range(9):
        y = 196 + i * i * 1.5
        if y > H - 6:
            break
        parts.append(
            f'<line x1="0" y1="{y:.0f}" x2="{W}" y2="{y:.0f}" stroke="{theme.grid}" '
            f'stroke-width="1" stroke-opacity="{theme.grid_op:.3f}"/>'
        )
    for i in range(-9, 10):
        x = 600 + i * 46
        parts.append(
            f'<line x1="{x:.0f}" y1="196" x2="{600 + i * 190:.0f}" y2="{H}" '
            f'stroke="{theme.grid}" stroke-width="1" stroke-opacity="{theme.grid_op:.3f}"/>'
        )

    # Drifting motes above the horizon.
    for i in range(22):
        x = 60 + (i * 127) % (W - 120)
        y = 34 + (i * 53) % 140
        r = 1.1 + (i % 3) * 0.5
        dur = 5 + (i % 5) * 1.7
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{theme.neon[i % 4]}" opacity="0.35">'
            f'<animate attributeName="opacity" values="0.08;0.5;0.08" dur="{dur:.1f}s" '
            f'begin="{i * 0.31:.2f}s" repeatCount="indefinite"/>'
            f'<animate attributeName="cy" values="{y};{y - 9};{y}" dur="{dur * 1.6:.1f}s" '
            f'begin="{i * 0.21:.2f}s" repeatCount="indefinite"/>'
            "</circle>"
        )

    # The name, filled by the rotating gradient.
    parts.append(
        f'<text x="600" y="150" text-anchor="middle" font-family="{FONT}" font-size="82" '
        'font-weight="700" letter-spacing="2" fill="url(#ink)">SAHIL CHHILLAR</text>'
    )
    # A highlight that travels across the letterforms.
    parts.append(
        '<g mask="url(#letters)">'
        '<rect x="-420" y="60" width="380" height="110" fill="url(#sweep)">'
        f'<animate attributeName="x" values="-420;{W}" dur="5.5s" repeatCount="indefinite"/>'
        "</rect></g>"
    )

    # Subtitle, letter-spaced and quiet.
    parts.append(
        f'<text x="600" y="186" text-anchor="middle" font-family="{MONO}" font-size="15" '
        f'letter-spacing="7" fill="{theme.muted}">FULL STACK  ·  WEB DEVELOPMENT  ·  PROBLEM SOLVING</text>'
    )

    # Rule under everything, with a bright travelling segment.
    parts.append(
        f'<rect x="300" y="206" width="600" height="2" rx="1" fill="url(#rule)" opacity="0.5"/>'
        f'<rect x="300" y="206" width="90" height="2" rx="1" fill="{theme.neon[0]}">'
        '<animate attributeName="x" values="300;810;300" dur="6s" repeatCount="indefinite"/>'
        '<animate attributeName="fill" values="'
        + ";".join(theme.neon + theme.neon[:1])
        + '" dur="9s" repeatCount="indefinite"/></rect>'
    )
    return svg(W, H, "".join(parts))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Section rule
# ─────────────────────────────────────────────────────────────────────────────
def rule(theme: Theme) -> str:
    W, H = 1200, 10
    body = (
        "<defs>"
        f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="0">{cycling_stops(theme, "8s")}</linearGradient>'
        "</defs>"
        f'<rect x="0" y="4" width="{W}" height="2" rx="1" fill="url(#g)" opacity="0.28"/>'
        f'<rect x="0" y="3.5" width="150" height="3" rx="1.5" fill="{theme.neon[1]}">'
        f'<animate attributeName="x" values="-150;{W}" dur="7s" repeatCount="indefinite"/>'
        '<animate attributeName="fill" values="'
        + ";".join(theme.neon + theme.neon[:1])
        + '" dur="7s" repeatCount="indefinite"/>'
        "</rect>"
    )
    return svg(W, H, body)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Pipeline: packets travelling through the stages I actually build
# ─────────────────────────────────────────────────────────────────────────────
def pipeline(theme: Theme) -> str:
    W, H = 1200, 170
    stages = ["INGEST", "EMBED", "INDEX", "SOLVE", "SERVE"]
    n = len(stages)
    pad, y = 130, 74
    step = (W - pad * 2) / (n - 1)
    xs = [pad + i * step for i in range(n)]

    parts = ["<defs>"]
    parts.append(
        f'<linearGradient id="wire" x1="0" y1="0" x2="1" y2="0">{cycling_stops(theme, "8s")}</linearGradient>'
    )
    parts.append("</defs>")

    # The wire. Drawn as a rect, not a <line>: a horizontal line has a
    # zero-height bounding box, which collapses an objectBoundingBox gradient
    # and renders nothing at all.
    parts.append(
        f'<rect x="{xs[0]:.0f}" y="{y - 1}" width="{xs[-1] - xs[0]:.0f}" height="2" '
        'rx="1" fill="url(#wire)" opacity="0.5"/>'
    )

    # Packets running left to right, staggered.
    for k in range(5):
        c = theme.neon[k % 4]
        parts.append(
            f'<circle cx="{xs[0]:.0f}" cy="{y}" r="4.5" fill="{c}">'
            f'<animate attributeName="cx" values="{xs[0]:.0f};{xs[-1]:.0f}" dur="4.2s" '
            f'begin="{k * 0.84:.2f}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.06;0.94;1" '
            f'dur="4.2s" begin="{k * 0.84:.2f}s" repeatCount="indefinite"/>'
            "</circle>"
        )

    # Nodes and labels.
    for i, (x, label) in enumerate(zip(xs, stages)):
        parts.append(
            f'<circle cx="{x:.0f}" cy="{y}" r="15" fill="none" stroke="{theme.neon[i % 4]}" '
            'stroke-width="1.6" opacity="0.85">'
            f'<animate attributeName="r" values="15;18;15" dur="3s" begin="{i * 0.6:.1f}s" '
            'repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0.85;0.35;0.85" dur="3s" '
            f'begin="{i * 0.6:.1f}s" repeatCount="indefinite"/></circle>'
        )
        parts.append(
            f'<circle cx="{x:.0f}" cy="{y}" r="5" fill="{theme.neon[i % 4]}"/>'
        )
        parts.append(
            f'<text x="{x:.0f}" y="{y + 44}" text-anchor="middle" font-family="{MONO}" '
            f'font-size="12" letter-spacing="3" fill="{theme.muted}">{label}</text>'
        )

    # A quiet sine under the wire, to give the strip some depth.
    pts = " ".join(
        f"{x:.0f},{130 + math.sin(x / 58) * 9:.1f}" for x in range(0, W + 1, 12)
    )
    parts.append(
        f'<polyline points="{pts}" fill="none" stroke="{theme.neon[2]}" stroke-width="1.4" '
        'opacity="0.18"><animateTransform attributeName="transform" type="translate" '
        'values="0 0;-72 0;0 0" dur="9s" repeatCount="indefinite"/></polyline>'
    )
    return svg(W, H, "".join(parts))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for dark in (True, False):
        t = Theme(dark)
        for name, fn in (("hero", hero), ("rule", rule), ("pipeline", pipeline)):
            p = OUT / f"neon-{name}-{t.suffix}.svg"
            p.write_text(fn(t), encoding="utf-8")
            written.append(p.name)
    print("wrote " + ", ".join(written))


if __name__ == "__main__":
    main()
