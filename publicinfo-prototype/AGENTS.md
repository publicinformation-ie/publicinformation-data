# Agent Notes: publicinfo-prototype Styling Update

## Session Summary

Migrated from Tailwind CSS to custom CSS tokens based on the GOV.UK/gov.ie design system from `docs/HANDOFF-ASTRO.md`.

## Key Changes

### Files Created
- `src/styles/tokens.css` - CSS custom properties (colors, typography, spacing)
- `src/styles/global.css` - Global reset, typography, utilities
- `src/components/AppNav.astro` - Navigation header
- `src/components/AppFooter.astro` - Footer component
- `src/components/AuthorityCard.astro` - Public body card component

### Files Updated
- `src/layouts/Layout.astro` - Semantic structure with skip link
- `src/pages/index.astro` - Restyled body list
- `src/pages/body/[id].astro` - Restyled detail page (Design C variant)
- `astro.config.mjs` - Removed Tailwind plugin
- `package.json` - Removed Tailwind dependencies

## Design System Applied

### Colors
| Token | Hex | Usage |
|-------|-----|-------|
| `--color-primary` | #00723B | CTAs, links, brand |
| `--color-secondary` | #1B3A5C | Navigation, headings |
| `--color-focus` | #FFDD00 | Focus ring (accessibility) |
| `--color-grey-lightest` | #F3F2F1 | Section backgrounds |
| `--color-grey-light` | #DEE0E2 | Borders, dividers |
| `--color-grey-dark` | #505A5F | Secondary text |
| `--color-black` | #0B0C0C | Body text |

### Typography
- System fonts only (no external loading)
- Type scale: `--text-xl` (48px) through `--text-body-xs` (14px)
- Mobile scaling for headings (body text never reduces below 19px)

### Spacing
- 4px base unit: `--space-1` (4px) through `--space-8` (96px)

## Component Patterns

### AuthorityCard
- Left border accent (4px solid `--color-primary`)
- Category tag (uppercase, 14px bold)
- Authority name as link
- View action

### AppNav
- Simple: `publicinformation.ie` branding only
- Background: `--color-secondary`
- White text, sticky positioning

### AppFooter
- Platform disclaimer
- Background: `--color-grey-lightest`
- Top border: `--color-grey-light`

## Accessibility Notes

- Skip link: `<a href="#main-content" class="skip-link">Skip to main content</a>`
- Focus visible: `*:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px; }`
- Semantic HTML: proper use of `<main>`, `<nav>`, `<article>`, `<aside>`
- ARIA: `aria-label` on navigation, `aria-hidden` on decorative elements

## Layout Patterns

### Page Structure
```
<Layout>
  <AppNav />
  <main id="main-content">
    <content />
  </main>
  <AppFooter />
</Layout>
```

### Container
- Max-width: 960px (content), 1200px (full grids)
- Padding: `var(--space-4)` horizontally

### Grid
- Two-column: `grid-template-columns: 280px 1fr; gap: var(--space-6)`
- Card grid: `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))`

## Responsive Breakpoints

| Name | Query | Usage |
|------|-------|-------|
| Mobile | `@media (max-width: 639px)` | Stack layouts, full-width |
| Tablet+ | `@media (min-width: 640px)` | Multi-column grids |
| Wide | `@media (min-width: 900px)` | Sidebar layouts |

## Utility Classes Available

- `.container` - Max-width 960px, centered
- `.prose` - Max-width 66ch for readability
- `.btn`, `.btn--primary`, `.btn--secondary` - Button styles
- `.border-top`, `.border-bottom` - Border utilities
- `.text-*` - Color utilities
- `.bg-*` - Background utilities
- `.mt-*`, `.mb-*`, `.py-*` - Spacing utilities
- `.table` - Table styling

## Lessons Learned

1. **Tailwind removal**: When replacing Tailwind, ensure `astro.config.mjs` doesn't reference `@tailwindcss/vite` plugin
2. **CSS imports**: Use `@import` for token files in global CSS
3. **Component structure**: Scoped styles in Astro components work well with CSS variables
4. **Accessibility first**: Build skip links and focus states from the start
5. **Mobile-first**: Design for mobile, enhance for desktop

## Future Work

- Add search functionality to homepage
- Implement mobile hamburger menu for AppNav
- Create remaining components from HANDOFF (StatusBadge, RequestCard, etc.)
- Add archive page for request browsing
- Authentication pages (login, register)
