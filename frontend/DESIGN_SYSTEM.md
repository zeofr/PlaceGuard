# PlaceGuard Design System

## Overview

PlaceGuard's design system is inspired by Ramaiah Institute of Technology's official website, creating a professional, trustworthy placement management platform that feels institutionally credible while maintaining modern SaaS sensibilities.

## Visual Identity

### Design Philosophy
- **Institutional credibility**: Professional appearance appropriate for an official college portal
- **Modern without being flashy**: Clean, purposeful design without AI-generated aesthetics
- **Student-focused**: Easy to navigate and understand
- **Information hierarchy**: Clear distinction between critical and supporting information

### What We Avoid
- Generic purple-blue AI gradients
- Excessive glassmorphism and gratuitous effects
- Meaningless decorative elements
- Overly rounded, card-heavy layouts
- Technical jargon exposed to end users

## Color System

### Primary Colors

**Brand Red** (from RIT identity)
```
brand-600: #dc2626 - Primary buttons, CTAs, links
brand-700: #b91c1c - Hover states, emphasis
brand-50:  #fef2f2 - Light backgrounds
```

**Navy Blue** (from RIT identity)
```
navy-700: #334e68 - Navigation bar, headers
navy-800: #243b53 - Primary headings
navy-300: #9fb3c8 - Subdued text in dark areas
```

### Semantic Colors

**Success (Eligible)**
```
success-600: #16a34a - Buttons, icons
success-100: #dcfce7 - Backgrounds
success-700: #15803d - Text
```

**Danger (Ineligible)**
```
danger-600: #dc2626 - Buttons, icons
danger-100: #fee2e2 - Backgrounds
danger-700: #b91c1c - Text
```

**Warning (Unknown/Attention)**
```
warning-600: #ca8a04 - Buttons, icons
warning-100: #fef9c3 - Backgrounds
warning-700: #a16207 - Text
```

### Neutral Colors

```
gray-50:  #f9fafb - Page backgrounds
gray-100: #f3f4f6 - Card hover states
gray-200: #e5e7eb - Borders
gray-600: #4b5563 - Secondary text
gray-900: #111827 - Primary text
```

## Typography

### Font Family
```css
font-family: 'Inter', system-ui, -apple-system, sans-serif
```

### Scale

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| Page title (h1) | 2xl-3xl | Bold (700) | navy-800 |
| Section heading (h2) | xl | Bold (700) | navy-800 |
| Subsection (h3) | lg | Semibold (600) | gray-900 |
| Body text | sm-base | Regular (400) | gray-900 |
| Secondary text | sm | Medium (500) | gray-600 |
| Caption/metadata | xs | Medium (500) | gray-500 |

### Line Height
- Headings: `leading-tight` (1.25)
- Body text: `leading-relaxed` (1.625)
- Dense UI: `leading-none` (1)

## Components

### Cards
```
Background: white
Border: 1px solid gray-200
Radius: rounded-xl (0.75rem)
Shadow: shadow-soft (custom)
Padding: p-6 (1.5rem)
Hover: shadow-medium, border-brand-300
```

### Buttons

**Primary**
```
Background: brand-600
Hover: brand-700
Text: white
Padding: px-4 py-2.5
Radius: rounded-lg
Font: font-medium
Shadow: shadow-md on hover
```

**Secondary**
```
Background: white
Border: 1px solid gray-300
Hover: bg-gray-50
Text: gray-700
```

### Badges

**Status Badges**
```
Padding: px-3 py-1
Radius: rounded-full
Font: text-xs font-semibold
Border: 1px solid (matching color)
```

Examples:
- Eligible: `bg-success-100 text-success-700 border-success-200`
- Ineligible: `bg-danger-100 text-danger-700 border-danger-200`
- Unknown: `bg-warning-100 text-warning-700 border-warning-200`

### Input Fields
```
Border: 1px solid gray-300
Radius: rounded-lg
Padding: px-4 py-2.5
Focus: ring-2 ring-brand-500, border-transparent
Font: text-sm
```

### Navigation Bar
```
Background: navy-700
Border: border-b border-navy-800
Shadow: shadow-md
Text: white with navy-200 for secondary
```

## Spacing System

Follows Tailwind's default spacing scale:
- **Micro**: `gap-2` (0.5rem) - Between closely related items
- **Small**: `gap-4` (1rem) - Standard component spacing
- **Medium**: `gap-6` (1.5rem) - Between sections
- **Large**: `gap-8` (2rem) - Major page sections

