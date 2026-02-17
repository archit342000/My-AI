# LMStudioChat — Design Directives (v3.0)

**Architect:** Visual Design System  
**Compliance Standard:** WCAG 2.1 AA  
**Philosophy:** Material Design 3 (Modified) · Glassmorphism · True Dark · Motion-First  
**Updated:** February 2026

---

## 1. Tech Stack & Rationale

| Layer        | Technology         | Notes |
|--------------|--------------------|-------|
| Structure    | Semantic HTML5     | Accessibility-first markup |
| Styling      | Vanilla CSS        | CSS Custom Properties for theming, no framework |
| Logic        | Vanilla JavaScript | Single `script.js`, no bundler |
| Typography   | Google Fonts (Inter, Manrope, JetBrains Mono, Lora) | Variable weight |
| Markdown     | marked.js (CDN)    | Real-time streaming render |
| Icons        | Inline SVG (Lucide-style) | Stroke-width: 2–2.5px |

### Methodology
- **CSS Custom Properties** (`--color-*`, `--radius-*`, `--ease-*`) for all design tokens.
- **Semantic aliases** (`--content-primary`, `--content-muted`) decoupled from primitive values.
- **Light/Dark toggle** via `.dark` class on `<html>` — all overrides use `.dark` prefix.

---

## 2. Design Tokens

### 2.1 Color System — Ocean Blue (Primary)

| Token                   | Light         | Dark              |
|-------------------------|---------------|-------------------|
| `--color-primary-50`    | `#EFF6FF`     | —                 |
| `--color-primary-100`   | `#DBEAFE`     | —                 |
| `--color-primary-200`   | `#BFDBFE`     | —                 |
| `--color-primary-300`   | `#93C5FD`     | —                 |
| `--color-primary-400`   | `#60A5FA`     | —                 |
| `--color-primary-500`   | `#3B82F6`     | —                 |
| `--color-primary-600`   | `#2563EB`     | —                 |
| `--color-primary-700`   | `#1D4ED8`     | —                 |
| `--color-primary-900`   | `#1E3A8A`     | —                 |

### 2.2 Neutral System — Zinc

Full scale `50`–`900`. Dark mode surfaces use:
- Canvas: `#09090B` (Zinc-950)
- Surface: `#0F0F12`
- Elevated: `#121212`
- Variant: `#1E1E1E`

### 2.3 Semantic Aliases

| Token                | Light                        | Dark                           |
|----------------------|------------------------------|--------------------------------|
| `--content-primary`  | `var(--color-neutral-900)`   | `var(--color-neutral-50)`      |
| `--content-muted`    | `var(--color-neutral-500)`   | `var(--color-neutral-400)`     |
| `--surface-secondary`| `var(--color-neutral-100)`   | `rgba(255,255,255,0.05)`       |

### 2.4 Functional Palette

| Token        | Light       | Dark       | Usage            |
|-------------|-------------|------------|------------------|
| Rose        | `#F43F5E`   | —          | Error / Danger   |
| Teal        | `#14B8A6`   | —          | Success / Accent |

---

## 3. Typography System

| Role     | Family   | Size   | Weight | Tracking  | Line-Height |
|----------|----------|--------|--------|-----------|-------------|
| Display  | Manrope  | 72px   | 800    | -0.05em   | 1.1         |
| H1       | Manrope  | 48px   | 700    | -0.025em  | 1.2         |
| H2       | Manrope  | 30px   | 600    | -0.025em  | 1.3         |
| Body     | Inter    | 18px   | 400    | normal    | 1.75        |
| Label    | Inter    | 12px   | 600    | 0.1em     | 1.0         |
| Code     | JetBrains Mono | 14px | 400 | normal   | 1.5         |
| Serif    | Lora     | 15px   | 400    | normal    | 1.6         |

### Rules
- Headlines: **Sentence case** only.
- Labels/micro: **UPPERCASE** with letter-spacing `0.1em`.
- Never use ALL CAPS on regular body text.

---

## 4. Spatial System

### 4.1 Grid
- **Base unit:** 4px (`0.25rem`)
- All padding, margin, gap values must be multiples of 4.
- **Minimum touch target:** 44×44px.

### 4.2 Border Radii

| Token          | Value |
|----------------|-------|
| `--radius-3xl` | 24px  |
| `--radius-2xl` | 16px  |
| `--radius-xl`  | 12px  |
| `--radius-lg`  | 8px   |

### 4.3 Z-Index Layers

