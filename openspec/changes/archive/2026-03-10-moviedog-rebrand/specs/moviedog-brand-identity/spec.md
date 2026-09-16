## ADDED Requirements

### Requirement: movie dog mascot icon
The application SHALL use a mascot icon depicting a stylized dog with a party hat, rendered as white on a vibrant blue background (#3B4CF6 or nearest Tailwind indigo equivalent). The icon SHALL be available as `icon.svg` (scalable vector), `icon-192.png` (192x192 pixels), and `icon-512.png` (512x512 pixels) in `/static/icons/`.

#### Scenario: SVG icon matches brand identity
- **WHEN** the SVG icon file is rendered
- **THEN** it displays a simplified dog head with party hat in white on a vibrant blue (#3B4CF6) rounded-rectangle background

#### Scenario: PNG icons are correctly sized
- **WHEN** the PNG icon files are examined
- **THEN** `icon-192.png` is exactly 192x192 pixels and `icon-512.png` is exactly 512x512 pixels, both depicting the same mascot as the SVG

### Requirement: movie dog color palette
The application SHALL use a color palette anchored on vibrant blue (Tailwind `indigo-500`/`indigo-600`) as the primary accent color, replacing the previous `blue-600`/`blue-700`. The dark background theme (`gray-900`/`gray-800`) SHALL be retained.

#### Scenario: Primary buttons use indigo accent
- **WHEN** a primary action button is rendered
- **THEN** it uses `indigo-600` as the background color and `indigo-700` on hover

#### Scenario: Dark theme is preserved
- **WHEN** any page is loaded
- **THEN** the body background remains `gray-900` and card/nav backgrounds remain `gray-800`

### Requirement: movie dog display name
All user-facing references to the application name SHALL display "movie dog" instead of "MegaQueue". This includes the HTML page title, PWA manifest name/short_name, navigation bar heading, and apple-mobile-web-app-title meta tag.

#### Scenario: Page title shows movie dog
- **WHEN** a user loads any page
- **THEN** the browser tab title starts with "movie dog"

#### Scenario: Nav bar shows movie dog
- **WHEN** a user views the navigation bar
- **THEN** the app name displayed is "movie dog"
