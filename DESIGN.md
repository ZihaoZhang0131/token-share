---
name: "Token Station"
description: "A mineral-enamel access-control console that makes every upstream-to-user circuit visible."
colors:
  ink: "#012445"
  ink-soft: "#36556a"
  muted: "#5e7280"
  ground: "#f8f7f1"
  ground-deep: "#f0efe9"
  panel: "#fcfbf7"
  line: "#c1ccd3"
  line-soft: "#dce2e3"
  circuit: "#095294"
  circuit-dark: "#073e70"
  circuit-soft: "#e7eff5"
  ok: "#237354"
  warn: "#b66516"
  warn-bright: "#d67d21"
  fault: "#b63832"
  focus: "#0c6db7"
typography:
  display:
    fontFamily: '"DIN Alternate", "Avenir Next Condensed", "Arial Narrow", sans-serif'
    fontSize: "clamp(52px, 6.2vw, 88px)"
    fontWeight: 700
    lineHeight: 0.9
    letterSpacing: "-0.03em"
  headline:
    fontFamily: '"DIN Alternate", "Avenir Next Condensed", "Arial Narrow", sans-serif'
    fontSize: "31px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.02em"
  title:
    fontFamily: '"DIN Alternate", "Avenir Next Condensed", "Arial Narrow", sans-serif'
    fontSize: "18px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.01em"
  body:
    fontFamily: '"Avenir Next", "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "13px"
    fontWeight: 400
  label:
    fontFamily: '"SFMono-Regular", "Roboto Mono", Consolas, "Liberation Mono", monospace'
    fontSize: "10px"
    fontWeight: 800
    lineHeight: 1.45
    letterSpacing: "0.04em"
rounded:
  meter: "1px"
  field: "2px"
  control: "3px"
  surface: "4px"
  round: "50%"
  pill: "99px"
spacing:
  compact: "8px"
  control: "12px"
  surface: "16px"
  section: "22px"
  page: "24px"
components:
  button-primary:
    backgroundColor: "{colors.circuit}"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "38px"
  button-primary-hover:
    backgroundColor: "{colors.circuit-dark}"
    textColor: "#ffffff"
  button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "38px"
  button-danger:
    backgroundColor: "{colors.fault}"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "38px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "38px"
  field-input:
    backgroundColor: "#ffffff"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "0 11px"
    height: "42px"
  nav-active:
    backgroundColor: "{colors.ink}"
    textColor: "#ffffff"
    rounded: "{rounded.field}"
    padding: "0 11px"
    height: "42px"
  panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "16px 18px"
  status-pill:
    backgroundColor: "#e3e8e8"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.pill}"
    padding: "3px 7px"
---

# Design System: Token Station

## Overview

**Creative North Star: "The Electric-Utility Single-Line Dispatch Board"**

Token Station is an operational control surface, not a generic SaaS dashboard. Its visual world is a mineral-enamel dispatch board where upstream providers, public model routes, quota checks, and user permissions read as one traceable electrical circuit. Ink-blue control rails and hard metal seams establish authority; cobalt shows the live path; amber isolates degraded or incomplete stages; red is reserved for faults.

The system is compact, flat, and exact. Continuous ledgers, tabular figures, engraved-looking labels, breaker geometry, and near-square controls make the interface feel built for supervision rather than presentation. The login, administrator console, user console, forms, and dialogs all remain inside the same material world.

**Key Characteristics:**

- Mineral-enamel grounds with ink-blue control structure.
- One visible access circuit as the signature operational model.
- Compact ledgers, tabular readouts, and monospaced identifiers.
- Hard seams, near-square controls, and restrained state motion.
- Cobalt live states, amber warnings, red faults, and green confirmation only.

## Colors

The palette behaves like a printed control panel: warm mineral neutrals carry the field, ink establishes structure, and state colors are sparse, semantic signals.

### Primary