| Layer     | Value | Usage                      |
|-----------|-------|----------------------------|
| Base      | 0     | Flow content               |
| Content   | 10    | Sticky elements            |
| Input     | 30    | Chat input area            |
| Sidebar   | 40    | Navigation rail            |
| Mobile    | 50    | Mobile toggle              |
| Overlay   | 100   | Modals, backdrops          |
| Tooltip   | 110   | Tooltips, toasts           |

---

## 5. Motion & Animation System

### 5.1 Easing Curves

| Name           | Value                              | Usage                    |
|----------------|-------------------------------------|--------------------------|
| `--ease-spring`| `cubic-bezier(0.2, 0.8, 0.2, 1)`   | UI interactions, modals  |
| `--ease-liquid`| `cubic-bezier(0.22, 1, 0.36, 1)`   | Content expansion        |
| Standard       | `cubic-bezier(0.4, 0, 0.2, 1)`     | Material standard        |

### 5.2 Duration Scale

| Tier     | Duration | Use Cases                                |
|----------|----------|------------------------------------------|
| Instant  | 0ms      | Color changes (theme switch)             |
| Micro    | 150ms    | Opacity fades, hover glows               |
| Fast     | 200ms    | Button lifts, icon transitions           |
| Medium   | 300ms    | Modal scale, thought expand              |
| Slow     | 400ms    | Sidebar transitions, carousel slides     |
| Feature  | 600ms    | Welcome hero entrance, page transitions  |

### 5.3 Chat-Specific Animations

#### Message Entrance
```
@keyframes message-slide-in {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}
Duration: 400ms
Easing: var(--ease-spring)
```

#### Streaming Cursor (Blinking caret during generation)
```
@keyframes blink-caret {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0; }
}
Applied to: .streaming-cursor (pseudo-element)
Duration: 800ms, infinite
```

#### AI Thinking Orbit
```
@keyframes orbit-spin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
}
Applied to: .avatar-orbit
Duration: 2s, linear, infinite
Visible only when: .bot-message.thinking
```

#### Typing Indicator (3-dot pulse)
```
@keyframes typing-pulse {
    0%, 100% { transform: scale(0.8); opacity: 0.4; }
    50%      { transform: scale(1.2); opacity: 1; }
}
Stagger: 200ms per dot
Duration: 1.4s, infinite
```

#### Send Button Spin (Loading state)
```
@keyframes spin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
}
Duration: 1s, linear, infinite
```

### 5.4 Interaction Physics

| Action      | Effect                                               |
|-------------|------------------------------------------------------|
| Hover       | `translateY(-2px)` + elevated shadow                 |
| Active/Press| `scale(0.98)`                                        |
| Focus       | `box-shadow: 0 0 0 2px var(--color-primary-500)`     |
| Thinking    | Avatar orbit animation + typing dots                 |

---

## 6. Component Library

### 6.1 Buttons — Atoms

