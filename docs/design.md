---
# CLF Gestión — Design System
# Format: https://github.com/google-labs-code/design.md

name: CLF Gestión
description: >
  Internal ERP for a B2B logistics distributor in Yucatán, México.
  Dense, data-first interface optimised for operators who spend the
  whole workday inside the tool. No marketing, no decoration — every
  pixel earns its place by carrying information.

colors:
  # ── Ink scale (Zinc-based neutral) ──────────────────────────────
  ink-900: "#18181b"   # body text, strong labels, active nav
  ink-800: "#27272a"   # secondary body text, table cells
  ink-700: "#3f3f46"   # muted text on white
  ink-600: "#52525b"   # nav links at rest, secondary labels
  ink-500: "#71717a"   # captions, meta, KPI labels
  ink-400: "#a1a1aa"   # placeholders, sort arrows, dot indicators
  ink-300: "#d4d4d8"   # borders, dividers on white
  ink-200: "#e4e4e7"   # card borders, table borders, rule lines
  ink-100: "#f4f4f5"   # intra-card dividers, row separators
  ink-50:  "#fafafa"   # surface hover, subnav background, table header bg
  paper:   "#ffffff"   # primary background

  # ── Accent (Forest Green — CLF brand) ───────────────────────────
  accent:      "#2d5a45"   # primary buttons, active pill dot, active mobile nav
  accent-soft: "#ecf0ed"   # tinted background for active states, focus rings
  accent-ink:  "#1a3a2c"   # text on accent-soft, hover for primary buttons

  # ── Warning (Amber Brown) ────────────────────────────────────────
  warn:      "#92400e"   # warning text
  warn-soft: "#fef3c7"   # warning background

  # ── Danger (Red) ─────────────────────────────────────────────────
  danger:      "#991b1b"   # error text, rejected status dot, KPI warn value
  danger-soft: "#fee2e2"   # error/rejected background

  # ── Status semantic colors (pill dots only) ──────────────────────
  status-pending:    "#d97706"   # Pendiente — amber
  status-scheduled:  "#1d4ed8"   # Programada / Parcial — blue
  status-delivered:  "#2d5a45"   # Entregada / Pagada — accent green
  status-invoiced:   "#6d28d9"   # Facturada — purple
  status-rejected:   "#991b1b"   # Rechazada — danger red
  status-draft:      "#a1a1aa"   # Borrador — ink-400 (neutral)

typography:
  # ── Font families ────────────────────────────────────────────────
  sans:  '"Inter Tight", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif'
  serif: '"Source Serif 4", Georgia, "Times New Roman", serif'
  mono:  '"JetBrains Mono", "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace'

  # ── Base ─────────────────────────────────────────────────────────
  base-size:    "13px"
  base-weight:  400
  line-height:  1.4
  font-smoothing: antialiased
  font-features: '"ss01", "cv11"'  # Inter Tight stylistic sets

  # ── Type scale (all sizes in px) ─────────────────────────────────
  scale:
    eyebrow:       { size: "10.5px", weight: 600, transform: uppercase, tracking: "0.12em" }
    label:         { size: "11px",   weight: 400, transform: uppercase, tracking: "0.07em" }
    table-header:  { size: "11px",   weight: 500, transform: uppercase, tracking: "0.06em" }
    pill:          { size: "11px",   weight: 400 }
    chip-count:    { size: "11px",   weight: 400, numeric: tabular-nums }
    caption:       { size: "11px",   weight: 400, color: ink-500 }
    note-mono:     { size: "10.5px", weight: 400, family: mono }
    subnav:        { size: "12px",   weight: 400 }
    button:        { size: "12px",   weight: 500 }
    chip:          { size: "12px",   weight: 400 }
    body-small:    { size: "12px",   weight: 400 }
    input:         { size: "12.5px", weight: 400 }
    table-cell:    { size: "12.5px", weight: 400 }
    folio:         { size: "11.5px", weight: 400, family: mono }
    body:          { size: "13px",   weight: 400 }
    card-title:    { size: "13px",   weight: 500, tracking: "-0.01em" }
    brand:         { size: "14px",   weight: 600, tracking: "-0.015em" }
    modal-title:   { size: "16px",   weight: 600 }
    page-title:    { size: "22px",   weight: 500, tracking: "-0.02em", line-height: 1.1 }
    kpi-value:     { size: "26px",   weight: 500, tracking: "-0.02em", line-height: 1.1, numeric: tabular-nums }

