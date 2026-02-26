# My-AI — Design Directives (v1.0.1)

**Architect:** Visual Design System  
**Compliance Standard:** WCAG 2.1 AA  
**Philosophy:** Material Design 3 (Modified) · Glassmorphism · True Dark · Motion-First  
**Updated:** late-February 2026

---

## 1. Tech Stack & Rationale

| Layer        | Technology         | Notes |
|--------------|--------------------|-------|
| Structure    | Semantic HTML5     | Accessibility-first markup |
| Styling      | Vanilla CSS        | CSS Custom Properties for theming, no framework |
| Logic        | Vanilla JavaScript | Single `script.js`, no bundler |
| Typography   | Google Fonts (Outfit, JetBrains Mono, Lora) | Variable weight |
| Markdown     | marked.js (CDN)    | Real-time streaming render |
| Highlighting | highlight.js (CDN) | Real-time code syntax highlighting |
| Icons        | Inline SVG (Lucide-style) | Stroke-width: 2–2.5px |

### Methodology
- **CSS Custom Properties** (`--color-*`, `--radius-*`, `--ease-*`) for all design tokens.
- **Semantic aliases** (`--content-primary`, `--content-muted`) decoupled from primitive values.
- **Light/Dark/System Toggle** via `.dark` class on `<html>` — all overrides use `.dark` prefix. Variable assignment happens within `:root` and `.dark` block. Theme preference is persisted in LocalStorage.

---

## 2. Design Tokens

### 2.1 Color System — Ocean Blue (Primary) & Zinc (Neutral)

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
| `--bg-light-start/mid`  | `#EFF6FF` / `#FFFFFF` | `#09090B`         |
| `--bg-dark`             | `#09090B`     | `#09090B`         |

### 2.2 Semantic Aliases

| Token                | Light                        | Dark                           |
|----------------------|------------------------------|--------------------------------|
| `--content-primary`  | `var(--color-neutral-900)`   | `var(--color-neutral-50)`      |
| `--content-muted`    | `var(--color-neutral-500)`   | `var(--color-neutral-400)`     |
| `--surface-secondary`| `var(--color-neutral-100)`   | `rgba(255,255,255,0.05)`       |
| `--bg-user-message`  | `var(--surface-secondary)`   | `var(--color-neutral-800)`     |
| `--text-user-message`| `var(--content-primary)`     | `#FFFFFF`                      |
| `--border-user-message` | `var(--color-neutral-200)` | `rgba(255, 255, 255, 0.1)` |
| `--bg-input`         | `var(--color-neutral-50)`    | `rgba(255, 255, 255, 0.05)`    |
| `--border-input`     | `var(--color-primary-500)`   | `var(--color-primary-400)`     |

### 2.3 Functional Options & Modifiers

| Token        | Light       | Dark       | Usage            |
|-------------|-------------|------------|------------------|
| Rose        | `#F43F5E`   | —          | Error / Danger   |
| Teal        | `#14B8A6`   | —          | Success / Accent |
| Yellow/Amber| `#f59e0b`   | —          | Warning          |
| Emerald     | `#10b981`   | —          | Complete / OK    |
| Violet/Purple| `#a855f7`  | —          | Deep Research Mode Tag |
| Cyan        | `var(--brand-accent-1)` | — | Vision Capability Tag |

---

## 3. Typography System

| Role     | Family   | Size   | Weight | Tracking  | Line-Height |
|----------|----------|--------|--------|-----------|-------------|
| Display  | Outfit   | 72px   | 800    | -0.05em   | 1.1         |
| H1       | Outfit   | 48px   | 700    | -0.025em  | 1.2         |
| H2       | Outfit   | 30px   | 600    | -0.025em  | 1.3         |
| Body     | Outfit   | 18px   | 400    | normal    | 1.75        |
| Label    | Outfit   | 12px   | 600    | 0.1em     | 1.0         |
| Code     | JetBrains Mono | 14px | 400 | normal   | 1.5         |
| Serif    | Lora     | 15px   | 400    | normal    | 1.6         |

### Code Block Theme Integration
- Highlight.js automatically switches between `github.min.css` and `github-dark.min.css` based on the `.dark` class state for robust highlighting.

---

## 4. Spatial System

### 4.1 Border Radii
| Token          | Value |
|----------------|-------|
| `--radius-3xl` | 24px  |
| `--radius-2xl` | 16px  |
| `--radius-xl`  | 12px  |
| `--radius-lg`  | 8px   |

