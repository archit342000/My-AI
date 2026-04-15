# My-AI — Design Directives

**Architect:** Visual Design System  
**Compliance Standard:** WCAG 2.1 AA  
**Philosophy:** Aurora + Obsidian · Atmospheric Glass · Monochrome + Ocean Blue · True Dark · Motion-First
**Updated:** March 2026

---

## 1. Tech Stack & Rationale

| Layer        | Technology         | Notes |
|--------------|--------------------|-------|
| Structure    | Semantic HTML5     | Accessibility-first markup |
| Styling      | Vanilla CSS        | CSS Custom Properties for theming, no framework |
| Logic        | Vanilla JavaScript | Single `script.js`, no bundler |
| Typography   | Google Fonts (Outfit, JetBrains Mono, Lora) | Variable weight (100–900) |
| Markdown     | marked.js (CDN)    | Real-time streaming render |
| Highlighting | highlight.js (CDN) | Real-time code syntax highlighting |
| Icons        | Inline SVG (Lucide-style) | Stroke-width: 2–2.5px |

### Methodology
- **CSS Custom Properties** (`--accent-*`, `--glass-*`, `--radius-*`, `--ease-*`) for all design tokens.
- **Semantic aliases** (`--content-primary`, `--content-muted`, `--content-ghost`) decoupled from primitive values.
- **Light/Dark/System Toggle** via `.dark` class on `<html>` — all overrides use `.dark` prefix. Variable assignment happens within `:root` and `.dark` block. Theme preference is persisted in LocalStorage.

---

## 2. Design Tokens

### 2.1 Color System — Ocean Blue (Accent) & Slate (Neutral)

The v2.0.0 Aurora + Obsidian system uses a **single accent color** — Ocean Blue — across the entire UI. The full Ocean Blue scale (`--color-primary-*`) is retained only as legacy compatibility aliases; all new code must use the `--accent-*` token family.

#### Accent Tokens (Canonical)

| Token              | Value                         | Usage                           |
|--------------------|-------------------------------|---------------------------------|
| `--accent`         | `#3B82F6`                     | Primary action, active states   |
| `--accent-hover`   | `#2563EB`                     | Hover/pressed states            |
| `--accent-light`   | `#60A5FA`                     | Dark-mode foreground accent     |
| `--accent-subtle`  | `rgba(59, 130, 246, 0.08)`    | Tinted hover backgrounds        |
| `--accent-border`  | `rgba(59, 130, 246, 0.15)`    | Accent-tinted borders           |
| `--accent-glow`    | `rgba(59, 130, 246, 0.25)`    | Glow / ring effects             |
| `--accent-rgb`     | `59, 130, 246`                | For inline `rgba()` composition |

#### Neutral Scale (Slate)

| Token                  | Value      |
|------------------------|------------|
| `--color-neutral-50`   | `#F8FAFC`  |
| `--color-neutral-100`  | `#F1F5F9`  |
| `--color-neutral-200`  | `#E2E8F0`  |
| `--color-neutral-300`  | `#CBD5E1`  |
| `--color-neutral-400`  | `#94A3B8`  |
| `--color-neutral-500`  | `#64748B`  |
| `--color-neutral-600`  | `#475569`  |
| `--color-neutral-700`  | `#334155`  |
| `--color-neutral-800`  | `#1E293B`  |
| `--color-neutral-900`  | `#0F172A`  |

#### Legacy Compatibility Aliases

The old `--color-primary-*` tokens are remapped to the blue scale for JS compatibility:

| Legacy Token            | Mapped Value |
|-------------------------|--------------|
| `--color-primary-500`   | `#3B82F6`    |
| `--color-primary-600`   | `#2563EB`    |
| `--color-primary-400`   | `#60A5FA`    |
| `--color-primary-500-rgb` | `59, 130, 246` |

### 2.2 Glass Surface Tokens

These tokens define the frosted-glass aesthetic central to Aurora + Obsidian. Every panel in the UI (sidebar, input bar, modals, toasts, thought containers, dropdowns) uses them.

| Token                  | Light                              | Dark                              |
|------------------------|------------------------------------|-----------------------------------|
| `--glass-bg`           | `rgba(255, 255, 255, 0.85)`        | `rgba(12, 12, 15, 0.92)`         |
| `--glass-border`       | `rgba(59, 130, 246, 0.08)`         | `rgba(59, 130, 246, 0.08)`       |
| `--glass-blur`         | `blur(20px) saturate(160%)`        | `blur(20px) saturate(160%)`       |
| `--glass-blur-sidebar` | `= --glass-blur`                   | `= --glass-blur`                  |

