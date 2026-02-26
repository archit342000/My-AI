# My-AI — Design Directives (v2.0.0)

**Architect:** Visual Design System  
**Compliance Standard:** WCAG 2.1 AA  
**Philosophy:** Technical Precision · Deep Dark · Data-First · Brutalist Functionality
**Updated:** late-February 2026

---

## 1. Tech Stack & Rationale

| Layer        | Technology         | Notes |
|--------------|--------------------|-------|
| Structure    | Semantic HTML5     | Accessibility-first markup |
| Styling      | Vanilla CSS        | CSS Custom Properties for theming, no framework |
| Logic        | Vanilla JavaScript | Single `script.js`, no bundler |
| Typography   | Google Fonts (Inter, JetBrains Mono) | Variable weight |
| Markdown     | marked.js (CDN)    | Real-time streaming render |
| Highlighting | highlight.js (CDN) | Real-time code syntax highlighting |
| Icons        | Inline SVG (Lucide-style) | Stroke-width: 1.5px (Refined) |

### Methodology
- **CSS Custom Properties** (`--color-*`, `--radius-*`, `--ease-*`) for all design tokens.
- **Semantic aliases** (`--content-primary`, `--content-muted`) decoupled from primitive values.
- **Dark-First**: The default experience is "Deep Dark" (Void Black). Light mode is secondary but fully supported via `.light` class logic if needed (but UI is optimized for dark).

---

## 2. Design Tokens

### 2.1 Color System — Protocol (Electric Blue) & Void (Black)

| Token                   | Value (Dark Default) | Usage |
|-------------------------|-------------------|-------|
| `--bg-app`              | `#050505`         | Main background (Void) |
| `--bg-panel`            | `#09090b`         | Sidebars, Cards (Zinc 950) |
| `--bg-surface`          | `#121212`         | Input fields, Modals |
| `--color-primary`       | `#3B82F6`         | Electric Blue (Action) |
| `--color-primary-dim`   | `rgba(59, 130, 246, 0.15)` | Background tints |
| `--color-accent`        | `#06B6D4`         | Cyan (Vision/Data) |
| `--color-border`        | `#27272a`         | 1px Borders (Zinc 800) |
| `--color-border-active` | `#3f3f46`         | Hover borders |

### 2.2 Semantic Aliases

| Token                | Value (Dark)                   |
|----------------------|--------------------------------|
| `--content-primary`  | `#FAFAFA` (Zinc 50)            |
| `--content-secondary`| `#A1A1AA` (Zinc 400)           |
| `--content-muted`    | `#52525B` (Zinc 600)           |
| `--surface-hover`    | `rgba(255,255,255,0.03)`       |
| `--bg-user-message`  | `rgba(255,255,255,0.05)`       |
| `--border-user-message`| `var(--color-border)`        |
| `--bg-bot-message`   | `transparent`                  |

### 2.3 Functional Options & Modifiers

| Token        | Hex         | Usage            |
|-------------|-------------|------------------|
| Error       | `#ef4444`   | System Failure   |
| Success     | `#10b981`   | Operation Valid  |
| Warning     | `#f59e0b`   | Latency / Alert  |
| Info        | `#3B82F6`   | System Status    |
| Research    | `#a855f7`   | Agent Activity   |

---

## 3. Typography System

**Primary Font**: `Inter` (Readability, Body, Long-form)
**Mono Font**: `JetBrains Mono` (Headings, UI Controls, Data, Code)

| Role     | Family         | Size   | Weight | Letter Spacing |
|----------|----------------|--------|--------|----------------|
| Display  | JetBrains Mono | 64px   | 700    | -0.04em        |
| H1       | JetBrains Mono | 32px   | 600    | -0.02em        |
| H2       | JetBrains Mono | 24px   | 500    | -0.02em        |
| H3       | JetBrains Mono | 18px   | 500    | 0              |
| Body     | Inter          | 16px   | 400    | 0              |
| Label    | JetBrains Mono | 11px   | 500    | 0.05em (CAPS)  |
| Code     | JetBrains Mono | 13px   | 400    | 0              |

---

## 4. Spatial System

### 4.1 Border Radii (Technical)
| Token          | Value | Notes |
|----------------|-------|-------|
| `--radius-sm`  | 4px   | Tags, small buttons |
| `--radius-md`  | 6px   | Cards, Inputs |
| `--radius-lg`  | 8px   | Modals, Large containers |
| `--radius-full`| 99px  | Pills, Avatars |

*Departure from v1: We are abandoning large 24px/32px rounded corners for a tighter, more data-dense aesthetic.*

### 4.2 Grid System
- The background uses a subtle 20px x 20px dot grid or line grid (`rgba(255,255,255,0.03)`) to emphasize precision.
- Layouts align to a 4px baseline grid.

---

## 5. Component Library (Protocol 2.0)

### 5.1 Buttons
- **`btn-primary`**: Sharp/Minimal radius (6px). Electric Blue background. White text. `1px` border `rgba(255,255,255,0.2)`.
- **`btn-secondary`**: Transparent background. `1px` border `var(--color-border)`. Hover: `var(--surface-hover)`.
- **`btn-icon`**: Square `32x32` or `40x40`. Centered icon. Hover glow.

### 5.2 Inputs
- **`input-tech`**: Height `40px` or `48px`. Background `var(--bg-surface)`. Border `1px solid var(--color-border)`.
- Focus State: Border color becomes `--color-primary` with a `0 0 0 1px --color-primary` ring (no blur).
- Font: `JetBrains Mono` for input text.

### 5.3 Surfaces & Panels
- **`panel-glass`**: Background `rgba(9, 9, 11, 0.7)`. Backdrop filter `blur(12px)`. Border `1px solid var(--color-border)`.
- **`card-tech`**: Solid `var(--bg-panel)`. Border `1px solid var(--color-border)`.
- **Shadows**: Minimal. We rely on borders and distinct background shades rather than drop shadows.

### 5.4 Sidebar
- "Floating" glass panel on Desktop (or fixed rail).
- Width: `260px`.
- Border-right: `1px solid var(--color-border)`.
- Items: `12px` padding. Hover: `var(--surface-hover)` + `2px` left accent bar (Blue).

### 5.5 Chat Interface
- **User Message**: Aligned Right. Background `var(--bg-user-message)`. Border `1px solid var(--color-border)`. Radius `6px`.
- **Agent Message**: Aligned Left. Transparent background. No border. Full width text.
- **Thinking State**:
    - "Terminal" style loader.
    - `>_ Analyzing request...` typing effect.
    - blinking cursor block `█`.

---

## 6. Deep Research UI (Data Visualization)
- **Status Indicators**: Small dots (pulsing for active).
- **Log Stream**: Monospace font, distinct colors for [SEARCH], [VISIT], [EXTRACT].
- **Plan**: Tree structure visual. Lines connecting steps.

---

## 7. Motion
- **Instant/Snappy**: 150ms - 200ms durations.
- **Easing**: `cubic-bezier(0.16, 1, 0.3, 1)` (Expo Out) for snappy mechanical feel.
- **No bounce**. Linear or Expo only.

---

## 8. Anti-Patterns
1. **No Bloom/Glow Overuse**: Keep it legible.
2. **No gradients on text**: Solid, high-contrast text.
3. **No large rounded corners**: Maximum 8-12px for outer containers.
4. **No Skeuomorphism**: Flat, layered depth only.
