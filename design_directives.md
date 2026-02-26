# My-AI — Design Directives (v2.0.0)

**Architect:** Visual Design System — "Protocol 2.0"
**Compliance:** WCAG 2.1 AA
**Aesthetic:** Technical Precision · Deep Dark · HUD/Cybernetics · Sharp Geometries
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
- **CSS Custom Properties**: Strict tokenization for "Technical" feel.
- **Deep Dark Default**: The interface is natively dark. Light mode is secondary or high-contrast utility.
- **Sharp Geometry**: Border radii are tight (4px - 8px). Circles are reserved for status indicators only.

---

## 2. Design Tokens

### 2.1 Color System — Electric Blue (Primary) & Carbon (Neutral)

| Token                   | Hex / Value   | Usage |
|-------------------------|---------------|-------|
| `--bg-app`              | `#050505`     | Main Application Background |
| `--bg-surface`          | `#0A0A0A`     | Panels / Cards |
| `--bg-surface-2`        | `#171717`     | Hovers / Secondary inputs |
| `--border-subtle`       | `rgba(255,255,255,0.08)` | Dividers |
| `--border-contrast`     | `rgba(255,255,255,0.15)` | Active Borders |
| `--color-primary`       | `#3B82F6`     | Electric Blue |
| `--color-accent`        | `#06B6D4`     | Cyan (Data/Vision) |
| `--color-success`       | `#10B981`     | Emerald (Operations) |
| `--color-warning`       | `#F59E0B`     | Amber (Alerts) |
| `--color-danger`        | `#EF4444`     | Rose (Destructive) |

### 2.2 Semantic Aliases (Dark Mode First)

| Token                | Value                        |
|----------------------|------------------------------|
| `--content-primary`  | `#EDEDED`                    |
| `--content-secondary`| `#A1A1AA`                    |
| `--content-tertiary` | `#52525B`                    |
| `--border-focus`     | `var(--color-primary)`       |

---

## 3. Typography System

**Primary Font:** `Outfit` (Headings, Body)
**Monospace Font:** `JetBrains Mono` (UI Elements, Data, Code, Labels)

| Role     | Family   | Size   | Weight | Tracking  | Line-Height |
|----------|----------|--------|--------|-----------|-------------|
| Display  | Outfit   | 64px   | 600    | -0.04em   | 1.1         |
| H1       | Outfit   | 32px   | 600    | -0.02em   | 1.2         |
| H2       | Outfit   | 24px   | 500    | -0.01em   | 1.3         |
| Body     | Outfit   | 16px   | 400    | normal    | 1.6         |
| UI Mono  | JetBrains| 13px   | 500    | 0.02em    | 1.4         |
| Label    | JetBrains| 11px   | 600    | 0.05em    | 1.0         |
| Code     | JetBrains| 14px   | 400    | normal    | 1.5         |

---

## 4. Spatial System

### 4.1 Border Radii (Sharp)
| Token          | Value |
|----------------|-------|
| `--radius-sm`  | 2px   |
| `--radius-md`  | 4px   |
| `--radius-lg`  | 8px   |
| `--radius-xl`  | 12px  |
| `--radius-full`| 9999px| (Only for status dots/avatars)

### 4.2 Depth & Effects
| Effect         | Value |
|----------------|-------|
| `--glow-primary`| `0 0 20px rgba(59, 130, 246, 0.15)` |
| `--glow-accent` | `0 0 20px rgba(6, 182, 212, 0.15)` |
| `--border-glow` | `0 0 0 1px rgba(255,255,255,0.1)` |

---

## 5. Component Directives

### 5.1 Buttons
- **Shape**: Rectangular with `--radius-md` (4px).
- **Style**:
    - **Primary**: Solid Electric Blue background, white text. No gradient.
    - **Secondary**: Transparent background, 1px border (`--border-contrast`). Hover: White 5% fill.
    - **Ghost**: Text only, hover background.
- **Typography**: JetBrains Mono, uppercase or sentence case, 13px.

### 5.2 Inputs
- **Shape**: `--radius-md` (4px).
- **Style**: Dark background (`--bg-surface-2`), 1px border (`--border-subtle`).
- **Focus**: Border turns Primary Color + Box Shadow Glow.

### 5.3 Surfaces (Cards/Panels)
- **Background**: `#0A0A0A` or `#111111`.
- **Border**: 1px solid `rgba(255,255,255,0.06)`.
- **Shadow**: Minimal. Depth is achieved via borders and subtle inset gradients.

### 5.4 Sidebar
- **Appearance**: "Console" aesthetics.
- **Border**: Right border 1px solid `--border-subtle`.
- **Items**:
    - Active: Left border strip (2px) + subtle background.
    - Hover: Text brightens.

### 5.5 Chat Interface
- **User Message**:
    - Align: Right.
    - Background: `--bg-surface-2`.
    - Border: 1px solid `--border-subtle`.
    - Radius: `--radius-lg` (8px).
- **Bot Message**:
    - Align: Left.
    - Background: Transparent.
    - Typography: Clean, legible markdown.
- **Thought Process**:
    - "Collapsible Terminal" style.
    - Monospace font.
    - Darker background block.

### 5.6 Deep Research UI
- **Activity Feed**: Terminal-like log.
- **Status Indicators**: Small glowing dots (Green/Amber/Red).
- **Cards**: "Data Plate" aesthetic. Top border highlight.

---

## 6. Motion
- **Speed**: Snappy (`150ms` - `250ms`).
- **Curve**: `cubic-bezier(0.16, 1, 0.3, 1)` (Exposure).
- **Type**:
    - Fade + Scale (0.98 -> 1.00).
    - Slide (Transform Y 4px -> 0).
    - No bouncy springs.

---

## 7. Anti-Patterns
1.  **No Pill Shapes** for main containers/buttons (reserved for tags).
2.  **No Large Drop Shadows**. Use Glows/Borders instead.
3.  **No Gradients** on backgrounds (except subtle localized glows).
4.  **No Serif Fonts**. Keep it strictly Sans/Mono.