| Variant     | Background                          | Border              | Text Color     |
|-------------|-------------------------------------|----------------------|----------------|
| Primary     | Gradient (primary-600 → #3B82F6)    | none                 | white          |
| Secondary   | white                               | 1px primary-200      | primary-700    |
| Ghost       | transparent                         | none                 | neutral-500    |
| Destructive | rose-500                            | none                 | white          |

All buttons: `border-radius: 9999px`, height `48px`, `transition: all 0.2s var(--ease-spring)`.

### 6.2 Inputs

- **Text Input:** `min-height: 48px`, `border-radius: var(--radius-xl)`, focus ring `2px primary-500`.
- **Textarea (Chat):** Auto-resize, no border, transparent background, `font-size: 1rem`.
- **Range Slider:** Track `8px` tall, thumb `24px` circle with `border: 2px solid primary-600`.

### 6.3 Cards — Hardware Surface

```css
.hardware-surface {
    background: white;
    border: 1px solid var(--color-primary-100);
    box-shadow: var(--surface-shadow);
    border-radius: var(--radius-2xl);
    padding: 32px;
    transition: transform 0.2s, box-shadow 0.2s;
}
```

Hover: `translateY(-2px)` + intense shadow.

### 6.4 Chat Messages

| Element         | User                                   | Bot                        |
|-----------------|----------------------------------------|----------------------------|
| Alignment       | `flex-direction: row-reverse`          | `flex-direction: row`      |
| Content BG      | `var(--surface-secondary)` with border | transparent                |
| Border Radius   | `1.5rem`                               | none                       |
| Avatar          | Hidden                                 | Gradient blue circle       |
| Entrance Anim   | `message-slide-in 400ms`              | `message-slide-in 400ms`   |

#### Streaming State
- Bot message gets `.thinking` class while generating
- Avatar orbit becomes visible (spinning conic gradient border)
- Streaming cursor (blinking `|`) appended as pseudo-element after `.actual-content-wrapper`
- Cursor removed when generation completes

### 6.5 Thought Process / Reasoning

Collapsible container using `display: none` / `display: block` toggle.

| Element       | Style                                    |
|---------------|------------------------------------------|
| Container     | `background: neutral-100`, `border-radius: radius-xl`, `border: 1px solid primary-100` |
| Header        | `gradient background`, clickable, `cursor: pointer` |
| Body          | Hidden by default, shown when `.expanded` |
| Body Content  | `font-family: monospace`, `font-size: 13px`, `white-space: pre-wrap` |

### 6.6 Modals

- **Backdrop:** `rgba(15,23,42,0.2)` + `backdrop-filter: blur(4px)`.
- **Content:** `scale(0.95)→1` entrance, `max-width: 512px`, `border-radius: radius-2xl`.
- **Close:** Backdrop click + close button.

### 6.7 Sidebar / Navigation Rail

- **Expanded:** `width: 16rem` (256px)
- **Collapsed:** `width: 5rem` (80px)
- **Transition:** `400ms var(--ease-spring)`
- **Mobile:** `translateX(-100%)` when collapsed, `80% width` overlay when expanded
- **Resize Handle:** 4px invisible, hover reveals primary-300 accent line

#### Nav Item States
- Default: `color: var(--content-muted)`, no background
- Hover: `background: primary-50`, `color: primary-600`
- Active: same as hover + 3px left indicator bar

---

## 7. Responsive Strategy

### Breakpoints

| Name    | Width       | Behavior                                    |
|---------|-------------|---------------------------------------------|
| Mobile  | ≤768px      | Sidebar = overlay, input fixed at bottom     |
| Tablet  | ≤1024px     | Carousel 16:9, reduced padding               |
| Desktop | >1024px     | Full sidebar + 21:9 carousel                 |

### Mobile-Specific Rules
- Sidebar collapses via `transform: translateX(-100%)` (not `display: none`)
- Chat input area: `position: absolute`, `inset-inline-start: 0`
- Mobile toggle button: `position: fixed`, top-start with glassmorphism
- Visual Viewport API integration for keyboard stability: `transform: translateY(-offset)`

---

## 8. Visual Fidelity

### Shadows
- **Never** use pure black shadows for brand elements.
- Inject 20–30% of primary color: `rgba(37, 99, 235, 0.08)` → `rgba(37, 99, 235, 0.15)`.

### Glassmorphism
- **Layer 50+ elements** use `backdrop-filter: blur(12px–16px)`.
- Semi-transparent backgrounds: `rgba(255,255,255,0.4)` (light) / `rgba(255,255,255,0.05)` (dark).

### Optical Borders (Dark Mode)
- All surfaces: `box-shadow: inset 0 0 0 1px rgba(255,255,255,0.05)`.
- Active elements: `border-color: rgba(37, 99, 235, 0.2)`.

### Logical Properties
- **Required:** Use `inset-inline-start`, `inset-inline-end`, `margin-inline-start`, `padding-inline-start`.
- **Forbidden:** `left`, `right`, `margin-left`, `margin-right`, `padding-left`, `padding-right` (except in rare OS-level overrides).

---

## 9. Anti-Patterns — The "Never" List

1. **No flat borders** on cards without shadow or inner ring.
2. **No default black shadows** on colored elements — always inject brand color.
3. **No CSS frameworks** (Tailwind, Bootstrap) — vanilla CSS only.
4. **No React/Angular/Vue** — vanilla JS with DOM APIs.
5. **No un-animated state changes** — every visibility/position change needs a transition.
6. **No `display: none` for animated elements** — use `opacity + visibility + transform` or `max-height: 0`.
7. **No hardcoded colors in JS** — always reference CSS custom properties.
8. **No placeholder images** — generate real assets or use SVG.

---

## 10. Accessibility

- All interactive elements: minimum `44×44px` touch target.
- Focus rings: visible `2px` ring with `offset-2` in primary color.
- Color contrast: WCAG AA (4.5:1 for text, 3:1 for UI elements).
- `aria-label` on icon-only buttons.
- Keyboard navigable: modals trap focus, Escape closes overlays.
- `prefers-reduced-motion`: disable orbit, typing, and entrance animations.

---

## 11. Performance

- **Single CSS file** — no splits, no imports except Google Fonts.
- **Single JS file** — no modules, inline event delegation.
- **Streaming SSE** for chat — no polling, no WebSocket.
- **`requestAnimationFrame`** for scroll syncing.
- **`scrollbar-width: thin`** for native thin scrollbars.
- **`will-change: transform`** on animated elements sparingly.