### 2.3 Ambient Background Tokens

A fixed `#ambient-bg` div renders two large radial gradient orbs that drift slowly across the viewport. In dark mode they are extremely subtle; in light mode they are warmer and more present.

| Token             | Light                            | Dark                             |
|-------------------|----------------------------------|----------------------------------|
| `--ambient-orb-1` | `rgba(59, 130, 246, 0.6)`        | `rgba(59, 130, 246, 0.35)`      |
| `--ambient-orb-2` | `rgba(59, 130, 246, 0.5)`        | `rgba(59, 130, 246, 0.3)`       |
| `--bg-base`       | `#F8F7F4` (warm off-white)       | `var(--bg-dark)` (`#09090B`)     |

### 2.4 Semantic Aliases

| Token                  | Light                              | Dark                              |
|------------------------|------------------------------------|------------------------------------|
| `--content-primary`    | `var(--color-neutral-900)`         | `var(--color-neutral-50)`          |
| `--content-muted`      | `var(--color-neutral-600)`         | `var(--color-neutral-300)`         |
| `--content-ghost`      | `var(--color-neutral-400)`         | `var(--color-neutral-700)`         |
| `--surface-secondary`  | `var(--color-neutral-100)`         | `rgba(255, 255, 255, 0.04)`       |
| `--bg-sidebar`         | `var(--glass-bg)`                  | `var(--glass-bg)`                  |
| `--sidebar-border-color` | `rgba(59, 130, 246, 0.12)`      | `rgba(255, 255, 255, 0.08)`       |
| `--bg-header`          | `rgba(248, 247, 244, 0.4)`        | `rgba(9, 9, 11, 0.4)`             |
| `--border-header`      | `var(--glass-border)`              | `var(--glass-border)`              |
| `--bg-chat-display`    | `rgba(0, 0, 0, 0.02)`             | `rgba(255, 255, 255, 0.02)`       |
| `--border-chat-display`| `var(--glass-border)`              | `var(--glass-border)`              |
| `--border-subtle`      | `rgba(59, 130, 246, 0.08)`        | `rgba(255, 255, 255, 0.06)`       |
| `--bg-user-message`    | `var(--glass-bg)`                  | `rgba(255, 255, 255, 0.04)`       |
| `--text-user-message`  | `var(--content-primary)`           | `#F8FAFC`                          |
| `--border-user-message`| `var(--glass-border)`              | `rgba(255, 255, 255, 0.08)`       |
| `--shadow-user-message`| `0 1px 4px rgba(59, 130, 246, 0.06)` | `none`                          |
| `--bg-input`           | `rgba(255, 255, 255, 0.85)`       | `rgba(255, 255, 255, 0.04)`       |
| `--border-input`       | `var(--accent)`                    | `var(--accent)`                    |

### 2.5 Functional Colors & Modifiers

| Token        | Value       | Usage            |
|-------------|-------------|------------------|
| Rose        | `#F43F5E`   | Error / Danger   |
| Emerald     | `#10B981`   | Success / OK     |
| Amber       | `#F59E0B`   | Warning          |
| Blue      | `#3B82F6`   | Primary Accent   |

---

## 3. Typography System

All sizes use responsive `rem` and `clamp()` units (not fixed `px`). Bold weight contrast (200↔800) is a signature feature.

| Role     | Family         | Size                         | Weight | Tracking   | Line-Height |
|----------|----------------|------------------------------|--------|------------|-------------|
| Display  | Outfit         | `clamp(3rem, 6vw, 5rem)`    | 800    | -0.05em    | 1.1         |
| H1       | Outfit         | `1.75rem`                    | 800    | -0.03em    | 1.2         |
| H2       | Outfit         | `1.125rem`                   | 700    | -0.02em    | 1.3         |
| Body     | Outfit         | `1rem`                       | 400    | normal     | 1.7         |
| Label    | Outfit         | `0.6875rem`                  | 600    | 0.15em     | 1.0         |
| Code     | JetBrains Mono | `0.875rem`                   | 400    | normal     | 1.5         |
| Serif    | Lora           | `15px`                       | 400    | normal     | 1.6         |

**Signature Label Style**: Section labels (RECENT CHATS, THOUGHT PROCESS, model attributions) use `font-weight: 600`, `letter-spacing: 0.15em`, `text-transform: uppercase` for a clean, structured appearance.

### Code Block Theme Integration
- Highlight.js automatically switches between `github.min.css` and `github-dark.min.css` based on the `.dark` class state for robust highlighting.
- Inline code uses `rgba(var(--accent-rgb), 0.1)` background with `var(--accent-hover)` text color (light) or `var(--accent-light)` (dark).

