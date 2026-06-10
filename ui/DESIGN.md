---
name: Authsome Secure Console
colors:
  surface: '#131315'
  surface-dim: '#0e0e10'
  surface-bright: '#2a2a2c'
  surface-container-lowest: '#0e0e10'
  surface-container-low: '#1c1b1d'
  surface-container: '#201f22'
  surface-container-high: '#2a2a2c'
  surface-container-highest: '#353437'
  on-surface: '#e5e1e4'
  on-surface-variant: '#bbcabf'
  inverse-surface: '#e5e1e4'
  inverse-on-surface: '#313032'
  outline: '#86948a'
  outline-variant: '#3c4a42'
  surface-tint: '#4edea3'
  primary: '#4edea3'
  on-primary: '#003824'
  primary-container: '#10b981'
  on-primary-container: '#00422b'
  inverse-primary: '#006c49'
  secondary: '#a6d1ad'
  on-secondary: '#10381f'
  secondary-container: '#284f33'
  on-secondary-container: '#95bf9d'
  tertiary: '#bcc7de'
  on-tertiary: '#263143'
  tertiary-container: '#98a3ba'
  on-tertiary-container: '#2e394c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6ffbbe'
  primary-fixed-dim: '#4edea3'
  on-primary-fixed: '#002113'
  on-primary-fixed-variant: '#005236'
  secondary-fixed: '#c1edc8'
  secondary-fixed-dim: '#a6d1ad'
  on-secondary-fixed: '#00210d'
  on-secondary-fixed-variant: '#284f33'
  tertiary-fixed: '#d8e3fb'
  tertiary-fixed-dim: '#bcc7de'
  on-tertiary-fixed: '#111c2d'
  on-tertiary-fixed-variant: '#3c475a'
  background: '#131315'
  on-background: '#e5e1e4'
  surface-variant: '#353437'
typography:
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '450'
    lineHeight: 20px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  margin-page: 2rem
  gutter-grid: 1rem
  stack-sm: 0.5rem
  stack-md: 1.5rem
  container-width: 1200px
---

## Brand & Style

The brand identity centers on **Secure Developer Console**: the calm, precise feeling of a well-instrumented control plane for agent credentials. It is built for engineers, platform teams, and security reviewers who need to trust the product before they try it.

The visual style is **minimal infrastructure with quiet depth**. It keeps shadcn component discipline, but avoids a page made of identical boxes. Sections should feel like layered panels, terminal surfaces, request traces, and security status bands rather than marketing cards. Gradients are allowed only as low-opacity light, edge glow, or inspection depth; they should never dominate the palette.

The strongest emotional signals are:

- **Developer-focused:** terminal fragments, command affordances, monospace metadata, request/audit language.
- **Trustworthy:** stable layout, restrained contrast, no bouncy motion, no over-decorated cards.
- **Secure:** emerald status accents, crisp boundaries, explicit policy/audit/vault language, subtle glow only around protected or verified states.
- **Friendly:** clear hierarchy, readable copy, obvious actions, enough whitespace for scanning.

## Colors

The palette is anchored by **Deep Emerald** and **Obsidian**. We use a dark-first strategy to reduce eye strain for technical work and to evoke a code editor/control plane.

