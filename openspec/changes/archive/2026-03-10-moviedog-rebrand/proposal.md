## Why

MegaQueue's current branding is generic and forgettable — a simple download arrow icon with a dark gray theme. By rebranding the user-facing identity to "movie dog" with a playful, illustrative design language inspired by a hand-drawn dog mascot, the app becomes more distinctive, fun, and recognizable as a home-built tool with personality.

## What Changes

- **Rename the display name** from "MegaQueue" to "movie dog" across all user-facing surfaces (page titles, manifest, nav bar). File names, URLs, and code references remain unchanged.
- **Replace PWA icons** (icon.svg, icon-192.png, icon-512.png) with new icons derived from the dog mascot illustration (dog1.jpeg) — a white chalk/stamp-style dog on a vibrant blue (#3B4CF6) background.
- **New design language** inspired by the mascot illustration:
  - Primary color shifts from dark gray/blue (#1f2937/#3b82f6) to a vibrant blue (#3B4CF6) with white as the accent/contrast color.
  - Chalk/hand-drawn aesthetic for the icon and branding elements.
  - Overall UI remains dark-themed but accent colors update to match the new vibrant blue palette.
- **Update PWA manifest** with new name, colors, and icon references.
- **Update HTML meta tags** (theme-color, apple-touch-icon, page title) to reflect the new brand.

## Capabilities

### New Capabilities
- `moviedog-brand-identity`: Defines the new movie dog visual identity — mascot icon, color palette, typography feel, and how they apply across the PWA (icons, manifest, meta tags, nav bar title).

### Modified Capabilities
- `pwa`: Update manifest name/short_name, theme_color, background_color, and icon references to reflect the movie dog brand.
- `web-ui`: Update base template title, theme-color meta tag, nav bar app name, and accent color classes to use the new movie dog design language.

## Impact

- **Static assets**: `megaqueue/static/icons/` — all three icon files replaced (icon.svg, icon-192.png, icon-512.png)
- **PWA manifest**: `megaqueue/static/manifest.json` — name, colors, icons updated
- **HTML template**: `megaqueue/templates/base.html` — title, meta tags, nav branding updated
- **CSS/Tailwind classes**: Accent color classes in templates shift from `blue-600`/`blue-700` to the new vibrant blue, or a custom Tailwind config color
- **No backend changes** — this is purely a frontend/branding change
- **No URL or filename changes** — routes, Python modules, and repo names stay as-is
