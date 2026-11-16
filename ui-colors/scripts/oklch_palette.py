#!/usr/bin/env python3
"""Deterministic OKLCh / OKLab palette generator, contrast auditor & multi-language emitter.

Zero external dependencies. Implements Bjorn Ottosson's OKLab/OKLCh transforms,
binary-search perceptual sRGB gamut clamping, WCAG 2.2 relative luminance contrast,
and APCA-W3 Lc perceptual contrast.

Subcommands:
  ramp   Generate an 11-step perceptual OKLCh ramp and emit CSS, Rust, C++, Go, or JSON.
  check  Compute OKLCh coords, gamut status, WCAG 2.2 ratio, and APCA Lc for two colors.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys

STEPS: list[tuple[str, float, float]] = [
    ("50", 0.980, 0.06),
    ("100", 0.950, 0.14),
    ("200", 0.905, 0.28),
    ("300", 0.835, 0.48),
    ("400", 0.740, 0.75),
    ("500", 0.640, 0.95),
    ("600", 0.545, 1.00),
    ("700", 0.460, 0.90),
    ("800", 0.375, 0.72),
    ("900", 0.285, 0.50),
    ("950", 0.195, 0.30),
]


def oklab_to_linear_srgb(L: float, a: float, b: float) -> tuple[float, float, float]:
    lp = L + 0.3963377774 * a + 0.2158037573 * b
    mp = L - 0.1055613458 * a - 0.0638541728 * b
    sp = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = lp**3, mp**3, sp**3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return r, g, bl


def linear_srgb_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    lp = math.copysign(abs(l) ** (1.0 / 3.0), l)
    mp = math.copysign(abs(m) ** (1.0 / 3.0), m)
    sp = math.copysign(abs(s) ** (1.0 / 3.0), s)
    L = 0.2104542553 * lp + 0.7936177850 * mp - 0.0040720468 * sp
    a = 1.9779984951 * lp - 2.4285922050 * mp + 0.4505937099 * sp
    bk = 0.0259040371 * lp + 0.7827717662 * mp - 0.8086757660 * sp
    return L, a, bk


def in_srgb_gamut(r: float, g: float, b: float, eps: float = 1e-6) -> bool:
    return (-eps <= r <= 1.0 + eps) and (-eps <= g <= 1.0 + eps) and (-eps <= b <= 1.0 + eps)


def srgb_encode_channel(x: float) -> int:
    c = min(1.0, max(0.0, x))
    v = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055
    return int(round(v * 255.0))


def srgb_decode_channel(byte_val: int) -> float:
    v = byte_val / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def oklch_to_srgb_bytes(L: float, C: float, h_deg: float) -> tuple[int, int, int, float, bool]:
    """Return (R, G, B, clamped_C, was_clamped)."""
    if L <= 0.0:
        return 0, 0, 0, 0.0, C > 1e-6
    if L >= 1.0:
        return 255, 255, 255, 0.0, C > 1e-6
    hr = math.radians(h_deg)
    ch, sh = math.cos(hr), math.sin(hr)
    r, g, b = oklab_to_linear_srgb(L, C * ch, C * sh)
    if in_srgb_gamut(r, g, b):
        return srgb_encode_channel(r), srgb_encode_channel(g), srgb_encode_channel(b), C, False
    lo, hi = 0.0, C
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        rm, gm, bm = oklab_to_linear_srgb(L, mid * ch, mid * sh)
        if in_srgb_gamut(rm, gm, bm):
            lo = mid
        else:
            hi = mid
    r, g, b = oklab_to_linear_srgb(L, lo * ch, lo * sh)
    return srgb_encode_channel(r), srgb_encode_channel(g), srgb_encode_channel(b), lo, True


def trunc_decimals(val: float, decimals: int) -> float:
    """Truncate toward zero so displayed values never overstate contrast thresholds."""
    scale = 10**decimals
    t = math.trunc(val * scale) / scale
    if abs(t) > abs(val):
        t = math.trunc(math.nextafter(val * scale, 0.0)) / scale
    return 0.0 if t == 0.0 else t


def parse_color(
    spec: str,
) -> tuple[int, int, int, tuple[float, float, float], bool, float | None]:
    """Return (R, G, B, (L, C_used, hue), was_clamped, requested_C_or_None)."""
    s = spec.strip()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        if len(h) != 6:
            raise ValueError(f"Unsupported hex color: {spec}")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        L, a, bk = linear_srgb_to_oklab(
            srgb_decode_channel(r), srgb_decode_channel(g), srgb_decode_channel(b)
        )
        C = math.hypot(a, bk)
        hue = (math.degrees(math.atan2(bk, a)) + 360.0) % 360.0 if C > 1e-5 else 0.0
        return r, g, b, (L, C, hue), False, None
    m = re.match(
        r"^oklch\(\s*([0-9.]+)(%?)\s+([0-9.]+)\s+([+-]?[0-9.]+)(?:deg)?\s*\)$", s, re.I
    )
    if m:
        L = float(m.group(1)) / (100.0 if m.group(2) == "%" else 1.0)
        C = float(m.group(3))
        hue = float(m.group(4)) % 360.0
        if hue >= 360.0:
            hue = 0.0
        r, g, b, c_used, was_clamped = oklch_to_srgb_bytes(L, C, hue)
        return r, g, b, (L, c_used, hue), was_clamped, C
    raise ValueError(f"Use '#rrggbb' or 'oklch(L C H)': got {spec!r}")


def wcag_contrast(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    def lum(rgb: tuple[int, int, int]) -> float:
        rl, gl, bl = (srgb_decode_channel(c) for c in rgb)
        return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl

    y1, y2 = lum(fg), lum(bg)
    hi, lo = (y1, y2) if y1 >= y2 else (y2, y1)
    return (hi + 0.05) / (lo + 0.05)


def apca_lc(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    def ys(rgb: tuple[int, int, int]) -> float:
        r, g, b = ((c / 255.0) ** 2.4 for c in rgb)
        y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
        return y + ((0.022 - y) ** 1.414) if y < 0.022 else y

    ytxt, ybg = ys(fg), ys(bg)
    if abs(ybg - ytxt) < 0.0005:
        return 0.0
    if ybg > ytxt:
        sapc = ((ybg**0.56) - (ytxt**0.57)) * 1.14
        return 0.0 if sapc < 0.1 else (sapc - 0.027) * 100.0
    sapc = ((ybg**0.65) - (ytxt**0.62)) * 1.14
    return 0.0 if sapc > -0.1 else (sapc + 0.027) * 100.0


def cmd_ramp(args: argparse.Namespace) -> None:
    hue = args.hue % 360.0
    if hue >= 360.0:
        hue = 0.0
    rows = []
    for step, L, factor in STEPS:
        req_c = args.chroma * factor
        r, g, b, c_used, clamped = oklch_to_srgb_bytes(L, req_c, hue)
        hex_code = f"#{r:02x}{g:02x}{b:02x}"
        rows.append(
            {
                "step": step,
                "L": round(L, 4),
                "C": round(c_used, 4),
                "h": round(hue, 2),
                "clamped": clamped,
                "rgb": [r, g, b],
                "hex": hex_code,
                "wcag_vs_white": trunc_decimals(wcag_contrast((r, g, b), (255, 255, 255)), 2),
                "wcag_vs_black": trunc_decimals(wcag_contrast((r, g, b), (0, 0, 0)), 2),
            }
        )
    name = args.name
    uname = re.sub(r"[-_]+", "_", name).upper()
    pascal = "".join(p.capitalize() for p in re.split(r"[-_]+", name))
    if args.format == "json":
        print(json.dumps(rows, indent=2))
    elif args.format == "css":
        print(":root {")
        for row in rows:
            print(
                f"  --{name}-{row['step']}: oklch({row['L']} {row['C']} {row['h']}); "
                f"/* {row['hex']} | vs #fff {row['wcag_vs_white']}:1 */"
            )
        print("}")
    elif args.format == "rust":
        for row in rows:
            r, g, b = row["rgb"]
            print(
                f"/// oklch({row['L']} {row['C']} {row['h']}) -> {row['hex']} "
                f"(vs white {row['wcag_vs_white']}:1)\n"
                f"pub const {uname}_{row['step']}: [u8; 4] = [{r}, {g}, {b}, 255];"
            )
    elif args.format == "cpp":
        for row in rows:
            r, g, b = row["rgb"]
            print(
                f"// oklch({row['L']} {row['C']} {row['h']}) -> {row['hex']} "
                f"(vs white {row['wcag_vs_white']}:1)\n"
                f"inline constexpr uint32_t k{pascal}{row['step']} = "
                f"0x{r:02X}{g:02X}{b:02X}FFu;"
            )
    elif args.format == "go":
        for row in rows:
            r, g, b = row["rgb"]
            print(
                f"// oklch({row['L']} {row['C']} {row['h']}) -> {row['hex']} "
                f"(vs white {row['wcag_vs_white']}:1)\n"
                f"var {pascal}{row['step']} = "
                f"[4]uint8{{{r}, {g}, {b}, 255}}"
            )


def cmd_check(args: argparse.Namespace) -> None:
    fg_r, fg_g, fg_b, fg_oklch, fg_clamped, fg_req_c = parse_color(args.foreground)
    bg_r, bg_g, bg_b, bg_oklch, bg_clamped, bg_req_c = parse_color(args.background)
    fg = (fg_r, fg_g, fg_b)
    bg = (bg_r, bg_g, bg_b)
    ratio = wcag_contrast(fg, bg)
    lc = apca_lc(fg, bg)
    fg_info: dict[str, object] = {
        "hex": f"#{fg[0]:02x}{fg[1]:02x}{fg[2]:02x}",
        "oklch": [round(x, 4) for x in fg_oklch],
        "clamped": fg_clamped,
    }
    if fg_req_c is not None:
        fg_info["requested_C"] = round(fg_req_c, 4)
    bg_info: dict[str, object] = {
        "hex": f"#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}",
        "oklch": [round(x, 4) for x in bg_oklch],
        "clamped": bg_clamped,
    }
    if bg_req_c is not None:
        bg_info["requested_C"] = round(bg_req_c, 4)
    out = {
        "foreground": fg_info,
        "background": bg_info,
        "fg_clamped": fg_clamped,
        "bg_clamped": bg_clamped,
        "wcag22_ratio": trunc_decimals(ratio, 2),
        "passes_aa_normal_text_4_5": ratio >= 4.5,
        "passes_aa_large_or_ui_3_0": ratio >= 3.0,
        "apca_Lc": trunc_decimals(lc, 1),
        "passes_apca_body_75": abs(lc) >= 75.0,
        "passes_apca_label_60": abs(lc) >= 60.0,
        "passes_apca_ui_30": abs(lc) >= 30.0,
    }
    print(json.dumps(out, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description="OKLCh palette & contrast utility")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("ramp", help="Generate an 11-step perceptual OKLCh ramp")
    pr.add_argument("--name", default="accent")
    pr.add_argument("--hue", type=float, required=True, help="OKLCh hue in degrees [0..360)")
    pr.add_argument("--chroma", type=float, default=0.18, help="Peak mid-ramp OKLCh chroma")
    pr.add_argument("--format", choices=("css", "rust", "cpp", "go", "json"), default="css")
    pr.set_defaults(func=cmd_ramp)

    pc = sub.add_parser("check", help="Check WCAG 2.2 + APCA contrast between two colors")
    pc.add_argument("foreground", help="'#rrggbb' or 'oklch(L C H)'")
    pc.add_argument("background", help="'#rrggbb' or 'oklch(L C H)'")
    pc.set_defaults(func=cmd_check)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
