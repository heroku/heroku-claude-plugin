# Browser App Coding Standards

*Standards-based front-end development: accessible, secure, resilient, and fast*

---

## Core Philosophy

- **The web platform first**: Prefer semantic HTML, CSS, and browser APIs before adding abstractions
- **Progressive enhancement**: Deliver meaningful content and core actions before optional JavaScript
- **Accessibility by default**: Keyboard, screen-reader, zoom, contrast, and motion needs are requirements
- **Public-client boundary**: Treat all browser code, assets, and configuration as visible and untrusted
- **Performance is a feature**: Ship only the code and assets needed for the current experience

---

## HTML

### Document Structure

- Include `<!doctype html>`, a valid `lang` attribute, UTF-8 charset, and responsive viewport metadata
- Use landmark elements such as `header`, `nav`, `main`, and `footer`
- Keep headings hierarchical; do not choose heading levels for visual size
- Use buttons for actions and links for navigation; do not make non-interactive elements clickable
- Preserve useful content and navigation when optional JavaScript fails

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Catalog</title>
  </head>
  <body>
    <header>
      <nav aria-label="Primary">...</nav>
    </header>
    <main id="main-content">...</main>
  </body>
</html>
```

### Semantics and Forms

- Associate every form control with a visible `label`; placeholders are not labels
- Group related controls with `fieldset` and `legend`
- Use the correct `type`, `name`, `autocomplete`, and `inputmode` attributes
- Connect help and error text with `aria-describedby`
- Prefer native validation semantics, then add clear inline error messages
- Use ARIA only when native HTML cannot express the required semantics

---

## JavaScript

### Language and Modules

- Use ES modules, `const` by default, and `let` only for reassignment; never use `var`
- Use `===` and `!==`; avoid implicit coercion at data boundaries
- Prefer small named functions for domain behavior and arrow functions for short callbacks
- Use async/await with explicit loading, success, empty, and error states
- Keep state local; introduce global stores only when several independent views share state
- Follow the framework's established conventions when working in an existing app

### DOM and Events

- Query stable semantic hooks rather than layout-dependent selectors
- Use `textContent` for untrusted text; never insert untrusted content with `innerHTML`
- Attach behavior to native controls and preserve keyboard activation semantics
- Use event delegation only when it materially reduces listeners or supports dynamic children
- Remove global listeners, timers, observers, and subscriptions when their owner is destroyed
- Do not block the main thread with large synchronous loops or repeated layout reads and writes

### Network Requests

- Handle non-2xx responses explicitly; `fetch()` only rejects on network failure
- Give users a retry path for recoverable failures
- Cancel obsolete requests when a view changes or a newer request supersedes them
- Validate response shapes before rendering or using external data
- Keep API base URLs in public runtime configuration, not hardcoded per-environment builds

```javascript
async function loadCatalog(signal) {
  const apiUrl = document.head.dataset.public_web_api_url;
  const response = await fetch(`${apiUrl}/catalog`, { signal });

  if (!response.ok) {
    throw new Error(`Catalog request failed: ${response.status}`);
  }

  return response.json();
}
```

---

## CSS and Responsive Design

- Use normal document flow, Grid, and Flexbox before absolute positioning
- Design mobile-first and add breakpoints when content requires them, not for named devices
- Use relative units for typography and spacing so zoom and user preferences continue to work
- Define reusable colors, spacing, typography, and layer values with custom properties
- Keep selectors shallow and component-scoped; avoid `!important` except for documented overrides
- Reserve space for images and embeds to prevent layout shift
- Test narrow mobile, wide desktop, 200% zoom, and long or translated content

```css
:root {
  --color-text: #1f2937;
  --color-surface: #ffffff;
  --space-page: clamp(1rem, 4vw, 3rem);
}

