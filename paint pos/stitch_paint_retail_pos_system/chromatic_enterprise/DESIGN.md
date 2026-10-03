---
name: Chromatic Enterprise
colors:
  surface: '#f8f9fa'
  surface-dim: '#d9dadb'
  surface-bright: '#f8f9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f5'
  surface-container: '#edeeef'
  surface-container-high: '#e7e8e9'
  surface-container-highest: '#e1e3e4'
  on-surface: '#191c1d'
  on-surface-variant: '#434655'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f2'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#545f73'
  on-secondary: '#ffffff'
  secondary-container: '#d5e0f8'
  on-secondary-container: '#586377'
  tertiary: '#006242'
  on-tertiary: '#ffffff'
  tertiary-container: '#007d55'
  on-tertiary-container: '#bdffdb'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#d8e3fb'
  secondary-fixed-dim: '#bcc7de'
  on-secondary-fixed: '#111c2d'
  on-secondary-fixed-variant: '#3c475a'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#f8f9fa'
  on-background: '#191c1d'
  surface-variant: '#e1e3e4'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  mono-data:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  container-margin: 24px
  gutter: 16px
---

## Brand & Style
The design system for this retail POS environment is rooted in **Corporate Modernism** with a high-contrast, functional edge. It is engineered for high-velocity retail environments where clarity and speed are paramount. The aesthetic balances the utility of industrial software with the sleekness of contemporary SaaS.

The interface utilizes a "split-surface" strategy: a clean, airy workspace for data entry and customer interaction, contrasted against deep, authoritative control panels for systemic navigation. This creates an immediate mental model for the user between "Work Area" and "Navigation/Global Controls."

**Key Principles:**
- **Precision:** Mathematical alignment and consistent 8px increments.
- **Vibrancy:** High-saturation accents to guide the eye toward primary actions.
- **Efficiency:** Minimalist ornamentation to reduce cognitive load during long shifts.
- **Tactility:** Subtle micro-shadows to provide depth without cluttering the screen.

## Colors
The palette is dominated by three distinct functional zones:

1.  **Canvas (#F8F9FA):** A light, neutral base used for the main workspace, ensuring that text and data points are highly legible.
2.  **Control (#1E293B):** A deep Navy Slate used for sidebar navigation, header bars, and persistent control panels. This creates a high-contrast anchor for the UI.
3.  **Action (#2563EB):** An "Electric Blue" reserved exclusively for primary calls-to-action (CTAs), focus states, and progress indicators.
4.  **Feedback (#10B981):** A "Muted Sage" used for success states, completed orders, and active inventory status.

**Dynamic Motif:** Use a rotating hue-shift for the "Color Wheel" motif (e.g., paint mixing status) that spans the spectrum, but ensure it always sits against a white or neutral background to prevent color vibrating.

## Typography
This design system uses **Inter** for its exceptional legibility in data-dense environments. 

- **Numeric Data:** Always enable "tabular figures" (`tnum`) for price columns, SKU numbers, and quantities to ensure vertical alignment in tables.
- **Hierarchy:** Use the Navy Slate color for headlines to maintain contrast. Use `text_muted` for secondary labels.
- **Scale:** On mobile or tablet devices, `display-lg` should scale down to `24px` to ensure the layout remains functional for handheld inventory scanning.

## Layout & Spacing
The layout follows a **8px grid system**. This mathematical rhythm ensures that all components, regardless of complexity, feel unified.

- **Desktop:** 12-column fluid grid for the main canvas, with a fixed 240px sidebar (Navy Slate).
- **Tablet (Landscape):** Persistent sidebar collapses into an icon-only rail (72px) to maximize the workspace for paint mixing controls.
- **Mobile:** Single column layout with a bottom-docked action bar for checkout.

**Density:** The "High-Contrast" nature allows for a "Compact" density mode in data tables, reducing row height to 40px while maintaining a 16px horizontal cell padding.

## Elevation & Depth
Depth is conveyed through **Low-Contrast Outlines** and **Micro-Shadows**.

- **Surfaces:** Use 1px borders (#E2E8F0) for all containers and input fields.
- **Shadows:** Only used to indicate "interactability" or "overlay." Use a single, very soft shadow: `0px 1px 2px rgba(15, 23, 42, 0.05)`.
- **Active State:** When an element (like a card) is selected, use a 2px Electric Blue border rather than a larger shadow to maintain the clean, "flat-plus" aesthetic.
- **Overlays:** Modals and dropdowns use a slightly more pronounced shadow: `0px 10px 15px -3px rgba(15, 23, 42, 0.1)`.

## Shapes
The design system uses a consistent **8px (0.5rem)** radius for all primary UI components including buttons, input fields, and cards.

- **Branch Selectors:** These use the "Pill" shape (Full Radius) to distinguish them from functional action buttons.
- **Status Indicators:** Use a 4px (Soft) radius for small tags to maintain crispness at small scales.
- **Mixing Controls:** Circular elements (Color Wheels) are the only true circles allowed in the UI, highlighting their unique functional role.

## Components

### Buttons & CTAs
- **Primary:** Electric Blue background, white text. No gradient.
- **Secondary:** Transparent background, Navy Slate border and text.
- **Ghost:** No border, Muted Slate text, becomes lightly filled on hover.

### Data Tables
- **Header:** Light gray (#F1F5F9) background, uppercase `label-md` typography.
- **Row:** White background, 1px bottom border. Hover state uses a 2% tint of Electric Blue.
- **Numeric Cells:** Right-aligned with tabular font settings.

### Branch Selector Pills
- High-contrast Navy Slate pills with a white location icon. When active, they switch to Electric Blue to indicate the current branch context.

### Filter Chips
- Rounded 8px containers with a subtle #E2E8F0 border. Use a "Close" (X) icon that appears only when the filter is active.

### Paint Mixing Controls
- A custom component featuring a circular "Hue Ring" and a "Saturation/Value" square. 
- Input fields for CMYK/RGB values should be grouped horizontally with a 1px divider.
- Large, 48px square swatches provide a "Real-view" of the mixed color.

### Input Fields
- Height: 40px for standard, 48px for touch-optimized POS views.
- Border: 1px #E2E8F0, switching to 2px #2563EB on focus.
- Labels: Always positioned above the field, never as placeholders only.