---

## 4. Spatial System

### 4.1 Border Radii
| Token          | Value  |
|----------------|--------|
| `--radius-3xl` | `24px` |
| `--radius-2xl` | `16px` |
| `--radius-xl`  | `12px` |
| `--radius-lg`  | `8px`  |
| `--radius-full`| `9999px`|

### 4.2 Shadows

| Token                      | Value                                              |
|----------------------------|----------------------------------------------------|
| `--surface-shadow`         | `0 4px 20px -2px rgba(59, 130, 246, 0.06)`         |
| `--surface-shadow-intense` | `0 10px 25px -5px rgba(59, 130, 246, 0.12)`        |

All shadows use blue tinting — never pure black on brand elements.

### 4.3 Z-Index Layers
| Layer     | Token           | Value  | Usage                                |
|-----------|-----------------|--------|--------------------------------------|
| Base      | `--z-base`      | `0`    | Flow content                         |
| Content   | `--z-content`   | `10`   | Sticky elements                      |
| Input     | —               | `30`   | Chat input area                      |
| Header    | `--z-header`    | `40`   | Sticky chat title header             |
| Sidebar   | `--z-sidebar`   | `1000` | Navigation rail / Sidebar            |
| Overlay   | `--z-overlay`   | `10000`| Modals, backdrops                    |
| Tooltip   | `--z-tooltip`   | `11000`| Tooltips, dropdowns, toasts          |
| Max Z     | —               | `2147483647` | Model Switch Overlay (blocking) |

---

## 5. Motion & Animation System

### 5.1 Easing Curves
| Name           | Value                              | Usage                    |
|----------------|-------------------------------------|--------------------------| 
| `--ease-spring`| `cubic-bezier(0.2, 0.8, 0.2, 1)`   | UI interactions, modals  |
| `--ease-liquid`| `cubic-bezier(0.22, 1, 0.36, 1)`   | Content expansion        |
| Standard       | `cubic-bezier(0.4, 0, 0.2, 1)`     | Material standard        |

### 5.2 Keyframes
All animations are defined in CSS — never in JS logic:

| Name                    | Behaviour                                                       | Duration / Timing              |
|-------------------------|-----------------------------------------------------------------|--------------------------------|
| `ambient-orb-1-drift`   | Primary ambient orb drifts via translate/scale/rotate          | `45s ease-in-out infinite alternate` |
| `ambient-orb-2-drift`   | Secondary ambient orb drifts via translate/scale/rotate        | `38s ease-in-out infinite alternate-reverse` |
| `message-slide-in`      | Messages rise from bottom (`translateY(12px) → 0`)              | `400ms --ease-spring`          |
| `blink-caret`           | AI generating cursor pulsing                                    | `800ms steps(2) infinite`      |
| `orbit-spin`            | AI avatar conic-gradient ring                                   | `2s linear infinite`           |
| `typing-pulse`          | Loading dots scale variation `(0.7 → 1.3)`                     | `1.4s infinite --ease-spring`  |
| `spinner-spin` / `spin` | Simple rotate (`360deg`)                                        | `1s linear infinite`           |
| `shimmer`               | Skeleton load / shimmer text                                    | `1.5s ease-in-out infinite`    |
| `activitySlideIn`       | Research items popping in (`translateY(8px) → 0`)               | `0.3s ease-out`                |
| `liveIndicatorPulse`    | Deep Research glowing pulse loop                                | `2.5s infinite ease-in-out`    |
| `planSpin`              | Planning loader spinner                                         | `0.8s linear infinite`         |
| `checkPop`              | Complete mark scale pop (`0 → 1.3 → 1`)                        | `0.3s ease-out`                |
| `slideUp`               | Dropdown/toast slide up (`translateY(10-20px) → 0`)             | `0.3s --ease-spring`           |
| `reasoning-pulse`       | Thought container glow pulse while AI reasons                   | `2s ease-in-out infinite`      |
| `thought-dot-bounce`    | Small "Thinking..." dots bounce                                 | `1.4s ease-in-out infinite`    |
| `greeting-entrance`     | Welcome hero fade-in from below (`translateY(20px) → 0`)       | `0.8s --ease-liquid`           |
| `fadeScale`              | Tab content fade in (`scale(0.98) → 1`)                        | `0.2s ease-out`                |
| `banner-slide-in`       | Temp chat banner entrance                                       | `300ms --ease-spring`          |

---

## 6. Component Library (Comprehensive)

