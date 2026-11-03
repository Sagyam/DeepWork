# Design language

One look across Sagyam's apps and sites: the portfolio
(sagyamthapa.com.np), the labelling-harness site, DeepWork's landing page
(`Sagyam/deepwork-site`, `src/styles/global.css`) and this app
(`ui/src/style.css`). A new app copies the tokens and fonts below, then picks
one brand colour of its own.

## Fonts

| Role | Font | Used for |
|---|---|---|
| Display | Space Grotesk (variable, 300–700) | headings, nav labels, field labels, eyebrows, big numbers |
| Body | Work Sans (variable, 100–900) | everything else |
| Mono | JetBrains Mono (variable, 100–800) | code, domains, commands |

Self-hosted latin `woff2` files (`/fonts/*.woff2`), never a font CDN: the
desktop apps work offline. Preload the display and body files.

## Colour tokens

Light is `:root`, dark is `.dark` on `<html>`. Names follow shadcn/ui, so a
Tailwind 4 `@theme inline` block can map them one to one (as the site does).

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `--background` | `#f8fafc` | `#020817` | page / window canvas, input fill |
| `--card` | `#ffffff` | `#0b1522` | cards, sheets, dialogs, outline buttons |
| `--foreground` | `#0f1729` | `#f8fafc` | text |
| `--muted` | `#eaf0f6` | `#1d283a` | hover fill, tags, tracks |
| `--muted-foreground` | `#4e5e73` | `#94a3b8` | secondary text, labels |
| `--border` | `#d7dfea` | `#1d283a` | every border and divider |
| `--primary` | `#0977ae` | `#5abff2` | actions and choices: primary buttons, links, checkboxes, selected items, focus ring |
| `--primary-foreground` | `#ffffff` | `#0f1c2e` | text on primary |
| `--brand` | per app | per app | the app's own colour (DeepWork: `#b45309` / `#f2b336`, amber) |
| `--brand-soft` | per app | per app | brand-tinted backgrounds (DeepWork: `#fdf3e2` / `#2a1f0b`) |
| `--loss` / `--loss-soft` | `#c52020` / `#fdecec` | `#e45858` / `#2b1214` | errors, destructive, what was lost |
| `--pass` / `--pass-soft` | `#138a61` / `#e6f6ef` | `#1baf7a` / `#0b2419` | success, saved, allowed |
| `--night` | `#141a2e` | `#0b1020` | shadows, modal backdrops |

Rules:

- Sky blue means "you can act here or you chose this". The brand colour is
  identity and data (DeepWork: the timer ring, progress bar, chart bars,
  pending-change notices), never a button.
- Red and green carry meaning only; never decoration.
- Tints are `color-mix(in oklab, var(--x) N%, transparent)`, not new hex values.

## Shapes and components

- **Cards**: `1px solid var(--border)`, radius 12px, `var(--card)` fill.
  Nested panels (rule groups, routine cards, stat tiles) use radius 8–10px and
  `var(--background)` fill, so they read as wells inside the card.
- **Buttons** (radius 6px, weight 500): outline by default (card fill, border,
  hover `--muted`); `.primary` is filled sky blue; `.danger` is a red outline;
  `.link` is primary text with an underline on hover.
- **Inputs and selects**: radius 6px, `--background` fill, 32px tall in forms.
- **Eyebrow**: a 24–32px rule, then an uppercase Space Grotesk label,
  `letter-spacing: 0.16em`, muted. Sits above a section heading.
- **Field labels**: uppercase Space Grotesk 11px, `letter-spacing: 0.1em`, muted.
- **Segmented control** (also the theme switch): a muted, bordered track; the
  chosen option is a raised `--card` chip with a hairline shadow.
- **Selected nav item**: a raised card with a border; the label turns primary.
- Shadows are soft and rare: hairline (`0 1px 2px`) on raised controls,
  `0 8px 28px` only on floating things (HUD cards, dialogs, tooltips).

## Theme switch

System / Light / Dark, with icons (monitor, sun, moon). Stored in
`localStorage.theme` (missing means System); a tiny inline script in `<head>`
sets `.dark` before first paint, and the page follows the OS while on System.
On the site it sits in the footer; in an app it is Settings → Appearance. It
is a view preference: it never goes into the app's config or backend.