### 4.2 Z-Index Layers
| Layer     | Value | Usage                                |
|-----------|-------|--------------------------------------|
| Base      | 0     | Flow content                         |
| Content   | 10    | Sticky elements                      |
| Input     | 30    | Chat input area                      |
| Sidebar   | 40    | Navigation rail / Sidebar            |
| Mobile    | 50    | Mobile toggle menu                   |
| Overlay   | 100   | Modals, backdrops                    |
| Tooltip   | 110   | Tooltips                             |
| Max Z     | 9999  | Blocking UI (Model Switch Overlay)   |

---

## 5. Motion & Animation System

### 5.1 Easing Curves
| Name           | Value                              | Usage                    |
|----------------|-------------------------------------|--------------------------|
| `--ease-spring`| `cubic-bezier(0.2, 0.8, 0.2, 1)`   | UI interactions, modals  |
| `--ease-liquid`| `cubic-bezier(0.22, 1, 0.36, 1)`   | Content expansion        |
| Standard       | `cubic-bezier(0.4, 0, 0.2, 1)`     | Material standard        |

### 5.2 Animations
We use intensive frame-by-frame animation defined entirely within the CSS instead of JS logic where possible:
- **`message-slide-in`**: Messages rise from bottom-up (`transform: translateY(12px) -> 0`, `400ms`).
- **`blink-caret`**: AI generating cursor pulsing (`800ms steps(2) infinite`).
- **`orbit-spin`**: AI avatar conic-gradient ring (`2s linear infinite` when `.thinking`).
- **`typing-pulse`**: Loading dots scale variation `(0.7 opacity 0.3) -> (1.3 opacity 1)`.
- **`spinner-spin`**: Simple rotate (`360deg 1s linear infinite`).
- **`shimmer`**: Skeleton load shimmering text background effect (`1.5s ease-in-out infinite`).
- **`activitySlideIn`**: Research items popping in (`0.3s ease-out`).
- **`liveIndicatorPulse`**: Deep Research glowing loop (`2.5s infinite`).
- **`planSpin` & `checkPop`**: Planning loader and complete mark.

---

## 6. Component Library (Comprehensive)

### 6.1 Buttons
- **`btn-primary`**: Full rounded `9999px`, height `48px`, blue gradient (`primary-600` to `#3B82F6`). Box shadow. Lifts lightly on hover.
- **`btn-secondary`**: White/Dark background with colored border `1px primary-200`. Hover state changes bg to `primary-50`.
- **`btn-ghost`**: No border/bg initially. Hover makes it lightly tinted `rgba(37,99,235,0.05)`.
- **`btn-approve`** (Research): Primary style but smaller inline footprint.
- **`pagination-btn`**: Circles, used for sliders/carousel.
- **Send Toggle (`.send-btn`)**: Fixed `40px` dimensions, flex centered icon, blue gradient.
- **`utility-btn`**: Floating or docked glassmorphism buttons used for global actions (e.g. `Clear Chat`). Uses `backdrop-filter: blur(8px)` and semi-transparent background.
- **`action-btn`**: Small `14px` icons for per-message actions (Copy, Edit, Delete). Appear on row hover with `opacity` transition.

### 6.2 Inputs
- **`input-luminous`**: Universal text fields. Min-height `48px`, rounded `var(--radius-xl)`. Focus displays `2px primary-500` ring.
- **`textarea` (Chat)**: Fluid height auto-resize, transparent background natively without ring. Handled by an `.input-container` wrapper that receives the focus border and shadow.
- **Sliders (`input[type=range]`)**: Fluid Control style. Track is `8px` rounded. Thumb is `24px` circle with `primary-600` border, `white` filled. Hover/Active scales thumb to `1.1`.
- **Toggles (`.toggle-switch`)**: Pills measuring `48x28px`. Inner handle `20x20px` transforms `20px` to active state using `--ease-spring`.
- **Checkboxes**: Custom div `.checkbox` with absolute icon centered inside, pops in on `.checked`.

### 6.3 Surface Containers
- **`hardware-surface`**: Card container. White (Light) or Zinc 950 Base (Dark). `1px` subtle borderline, `padding: 32px`, rounded `24px`. Intense hover drop shadow `var(--surface-shadow-intense)` combined with `-2px translateY` lift.
- **`metaphor-block` / Insight Cards**: Content callouts that overlay a quote `“` mark from bottom-right to top-left gradients.