### 6.1 Buttons
- **`btn-primary`**: Full rounded `9999px`, height `48px`, `var(--accent)` background. Box shadow with `rgba(var(--accent-rgb), 0.3)`. Hover → `--accent-hover`, lift `-1px`, intensified shadow.
- **`btn-secondary`**: Transparent background, `1px solid var(--accent-border)`. Hover → `var(--accent-subtle)` background. Dark mode uses `--accent-light` text.
- **`btn-ghost`**: No border/bg initially. Hover → `var(--accent-subtle)` bg. Active state → `rgba(var(--accent-rgb), 0.1)` bg.
- **`btn-approve`** (Research): Accent-colored pill, inline footprint.
- **`pagination-btn`**: `40px` circles with glass background and glass border. Active → `var(--accent)` bg.
- **Send Button (`.send-btn`)**: Fixed `40px` dimensions, `var(--accent)` background, `var(--radius-lg)` rounded. Stop mode → rose-outlined. Disabled → neutral-300 bg.
- **`utility-btn`**: Floating or docked glassmorphism buttons used for global actions. Uses `backdrop-filter: blur(12px)` and semi-transparent background.
- **`action-btn`**: Small `14px` icons for per-message actions (Copy, Edit, Delete). Appear on row hover with `opacity` transition. Hover → `var(--accent)` color.

### 6.2 Inputs
- **`input-luminous`**: Universal text fields. Min-height `48px`, rounded `var(--radius-xl)`. Focus displays `0 0 0 2px var(--accent)` ring via box-shadow (no longer `primary-500`).
- **Chat Textarea**: Fluid height auto-resize, transparent background. Handled by `.input-container` wrapper with glass surface (`var(--glass-bg)`, `backdrop-filter: var(--glass-blur)`, `1px solid var(--glass-border)`). Focus → accent-light border, `3px` accent ring via box-shadow.
- **Sliders (`input[type=range]`)**: Track is `8px` rounded. Thumb is `24px` circle with `var(--accent-hover)` border, white filled. Hover/Active scales thumb to `1.1`.
- **Toggles (`.toggle-switch`)**: Pills measuring `48x28px`. Inner handle `20px` transforms with `--ease-spring`. Active → `var(--accent)` background.
- **Checkboxes**: Custom div `.checkbox` with absolute icon centered inside. Checked → `var(--accent)` background.

### 6.3 Surface Containers
- **`hardware-surface`** (Glass Surface): `var(--glass-bg)` background with `backdrop-filter: var(--glass-blur-sidebar)`. `1px solid var(--glass-border)`. `padding: 32px`, rounded `var(--radius-2xl)`. Hover → `-2px translateY` lift + `--surface-shadow-intense`. Dark mode → `rgba(255, 255, 255, 0.02)` bg with `inset 0 0 0 1px rgba(255, 255, 255, 0.03)`.
- **`metaphor-block` / Insight Cards**: Light mode → gradient from `var(--accent-subtle)` to white + `var(--glass-border)` border. Dark mode → `var(--glass-bg)` background. Decorative `"` mark uses `var(--accent-border)`.

### 6.4 Sidebar & Navigation Rail
- **Glass Panel**: `var(--bg-sidebar)` with `backdrop-filter: var(--glass-blur-sidebar)`. `border-inline-end: 1px solid var(--sidebar-border-color)`. Dark mode aside → `rgba(12, 12, 15, 0.4)` with white edge inset shadow.
- **Dimensions**: `16rem` (256px) when expanded (`.sidebar-expanded`), `4.5rem` (72px) when collapsed (`.sidebar-collapsed`). Transition: `400ms --ease-spring`.
- **Nav Items** (`.nav-item`): Height `48px`, rounded `var(--radius-xl)`. Active → `var(--accent-subtle)` bg, `var(--accent)` text, `3px` blue bar at left via `::before`. Dark active → `rgba(var(--accent-rgb), 0.15)` bg. Danger variant → rose coloring.
- **Brand Logo** (`.sidebar-logo-icon`): Blue gradient SVG with `drop-shadow` filter using `rgba(59, 130, 246, ...)`.
- **Sidebar Icon Buttons** (`.sidebar-icon-btn`): `2.25rem` square, `0.625rem` radius. Hover → `var(--accent-subtle)` bg, accent-colored border/text.
- **Sidebar Footer**: `border-top: 1px solid var(--glass-border)`.
- **Section Labels** (`.sidebar-section-label`): `0.6875rem`, weight 600, `0.15em` letter-spacing, uppercase.
- **Resize Handle** (`#sidebar-resizer`): `4px` wide, hover → blue gradient line.
- **Dynamic Tags (Pills)**: Chat items display inline status tags:
  - **Vision**: Light Cyan background (`rgba(6,182,212,0.1)`), Cyan border, `-brand-accent-1` text.
  - **Research**: Light Purple background (`rgba(168,85,247,0.1)`), Purple border, `#a855f7` text.
  - Both tags use `0.6rem` font size, `500` weight, and `4px` radius.

