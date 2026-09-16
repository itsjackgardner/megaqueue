## Context

MegaQueue is a Flask-based PWA that manages downloads via a MegaBasterd backend. It currently uses a generic dark theme with blue accents (#3b82f6) and the name "MegaQueue" everywhere. The app is served behind Cloudflare Tunnel/Zero Trust.

The user has a hand-drawn dog mascot illustration (dog1.jpeg) — a white chalk/stamp-style dog wearing a party hat on a vibrant blue (#3B4CF6) background. This becomes the foundation for a new "movie dog" brand identity.

The rebrand is cosmetic only — no file renames, URL changes, or backend modifications.

## Goals / Non-Goals

**Goals:**
- Replace all user-facing "MegaQueue" text with "movie dog"
- Generate new PWA icons from the dog1.jpeg mascot in all required sizes (SVG, 192px, 512px)
- Establish a new color palette anchored on the mascot's vibrant blue
- Update the manifest, meta tags, and nav bar to reflect the new brand

**Non-Goals:**
- Renaming Python modules, file paths, repo names, or URLs
- Changing MegaBasterd branding (separate desktop app)
- Redesigning the full UI layout or adding new features
- Adding custom fonts or complex CSS — Tailwind utility classes remain the approach

## Decisions

### 1. Icon generation approach
**Decision**: Create a new SVG icon by tracing the key elements of the dog mascot (head, party hat) as a simplified vector. Generate PNGs from the SVG at 192x192 and 512x512.

**Rationale**: The source image (dog1.jpeg) is a raster with a chalk texture that won't scale well as a tiny favicon. A simplified vector capture of the dog's silhouette on the vibrant blue background keeps the spirit while being crisp at all sizes. The PNGs can be generated from the SVG or from a resized/optimized version of the original jpeg.

**Alternative considered**: Using the raw jpeg cropped/resized — rejected because JPEG artifacts look poor at small icon sizes and PWA icons should ideally be PNG.

### 2. Color palette
**Decision**: Shift primary accent from Tailwind `blue-600` (#2563eb) to a custom vibrant blue matching the mascot background (~`#3B4CF6`, closest to Tailwind `indigo-500`/#6366f1 or a custom value). Use Tailwind's `indigo-500`/`indigo-600` as the closest standard palette match.

**Rationale**: Using an existing Tailwind color avoids needing a custom Tailwind config (which would require moving off CDN). `indigo-500`/`indigo-600` is the closest standard Tailwind shade to the mascot's blue. The dark background theme (#111827 gray-900) stays — it provides good contrast with the vibrant blue.

**Alternative considered**: Custom Tailwind color via CDN config block — adds complexity for marginal color accuracy gain.

### 3. Scope of text renaming
**Decision**: Replace "MegaQueue" with "movie dog" in: page `<title>`, manifest `name`/`short_name`, nav bar heading, and apple-mobile-web-app-title meta tag. Leave all Python identifiers, filenames, and URLs unchanged.

**Rationale**: The user explicitly wants a superficial rename only. Internal code names don't matter to end users.

## Risks / Trade-offs

- **[Existing PWA installs]** → Users who previously installed the PWA will see the old name/icon cached. They'll need to reinstall. The service worker has no caching so this should resolve on next visit, but the home screen icon won't auto-update. Acceptable for a personal-use app.
- **[Color shift subtlety]** → Moving from blue-600 to indigo-500/600 is a modest shift. Some UI elements may need manual review to ensure contrast is adequate. Mitigated by testing in browser after changes.
- **[Icon fidelity]** → A simplified SVG won't capture the full chalk texture of the original. This is intentional — clean icons work better at small sizes. The original illustration spirit (dog + party hat + blue bg) is preserved.
