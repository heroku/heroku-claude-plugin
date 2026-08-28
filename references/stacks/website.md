<!-- Sources: https://devcenter.heroku.com/articles/deploying-front-end-web and https://github.com/heroku/buildpacks-frontend-web/blob/main/README.md - verified 2026-08-28 -->

# Front-End Web Apps on Heroku

Use the Front-End Web Cloud Native Buildpacks (CNBs) for static websites, browser apps,
single-page apps (SPAs), progressive web apps (PWAs), and static web apps (SWAs). They
build an OCI image and run a purpose-built static web server on a Heroku dyno.

The resulting app serves HTML, CSS, JavaScript, and other static assets. It cannot run
custom server-side application code. Deploy a backend API as a separate app using the
appropriate language stack.

## Required Files

| App type | Required files |
|----------|----------------|
| Basic website | `project.toml` + `public/index.html` |
| Node-built website | `project.toml` + `package.json` + lockfile; build must produce a document root |
| Other static generator | `project.toml` + the language buildpack's marker files; build must produce a document root |

The static web server defines the default `web` process and listens on Heroku's assigned
`$PORT`. Front-end-only apps do not need a `Procfile` or the `heroku/procfile` buildpack.

## Basic Website

Place the site in `public/`, including a default `public/index.html`:

```toml
[_]
schema-version = "0.2"

[[io.buildpacks.group]]
id = "heroku/static-web-server"

[com.heroku.static-web-server]
root = "public"
index = "index.html"
```

`public` and `index.html` are the defaults, so the configuration table is optional when
those paths are used.

## Website with a Node.js Build

Define a `build` script in `package.json`. The Node.js CNB runs standard build-script
hooks, so a separate static-server build command is normally unnecessary:

```json
{
  "scripts": {
    "build": "vite build"
  }
}
```

List the language buildpack before the static web server, then configure the server to
serve the build output directory:

```toml
[_]
schema-version = "0.2"

[[io.buildpacks.group]]
id = "heroku/nodejs"

[[io.buildpacks.group]]
id = "heroku/static-web-server"

[com.heroku.static-web-server]
root = "dist"
index = "index.html"
```

Pin the Node.js version in `package.json` and commit exactly one package-manager lockfile.

## Framework Presets

Optional framework buildpacks detect common source layouts and configure the static web
server. List the language buildpack first, the static web server second, and the framework
buildpack last.

| Framework or layout | Buildpack | Detection or requirement | Delivery model |
|---------------------|-----------|--------------------------|----------------|
| Vite | `heroku/website-vite` | `vite` in `package.json` | SPA from Vite output |
| Next.js | `heroku/website-nextjs` | `next` in `package.json`; `output: 'export'` | Clean-URL, multi-page static export |
| Ember.js | `heroku/website-ember` | `ember-cli` in `package.json` | SPA from Ember output |
| Create React App | `heroku/website-cra` | `react-scripts` in `package.json` | SPA from CRA output |
| Public HTML | `heroku/website-public-html` | `public/index.html` | Website from `public/` |

Example for Vite:

```toml
[_]
schema-version = "0.2"

[[io.buildpacks.group]]
id = "heroku/nodejs"

[[io.buildpacks.group]]
id = "heroku/static-web-server"

[[io.buildpacks.group]]
id = "heroku/website-vite"
```

For Next.js, static export is required. For example, in `next.config.mjs`:

```javascript
const nextConfig = {
  output: 'export',
};

export default nextConfig;
```

Create React App was sunset in February 2025. Keep `heroku/website-cra` for existing apps,
but use Vite or a current framework for new apps.

## Website with Other Build Tools

For a generator written in another language, list that language's buildpack before the
static web server and configure the server's build hook. For example, Hugo:

```toml
[_]
schema-version = "0.2"

[[io.buildpacks.group]]
id = "heroku/go"

[[io.buildpacks.group]]
id = "heroku/static-web-server"

[com.heroku.static-web-server.build]
command = "sh"
args = ["-c", "hugo"]
```

Set `[com.heroku.static-web-server].root` if the generator does not write to `public/`.

## Server Configuration

Build-time server configuration belongs in `project.toml`. Changes require a rebuild.

### Document Root and Index

Defaults: `root = "public"` and `index = "index.html"`.

```toml
[com.heroku.static-web-server]
root = "dist"
index = "main.html"
```

### Response Headers and Caching

Use short-lived caching for HTML that can change between deploys and long-lived caching
only for assets with content-hashed filenames:

```toml
[com.heroku.static-web-server.headers."/"]
Cache-Control = "max-age=300, stale-while-revalidate=86400, stale-if-error=86400"

[com.heroku.static-web-server.headers."/*.html"]
Cache-Control = "max-age=300, stale-while-revalidate=86400, stale-if-error=86400"

[com.heroku.static-web-server.headers."/assets/*"]
Cache-Control = "max-age=31536000, immutable"
```

The server also supplies `Last-Modified` and `Etag` headers and supports conditional and
range requests. Configure security headers, including Content Security Policy, under
`[com.heroku.static-web-server.headers."*"]` or environment-specific header tables.

### Custom 404 Page

The file path is relative to the document root and must remain inside it:

```toml
[com.heroku.static-web-server.errors.404]
file_path = "error-404.html"
```

### SPA Client-Side Routing

Return the app shell for client-side routes, but exclude static asset paths so missing
assets still return a real `404`:

```toml
[com.heroku.static-web-server.errors.404]
file_path = "index.html"
status = 200
path_exclusions = ["/assets/*", "/static/*"]
```

Set exclusions to match the actual asset directories produced by the build tool.

### Additional Capabilities

The static web server also supports clean URLs, redirects and other static responses,
access logs, basic authorization, Caddy templates, and CSP nonces. These are optional;
prefer portable static delivery unless the app has a concrete need for server-specific
behavior.

## Build-Time Config Vars

Heroku config vars are not exposed to CNB builds by default. Enable build-time config
vars only when the build requires values such as private dependency credentials or
compilation flags:

```toml
[com.heroku.build.labs]
build_config_vars = true
```

Enabling this setting exposes config vars to the build process. Do not enable it for an
untrusted build tool, and do not compile secrets into browser-delivered files.

Source-controlled, non-secret build settings can instead use CNB build environment entries:

```toml
[[io.buildpacks.build.env]]
name = "CI"
value = "1"
```

## Runtime Config Vars

Use runtime configuration for public values that differ between staging and production,
such as API URLs, telemetry IDs, release versions, and browser-visible feature flags.
Prefix each Heroku config var with `PUBLIC_WEB_`:

```text
PUBLIC_WEB_API_URL=https://api-staging.example.com
PUBLIC_WEB_RELEASE_VERSION=v42
```

At every web-process start, the buildpack writes these values as data attributes on the
configured HTML document's `<head>`. JavaScript reads the lowercased keys through
`document.head.dataset`:

```javascript
const apiUrl =
  document.head.dataset.public_web_api_url || 'https://api.example.com';
```

Only `PUBLIC_WEB_*` variables are exposed. They are still public browser data: never put
passwords, API secrets, private tokens, or other credentials in them.

By default, the index document is rewritten. Configure multiple files or globs when needed:

```toml
[com.heroku.static-web-server.runtime_config]
html_files = ["**/*.html"]
```

Runtime configuration is enabled by default. Disable it only when the app does not need
HTML rewriting:

```toml
[com.heroku.static-web-server.runtime_config]
enabled = false
```

## Local Build and Run

Docker and `pack` are required for local CNB builds:

```bash
pack build my-web-app --builder heroku/builder:24
docker run --env PORT=8888 -p 8888:8888 \
  --env PUBLIC_WEB_API_URL=https://api.example.com \
  my-web-app
```

Then visit `http://localhost:8888`. The web process honors shutdown signals and uses the
same runtime configuration behavior as the deployed image.

## Default Addons

Front-end-only apps have no default addons. Databases, queues, and private credentials
belong behind a separately deployed server-side API rather than in browser code.

## Heroku-Specific Gotchas

- The Front-End Web CNB is a Cloud Native Buildpack; configure it in `project.toml`.
- List every required language buildpack before `heroku/static-web-server`.
- Do not add a custom Node.js static server solely to bind `$PORT`; the buildpack provides it.
- Do not add a `Procfile` unless replacing the buildpack's default `web` process intentionally.
- A Node-built site needs a valid `package.json` build script and the correct output root.
- Client-side routing, not-found handler must exclude asset directories or missing bundles.
- `PUBLIC_WEB_*` values are visible to every website visitor and must never contain secrets.
- Runtime config rewrites HTML at process start; invalid HTML can be normalized by the parser.
- Globbing thousands of runtime-config HTML files can noticeably delay process startup.
- Heroku CI does not support CNB.