### 6.5 Chat Messages
- Container `#messages`. Fluid layout with flex-row alignments.
- **User Message**: Row-reverse flex. Bubble background `var(--bg-user-message)` (glass), rounded `1.5rem`, `1px solid var(--border-user-message)`, max-width `80%`. User avatar hidden.
- **Bot Message**: Content expands fully without colored backing (transparent background). Features an avatar wrapper container.
  - Avatar is `32px`. `var(--accent)` background (Light) / `var(--accent-light)` (Dark).
  - When Bot has `.thinking` class, avatar gets `.avatar-orbit` visible, applying a conic gradient spinning mask (`conic-gradient(from 0deg, transparent, var(--accent), transparent)`) over the edges.
  - **Message Actions**: `.message-actions-container` appears on message row hover. On mobile, always visible.
  - **Model Attribution Footer**: `.bot-model-label` in `0.6rem`, weight 600, `0.12em` tracking, uppercase.

### 6.6 Deep Research UI (Agents)
- **Research Plan Card**: `.research-plan-card`, `var(--surface-secondary)` bg, `1px solid var(--accent-border)`. Dark → `rgba(var(--accent-rgb), 0.05)` bg. Plan title uses `var(--accent-hover)` / `var(--accent-light)`.
- **Activity Feed**: Vertical stream of `.research-activity-item` lines with `activitySlideIn` animation.
- **Live Indicator**: `.research-live-indicator` — blue-tinted pill with `liveIndicatorPulse` animation. Uses `rgba(var(--accent-rgb), ...)` not violet.
- **Activity Icons**: Distinct colors by type:
  - Search: `rgba(var(--accent-rgb), 0.15)` bg, `var(--accent)` color (Blue)
  - Visit: Emerald (`#10b981`)
  - Status: Amber (`#f59e0b`)
  - Phase: Purple (`#8b5cf6`)
- **Search Results Pills** (`.activity-search-result-pill`): `9999px` rounded, accent-tinted bg + border. Dark → `var(--accent-light)` text.
- **Visit Card** (`.activity-visit-card`): Emerald-tinted card with domain tracking and truncated summaries.
- **Phase/Planning Indicator**: Gradient cells with blue-cyan gradients. Active uses `shimmer` text animation, complete → Emerald UI with `checkPop` animation.
- **Research Report Card**: Accent-subtle bg, accent-border, centered layout. "View Report" button.

### 6.7 Thought Process (Reasoning CoT)
- Nested inside bot messages. **Glass Container** → `.thought-container` uses `var(--glass-bg)`, `backdrop-filter: var(--glass-blur)`, `1px solid var(--glass-border)`. Dark → `rgba(255, 255, 255, 0.03)` bg.
- **Header**: Gradient background `linear-gradient(to right, rgba(var(--accent-rgb), 0.05), transparent)`. Title uses accent color, `0.6875rem`, weight 600, `0.15em` tracking, uppercase.
- Expand/collapse via CSS `grid-template-rows` transition (`0fr → 1fr`), `0.35s --ease-liquid`.
- **Reasoning Active State**: When AI is thinking, container gets `reasoning-pulse` glow animation and accent-colored border.
- **Streaming Cursor**: When expanded during reasoning, a blinking `◎` character cursor appears.

### 6.8 Tools Dropdown & Tool Options
- **Tools Button** (`.input-action-btn`): `40px` circle, rounded `var(--radius-full)`. Hover → accent bg. Active → `rgba(var(--accent-rgb), 0.1)` bg. Contains `#active-tool-icon` div that dynamically swaps SVG icons based on selected tool.
- **Attach Button**: Plus/cross icon (not paperclip). Same `.input-action-btn` styling.
- **Dropdown** (`#tools-dropdown`): Glass surface (`var(--glass-bg)`, `backdrop-filter: var(--glass-blur-sidebar)`, `1px solid var(--sidebar-border-color)`). Positioned absolute above input, `min-width: 280px`, `var(--radius-xl)` rounded. Entry via `slideUp` animation. Dark → `box-shadow: 0 40px 80px rgba(0, 0, 0, 0.5), inset 0 0 0 1px rgba(255, 255, 255, 0.08)`.
- **Tool Option Row** (`.tool-option`): Flex row, `justify-content: space-between`, `10px 12px` padding, `var(--radius-lg)` rounded. Hover → `rgba(var(--accent-rgb), 0.05)` bg.
- **Tool Icon Circle** (`.tool-icon-circle`): `32px` circle, `var(--radius-lg)` rounded, `rgba(var(--accent-rgb), 0.1)` bg, `var(--accent)` color.
- **Tool Name/Desc** (`.tool-name`, `.tool-desc`): Name → weight 700, `0.925rem`. Desc → `0.775rem`, muted color.
- **Mutual Exclusivity**: Research Agent and Deep Search toggles block each other. Research blocks when chat started. Deep Search option separated by `border-top: 1px solid var(--border-subtle)`.