main {
  width: min(72rem, 100% - 2 * var(--space-page));
  margin-inline: auto;
}
```

---

## Accessibility

- Meet WCAG 2.2 AA for all confirmed features
- Ensure every action is operable with keyboard alone in a logical focus order
- Provide a visible focus indicator; never remove outlines without an equivalent replacement
- Move focus only for a clear interaction reason, such as opening a modal or reporting validation errors
- Provide text alternatives for meaningful images and empty `alt` text for decorative images
- Do not communicate status, errors, or selection by color alone
- Meet contrast requirements for text, controls, focus indicators, and meaningful graphics
- Support browser zoom and text reflow without clipped content or two-dimensional scrolling
- Honor `prefers-reduced-motion` and avoid unnecessary animation
- Announce asynchronous status changes when they are not otherwise exposed to assistive technology
- Test with keyboard navigation and browser accessibility tooling, not only static linting

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Testing (TDD)

- **Write the failing test first**, then implement the smallest behavior that passes
- Use Vitest for Vite and ESM-first apps; use Jest where it is already established
- Use Testing Library queries that reflect how users find content: role, label, name, and text
- Test behavior and visible outcomes, not component internals or CSS class names
- Use Playwright for a small set of critical browser journeys and routing behaviors
- Run automated accessibility checks, then manually test keyboard and focus behavior
- Maintain at least 90% line coverage for application JavaScript; do not inflate coverage with trivial tests
- Test loading, empty, success, malformed-data, network-error, and retry states where applicable

```javascript
test('shows an accessible error when the catalog request fails', async () => {
  renderCatalog({ loadCatalog: () => Promise.reject(new Error('offline')) });

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Unable to load the catalog'
  );
  expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled();
});
```

For static sites without application JavaScript, verify generated HTML, links, metadata,
accessibility, and the deployed server behavior instead of adding meaningless unit tests.

---

## Security and Privacy

- Assume users can read and modify every downloaded script, asset, and runtime config value
- Never put passwords, private API keys, signing keys, or privileged tokens in browser code
- Never put secrets in `PUBLIC_WEB_*`, `VITE_*`, `NEXT_PUBLIC_*`, or similar public variables
- Keep authorization and trusted validation on the server; client checks improve UX only
- Prefer `textContent`, DOM construction, or a vetted sanitizer over raw HTML insertion
- Restrict third-party scripts and load only those required for confirmed functionality
- Configure a restrictive Content Security Policy and test it without unsafe exceptions where possible
- Use HTTPS for API calls and avoid mixed content
- Avoid storing sensitive data in `localStorage`; minimize retention of identifiers and telemetry
- Run `npm audit --audit-level=high` before deploy and address high or critical findings
- Commit one lockfile and review dependency changes, transitive packages, and install scripts

---

## Performance

- Set explicit performance goals and measure production builds, not only the development server
- Keep the initial JavaScript bundle small; split routes or features when it improves startup
- Lazy-load below-the-fold images and non-critical modules
- Serve correctly sized responsive images using `srcset` and `sizes`
- Preload only critical resources; excessive preloads compete with more important downloads
- Prefer system fonts or subset and self-host only the weights actually used
- Prevent layout shift by setting image dimensions and reserving space for asynchronous content
- Minify production assets and remove source maps from public deployment unless intentionally exposed
- Use immutable caching only for content-hashed assets; keep mutable HTML short-lived

---

## Routing and Error Handling

- Use normal links for navigation so open-in-new-tab, copy-link, and browser history work
- Give every meaningful view a stable URL when client-side routing is used
- Render a useful in-app not-found view for unknown client routes
- Configure Heroku SPA fallback only for app routes and exclude asset directories
- Let missing scripts, stylesheets, images, and source maps return actual `404` responses
- Preserve useful content and recovery actions when API requests fail

---

## Runtime Configuration

- Read environment-specific public values from `document.head.dataset`
- Access `PUBLIC_WEB_API_URL` as `document.head.dataset.public_web_api_url`
- Centralize config reads at the application boundary and validate required values at startup
- Provide safe defaults only when the behavior is genuinely environment-independent
- Treat every runtime config value as public, user-controlled input

```javascript
function readPublicConfig() {
  const apiUrl = document.head.dataset.public_web_api_url;

  if (!apiUrl) {
    throw new Error('PUBLIC_WEB_API_URL is required');
  }

  return { apiUrl: new URL(apiUrl) };
}
```

---

## Formatting and Pre-Commit

For JavaScript or TypeScript projects:

- Use ESLint with the framework's recommended rules and accessibility rules where available
- Use Prettier for JavaScript, TypeScript, JSON, CSS, and HTML
- Run unit tests, linting, formatting checks, and `npm audit --audit-level=high`
- Build the production bundle and verify that the configured document root contains `index.html`
- Test deep links directly when SPA fallback or clean URLs are enabled
- Check generated output for secrets and unintended environment values
- Remove debug logs, dead code, unused assets, and stale source maps before deploy

---

## Heroku-Specific

- See `references/stacks/website.md` for buildpack order, `project.toml`, routing, headers, and caching
- Use the `heroku/static-web-server` CNB instead of adding a custom server solely to host static files
- Let the buildpack's default `web` process bind to `$PORT`; front-end-only apps need no `Procfile`
- Use `PUBLIC_WEB_*` for public runtime values that must change without rebuilding
- Never expose secrets through public runtime config or compile them into static assets
- Keep server-side APIs and data stores in separate apps using the appropriate language stack
