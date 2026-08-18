---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: ["frontend/src/Login.tsx","frontend/src/AdminConsole.tsx","frontend/src/UserConsole.tsx","frontend/src/components.tsx","frontend/src/styles.css"]
---

# Frontend application redesign

- Scope: `frontend/src/App.tsx`, login/password gates, administrator console, user console, shared components and styles.
- Visitor mode: Operate.
- Primary audience/job: administrators configure and supervise the complete access chain; ordinary users inspect quota, create/revoke keys and reach a successful first API call.
- Required action and content: preserve every existing feature, API call, field, role boundary and security warning; make current state, dependency order and next action easier to scan.
- Constraints: React 19 + TypeScript + native CSS + lucide-react; Chinese UI; desktop and mobile web; no fabricated claims or production data.

## Chosen direction

- World: electric-utility single-line dispatch board. Upstream services, public model aliases and user permissions are one traceable supply circuit rather than independent dashboard cards.
- Approved comp: `.impeccable/mocks/composition-horizontal.png`.
- Memorable moment: the dashboard opens with a horizontal access circuit that makes a broken or incomplete stage visible before the user reads the ledger.
- Signature interaction: navigation and current-path states snap into place; changing a section preserves a short, reduced-motion-safe line trace rather than using unrelated hover effects.
- Unresolved: the repository-backed assumptions in `PRODUCT.md` remain subject to later user confirmation.

## Sampled visual record

| Role | Sample |
|---|---|
| Page ground | `#F8F7F1` (dominant interior average) |
| Control-rail ink | `#012445` |
| Live circuit | `#095294` |
| Warning | `#D67D21` |
| Hairline / metal seam | `#C1CCD3` |
| Fault | `#B63832` (direction palette; preserve for errors only) |

## Comp inventory and implementation medium

| Ingredient | Comp commitment | Medium |
|---|---|---|
| Application chrome | 64–72px instrument header, 208px control rail, hard seams and near-square controls | Semantic HTML/CSS; lucide-react icons |
| Access circuit | One horizontal path occupying roughly half the opening field; named upstream, breaker, mapping, quota and user-permission stages | Semantic HTML plus authored responsive inline SVG/CSS; live counts from existing props; never rasterized |
| Status language | Cobalt live line; amber degraded; red blocked; each also has text, icon/shape and accessible label | HTML/CSS/SVG with text equivalents |
| Operational ledger | Dense continuous rows under the circuit; compact 12–13px labels and tabular figures | Semantic tables and lists |
| Primary actions | Integrated into the instrument strip or page head; compact rectangular switch vocabulary, 4px corner maximum | Semantic buttons with lucide-react icon; HTML/CSS |
| Forms and modals | Same enamel ground, inset label slots, 1px seams, no floating glass card vocabulary | Semantic form/dialog HTML and CSS |
| Type | Workhorse system Chinese sans; tabular/monospaced identifiers; approximate ramp 11/12/13/16/28/36 | CSS system stacks; no raster text |
| Material | Smooth mineral enamel ground with faint printed registration lines; no photographic depth or texture | CSS solid fields, seams and sparse linear marks |
| Mobile adaptation | Circuit becomes a vertical ordered sequence; navigation becomes a scrollable instrument strip; ledgers become labeled data stacks | Responsive CSS and SVG viewBox changes |
| Motion | One circuit trace on entry/section change; controls snap; old state fades for one beat | CSS transitions/animation with `prefers-reduced-motion` fallback |