### 6.9 Research Mode Selector (Segmented Control)
- Displayed in the welcome hero area when Research Agent is active.
- `.research-mode-selector`: Glass surface (`var(--glass-bg)`, `backdrop-filter: var(--glass-blur)`, `1px solid var(--glass-border)`), `4px` padding, `var(--radius-xl)` rounded, `var(--surface-shadow)` shadow.
- **Mode Buttons** (`.mode-btn`): `6px 20px` padding, `0.825rem` font, weight 700, `min-width: 90px`. Active → white text (sits above the indicator pill).
- **Sliding Indicator** (`.mode-indicator`): `var(--accent)` background pill with `0.4s --ease-spring` transition. Uses `data-mode` attribute on parent to `translateX(100%)` for "deep" mode. Glow → `0 2px 8px rgba(var(--accent-rgb), 0.3)`.
- Animates in using `greeting-entrance` keyframes.

### 6.10 Modals & Settings
- **Backdrop**: `background: transparent` (no gray overlay). `backdrop-filter: blur(8px)` to focus attention. Opacity transition `300ms --ease-spring`.
- **Content**: Glass surface (`var(--glass-bg)`, `backdrop-filter: var(--glass-blur-sidebar)`, `1px solid var(--sidebar-border-color)`). Max-width `512px`, rounded `var(--radius-2xl)`. Initial scale `0.92`, translateY `8px`. Expanding to `scale(1)` via `.open` state. Dark → prism edge inset shadow.
- **Header h2**: Weight 800, `-0.03em` tracking.
- **Scrollbar**: `6px` width, `var(--accent-border)` thumb on transparent track.
- **System Settings**: Includes Appearance controls (Light, Dark, System), connection settings, and danger zone actions.
- **Chat Settings**: Multi-tab interface (General, Persona, Parameters) with accent-colored active tab.
- **Model Switching Overlay**: Max z-index (`2147483647`), `backdrop-filter: blur(4px)`, blocks all interaction.

### 6.11 Headers & Banners
- **Chat Title Header**: Sticky at top, `4.5rem` height. Glass surface → `var(--bg-header)`, `backdrop-filter: var(--glass-blur)`, `1px solid var(--border-header)`. z-index `var(--z-header)` (40).
- **Chat Title Display**: `0.9375rem`, weight 600. `var(--bg-chat-display)` bg with `var(--border-chat-display)` border, `12px` rounded. Dark → muted text.
- **Temporary Chat Banner**: Amber-tinted → `rgba(245, 158, 11, 0.08)` bg, `rgba(245, 158, 11, 0.2)` border, `#b45309` text. Dark → `#fbbf24` text. Contains save button pill. Entry via `banner-slide-in`.

### 6.12 Empty State & Hero
- **Centered Greeting**: Fixed positioned, centered via `translate(-50%, -50%)`. Fades out with scale when hidden.
- **Greeting Text**: `clamp(3rem, 10vw, 5rem)`, weight 800. Solid color (not gradient fill). Light → `var(--content-primary)`, Dark → `#F8FAFC`.
- **Greeting Sub**: `clamp(1.5rem, 5vw, 2.5rem)`, weight 500, `opacity: 0.7`.
- **Research Depth Selector**: Segmented control (§6.9 above) displayed below greeting when Research mode is active. Uses `var(--accent)` indicator pill.

### 6.13 Chat Input Area
- `#chat-input-area`: `background: transparent` (no gradient overlay). Absolutely positioned at bottom. No layout shift from sidebar.
- `.input-container`: Max-width `800px`, width `calc(100% - 32px)`, centered. Glass surface with focus-within accent border and ring.