- **Primary:** Emerald (#10B981) used sparingly for successful states, primary actions, verified markers, and active request paths. It represents secure access, not decoration. Maps to `--primary`.
- **Secondary:** A deep Forest Green (#052E16) used for subtle backgrounds on active navigation items or success-themed containers.
- **Neutral/Background:** We use a true Obsidian (#09090B) for the primary background to maximize contrast with borders.
- **Accents:** Slate, zinc, and muted blue-gray tones support borders, secondary text, and architecture diagrams. Use them to create confidence without making the page monochrome.

### Design token rules

| Token | Dark mode value | Use |
|-------|----------------|-----|
| `--primary` | Emerald `#10B981` | Primary buttons, focus rings, active states, verified indicators |
| `--accent` | `#2a2a2c` (surface-container-high) | **Neutral** hover surface for cards, list rows, and menu items. Never set to emerald — that bleeds color into every interactive hover. |
| `--muted` | `#201f22` | Inactive backgrounds, inset panels, metadata rows |
| `--border` | `#27272A` | All 1px dividers and card outlines |

`--accent` is intentionally a mid-level neutral surface, not a chromatic tint. Emerald influence on hover comes only from `border-primary` or a very low-opacity `ring` — never from `bg-accent`.

## Typography

The typography system uses a dual-font approach to distinguish between "Interface" and "Data."

**Hanken Grotesk** serves as the primary UI font. It provides a sharp, contemporary sans-serif look that is highly legible at small sizes. Headings use tighter letter-spacing and heavier weights to feel structural.

**JetBrains Mono** is used for all "output" and system-related data, including IDs, terminal logs, audit event details, and credential strings. This distinction helps developers mentally categorize information: sans-serif is what the app is telling them, and monospace is the data they are managing. All labels for status or metadata use the `label-caps` role to mimic the appearance of a command-line header.

## Layout & Spacing

The layout uses a **fixed-fluid hybrid** grid. Marketing pages should feel like product surfaces, not brochure sections: wide enough for technical detail, constrained enough for scanability.

- **Navigation:** Sticky, compact, and utility-like. The brand should read as a product in the first viewport.
- **Content:** Uses a 1rem gutter between elements. Information is grouped into panels, rows, terminal surfaces, and connected grids rather than repeated boxes.
- **Rhythm:** We follow a 4px base unit. Spacing between related items (label to input) is 8px, while spacing between unrelated sections is 24px or 32px.
- **Mobile:** On mobile devices, the grid collapses to a single column, the sidebar becomes a bottom sheet or a hidden menu, and page margins reduce to 1rem.

## Elevation, Depth & Animations

This design system avoids high-elevation shadows in favor of **Tonal Layering**, **Crisp Outlines**, and **Subtle Glows (Linear-style)**.

Depth is achieved through background contrast, hairline borders, and very soft gradients:

- **Level 0 (Base):** The primary app background (#09090B), with a subtle grid/cross texture.
- **Level 1 (Panel/Section):** A slightly lighter shade (#131315) with a subtle 1px border (#27272A).
- **Level 2 (Terminal/Inspector):** A higher contrast surface (#0E0E10 or #1C1B1D), internal dividers, and a soft ambient shadow.
- **Gradient Use:** Emerald gradients should sit at section edges, terminal glows, or hover borders at 5-12% opacity. They should imply protected flow, not decoration.

Shadows, when used, are strictly ambient: no heavy offset, large blur, low opacity. Interaction feedback is represented by changing the border color, surface tone, or very subtle glow. Avoid scaling cards and buttons; the product should feel steady.

**Animations & Micro-interactions:**
- **Linear-style motion:** Animations should be minimal, spring-based or smooth ease-outs using Framer Motion. 
- Elements should fade in and slide up slightly (`y: 20` to `0`) as they enter the viewport.
- Staggered entrances for list items and grid cards.
- Hover states should include a subtle ease-in-out glow or border transition. Elements should feel responsive but not bouncy.

## Shapes

The shape language is **Soft-Technical**. Use small radii and occasional open or split panels so the UI does not become boxy.

- **Inputs & Buttons:** 4px to 6px radius to provide just enough approachability.
- **Containers:** 8px radius for primary panels. Avoid large rounded cards unless they are terminal or inspector surfaces.
- **Pills:** Status badges (e.g., "Active", "Success") use a fully rounded/pill shape to distinguish them from interactive buttons.
- **Section Grids:** Prefer connected panels, timeline rows, split layouts, and hairline dividers over repeating boxed cards.

## Components

### Buttons
- **Primary:** Solid #10B981 with black text. No gradient. High contrast.
- **Secondary:** Transparent background with a 1px border (#27272A) and white text.
- **Ghost:** No border or background unless hovered.

### Input Fields
- Dark backgrounds (#09090B) with 1px borders. Focus state should change the border color to #10B981 with a subtle emerald outer glow (2px). Labels should be in `code-sm` or `body-sm`.

### Cards & Panels
- Cards must have a 1px border, but repeated cards should not all have the same box silhouette. Use connected grids, split panels, list rows, or asymmetric feature panels where possible.
- Use tonal surfaces over heavy shadows. A card hover can reveal a faint emerald edge or gradient, but should not jump or scale.

### Status Chips
- Use the `code-sm` font. Backgrounds should be low-saturation (e.g., a very dark red for "Error" with light red text) to ensure the interface doesn't become too "noisy."

### Code Blocks
- Use a distinct background (#000000) with a 1px emerald border left-accent. Use JetBrains Mono for the content.

### Homepage Sections
- **Hero:** Must immediately communicate developer trust: install command, source link, runtime credential injection, and a real terminal/agent moment.
- **Incident Proof:** Should feel like a security briefing, not blog cards. Use compact evidence panels with source metadata.
- **Problem/Context:** Use a high-readability editorial block plus a connected claim grid.
- **Features:** Should look like capability inventory for platform engineers. Numbering, labels, and borders matter.
- **Audience:** Should feel human and clear, with less box weight than feature inventory.
- **Architecture:** Should read like a layered control plane, with terminal/trace language and calm state indicators.