spacing:
  # ── Base unit: 4px ───────────────────────────────────────────────
  "1":  "4px"
  "2":  "8px"
  "3":  "12px"
  "4":  "14px"
  "5":  "16px"
  "6":  "18px"
  "7":  "20px"
  "8":  "22px"
  "9":  "24px"
  "10": "28px"
  "11": "32px"
  "12": "36px"

  # ── Semantic spacing ─────────────────────────────────────────────
  page-padding-y:      "28px"
  page-padding-x:      "36px"
  page-max-width:      "1320px"
  section-gap:         "22px"
  card-padding-header: "12px 16px"
  card-padding-kpi:    "18px 20px"
  card-padding-modal:  "28px"
  btn-padding:         "7px 14px"
  btn-padding-sm:      "4px 9px"
  btn-padding-ghost:   "6px 10px"
  input-padding:       "7px 10px"
  table-cell-padding:  "11px 14px"
  table-header-padding:"9px 14px"
  chip-padding:        "5px 10px"
  pill-padding:        "2px 8px"

radii:
  none:    "0"
  sm:      "2px"   # role-tag, qb-tag
  default: "3px"   # kbd, subnav active
  btn:     "4px"   # buttons, inputs, chips, FieldGrid
  card:    "6px"   # cards, KpiGrid, next-ribbon, modal
  login:   "8px"   # login card
  pill:    "9999px" # status pills

elevation:
  # CLF uses borders not shadows — elevation is conveyed by stacking
  # order, sticky positioning, and background contrast
  topbar:
    position:    "sticky top: 0"
    z-index:     50
    border:      "bottom 1px ink-200"
    background:  paper
  subnav:
    position:    "sticky top: 52px"
    z-index:     40
    border:      "bottom 1px ink-200"
    background:  ink-50
  modal-overlay:
    background:  "rgba(0,0,0,0.35)"
    z-index:     100
  mobile-nav:
    position:    "fixed bottom: 0"
    z-index:     50
    border:      "top 1px ink-200"
  focus-ring:
    box-shadow:  "0 0 0 3px accent-soft"
    border-color: accent

layout:
  topbar-height:    "52px"
  subnav-height:    "~36px"
  mobile-nav-height:"56px"
  shell:
    display: grid
    rows: "52px auto 1fr"
    height: "100%"
  content:
    max-width: "1320px"
    padding: "28px 36px"
  mobile-breakpoint: "768px"

motion:
  # Micro-interactions only — the UI does not animate data or layout
  transition-duration: "150ms"
  transition-property: color
  easing: linear
  # Mobile nav link: color transition 0.15s
  # No transforms, no fade-ins, no skeleton loaders

components:
  topbar:
    height: "52px"
    brand-separator: "right 1px ink-200"
    active-indicator: "2px bottom accent"
    nav-link-size: "12.5px"

  pill:
    shape: "rounded-full (999px)"
    dot-size: "5px"
    dot-position: "::before pseudo-element"
    padding: "2px 8px"
    gap: "6px"
    border: "1px ink-200"
    background: paper

  chip:
    shape: "4px radius"
    padding: "5px 10px"
    active: "background ink-900, color white, border ink-900"
    count-color: ink-500

  stepper:
    states:
      done:    "background accent-soft, text accent-ink"
      current: "background ink-900, text white"
      todo:    "background ink-50, text ink-400"
    border-radius: "4px"
    overflow: hidden

  next-ribbon:
    variants:
      default: "border accent, background accent-soft, text accent-ink"
      warn:    "border #f5e6c0, background #fffbf2, text warn"
    border-radius: "6px"
    padding: "12px 16px"

  kpi-card:
    label: "11px uppercase tracking-0.08em ink-500"
    value: "26px weight-500 tracking--0.02em tabular-nums"
    warn-color: danger
    grid: "equal columns, 1px ink-200 dividers, 6px radius border"

  table:
    header-bg: ink-50
    row-hover: ink-50
    selected: "background accent-soft"
    selected-hover: "#dde8e0"
    folio-font: mono

  card:
    background: paper
    border: "1px ink-200"
    radius: "6px"

  modal:
    width-default: "480px"
    max-height: "90vh"
    overlay: "rgba(0,0,0,0.35)"
    close: "click outside"

  side-preview:
    background: ink-50
    border-left: "1px ink-200"
    padding: "18px 20px"
