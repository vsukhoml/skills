# OKLCh / OKLab Math, Compile-Time Helpers & Data-Viz Scales (`ui-colors`)

## 1. Exact Closed-Form Pipeline (`OKLCh -> Gamut-Safe sRGB`)

Björn Ottosson's perceptual transform converts cylindrical `OKLCh(L, C, h_deg)`
into gamma-encoded 8-bit `sRGB(R, G, B)` in four deterministic steps:

1. **Polar to Cartesian OKLab:**
   $a = C \cos(h \cdot \pi / 180)$, $\quad b = C \sin(h \cdot \pi / 180)$
2. **OKLab to non-linear cone responses $(l', m', s')$, then cube:**
   - $l = (L + 0.3963377774 a + 0.2158037573 b)^3$
   - $m = (L - 0.1055613458 a - 0.0638541728 b)^3$
   - $s = (L - 0.0894841775 a - 1.2914855480 b)^3$
3. **Linear LMS to Linear sRGB $(r, g, b)$:**
   - $r = +4.0767416621 l - 3.3077115913 m + 0.2309699292 s$
   - $g = -1.2684380046 l + 2.6097574011 m - 0.3413193965 s$
   - $b = -0.0041960863 l - 0.7034186147 m + 1.7076147010 s$
   *(For GPU shaders / linear render targets, stop here after gamut clamping!)*
4. **Perceptual Gamut Clamping + sRGB Transfer Function:**
   - If $\min(r, g, b) < 0$ or $\max(r, g, b) > 1$, **do not clamp RGB channels
     independently** (that twists hue!). Binary-search $c \in [0, C]$ for 20
     iterations holding $(L, h)$ constant until $(r, g, b) \in [0, 1]^3$.
   - Encode each channel: $f(x) = 12.92 x$ for $x \le 0.0031308$, else
     $1.055 x^{1/2.4} - 0.055$, then `round(255 * f(x))`.

---

## 2. Two Zero-Runtime-Cost Ways to Use OKLCh in Any Language

### Strategy A: Build-Time / Script Codegen (Works in C, Go, Rust, C++, Swift, Kotlin, Zig, Python, TUI)

Run [`../scripts/oklch_palette.py`](../scripts/oklch_palette.py) during token
design or inside `build.rs` / `go generate` / `CMake` custom commands to emit
strongly typed constants annotated with exact `OKLCh(L, C, h)` provenance and
verified contrast ratios:

```bash
# Generate an 11-step perceptual ramp and emit Rust / C++ / Go / CSS / JSON:
python3 scripts/oklch_palette.py ramp --name accent --hue 260 --chroma 0.19 --format rust

# Verify WCAG 2.2 + APCA Lc contrast between foreground and background colors:
python3 scripts/oklch_palette.py check "oklch(0.24 0.015 260)" "oklch(0.97 0.005 260)"
```

### Strategy B: Inline Compile-Time / Init Helpers (`C++20 constexpr`, `Rust const fn`, `Go`)

For native GUI toolkits (`Qt`, `ImGui`, `WinUI`, `egui`, `iced`, `Slint`,
`ratatui`, `Bubble Tea`, `Gio`) where authors want to write `constexpr Rgba
ACCENT = oklch(0.55, 0.19, 260.0);` directly in theme modules with **zero
per-frame runtime cost**:

#### Self-Contained C++20 `constexpr` Helper (`constexpr` Without `<cmath>`)

```cpp
#include <cstdint>

struct Rgba { uint8_t r, g, b, a; constexpr uint32_t pack() const {
    return (uint32_t(r) << 24) | (uint32_t(g) << 16) | (uint32_t(b) << 8) | a;
}};

namespace detail {
constexpr double pi = 3.14159265358979323846;
constexpr double cos_rad(double x) {
    // Wrap to [-pi, pi], fold into [0, pi/2] via cos(pi - |x|) = -cos(x),
    // then evaluate 8-term Taylor (< 2.1e-11 max error across all hues; ~5.3e-13)
    while (x > pi) x -= 2.0 * pi;
    while (x < -pi) x += 2.0 * pi;
    double sign = 1.0;
    if (x < 0.0) x = -x;
    if (x > 0.5 * pi) { x = pi - x; sign = -1.0; }
    double x2 = x * x, term = 1.0, sum = 1.0;
    for (int i = 1; i <= 8; ++i) {
        term *= -x2 / ((2 * i - 1) * (2 * i));
        sum += term;
    }
    return sign * sum;
}
constexpr double sin_rad(double x) { return cos_rad(pi * 0.5 - x); }
// Newton-Raphson x^(1/2.4) = x^(5/12): solve y^12 = x^5 in double
constexpr double pow_5_12(double x) {
    if (x <= 0.0) return 0.0;
    if (x >= 1.0) return 1.0;
    double x5 = x * x * x * x * x, y = 0.7;
    for (int i = 0; i < 28; ++i) {
        double y11 = y*y*y*y*y*y*y*y*y*y*y;
        y = (11.0 * y + x5 / y11) / 12.0;
    }
    return y;
}
constexpr void oklab_to_lin_srgb(double L, double a, double b,
                                 double& r, double& g, double& bl) {
    double lp = L + 0.3963377774 * a + 0.2158037573 * b;
    double mp = L - 0.1055613458 * a - 0.0638541728 * b;
    double sp = L - 0.0894841775 * a - 1.2914855480 * b;
    double l = lp*lp*lp, m = mp*mp*mp, s = sp*sp*sp;
    r  = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
    g  = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;
}
constexpr uint8_t encode_srgb(double x) {
    double c = x <= 0.0 ? 0.0 : (x >= 1.0 ? 1.0 : x);
    double v = c <= 0.0031308 ? 12.92 * c : 1.055 * pow_5_12(c) - 0.055;
    return uint8_t(v * 255.0 + 0.5);
}
} // namespace detail

// Compile-time OKLCh -> gamut-clamped sRGB Rgba
constexpr Rgba oklch(double L, double C, double h_deg, uint8_t alpha = 255) {
    if (L <= 0.0) return {0, 0, 0, alpha};
    if (L >= 1.0) return {255, 255, 255, alpha};
    double hr = h_deg * (detail::pi / 180.0);
    double ch = detail::cos_rad(hr), sh = detail::sin_rad(hr);
    double r = 0, g = 0, b = 0;
    detail::oklab_to_lin_srgb(L, C * ch, C * sh, r, g, b);
    if (r < 0.0 || r > 1.0 || g < 0.0 || g > 1.0 || b < 0.0 || b > 1.0) {
        double lo = 0.0, hi = C;
        for (int i = 0; i < 22; ++i) {
            double mid = 0.5 * (lo + hi);
            detail::oklab_to_lin_srgb(L, mid * ch, mid * sh, r, g, b);
            if (r >= 0.0 && r <= 1.0 && g >= 0.0 && g <= 1.0 && b >= 0.0 && b <= 1.0)
                lo = mid;
            else
                hi = mid;
        }
        detail::oklab_to_lin_srgb(L, lo * ch, lo * sh, r, g, b);
    }
    return {detail::encode_srgb(r), detail::encode_srgb(g), detail::encode_srgb(b), alpha};
}
```

#### Equivalent Rust `const fn` & Go Helpers

The identical floating-point loop compiles in stable Rust `const fn oklch(l: f64,
c: f64, h_deg: f64, a: u8) -> [u8; 4]` (using the same `[-PI, PI]` wrap +
`cos(PI - |x|) = -cos(x)` half-angle fold in `const fn cos_rad(mut x: f64) -> f64`
so accuracy stays `< 2.1e-11` across all hues without `std` math intrinsics!),
converting directly into `egui::Color32::from_rgba_unmultiplied`,
`iced::Color::from_rgba8`, or TUI `ratatui::style::Color::Rgb(r, g, b)` inside
`const` theme structs:

```rust
const PI: f64 = 3.14159265358979323846;
const fn cos_rad(mut x: f64) -> f64 {
    while x > PI { x -= 2.0 * PI; }
    while x < -PI { x += 2.0 * PI; }
    let mut sign = 1.0;
    if x < 0.0 { x = -x; }
    if x > 0.5 * PI { x = PI - x; sign = -1.0; }
    let x2 = x * x;
    let (mut term, mut sum, mut i) = (1.0, 1.0, 1);
    while i <= 8 {
        term *= -x2 / (((2 * i - 1) * (2 * i)) as f64);
        sum += term;
        i += 1;
    }
    sign * sum
}
```

In Go (where `const` excludes composite `[4]uint8` arrays and loops), either emit
static `[4]uint8` literals via `scripts/oklch_palette.py ramp --format go`
(Strategy A) or evaluate the same gamut-clamped `Oklch(l, c, hDeg, alpha)` helper
once into package-level `var` tokens at startup (`cosRad` above or `math.Sincos`).

### Strategy C: Native CSS / Web Progressive Gamut Layering

On modern web runtimes, `oklch()` and `color-mix(in oklab, ...)` work natively.
Keep default tokens inside sRGB so standard monitors don't clip unpredictably,
and opt into wider Display P3 chroma explicitly where vivid status/chart accents
benefit:

```css
:root {
  --accent-solid: oklch(0.55 0.19 260);
}
@media (color-gamut: p3) {
  :root {
    --accent-solid: oklch(0.55 0.23 260);
  }
}
```

---

## 3. Recommended OKLCh Role Step Schedule (`11`-Step Reference)

| Step | Light-Mode $L$ | Chroma Factor ($k \times C_{\text{peak}}$) | Typical Semantic Role |
| --- | --- | --- | --- |
| `50` | `0.980` | `0.06` | `bg_canvas` / subtle tinted wash |
| `100` | `0.950` | `0.14` | `bg_surface_subtle` / badge fill |
| `200` | `0.905` | `0.28` | `bg_hover` / `border_subtle` |
| `300` | `0.835` | `0.48` | `border_strong` / focus halo tint |
| `400` | `0.740` | `0.75` | Chart series / dark-mode accent text |
| `500` | `0.640` | `0.95` | Brand indicator / icon fill |
| `600` | `0.545` | `1.00` | `accent_solid` button fill (passes `>= 4.5:1` with white!) |
| `700` | `0.460` | `0.90` | `accent_solid_hover` |
| `800` | `0.375` | `0.72` | `accent_text` on light surface |
| `900` | `0.285` | `0.50` | High-contrast secondary text / deep border |
| `950` | `0.195` | `0.30` | `text_primary` (or dark-mode elevated surface) |