## Layout Patterns

### Page Structure
```
<Navbar /> - Full width, navy background
<main className="max-w-7xl mx-auto px-6 py-8">
  <Page header> - Title, description, actions
  <Content grid> - Responsive grid or single column
</main>
```

### Card Grid
```tsx
<div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
  {items.map(item => <Card key={item.id} {...item} />)}
</div>
```

### Two-Column Layout (Detail Page)
```tsx
<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div className="lg:col-span-2">{/* Main content */}</div>
  <div>{/* Sidebar */}</div>
</div>
```

## Text Formatting Rules

### Never Expose Technical Identifiers

Transform all backend identifiers before display:

| ❌ Don't Show | ✅ Show Instead |
|--------------|----------------|
| `min_cgpa_lte: 7.5` | Minimum CGPA: 7.5 or below |
| `allowed_branches: ["CSE"]` | Eligible branches: Computer Science and Engineering |
| `backlog_count_lte: 0` | Active backlogs: None allowed |
| `has_prior_offer: false` | Prior placement offer: Not allowed |

Implementation: Use `src/lib/formatters.ts` utilities throughout the application.

### Branch Name Expansion

Always expand branch abbreviations:
- CSE → Computer Science and Engineering
- ISE → Information Science and Engineering
- ECE → Electronics and Communication Engineering
- etc.

### Operator Formatting

Convert comparison operators to natural language:
- `gte` → "at least" or "or above"
- `lte` → "maximum" or "or below"
- `eq` → "exactly" or just show value
- `in` → "one of"

## Iconography

Use Heroicons (already included in Tailwind):
- Simple, outline style
- 16px (`w-4 h-4`) for inline icons
- 20px (`w-5 h-5`) for emphasis
- 24px (`w-6 h-6`) for headers

Examples:
- Checkmark: Success states
- X mark: Error/ineligible states
- Question mark: Unknown states
- Clock: Deadlines, time-based info
- Arrow right: Navigation, CTAs

## Animation & Interaction

### Hover States
```
transition-colors duration-200
hover:shadow-medium
hover:border-brand-300
```

### Loading States
- Spinner: Circular with brand-600 accent
- Skeleton: Gray animated pulse
- Button: Opacity 60%, disabled cursor

### Focus States
Always show clear focus rings for accessibility:
```
focus:outline-none focus:ring-2 focus:ring-brand-500
```

## Responsive Design

### Breakpoints
- **sm**: 640px - 2-column grids
- **md**: 768px - Enhanced spacing
- **lg**: 1024px - 3-column grids, sidebars
- **xl**: 1280px - Maximum content width

### Mobile-First Approach
Start with single-column, stack layouts, then enhance for larger screens.

## Accessibility

### Color Contrast
- Text on backgrounds: Minimum WCAG AA (4.5:1)
- Interactive elements: Clear hover and focus states
- Status colors: Additional non-color indicators (icons, text)

### Keyboard Navigation
- All interactive elements focusable
- Clear focus indicators
- Logical tab order

### Screen Readers
- Semantic HTML (nav, main, article, section)
- Alt text for images
- ARIA labels where needed

## Component Composition

### Example: Drive Card
```tsx
<Link href={`/drive/${id}`} className="card p-6 hover:shadow-medium...">
  <div className="flex items-start justify-between mb-4">
    <h2 className="font-bold text-navy-800...">{company}</h2>
    <StatusBadge status={status} />
  </div>
  
  <div className="mb-4">
    <p className="text-xs font-semibold text-gray-500...">Deadline</p>
    <p className="text-sm font-semibold text-gray-900">{formattedDate}</p>
  </div>
  
  <div className="flex items-center gap-2 text-brand-600...">
    <span>View details</span>
    <ArrowRightIcon />
  </div>
</Link>
```

## Resources

- Tailwind CSS Documentation: https://tailwindcss.com
- Inter Font: https://fonts.google.com/specimen/Inter
- Heroicons: https://heroicons.com
- WCAG Guidelines: https://www.w3.org/WAI/WCAG21/quickref/

## Maintenance

When adding new features:
1. Use existing color tokens
2. Follow spacing conventions
3. Apply formatters to all user-facing text
4. Test on mobile, tablet, desktop
5. Verify keyboard navigation
6. Check color contrast

This design system should remain stable while allowing PlaceGuard to grow and evolve.
