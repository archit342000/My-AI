# My-AI — Design Directives (v2.0.0)

**Architect:** Visual Design System  
**Compliance Standard:** WCAG 2.1 AA  
**Philosophy:** Advanced Agentic AI · Technical Precision · Deep Dark · Data-First
**Updated:** late-February 2026

---

## 1. Tech Stack & Rationale

| Layer        | Technology         | Notes |
|--------------|--------------------|-------|
| Structure    | Semantic HTML5     | Accessibility-first markup |
| Styling      | Vanilla CSS        | CSS Custom Properties for theming, no framework |
| Logic        | Vanilla JavaScript | Single `script.js`, no bundler |
| Typography   | Google Fonts (JetBrains Mono, Outfit) | Technical bias |
| Markdown     | marked.js (CDN)    | Real-time streaming render |
| Highlighting | highlight.js (CDN) | Real-time code syntax highlighting |
| Icons        | Inline SVG (Lucide-style) | Stroke-width: 1.5–2px (Sharp) |

### Methodology
- **CSS Custom Properties** (`--color-*`, `--radius-*`, `--ease-*`) for all design tokens.
- **Semantic aliases** (`--content-primary`, `--content-muted`) decoupled from primitive values.
- **Dark Mode Default** — The interface is primarily dark ("Void"). Light mode is a high-contrast clinical alternative.

---

## 2. Design Tokens

### 2.1 Color System — Void Black (Base) & Electric Blue (Accent)

| Token                   | Light (Clinical) | Dark (Void)       |
|-------------------------|---------------|-------------------|
| `--color-primary-50`    | `#F0F4FF`     | `#0A0F1E`         |
| `--color-primary-100`   | `#DBEAFE`     | `#111827`         |
| `--color-primary-200`   | `#BFDBFE`     | `#1F2937`         |
| `--color-primary-300`   | `#93C5FD`     | `#374151`         |
| `--color-primary-400`   | `#60A5FA`     | `#4B5563`         |
| `--color-primary-500`   | `#3B82F6`     | `#3B82F6` (Electric) |
| `--color-primary-600`   | `#2563EB`     | `#60A5FA`         |
| `--color-primary-700`   | `#1D4ED8`     | `#93C5FD`         |
| `--color-primary-900`   | `#1E3A8A`     | `#BFDBFE`         |
| `--bg-base`             | `#F8FAFC`     | `#000000`         |
| `--bg-surface`          | `#FFFFFF`     | `#050505`         |

### 2.2 Semantic Aliases

| Token                | Light                        | Dark                           |
|----------------------|------------------------------|--------------------------------|
| `--content-primary`  | `#0F172A`                    | `#F8FAFC`                      |
| `--content-muted`    | `#64748B`                    | `#94A3B8`                      |
| `--surface-secondary`| `#F1F5F9`                    | `#0A0A0A`                      |
| `--bg-user-message`  | `#E2E8F0`                    | `#171717`                      |
| `--text-user-message`| `#0F172A`                    | `#F8FAFC`                      |
| `--border-user-message` | `#CBD5E1`                 | `#262626`                      |
| `--bg-input`         | `#FFFFFF`                    | `#0A0A0A`                      |
| `--border-input`     | `#94A3B8`                    | `#3B82F6`                      |

### 2.3 Functional Options & Modifiers

| Token        | Light       | Dark       | Usage            |
|-------------|-------------|------------|------------------|
| Rose        | `#DC2626`   | `#EF4444`  | Error / Danger   |
| Teal        | `#0D9488`   | `#14B8A6`  | Success / Accent |
| Amber       | `#D97706`   | `#F59E0B`  | Warning          |
| Emerald     | `#059669`   | `#10B981`  | Complete / OK    |
| Violet      | `#7C3AED`   | `#8B5CF6`  | Deep Research    |
| Cyan        | `#0891B2`   | `#06B6D4`  | Vision           |

---

## 3. Typography System

| Role     | Family         | Size   | Weight | Tracking  | Line-Height |
|----------|----------------|--------|--------|-----------|-------------|
| Display  | JetBrains Mono | 48px   | 700    | -0.02em   | 1.1         |
| H1       | Outfit         | 32px   | 600    | -0.01em   | 1.2         |
| H2       | Outfit         | 24px   | 600    | normal    | 1.3         |
| Body     | Outfit         | 16px   | 400    | normal    | 1.6         |
| Mono     | JetBrains Mono | 14px   | 400    | normal    | 1.5         |
| Label    | JetBrains Mono | 11px   | 600    | 0.05em    | 1.0         |