### 6.14 Image Attachment UI
- **Trigger**: Plus icon (`#attach-btn`) inside the input container.
- **Image Preview** (`#image-preview-container`): Absolute-positioned above input. Glass surface with accent-tinted shadow. Entry via `slideUp` animation.
- **Remove Button** (`#remove-image-btn`): `24px` circle, rose-500 bg, positioned top-right with `2px` white border.

### 6.15 Toasts
- Glass surface (`var(--glass-bg)`, `backdrop-filter: var(--glass-blur)`, `1px solid var(--glass-border)`). Fixed at `bottom: 32px`, `inset-inline-end: 32px`. Intense shadow. Entry via `slideUp`. z-index `var(--z-tooltip)`.

### 6.16 Research Report Canvas
- Full-screen overlay (`z-index: 9999`), transparent background (not grayed). Entry via opacity + translateY transition.
- **Content**: Glass surface, `max-width: 1000px`, centered. Dark → deep shadow `0 0 50px rgba(0, 0, 0, 0.5)`.
- **Header**: `var(--bg-header)` bg, `1px solid var(--glass-border)`. Title weight 800.

### 6.17 Markdown Rendering (Inside Messages)
- **H1, H2, H3**: Clean margins, sizes `1.25rem`, `1.125rem`, `1rem`.
- **Pre & Code**: Native `<pre>` wrappers get `var(--surface-secondary)` bg, `0.875rem` size. Inline `<code>` gets `rgba(var(--accent-rgb), 0.1)` bg with `var(--accent-hover)` color. Dark inline code → `var(--accent-light)`.
- **Images**: `max-width: 100%`, rounded `var(--radius-xl)`, `var(--surface-shadow)` shadow, `1px` border. Hover → slight scale + intense shadow + accent-light border.
- **Blockquotes**: `border-inline-start: 4px solid var(--accent-border)`.

### 6.18 File Upload UI
- **Upload Zone** (`.file-upload-zone`): Dashed border `2px dashed var(--accent-border)`, `border-radius: var(--radius-xl)`, padding `24px`. Glass surface `var(--glass-bg)` with `backdrop-filter: var(--glass-blur)`, `1px solid var(--glass-border)`. Rounded corners `var(--radius-xl)`. Dragover → `var(--accent)` border, `rgba(var(--accent-rgb), 0.08)` bg. Hover → same accent tint.
- **File Item** (`.file-item`): Flex row, `var(--glass-bg)` bg, `var(--radius-lg)` rounded, `10px 12px` padding. Icon circle `32px` with `rgba(var(--accent-rgb), 0.1)` bg. Hover → `var(--accent-border)` border.
- **File Info** (`.file-info`): Contains `.file-name` (`0.925rem`, weight 500), `.file-meta` (`0.75rem`, muted color). File meta uses inline dots (`·`) between size/type.
- **Remove Button** (`.remove-file-btn`): 24px circle, `var(--color-primary-500)` bg, `2px` white border. Hover → `transform: scale(1.1)`, `var(--color-rose-500)` bg.
- **File Type Icons**: `.file-type-icon` with type-specific classes (`.pdf`, `.docx`, `.txt`, `.image`, `.video`, `.audio`) for color coding.
- **Upload Progress** (`.upload-progress`): Shows upload status with progress bar (`var(--accent)` fill), turns green (`var(--color-emerald)`) on success.

---

## 7. Responsive Strategy

### Breakpoints
| Name    | Width       | Behavior                                    |
|---------|-------------|---------------------------------------------|
| Mobile  | ≤768px      | Sidebar = overlay via `translateX(-100%)`, input fixed at bottom |
| Tablet  | ≤1024px     | Reduced padding, collapsed sidebar by default |
| Desktop | >1024px     | Full sidebar + persistent navigation rail   |

### Mobile-Specific Rules
- Sidebar transforms to `280px` / `max-width: 85vw` overlay on expanded state. z-index `1000`.
- Mobile Toggle (`#mobile-toggle`) appears fixed at `top: 1.25rem; left: 1.25rem;` — glass surface with accent color. Hidden when sidebar is expanded.
- Chat input area fixed to viewport bottom (`position: fixed`), `background: transparent`.
- Message padding reduced to `5rem 1rem 8rem 1rem`.
- Welcome hero greeting scales down to `clamp(2rem, 12vw, 3rem)`.

---

## 8. Visual Fidelity

### Shadows
- **Never** use pure black shadows for brand elements.
- Inject blue tinting: `rgba(59, 130, 246, 0.06)` → `rgba(59, 130, 246, 0.12)`. Never use `rgba(168, 85, 247, ...)` (old violet).