---

# CLF Gestión — Design Language

## Philosophy

CLF Gestión is a **data-dense internal ERP**. The visual design is intentionally spare: no illustrations, no gradients, no heavy animations. The guiding principle is *information density without visual noise* — every element earns its place by communicating domain state.

The aesthetic is best described as **editorial-functional**: the typography leans on Inter Tight (condensed, professional) and Source Serif 4 appears only for prose content if needed. The neutral Zinc scale keeps chrome quiet while the forest-green accent provides wayfinding and positive confirmation.

## Color System

The palette has three tiers:

**Neutral (Ink scale):** A full 10-stop Zinc-gray scale from near-black `#18181b` to near-white `#fafafa`. The full range is used actively — `ink-900` for body text, `ink-200`/`ink-100` for borders and row separators, `ink-50` for surface hovers and sub-navigation backgrounds. `paper` (`#ffffff`) is the primary page background.

**Accent (Forest Green):** The brand color `#2d5a45` anchors all affirmative states: primary buttons, active navigation indicators, "done" stepper steps, status badges for delivered/paid orders. Its soft tint `#ecf0ed` appears as background for active chips, ribbon highlights, and focus rings. This green is muted and professional — not a bright UI green.

**Semantic signals:** Warning (amber brown `#92400e`) and danger (deep red `#991b1b`) each have a solid form for text and a pastel form for backgrounds. Status dots on pills use four additional semantic colors that are never used for text: amber for pending, blue for scheduled, purple for invoiced.

## Typography

Three families, each with a strict role:

- **Inter Tight** (sans) — everything interactive and data. Navigation, buttons, table cells, inputs, labels. Rendered at 13px base with `"ss01"` and `"cv11"` stylistic sets for cleaner figures.
- **Source Serif 4** — available for long-form prose if ever needed, but not currently active in the UI.
- **JetBrains Mono** — folio numbers (invoice/order IDs), keyboard shortcuts, and the `.note` class for field key labels in the `FieldGrid` component. Its tabular numerics ensure folios align perfectly in tables.

All uppercase labels use `letter-spacing: 0.06–0.12em` to compensate for Inter Tight's narrow proportions at small sizes.

The type scale is deliberately compressed: page titles at 22px, KPI values at 26px, and everything else below 16px. This keeps the UI feeling workstation-grade rather than consumer-grade.

## Layout & Chrome

The shell is a CSS grid with three rows: **topbar (52px)** · **subnav (conditional)** · **content (fills remaining)**. Both topbar and subnav are sticky, so the navigation never scrolls away during long data tables.

The topbar carries the brand name, role-scoped primary navigation tabs, and a right slot with username + role tag + logout. Active tabs are indicated by a 2px bottom border in accent green — not a background change. The subnav appears only when the active section has sub-routes and shows them as small pill-shaped links on an `ink-50` tinted bar.

Content pages use `max-width: 1320px` centered with `28px/36px` padding, giving breathing room on large displays while remaining usable on 1024px laptops.

Mobile (≤768px): the top nav collapses, the brand centers, and a fixed bottom bar (`MobileNav`) provides access to the five most common sections.

## Component Patterns

### Status Pills
Compact rounded badges (2px/8px padding, full radius) with a 5px colored dot as the sole color carrier. The pill background is always white with a `ink-200` border — color is intentionally minimal, conveyed only by the dot, not the whole badge. This prevents status from dominating the visual hierarchy.

States: Borrador (gray) · Pendiente (amber) · Programada (blue) · Entregada (green) · Facturada (purple) · Pagada (green) · Rechazada (red).