- **Live Circuit Cobalt** (#095294): Marks primary actions, connected paths, selected technical elements, meters, and active routing details.
- **Deep Circuit Cobalt** (#073e70): Darkens live controls on hover and strengthens technical identifiers.
- **Pale Circuit Wash** (#e7eff5): Carries quiet hover fields, model identifiers, and key-icon insets.

### Secondary

- **Control-Rail Ink** (#012445): Anchors the top bar, active navigation, code surfaces, primary copy, and the dark login field.
- **Engraved Ink** (#36556a): Carries secondary control labels and technical text that must remain firm but subordinate.
- **Focus Blue** (#0c6db7): Identifies keyboard focus and focused fields without changing the component's semantic state.

### Tertiary

- **Deep Safety Amber** (#b66516): Colors warning-stage iconography and readable warning text.
- **Safety Amber** (#d67d21): Identifies degraded, incomplete, or waiting circuit paths, seams, and lamps.
- **Fault Red** (#b63832): Is reserved for blocked paths, failed status, destructive action, and error feedback.
- **Protection Green** (#237354): Confirms healthy state and protection facts; it is never the brand accent.

### Neutral

- **Mineral Enamel** (#f8f7f1): Carries the page field and the open area behind the access circuit.
- **Recessed Enamel** (#f0efe9): Steps back the navigation rail, telemetry bands, table heads, and recessed tracks.
- **Instrument Panel** (#fcfbf7): Carries working surfaces, authentication cards, circuit modules, and dialogs.
- **Muted Readout** (#5e7280): Steps down explanatory copy, captions, and metadata without losing legibility.
- **Metal Seam** (#c1ccd3): Defines primary panel, rail, row, and instrument boundaries.
- **Hairline Seam** (#dce2e3): Divides dense rows and nested control regions without adding visual weight.

### Named Rules

**The Three-State Circuit Rule.** Cobalt means live, amber means degraded or waiting, and red means blocked; never swap these meanings or rely on color without text, icon, or geometry.

**The Green Is Confirmation Rule.** Green confirms health or protection only; it never replaces cobalt as the system's primary voice.

## Typography

**Display Font:** DIN Alternate (with Avenir Next Condensed, Arial Narrow, and sans-serif fallbacks)  
**Body Font:** Avenir Next (with SF Pro Text, PingFang SC, Microsoft YaHei, and sans-serif fallbacks)  
**Label/Mono Font:** SFMono-Regular (with Roboto Mono, Consolas, Liberation Mono, and monospace fallbacks)

**Character:** Condensed display faces give headings and readouts an instrument-panel authority. A workhorse Chinese sans keeps dense operational copy legible, while monospaced labels make identifiers, timestamps, counts, and telemetry scan as measured values.

### Hierarchy

- **Display** (700, fluid 52–88px, 0.9 line-height): Reserved for the split-screen login identity.
- **Headline** (700, 31px, 1 line-height): Page titles and major usage readouts.
- **Title** (700, 18px, 1 line-height): Panel heads, circuit labels, and compact product marks.
- **Body** (400–700, 11–13px): Controls, table cells, form copy, and operational explanations; density is intentional.
- **Label** (800, 8–10px, 0.04–0.08em tracking): Uppercase telemetry, ledger headers, captions, and engraved readouts.

### Named Rules

**The Readout Split Rule.** Human-facing Chinese copy stays in the workhorse sans; identifiers, timestamps, aliases, counters, and telemetry move to the monospaced readout face.

## Layout

Desktop uses a sticky instrument header (68px), a narrow control rail (212px), and a bounded workspace that grows to 1680px. The opening admin field places the instrument header, one continuous horizontal access circuit, then dense operational ledgers. Surfaces meet through seams and shared edges instead of floating as unrelated cards; recurring section spacing is compact, generally 12–22px.

At 1120px, readouts wrap beneath the instrument title, the circuit columns compress, and statistic grids halve. At 760px, navigation becomes a horizontal scrollable instrument strip, the access circuit becomes a vertical ordered sequence, two-column forms collapse, and tables retain horizontal overflow. At 420px, statistic groups and card grids become single-column. Content order and state meaning remain unchanged at every breakpoint.

## Elevation & Depth

The system is flat by default. Depth comes from tonal layering, one-pixel seams, inset control fields, and adjacency; panels do not float. A shadow appears only on the modal (`0 24px 60px rgba(1,36,69,.2)`) because the dialog must sit above a darkened ink backdrop.

### Shadow Vocabulary

- **Modal Lift** (`0 24px 60px rgba(1,36,69,.2)`): Used only for blocking dialogs above the ink-tinted backdrop.

### Named Rules

**The Flat-By-Default Rule.** Keep operational surfaces flush and seam-defined; reserve physical lift for modal interruption only.

## Shapes

The form language is engineered and near-square. Meters use a 1px edge, inputs and compact controls use 2px corners, primary controls and panels use 3px corners, and only identity tiles, authentication cards, and dialogs reach 4px. Pills and circular lamps are reserved for compact status or circuit symbolism, never as the default container language. Borders are predominantly one-pixel metal seams; breaker diamonds and round node symbols carry the electrical topology.

## Components

### Buttons

- **Shape:** Compact rectangular switches with a 38px minimum height, 3px corners, and 14px horizontal padding.
- **Primary:** White text on the cobalt live-circuit field; use for the next decisive operation.
- **Hover / Focus:** Primary darkens to the deep circuit tone, controls depress by 1px on active, and keyboard focus uses a 2px focus outline offset by 3px.
- **Secondary / Ghost / Danger:** Secondary is a panel-colored switch with a metal seam; ghost actions use transparent ink and a soft-circuit hover field; danger uses fault red with white text.

### Chips

- **Style:** Status pills are compact and semantic; neutral state uses a gray mineral fill, healthy state uses a pale green fill, and fault state uses a pale red fill.
- **State:** Model aliases use near-square soft-circuit chips instead of pills because they represent technical identifiers rather than status.

### Cards / Containers

- **Corner Style:** Near-square panel corners (3px), with authentication and modal surfaces allowed 4px.
- **Background:** Panel enamel over the page ground; telemetry and table headers step down to the deeper ground.
- **Shadow Strategy:** Flat at rest; use seams and tonal bands, not ambient elevation.
- **Border:** One-pixel metal seams, with stronger seams around instrument and circuit assemblies.
- **Internal Padding:** Dense 14–18px working surfaces; authentication and modal content may expand to 21–38px.

### Inputs / Fields

- **Style:** White 42px fields, 2px corners, 1px cool-gray stroke, and 11px horizontal inset beneath compact bold labels.
- **Focus:** The border becomes cobalt and gains a restrained 3px translucent cobalt ring; global keyboard focus remains a separate 2px outline.
- **Error / Disabled:** Errors use a pale fault field with dark red text and a red-gray seam; disabled controls retain shape and reduce opacity.

### Navigation

The desktop control rail uses 42px near-square rows with icons and 13px semibold labels. The active row becomes solid ink with white text and a pale-blue icon; hover returns to a white enamel field with a soft seam. On mobile the same rows become one horizontal, scrollable instrument strip beneath the top bar.

### Access Circuit

The signature component is a semantic single-line diagram: circular source and endpoint nodes, diamond breaker controls, a rectangular public-model routing module, state lamps, and one cobalt path. It reads horizontally on desktop and becomes a vertical ordered sequence below 760px. Its entry trace lasts 620ms with an ease-out curve and is suppressed by `prefers-reduced-motion`.

### Operational Ledger

Ledgers use continuous 34–51px rows, monospaced 8–10px headers, tabular figures, one-pixel dividers, and quiet hover feedback. Preserve horizontal scrolling when columns cannot collapse without losing meaning; do not turn dense operational records into unrelated cards.

## Do's and Don'ts

### Do:

- **Do** make the upstream-to-user dependency chain visible before asking operators to interpret rows of data.
- **Do** use hard seams, compact labels, and tabular figures to make state easy to scan and compare.
- **Do** preserve the cobalt, amber, red state grammar with text, icon, or shape redundancy.
- **Do** adapt the circuit into an ordered vertical sequence on narrow screens while preserving its meaning.
- **Do** keep sensitive, destructive, empty, loading, and error states explicit and operational.

### Don't:

- **Don't** replace the continuous dispatch-board structure with floating bento cards, glass surfaces, gradients, or decorative shadows.
- **Don't** use green as the primary brand color or red for ordinary emphasis.
- **Don't** soften controls into oversized capsules; rounded forms are reserved for lamps, nodes, and compact status pills.
- **Don't** add photography, perspective device mockups, decorative texture, or invented security claims.
- **Don't** rasterize circuit labels, data, icons, or topology that can remain semantic HTML, SVG, and CSS.