### Glassmorphism (Aurora + Obsidian Core)
- **Central to all surfaces**: Input container, sidebar, modals, toasts, thought containers, dropdowns, image preview, tools dropdown, research mode selector, canvas, accordions, breadcrumbs, pagination, tooltip proximity.
- Standard glass recipe: `background: var(--glass-bg)` + `backdrop-filter: var(--glass-blur)` (= `blur(20px) saturate(160%)`) + `1px solid var(--glass-border)`.
- Dark mode modals / dropdowns → heavy prism edge shadow: `box-shadow: 0 40px 80px rgba(0, 0, 0, 0.5), inset 0 0 0 1px rgba(255, 255, 255, 0.08)`.

### Ambient Background
- Fixed `#ambient-bg` div behind all content (`z-index: -1`).
- Two independent `ambient-orb` child elements (`orb-1` and `orb-2`) with custom radial gradients.
- Separate `ambient-orb-1-drift` and `ambient-orb-2-drift` animations: slow 38s-45s translate/scale/rotate cycles. Creates a living, atmospheric feel with independent, fluid movement.
- Light mode → more opaque orbs on warm off-white (`#F8F7F4`). Dark mode → extremely subtle orbs on deep black (`#09090B`).
- `body` background set to `transparent` — never a solid color — allowing the ambient layer to show through glass surfaces.

### Optical Borders (Dark Mode)
- All `.hardware-surface` units in Dark Mode explicitly implement `box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.03)` to artificially harden the perimeter.
- Sidebar dark mode → `inset -1px 0 0 rgba(255, 255, 255, 0.08)` white edge.

### Logical Properties
- Use `inset-inline-start`, `inset-inline-end`, `margin-inline-start`, `padding-inline-start` instead of generic Left/Right explicitly, to maintain flow stability with localized layouts.

### Favicon
- Updated from blue-teal gradient to blue gradient (`#3B82F6` → `#2563EB`).

---

## 9. Anti-Patterns — The "Never" List

1. **No flat borders** on cards without shadow or inner ring.
2. **No default black shadows** on colored elements — always inject blue (`rgba(59, 130, 246, ...)`) natively.
3. **No CSS frameworks** (Tailwind, Bootstrap) — vanilla CSS definitions only.
4. **No UI-Frameworks** (React/Angular/Vue/Svelte) — completely raw vanilla DOM API parsing.
5. **No un-animated state changes** — every visibility/position change requires transitions (`opacity + transform`).
6. **No `display: none` for animated elements** — use `opacity + visibility + transform` overlays.
7. **No hardcoded RGB in JS** — always apply classes to trigger CSS custom property shifts.
8. **No static inline structural styles in JS** — do not use JS to manually manipulate inline CSS for static structure or pre-defined animations. Always apply or toggle CSS classes (e.g., `.dark`). **Exception**: Dynamic, calculated values (like drag-to-resize pixel widths or fluid heights calculated via JS listeners) may use inline styles.
9. **No structural delays in transitions** — fallback to `requestAnimationFrame` scaling if needed.
10. **No violet references** — all `--color-primary-*` usage must map to blue. Never reference `#A855F7` or the old Electric Violet palette in new code.
11. **No solid body backgrounds** — body must remain transparent to allow ambient layer visibility through glass surfaces.

---

## 10. Accessibility

- Interactive touch targets: minimum `44×44px`. Focus rings prominently display `0 0 0 2px var(--accent)` via box-shadow. Wait spinners clearly visually intercept flow.
- Modals natively disable flow behind them via absolute position intercepts.
- Color contrast: WCAG AA compliant parameters explicitly mapped via Semantic Colors.
- System respects the `prefers-color-scheme` via logical DOM intercept mapping `.dark` classes seamlessly.
- **Reduced motion**: `@media (prefers-reduced-motion: reduce)` disables all animations (message-slide-in, blink-caret, orbit-spin, typing-pulse, reasoning-pulse, thought expansion, modal transitions).

---

## 11. Performance

- **Single CSS file** implementation — no dynamic imports for styles except external Google font rendering.
- **Single JS script execution** using procedural DOM mutations.
- **Event Delegation** implicitly used structurally.
- Natively exploits `transform`, `opacity`, `requestAnimationFrame` to limit repaint layouts dynamically on scrolling elements.
- Uses `scrollbar-width: thin` and equivalent `webkit-scrollbar` pseudoelements for non-blocking native scroll tracks. Scrollbar thumbs use `var(--accent-border)` color.
- CSS `saturate(160%)` in `--glass-blur` enhances perceived color vibrance through glass without additional rendering cost.