### 6.4 Sidebar & Navigation Rail
- Expandable navigation. `256px` wide when expanded (`.sidebar-expanded`), `80px` when collapsed (`.sidebar-collapsed`).
- Transition takes `400ms`.
- Features items `.nav-item` inside. Active item gets `var(--color-primary-50)` bg and an absolute `3px` tall bar positioned at left spanning `50%` of height.
- Contains Top Brand header, Actions (New Chat, Temp Chat), Scrollable Recent Chats (`chat-list-item`), and Bottom Footer (System & Chat Settings).
- Includes a **Resize Handle** (`#sidebar-resizer`) for manual width adjustments.
- **Dynamic Tags (Pills)**: Chat items display inline status tags:
  - **Vision**: Light Cyan background (`rgba(6,182,212,0.1)`), Cyan border, `-brand-accent-1` text.
  - **Research**: Light Purple background (`rgba(168,85,247,0.1)`), Purple border, `#a855f7` text.
  - Both tags use `0.6rem` font size, `500` weight, and `4px` radius.

### 6.5 Chat Messages
- Container `#messages`. Fluid layout with flex-row alignments.
- **User Message**: Row-reverse flex. Bubble background `var(--bg-user-message)`, rounded corners `1.5rem` on all corners but text wrap limits size to `80%`.
- **Bot Message**: Content expands fully without colored backing. Features an avatar wrapper container.
  - Avatar is `32px`. Blue gradient background for Bot.
  - When Bot has `.thinking` class, avatar gets `.avatar-orbit` visible, applying a conic gradient spinning mask over the edges.
  - **Message Actions**: `.message-actions-container` appears on message row hover, containing `.action-btn` elements for utility tasks.
  - **Model Attribution Footer**: `.bot-message-footer` located below content. Displays the generating model name (`.bot-model-label`) in `0.65rem` font weight `500`, ensuring clear context on response source across reloads.

### 6.6 Deep Research UI (Agents)
Features extreme granular component logic for Research Agent steps:
- **Research Plan Card**: `.research-plan-card`, shows plan with editable Markdown via `.plan-editor`. Has `btn-approve`.
- **Activity Feed**: Vertical stream of `.research-activity-item` lines.
- **Live Indicator**: `.research-live-indicator` glowing pill indicating agent scanning/browsing status. Pulse animation.
- **Activity Icons**: Distinct colors by type: Search (Blue), Visit (Emerald), Status (Warning Amber), Phase (Purple).
- **Search Results (`.activity-search-result-pill`)**: Clickable blue pills for generated search queries.
- **Visit Card (`.activity-visit-card`)**: Card for crawled sites with domain tracking and truncated summaries.
- **Phase/Planning Indicator**: Rich gradient cells `.research-planning-indicator`. Active uses shimmer text, complete switches to Emerald UI.

### 6.7 Thought Process (Reasoning CoT)
- Nested inside bot messages. Contains a `.thought-container` housing a `.thought-header` and `.thought-body`.
- Header shows title and chevron. Fully responsive expand/collapse via JS height adjustment and transition.
- Contains raw inner monolog via `.thought-body-content`.

### 6.8 Modals & Settings
- **Backdrop**: `rgba(15,23,42,0.25)` & `backdrop-filter: blur(8px)`.
- **Content**: Max-width `512px` (or wider like `640px` for tabs). Rounded `16px`. Initial scale `0.92`. Expanding to `scale(1)` via `.open` state.
- **System Settings**: Includes Appearance controls (Light, Dark, System preference), connection settings, and danger zone actions.
- **Chat Settings**: Multi-tab interface (General, Persona, Parameters) for granular AI control.
- **Model Switching Overlay**: Full-screen semi-transparent backdrop (`z-index: 9999`) with `backdrop-filter: blur(10px)` and a progress spinner to block interaction.

### 6.9 Headers & Banners
- **Temporary Chat Banner**: Yellow/Subtle header inserted before chat input when active to explicitly alert user "Temporary chat — not saved to history", includes standard button prompt to save manually.
- **Context Header**: Sticky top header for chat subject `(Gemini Style)`. 
  - Displays Chat Title + Active Feature Tags (Vision/Research pills) mirrored from sidebar state.
  - Subheaders show "Last model used" metrics when not in Deep Research mode.

### 6.10 Empty State & Hero
- **Gemini-Style Greeting**: Centered greeting with "Hello there" and "How can I help you today?" using `text-display` and `text-h1` styles.
- **Research Depth Selector**: Inline toggle buttons (Regular vs Deep) with active state highlighting (Blue background for active) and subtle shadows.