### Filter Chips
Horizontal strip of rounded-square chips for single-selection filtering. Inactive: white bg, `ink-200` border, `ink-700` text. Active: `ink-900` bg, white text. The count sits inline in a smaller muted font. The high-contrast active state makes the current filter unmistakable without color.

### Stepper
A horizontal segmented control showing workflow progress. Three visual states: **done** (green-tinted: `accent-soft` bg, `accent-ink` text), **current** (inverted: `ink-900` bg, white text), **todo** (muted: `ink-50` bg, `ink-400` text). No icons — state is communicated purely through background/text contrast inversion.

### KPI Grid
Borderless grid of KPI cards separated only by `1px ink-200` column dividers, with a shared outer border and 6px radius. Each card shows: a small uppercase label, a large tabular number value, and an optional footnote. Warning KPIs render the value in danger red. Used at the top of the Dashboard and detail pages for at-a-glance health metrics.

### Next-Action Ribbon
A contextual banner that tells the operator exactly what to do next in a workflow. Default variant: `accent-soft` tinted with `accent` border, text in `accent-ink`. Warning variant: light amber background. Always contains a bold message, an optional detail line, and action buttons right-aligned. This is the primary driver of the B2B sales workflow (Cotización → OC → Stock → Entrega → CFDI → Pago).

### Data Table
Full-width table with uppercase `ink-500` column headers on `ink-50` background. Row hover lifts to `ink-50`. Selected rows use `accent-soft`. The `.folio` class switches cells to monospace for document reference numbers. Client-side sortable with minimal indicators (↑↓↕ characters in 10px, partially opaque when inactive). Footer row for totals/counts in `ink-500`.

### Cards
Simple white panels with `1px ink-200` border and `6px` radius. No drop shadows anywhere. Card headers use `card-h` with a `1px ink-100` bottom divider inside the card. Elevation is expressed through **border contrast against a white background**, not shadow depth.

### Modal
Centered overlay with `rgba(0,0,0,0.35)` scrim. The modal panel is a card at 480px default width. Click-outside closes it. Scrollable content up to 90vh. No animation — it appears/disappears instantly (React conditional render with no transition).

### FieldGrid
A key-value grid inside `SidePreview` panels. Keys are rendered in `.note` (JetBrains Mono, 10.5px, uppercase, `ink-500`). Values at 12px. Separated by `1px ink-100` borders. Used in detail pages to show order metadata in a scannable format.

## Forms & Inputs

Inputs and selects share identical styling: 1px `ink-300` border, 4px radius, 12.5px sans text. Focus state adds `accent`-colored border plus a 3px `accent-soft` box-shadow ring — visible but not loud. Labels above inputs use the small uppercase style (11px, 0.07em tracking). All form controls are full-width within their layout column.

Buttons follow a three-variant hierarchy:
- **Primary** (`btn-primary`): solid `accent` fill, white text, hover darkens to `accent-ink`.
- **Default** (`btn`): white fill, `ink-300` border, hover to `ink-50`.
- **Ghost** (`btn-ghost`): no border, `ink-600` text, hover to `ink-100` background.

Small variant (`btn-sm`) reduces padding to 4px/9px and font to 11.5px. Buttons in ribbons and table rows commonly use `btn-sm`.

## Quote Builder (Inline Editing)

The `qb-line` pattern is a 7-column CSS grid for inline editable line items in a purchase/quote form. Cells with `.grip` use monospace for the drag handle character. Input cells reset border to 0 and only show a background on focus (the "invisible until edited" pattern). Flagged lines (`qb-line.flag`) get a light amber background (`#fffbf2`) and a `qb-tag` badge (10px uppercase, amber).

## Writing Style

Labels are Spanish, sentence-case for prose, uppercase for abbreviated labels (FOLIO, CLIENTE, MONTO). Date formats follow Mexican convention. Numbers use `tabular-nums` throughout tables and KPIs for column alignment. Currency values always right-aligned.

The UI voice is terse and operational: "Cotización en borrador. Completa las partidas y envía al cliente para continuar." No hedging, no marketing language.
