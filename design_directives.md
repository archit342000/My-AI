# My-AI — Design Directives (v2.1.0)

**Architect:** Visual Design System — "Advanced Technical"
**Compliance:** WCAG 2.1 AA
**Aesthetic:** Depth · Subtle Gradients · Precision · Atmospheric
**Updated:** late-February 2026

---

## 1. Tech Stack & Rationale

| Layer        | Technology         | Notes |
|--------------|--------------------|-------|
| Structure    | Semantic HTML5     | Accessibility-first markup |
| Styling      | Vanilla CSS        | CSS Custom Properties for theming, no framework |
| Logic        | Vanilla JavaScript | Single `script.js`, no bundler |
| Typography   | Google Fonts (Outfit, JetBrains Mono) | Variable weight |
| Markdown     | marked.js (CDN)    | Real-time streaming render |
| Highlighting | highlight.js (CDN) | Real-time code syntax highlighting |
| Icons        | Inline SVG (Lucide-style) | Stroke-width: 1.5px (Thinner, Technical) |

### Methodology
- **CSS Custom Properties**: Strict tokenization.
- **Deep Atmosphere**: Backgrounds use subtle gradients to avoid "flatness".
- **Glassmorphism**: High blur values (`20px`) on overlays for depth.

---

## 2. Design Tokens

### 2.1 Color System — Electric Blue (Primary) & Carbon (Neutral)

| Token                   | Hex / Value   | Usage |
|-------------------------|---------------|-------|
| `--bg-app`              | `#050505`     | Main Background |
| `--bg-surface`          | `#0A0A0A`     | Panels / Cards |
| `--gradient-surface`    | `linear-gradient(...)` | Surface Depth |
| `--border-subtle`       | `rgba(255,255,255,0.06)` | Dividers |
| `--border-highlight`    | `rgba(255,255,255,0.08)` | Top edge lighting |
| `--color-primary`       | `#3B82F6`     | Electric Blue |
| `--color-accent`        | `#06B6D4`     | Cyan |

### 2.2 Semantic Aliases

| Token                | Value                        |
|----------------------|------------------------------|
| `--content-primary`  | `#EDEDED`                    |
| `--content-secondary`| `#A1A1AA`                    |
| `--shadow-depth`     | `0 10px 30px rgba(0,0,0,0.5)`|

---

## 3. Typography System

**Primary Font:** `Outfit` (Headings, Body, Labels) — Clean, modern sans-serif.
**Monospace Font:** `JetBrains Mono` (Code, Data Values) — Technical precision.

| Role     | Family   | Size   | Weight | Tracking  |
|----------|----------|--------|--------|-----------|
| Display  | Outfit   | 56px   | 700    | -0.03em   |
| H1       | Outfit   | 32px   | 600    | -0.02em   |
| Body     | Outfit   | 16px   | 400    | normal    |
| Label    | Outfit   | 12px   | 600    | 0.03em    |
| Code     | JetBrains| 14px   | 400    | normal    |

---

## 4. Spatial System

### 4.1 Border Radii
| Token          | Value |
|----------------|-------|
| `--radius-sm`  | 4px   |
| `--radius-md`  | 6px   |
| `--radius-lg`  | 10px  |
| `--radius-xl`  | 16px  |

### 4.2 Depth & Effects
- **Inner Glows**: Use inset shadows to define edges without harsh borders.
- **Top Highlight**: 1px top border to simulate light source.

---

## 5. Component Directives

### 5.1 Buttons
- **Shape**: Rectangular with `--radius-md`.
- **Style**: Gradient background for primary. Subtle glow on hover.

### 5.2 Inputs
- **Style**: Dark background, inset shadow for depth.
- **Focus**: Blue glow ring.

### 5.3 Surfaces
- **Background**: `#0A0A0A` + Subtle Gradient.
- **Border**: Low contrast (`0.06 alpha`) + Top Highlight.

### 5.4 Sidebar
- **Appearance**: Glassy (`backdrop-filter: blur(20px)`).
- **Items**: Friendly sans-serif font.

### 5.5 Chat Interface
- **User Message**: Dark grey surface, slightly rounded (`--radius-xl`).
- **Bot Message**: Clean markdown.
- **Thought Process**: Collapsible block, secondary background.

---

## 6. Motion
- **Speed**: `0.2s` - `0.3s`.
- **Curve**: Smooth (`cubic-bezier(0.4, 0, 0.2, 1)`).
- **Type**: Slide + Fade.

---

## 7. Anti-Patterns
1.  **No Flat Colors**: Avoid pure hex fills on large surfaces; use gradients.
2.  **No "Terminal" Overload**: Don't use monospaced fonts for general UI text.
3.  **No Gimmicky Jargon**: Keep language natural ("Settings", not "Parameters").
