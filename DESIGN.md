---
name: "Token Station"
description: "A quiet graphite operations ledger for private model access, quota, keys, and routing."
colors:
  ink: "#e8f0ed"
  ink-soft: "#bdc8c4"
  muted: "#8c9a96"
  ground: "#0c1217"
  ground-deep: "#0d1218"
  panel: "#0e151a"
  line: "#2a363a"
  line-soft: "#202b30"
  circuit: "#4bcc99"
  circuit-dark: "#73dbb4"
  circuit-soft: "#122c24"
  ok: "#5ad3a5"
  warn: "#d5a967"
  warn-bright: "#e1b872"
  fault: "#ef8585"
  focus: "#73dbb4"
typography:
  display:
    fontFamily: 'ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "clamp(29px, 2.5vw, 38px)"
    fontWeight: 650
    lineHeight: 1
    letterSpacing: "-0.025em"
  metric:
    fontFamily: '"SFMono-Regular", "Roboto Mono", Consolas, "Liberation Mono", monospace'
    fontSize: "clamp(38px, 4.5vw, 58px)"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.035em"
  title:
    fontFamily: 'ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "17px"
    fontWeight: 650
    lineHeight: 1.2
  body:
    fontFamily: 'ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "13px"
    fontWeight: 400
  label:
    fontFamily: '"SFMono-Regular", "Roboto Mono", Consolas, "Liberation Mono", monospace'
    fontSize: "10px"
    fontWeight: 500
    lineHeight: 1.45
    letterSpacing: "0.02em"
rounded:
  none: "0"
  marker: "1px"
  meter: "2px"
  nav: "6px"
  control: "7px"
  circuit: "8px"
  modal: "10px"
  round: "50%"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  control: "14px"
  row: "18px"
  section: "28px"
  workspace: "38px"
components:
  button-primary:
    backgroundColor: "{colors.circuit}"
    textColor: "#07110d"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "38px"
  button-primary-hover:
    backgroundColor: "{colors.circuit-dark}"
    textColor: "#07110d"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "38px"
  button-danger:
    backgroundColor: "#9f3f46"
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
    backgroundColor: "#0a1014"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 11px"
    height: "42px"
  nav-active:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.nav}"
    padding: "0 14px 0 32px"
    height: "44px"
  panel:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "20px 0 15px"
  modal:
    backgroundColor: "#11191e"
    textColor: "{colors.ink}"
    rounded: "{rounded.modal}"
    padding: "21px"
---

# Design System: Token Station

## Overview

**Creative North Star: "Open Ledger"**

Token Station is a quiet operational ledger on one continuous graphite canvas. Whitespace and hairline seams organize quota, routing, access keys, permissions, and audit metadata without turning the console into a card wall. Soft white copy carries the facts; one low-saturation mint signal shows the active path or the next decisive action.

The world is calm, compact, and factual. Authentication unlocks private values and actions, while signed-out views keep protected values visibly unknown rather than filling the interface with examples. Role boundaries, destructive consequences, and security facts remain explicit at the point of action.

**Key Characteristics:**

- Deep graphite canvas with very small tonal steps between chrome and working regions.
- Hairline seams, open sections, and generous horizontal breathing room instead of stacked cards.
- One restrained mint signal for active location, capacity, focus, and decisive action.
- Soft white hierarchy with monospaced type reserved for measured or machine-readable data.
- Compact controls, explicit unknown states, and one reduced-motion-safe meter fill.

## Colors

The palette is a graphite field with soft neutral text and a single mint operational signal; amber and red remain sparse semantic exceptions.

### Primary