---

## 4. Spatial System

### 4.1 Border Radii — Technical & Sharp
| Token          | Value |
|----------------|-------|
| `--radius-sm`  | 2px   |
| `--radius-md`  | 4px   |
| `--radius-lg`  | 6px   |
| `--radius-xl`  | 8px   |

### 4.2 Z-Index Layers
| Layer     | Value | Usage                                |
|-----------|-------|--------------------------------------|
| Base      | 0     | Flow content                         |
| Content   | 10    | Sticky elements                      |
| Input     | 30    | Chat input area                      |
| Sidebar   | 40    | Control Rail                         |
| Mobile    | 50    | Mobile toggle menu                   |
| Overlay   | 100   | Modals, backdrops                    |
| Tooltip   | 110   | Tooltips                             |
| Max Z     | 9999  | Blocking UI                          |

---

## 5. Motion & Animation System

### 5.1 Easing Curves
| Name           | Value                              | Usage                    |
|----------------|-------------------------------------|--------------------------|
| `--ease-tech`  | `cubic-bezier(0.16, 1, 0.3, 1)`    | UI interactions (Snappy) |
| `--ease-linear`| `linear`                           | Progress, loops          |

### 5.2 Animations
- **`glitch-in`**: Content snaps in with slight opacity flicker.
- **`scanline`**: Subtle horizontal scan moving down overlay.
- **`blink-caret`**: Block cursor blinking.
- **`data-stream`**: Text revealing character by character.

---

## 6. Component Library (Advanced Agentic)

### 6.1 Buttons
- **`btn-primary`**: Sharp corners (`4px`), solid Electric Blue or Void border. Text uppercase `JetBrains Mono`. Hover effect: Invert colors or glow.
- **`btn-secondary`**: Transparent with 1px border. Hover: Subtle background fill.
- **`btn-ghost`**: No border, text only. Hover: Underline or bracket reveal `[ Action ]`.
- **`utility-btn`**: Small, icon-only or compact text.

### 6.2 Inputs ("Console")
- **`input-terminal`**: Dark background, monospace text, blinking block cursor. Active state has a glowing left border or bracket.
- **`textarea`**: Fluid height, looks like a code editor pane.

### 6.3 Surface Containers
- **`panel-surface`**: Deep black/grey background. 1px border (`#333`). No shadow, or very sharp drop shadow.
- **`hud-block`**: Semi-transparent, glass-like but technical (grid background optional).

### 6.4 Sidebar (Control Rail)
- **Compact**: 64px width. Icons only.
- **Expanded**: 240px width. Technical list items.
- **Active State**: Left border accent (`3px` Electric Blue), subtle background highlight.

### 6.5 Chat Messages ("Logs")
- **User Log**: Right-aligned, dark grey block, monospace timestamp.
- **Agent Log**: Left-aligned, transparent or deep blue tint. No "speech bubble" tails. Technical header (`[AGENT-01]`, timestamp).
- **Thinking**: Collapsible "Terminal" block showing raw thought process stream in `JetBrains Mono`.

### 6.6 Deep Research UI
- **Plan Card**: Looks like a manifest file or checklist.
- **Activity Feed**: Terminal-like log stream. Green/Red status indicators.
- **Live Indicator**: Pulsing dot or "scanning" radar animation.

### 6.7 Settings Modals
- **Style**: Floating HUD window. 1px borders, backdrop blur.
- **Tabs**: Segmented control style (Underline or Block highlight).

---

## 7. Responsive Strategy

### Breakpoints
| Name    | Width       | Behavior                                    |
|---------|-------------|---------------------------------------------|
| Mobile  | ≤768px      | Rail hidden, Input docked                   |
| Desktop | >1024px     | Persistent Control Rail                     |

### Mobile-Specific
- **Terminal Input**: Fixed at bottom, max height 40% screen.
- **Menu**: Slide-over panel (Glass effect).

---

## 8. Visual Fidelity

### Borders & Glows
- **Borders**: 1px solid is standard.
- **Glows**: `box-shadow: 0 0 10px rgba(59, 130, 246, 0.5)` for active elements.

### Anti-Patterns
1. **No rounded corners > 8px**.
2. **No skeumorphism**.
3. **No "friendly" bounce animations**.
4. **No heavy drop shadows** (prefer glows or flat borders).

---

## 9. Accessibility
- **Contrast**: High contrast (WCAG AAA preferred for text).
- **Focus**: Visible, sharp focus rings (Electric Blue).
- **Motion**: Respect `prefers-reduced-motion` by disabling glitch/scanline effects.