### 6.11 Markdown Rendering (Typography inside messages)
- **H1, H2, H3**: Clean margins, tighter top alignments.
- **Pre & Code**: Native `<pre>` wrappers get borders and `0.875rem` font scale. Code blocks without `<pre>` get subtle highlighting wrappers. Includes highlight JS markup. Img elements natively scale `max-width: 100%`.

### 6.12 Image Attachment UI
- **Localized Trigger**: Paperclip icon (`#attach-btn`) inside the input container.
- **Image Preview**: Scalable thumbnail (`#image-preview`) with a remove action (`#remove-image-btn`) appearing above the textarea when an image is selected.

### 6.13 Localized Deep Research Toggle
- **Input Area Toggle**: Globe icon (`#deep-research-toggle`) with "Deep Research" label. Transitions to `active` state with blue coloring. Auto-disables and shows a "cannot toggle after start" tooltip once conversation begins to maintain consistency.

---

## 7. Responsive Strategy

### Breakpoints
| Name    | Width       | Behavior                                    |
|---------|-------------|---------------------------------------------|
| Mobile  | ≤768px      | Sidebar = overlay via `translateX(-100%)`, input fixed at bottom |
| Tablet  | ≤1024px     | Reduced padding, collapsed sidebar by default |
| Desktop | >1024px     | Full sidebar + persistent navigation rail   |

### Mobile-Specific Rules
- Sidebar transforms to `80% max-width 300px` overlay on expanded state (`#sidebar.sidebar-expanded`).
- Mobile Toggle (`#mobile-toggle`) appears fixed at `top: 1.25rem; left: 1.25rem;` featuring glassmorphism blur and z-index 50.
- Chat input area stays solidly absolute docked to viewport bottom frame (`padding-bottom: 24px`).

---

## 8. Visual Fidelity

### Shadows
- **Never** use pure black shadows for brand elements.
- Inject 15–30% of primary color: Example `rgba(37, 99, 235, 0.08)` → `rgba(37, 99, 235, 0.15)`.

### Glassmorphism
- **Layering overlays** use `backdrop-filter: blur(8px-16px)`.
- Used natively in Mobile Toggle button and Modal backdrops. Semi-transparent backgrounds explicitly declared with RGBA.

### Optical Borders (Dark Mode)
- All `.hardware-surface` units in Dark Mode explicitly implement `box-shadow: inset 0 0 0 1px rgba(255,255,255,0.05)` to artificially harden the perimeter without bloating borders.
- Hover logic intensifies bounding borders to `rgba(37, 99, 235, 0.3)`.

### Logical Properties
- Use `inset-inline-start`, `inset-inline-end`, `margin-inline-start`, `padding-inline-start` instead of generic Left/Right explicitly, to maintain flow stability with localized layouts.

---

## 9. Anti-Patterns — The "Never" List

1. **No flat borders** on cards without shadow or inner ring.
2. **No default black shadows** on colored elements — always inject brand color natively.
3. **No CSS frameworks** (Tailwind, Bootstrap) — vanilla CSS definitions only.
4. **No UI-Frameworks** (React/Angular/Vue/Svelte) — completely raw vanilla DOM API parsing.
5. **No un-animated state changes** — every visibility/position change requires transitions (`opacity + transform`).
6. **No `display: none` for animated elements** — use `opacity + visibility + transform` overlays.
7. **No hardcoded RGB in JS** — always apply classes to trigger CSS custom property shifts.
8. **No structural delays in transitions** — fallback to `requestAnimationFrame` scaling if needed.

---

## 10. Accessibility

- Interactive touch targets: minimum `44×44px`. Focus rings prominently display `2px solid var(--color-primary-500)`. Wait spinners clearly visually intercept flow.
- Modals natively disable flow behind them via absolute position intercepts.
- Color contrast: WCAG AA compliant parameters explicitly mapped via Semantic Colors.
- System respects the `prefers-color-scheme` via logical DOM intercept mapping `.dark` classes seamlessly.

---

## 11. Performance

- **Single CSS file** implementation — no dynamic imports for styles except external Google font rendering.
- **Single JS script execution** using procedural DOM mutations.
- **Event Delegation** implicitly used structurally.
- Natively exploits `transform`, `opacity`, `requestAnimationFrame` to limit repaint layouts dynamically on scrolling elements.
- Uses `scrollbar-width: thin` and equivalent `webkit-scrollbar` pseudoelements for non-blocking native scroll tracks.