- **Ledger Mint** (#4bcc99): Marks the current navigation square, primary actions, quota fill, chart activity, and live technical paths.
- **Bright Mint** (#73dbb4): Strengthens hover and keyboard-focus states without introducing a second accent family.
- **Mint Well** (#122c24): Provides a subdued mint-tinted inset for technical identifiers and icon wells.

### Tertiary

- **Healthy Mint** (#5ad3a5): Confirms a healthy or protected state; use with text or a status shape.
- **Quiet Amber** (#d5a967): Carries warning copy and non-blocking degraded states.
- **Readable Amber** (#e1b872): Raises warning emphasis on the dark canvas.
- **Fault Rose** (#ef8585): Signals errors and blocked states; destructive button fills use a darker companion red so white labels remain calm and legible.

### Neutral

- **Soft Ledger White** (#e8f0ed): Primary copy and the highest information contrast.
- **Secondary Ledger White** (#bdc8c4): Supporting labels, control copy, and ordinary row values.
- **Quiet Metadata** (#8c9a96): Captions, help text, placeholders, and unknown-state explanations.
- **Graphite Canvas** (#0c1217): The continuous page field.
- **Graphite Rail** (#0d1218): The navigation rail and recessed chrome.
- **Graphite Surface** (#0e151a): Slightly lifted working regions such as the access map.
- **Ledger Rule** (#2a363a): Primary section and row boundaries.
- **Hairline Rule** (#202b30): Low-contrast internal separators.

### Named Rules

**The One Mint Signal Rule.** Mint is the only recurring accent and should remain visually rare: active location, primary action, capacity, focus, or live state only.

**The Unknown Remains Unknown Rule.** Protected values render as an em dash with a short login explanation; never substitute sample quotas, counts, permissions, or keys.

**The Semantic Exception Rule.** Amber warns and rose faults; both require a text label, icon, or state geometry so color is never the only carrier.

## Typography

**Display Font:** System UI sans (with SF Pro Display, PingFang SC, Microsoft YaHei, and sans-serif fallbacks)

**Body Font:** System UI sans (with SF Pro Text, PingFang SC, Microsoft YaHei, and sans-serif fallbacks)

**Label/Mono Font:** SFMono-Regular (with Roboto Mono, Consolas, Liberation Mono, and monospace fallbacks)

**Character:** The interface uses familiar system sans faces for quiet Chinese reading and avoids expressive display typography. Monospaced type appears only where alignment or machine identity matters, giving measured values a ledger-like rhythm without making the whole console feel like a terminal.

### Hierarchy

- **Display** (650, fluid 29–38px, 1 line-height): Page titles and primary workspace identity.
- **Metric** (500, fluid 38–58px, 1 line-height): Monthly token totals and other dominant measured values.
- **Title** (650, 17px, 1.2 line-height): Working-section and modal headings.
- **Body** (400–700, 11–13px): Controls, table values, form copy, and operational explanations.
- **Label** (500–800, 8–10px, up to 0.05em tracking): Timestamps, aliases, request IDs, table headers, counters, and technical metadata.

### Named Rules

**The Data-Only Mono Rule.** Use monospaced type for figures, timestamps, keys, model aliases, request IDs, code, and telemetry only; human-facing navigation and explanatory Chinese stay in the system sans.

## Layout

The authenticated shell uses a sticky 64px top bar, a 190px navigation rail, and a continuous workspace capped at 1720px. Workspace padding begins at 38px vertically and scales horizontally from 28px to 66px. Major regions remain open and are separated by 1px rules and 28–38px vertical rhythm rather than repeated containers.

The user usage view begins with the monthly total and a slim capacity meter across the full workspace, followed by three counters on one ruled band. Daily activity and model permissions form a two-column working area when space permits. Dense admin tables and ledgers preserve horizontal scrolling instead of collapsing critical columns into cards.

At 1120px the rail narrows to 176px and the user working columns stack. At 760px the top bar becomes 60px, the rail becomes a 52px horizontally scrollable navigation strip, forms collapse to one column, and counters use two columns. At 420px counters become a single vertical ledger. Information order and role boundaries do not change across breakpoints.

## Elevation & Depth

The system is flat by default. Depth comes from near-black tonal steps, open spacing, and hairline rules; ordinary panels, key rows, resources, charts, and tables do not float. Only blocking dialogs and the forced-password surface receive a deep black shadow because they interrupt the workspace and require a clear modal plane.

### Shadow Vocabulary

- **Modal Lift** (`0 28px 72px rgba(0,0,0,.5)`): Blocking dialogs above the dark backdrop.
- **Password Gate Lift** (`0 28px 72px rgba(0,0,0,.36)`): The mandatory password-change surface.

### Named Rules

**The Ledger-Stays-Flat Rule.** Operational content remains flush with the canvas; physical lift belongs only to blocking tasks.

## Shapes

The form language is compact and gently squared. Navigation rows use 6px corners, ordinary controls and fields use 7px, the bounded admin access map and code regions use 8px, and modal surfaces use 10px. The active navigation marker is a 6px square with a 1px corner. Meters use a 2px radius, while circles and pills are reserved for state dots, icon symbols, and short status labels. Open ledger sections have no enclosing radius.

## Components

### Buttons

- **Shape:** Compact 38px controls with 7px corners and 14px horizontal padding.
- **Primary:** Dark ink on ledger mint; reserve it for the next decisive action.
- **Hover / Focus:** Primary actions brighten to the focus mint; all buttons use a 160ms ease-out state transition and a 2px mint focus outline offset by 3px.
- **Secondary / Ghost / Danger:** Secondary actions are transparent with a cool-gray seam, ghost actions reveal only a faint white wash, and destructive fills use the darker red `#9f3f46` with white text.

### Navigation

The rail uses 44px transparent rows with muted labels. The current item stays unfilled: a 6px mint square, brighter text, and a mint icon locate the active section. On mobile the same items become a horizontal strip beneath the 60px top bar; preserve the marker and order.

### Usage Ledger

The monthly total is the signature readout: a monospaced 38–58px value followed by a 7px capacity line. The fill runs once over 560ms with an ease-out curve when motion is allowed. Three subordinate counters share one ruled band, and signed-out values remain em dashes with explicit login copy.

### Cards / Containers

Ordinary working regions are open sections with transparent backgrounds, square edges, and 1px top or bottom rules. Resource cards and key rows follow the same ledger treatment. The admin access map is a deliberate bounded exception with a graphite surface, 1px rule, and 8px corners because its topology must remain visually contained.

### Inputs / Fields

- **Style:** Dark 42px inset fields with 7px corners, 11px horizontal padding, soft-white text, and a cool-gray border.
- **Focus:** Border and 3px translucent ring shift to mint; caret follows the same signal.
- **Autofill / Error / Disabled:** Browser autofill is forced back to the dark field and soft-white text. Errors use a dark rose field with readable pale-rose text. Disabled controls retain their shape and reduce opacity.

### Status and Identifiers

Status pills are short 999px capsules because their content is categorical, not structural. Technical aliases use open ruled rows or compact mint wells rather than decorative chips. Healthy, warning, and fault states always pair color with words or geometry.

### Modal

Dialogs use a `#11191e` surface, 10px corners, a strong dark backdrop, and the only pronounced shadow in the system. The header is separated by a rule; forms use compact vertical rhythm, explicit consequences, focus trapping, Escape dismissal, and focus restoration.

### Admin Access Map

The administrator overview may use the semantic access-chain diagram to explain upstream credentials, public routes, quota checks, and user authorization. Keep it inside the graphite world, suppress decorative entry animation, and treat mint, amber, and rose as live, waiting, and blocked states rather than spectacle.

## Do's and Don'ts

### Do:

- **Do** keep quota, routing, key, permission, and audit facts on one continuous graphite canvas.
- **Do** separate working regions with whitespace and hairline rules before adding a bounded container.
- **Do** use mint sparingly for active location, decisive action, capacity, focus, and live state.
- **Do** keep private signed-out values unknown and explain that login loads the real data.
- **Do** preserve compact controls, readable contrast, dark autofill treatment, explicit security copy, and responsive horizontal navigation.
- **Do** use monospaced type only for measured or machine-readable data.

### Don't:

- **Don't** reintroduce Matrix code rain, scanlines, neon glow, decorative grids, gradients, glass, or visual theatre.
- **Don't** rebuild the workspace as a wall of floating cards or ambient shadows.
- **Don't** fabricate quotas, counts, permissions, model names, keys, or operational status for signed-out or empty views.
- **Don't** turn every label into terminal typography or uppercase telemetry.
- **Don't** fill the active navigation row; the small mint square is the selected-state signature.
- **Don't** add motion beyond the single quota-meter reveal and restrained control-state transitions.
