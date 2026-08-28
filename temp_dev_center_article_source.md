Deploy your static website, browser app, single-page app (SPA), progressive web app (PWA), or static web app (SWA) to Heroku with the [Front-End Web Cloud Native Buildpack](https://github.com/heroku/buildpacks-frontend-web) (CNB). Heroku supports the complete front-end development cycle, from local development, to review apps, to pipeline promotions to production.

With Heroku’s developer experience, the Front-End Web CNB builds a [12-factor app](https://12factor.net/), supporting [runtime configuration through HTML Data attributes](#runtime-config-vars). A high-efficiency web server, running on Heroku dynos, delivers the resulting website, optimized for the [role of a CDN origin](#caching). Like other CNBs, [Heroku CI](heroku-ci) doesn't support this CNB.

For an architectural overview, see [How the Front-End Web Cloud Native Buildpack Works](/articles/how-the-front-end-web-cloud-native-buildpack-works).

For pre-existing static sites deployed on Heroku, see the migration guides to Front-End Web CNB:

 * [Migrating from the Nginx Buildpack](/articles/migrating-from-the-nginx-buildpack-to-front-end-web-cnb)
 * [Migrating from create-react-app-buildpack](/articles/migrating-from-create-react-app-buildpack-to-front-end-web-cnb).

## Using the Buildpacks

Select the buildpacks for your app based on its architecture.

In the app source repo, add the buildpacks to [`project.toml`](managing-buildpacks#set-a-cloud-native-buildpack). This project file is the standard CNB way to configure how an app builds and launches. Begin the file with:

```toml
[_]
schema-version = "0.2"
```

#### Basic Website

For a basic website, add a `public/` directory containing HTML files, a default document of `index.html`:

```toml
[[io.buildpacks.group]]
id = "heroku/static-web-server"

[com.heroku.static-web-server]
root = "public"
index = "index.html"
```

#### Website with Node.js Build

For a website with a Node.js build dependency, like JavaScript/Node.js front-end frameworks, include a build command in the app's `package.json`. For example:

```json
{
  "scripts": {
    "build": "npm build"
  }
}
```

Then, set the buildpacks in the `project.toml`. In this example, the build command outputs to the `dist/` directory, so the web server is configured to serve that directory:

```toml
[[io.buildpacks.group]]
id = "heroku/nodejs"

[[io.buildpacks.group]]
id = "heroku/static-web-server"

[com.heroku.static-web-server]
root = "dist"
index = "index.html"
```

#### Website with Other Language Build Tools

For a website with a build tool in another language besides JavaScript/Node.js, for example Go/Hugo, the language buildpack compiles the tool and then calls it from the static web server's build hook:

```toml
[[io.buildpacks.group]]
id = "heroku/go"

[[io.buildpacks.group]]
id = "heroku/static-web-server"

[com.heroku.static-web-server.build]
command = "sh"
args = ["-c", "hugo"]
```

## Configuration

On Heroku, the [`project.toml`](managing-buildpacks#set-a-cloud-native-buildpack) file and [config vars](config-vars) set the CNB configuration. Heroku front-end web apps support two distinct phases of configuration, [during the build process](#build-time-config-vars) and then [at runtime](#runtime-config-vars) when the web server launches.

### Build-Time Config Vars

>warning  
>Enabling this feature can expose secret values to the build process. Using this feature along with untrusted third-party build tools can expose your app's sensitive config values to malicious actors.

This config controls how to build the app, requiring a rebuild for changes to take effect. The default value is `false` or not enabled.

Example build-time configurations:

* **Credentials for private dependencies**, such as `NPM_TOKEN`
* **Compilation flags**, such as `NODE_ENV`

To enhance security, Heroku doesn’t automatically expose config vars to the CNB build process. To get access to [Heroku config variables at build-time](build-time-config-vars), enable this feature. 

```toml
[com.heroku.build.labs]
build_config_vars = true
```

### Document Root

This config is the directory in the app's source code to serve over HTTP. The default value is `"public"`.

```toml
[com.heroku.static-web-server]
root = "my_docroot"
```

### Index Document

This config is the file to respond with when a request doesn't specify a document, such as requests to a bare hostname like `https://example.com`. The default value is `"index.html"`.

```toml
[com.heroku.static-web-server]
index = "main.html"
```

### Custom Response Headers

The default settings are the server's built-in headers.

#### Global Headers

Respond with custom headers for any request path with the wildcard `*`.

```toml
[com.heroku.static-web-server.headers."*"]
X-Server = "hot stuff"
```

#### Path-Matched Headers

Respond with custom headers that match exactly against the request URL's path:

```toml
# The index page (index.html is not specified in the URL).
[com.heroku.static-web-server.headers."/"]
Cache-Control = "max-age=300, stale-while-revalidate=86400, stale-if-error=86400"

# HTML pages.
[com.heroku.static-web-server.headers."/*.html"]
Cache-Control = "max-age=300, stale-while-revalidate=86400, stale-if-error=86400"

# Contents of a subdirectory.
[com.heroku.static-web-server.headers."/images/*"]
Cache-Control = "max-age=31536000, immutable"

# Set multiple headers for a match.
[com.heroku.static-web-server.headers."/downloads/*"]
Cache-Control = "public, max-age=604800"
Content-Disposition = "attachment"
```

### Custom Errors

The default settings are the server's built-in errors.

#### 404 Not Found

Set [error 404 configuration](https://github.com/heroku/buildpacks-frontend-web/blob/main/buildpacks/static-web-server/README.md#404-not-found) to respond with a custom `Not Found` HTML page. The path to this file is relative to the document root. Make sure that the file is inside the document root.

```toml
[com.heroku.static-web-server.errors.404]
file_path = "error-404.html"
```

#### 404 Not Found for Single Page Apps

Most modern single-page web apps use a path-based [`pushState`](https://developer.mozilla.org/en-US/docs/Glossary/Hash_routing#modern_alternatives) client-side routing. Include a [404 Not Found configuration](https://github.com/heroku/buildpacks-frontend-web/blob/main/buildpacks/static-web-server/README.md#404-not-found) in the `project.toml` to respond to all unmatched request URLs with the default document containing the static app.

For example, for single-page app (SPA) client-side routing, where not found request URLs respond with the single-page app, respond with a `200` instead:

```toml
[com.heroku.static-web-server.errors.404]
file_path = "index.html"
status = 200
path_exclusions = ["/assets/*", "/static/*"]
```

Set the `path_exclusions` to match server-side files that aren't included in the special behavior for client-side routing, such as a JavaScript bundle and image resources.

### Runtime Config Vars

Set any config values that are different for various environments, such as staging and production, of an app as runtime, not build-time, configuration.

Example runtime configurations:

* **API URLs**: such as `https://backend.example.com`, which requires a staging instance pointed to `https://backend-staging.example.com`.
* **Third-party service IDs**: such as for sending telemetry, logging, and analytics.
* **Feature flags**: used to enable and disable new functionality in an existing build.

Typically during build, front-end frameworks replace Node.js `process.env` references with their JSON value, a quoted string. Different build tools can implement different methodology for resolving build-time configuration. These build outputs are saved in the container image, and therefore can’t change without rebuilding the app.

With the Front-End Web CNB, runtime config is injected into the HTML `<head>` element every time a web process (dyno) restarts. Rebuild isn't required.

Only environment variables prefixed with `PUBLIC_WEB_` get exposed.

#### Runtime Configuration Enabled

Default: `true`

If it’s unnecessary or undesirable for a specific app, you can disable runtime configuration. The default value is `false`:

```toml
[com.heroku.static-web-server.runtime_config]
enabled = false
```

#### Runtime Configuration HTML Files

Default: the **[index document](#index-document)**

This config is the list of HTML files to rewrite with `<head data-public_web_*>` attributes loaded from the `PUBLIC_WEB_*` environment variables. The default is the **[index document](#index-document)**.

The files must be in the document root.

```toml
[com.heroku.static-web-server.runtime_config]
html_files = ["index.html", "subsection/index.html"]
```

`*` wildcards and globbing are supported for websites that include many HTML files.

```toml
[com.heroku.static-web-server.runtime_config]
html_files = ["*.html"]
```

Recursive globbing is also supported, for websites that include many HTML files nested within subdirectories.

```toml
[com.heroku.static-web-server.runtime_config]
html_files = ["**/*.html"]
```

#### Using Runtime Configuration

To access these runtime configuration values, the browser app reads its configuration from the standard JavaScript DOM property `document.head.dataset`.

>warning  
>Don’t include secret values in these `PUBLIC_WEB_`-prefixed environment variables. They’re injected into the website where anyone on the internet can see the values.

For example, an app starts with the environment:

```
PUBLIC_WEB_API_URL=https://api-staging.example.com
PUBLIC_WEB_RELEASE_VERSION=v42
PORT=3000
HOME=/workspace
```

When a web browser fetches the default HTML document, you can access the `PUBLIC_WEB_*` vars from JavaScript using the [HTML Data attributes](https://developer.mozilla.org/en-US/docs/Web/HTML/How_to/Use_data_attributes) via `document.head.dataset`:

```javascript
document.head.dataset.public_web_api_url
// → "https://api-staging.example.com"
document.head.dataset.public_web_release_version
// → "v42"

// Not exposed because not prefixed with PUBLIC_WEB_
document.head.dataset.port
// → null
document.head.dataset.home
// → null
```

The variable names are case-insensitive, accessed as lowercase. Although environment variables are colloquially uppercased, the resulting HTML Data attributes are set and accessed lowercased, because [they're case-insensitive XML names](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/data-*).

For example, when using the `public_web_api_url` for a `fetch()` call:

```javascript
// If the PUBLIC_WEB_API_URL variable is not set, default to the production API host.
const apiUrl = document.head.dataset.public_web_api_url || 'https://api.example.com';
const response = await fetch(apiUrl, {
  method: "POST",
  // …
});
```

Alternatively, preset default values in the HTML document's head element:

```html
<html>
<!-- If the PUBLIC_WEB_API_URL variable is set, this value in the document will be overwritten -->
<head data-public_web_api_url="https://api.example.com">
  <title>Example</title>
</head>
<body>
  <h1>Example</h1>
</body>
</html> 
```

Then, the JavaScript doesn’t need a default value specified:

```javascript
const response = await fetch(document.head.dataset.public_web_api_url, {
  method: "POST",
  // …
});
```

### More Config Options

The static web server includes an array of deeper configuration options. See the [Server-specific Configuration section of the GitHub docs](https://github.com/heroku/buildpacks-frontend-web/blob/main/buildpacks/static-web-server/README.md#server-specific-configuration) for more details about:

* Access logs
* Clean URLs
* Static responses such as redirects
* Basic authorization
* Content-security-policy (CSP) nonces

## Caching

Websites deployed with the Front-End Web CNB are hosted directly in Heroku dynos. The static web server running on Heroku handles all requests from the internet. While this works great for development and small-scale production deployment, you can enhance website performance and resiliency to traffic spikes with well-crafted cache control headers and a content delivery network (CDN), such as Cloudflare or Fastly.

### Cache-Control Headers

`Cache-Control` headers define how individual web browsers and caching proxies, like CDNs, can store and reuse content, enhancing the performance and resiliency of a website.

In the static web app's `project.toml` file, configure HTTP response headers. The web server automatically responds with `Last-Modified` and `Etag` headers, and handles requests with conditional `If-Match`, `If-Unmodified-Since`, `If-Modified-Since`, `If-None-Match`, `Range`, and `If-Range` headers.

For example, HTML documents with content that can change over their lifetime, through multiple deployments, cache optimistically for a short period. If the origin server is down, the cached pages are used:

```toml
# The index page (index.html isn't specified in the URL)
[com.heroku.static-web-server.headers."/"]
Cache-Control = "max-age=300, stale-while-revalidate=86400, stale-if-error=86400"

# HTML pages
[com.heroku.static-web-server.headers."/*.html"]
Cache-Control = "max-age=300, stale-while-revalidate=86400, stale-if-error=86400"
```

Many web frameworks output content-hashed JS and CSS bundles with unique filenames fingerprinted by each build. You can strongly cache these immutable assets to optimize their delivery and persistence in web browsers:

```toml
[com.heroku.static-web-server.headers."/assets/*"]
Cache-Control = "max-age=31536000, immutable"
```

### CDN Configuration

You can set up a CDN, such as Cloudflare or Fastly, in front of a Heroku app to cache responses geographically closer to end users, improving the performance and resiliency of a website.

Default or custom domains can reach Heroku apps deployed behind a CDN. Either target is valid. The choice is based on whether you're adding a CDN to an app that already has a custom domain.

#### CDN with herokuapp.com

The default Heroku app domain requires no additional DNS setup to bootstrap.

>note  
>This method works for a new app that doesn’t have a custom domain. When you plan to use custom domains, we recommend migrating to the [custom domain CDN config](#cdn-with-custom-domain).

For the CDN origin configuration, use the Heroku app's default hostname, like `my-app-1234567890.herokuapp.com`.

Make sure that the CDN:

* Connects to the origin via HTTPS/TLS.
* Uses the `herokuapp.com` name as `Host` for requests to the origin, so that it doesn’t forward an incorrect `Host` header to Heroku.

#### CDN with Custom Domain

[Custom domains for Heroku apps](custom-domains) along with [automated certificate management](automated-certificate-management) (ACM) supports gracefully switching public DNS from the Heroku app to the CDN.

>note  
>This method is ideal when adding a CDN to an app that‘s already set up with a custom domain. If the origin server must perform hostname-based routing, such as for hostname redirection, then this custom domain setup is required.

For the CDN origin configuration, use the target Heroku SNI endpoint name for the custom domain, like `whispering-willow-5678.herokudns.com`. You can find the unique target for each custom domain in the **`Settings`** tab of the [Heroku Dashboard](heroku-dashboard) or with the [`heroku domains`](heroku-cli-commands#heroku-domains) command from the CLI.

Make sure that the CDN:

* Connects to the origin via HTTPS/TLS.
* Forwards the `Host` header to the origin to indicate to the Heroku router what domain is being requested.

For the custom domain's Heroku ACM to continue to be successful behind a CDN, it must support passing through Acme HTTP-01 challenges via plain HTTP to origin for the path `/.well-known/acme-challenge/*`.

#### Public Domain Name Switchover

When you implement a CDN, you must point the public DNS name at the CDN, instead of at Heroku. Refer to the public DNS setup documentation for your selected CDN.

Whenever you switch over DNS records between targets, turn down the time to live (TTL) of the records to quickly propagate the change around the world. With a shorter TTL, if there's a mistake, you can quickly revert it. Before the switchover, lower the TTL to 300 seconds or five minutes. After a DNS change settles, you can turn the TTL back up to 86400-seconds or one day or longer to enhance lookup performance.

## Build and Run Locally with Docker

You need [Docker](https://store.docker.com/search?type=edition&offering=community) and [`pack`](https://buildpacks.io/docs/for-platform-operators/how-to/integrate-ci/pack/) for building and launching CNBs locally.

In the root of the app's source Git repo, build the app with `pack build`. 

For example, build `my-web-app` with its build config vars:

```
pack build \
--builder heroku/builder:24 \
--env NODE_ENV=development \
my-web-app
```

Then, run the app with `docker run`.  For example, run `my-web-app` with its runtime config vars:

```
docker run \
--env PORT=8888 -p 8888:8888 \
--env PUBLIC_WEB_API_URL=https://api.example.com \
my-web-app
```

Visit [http://localhost:8888](http://localhost:8888/) in a web browser.

## Deploying on Heroku

In the root of the app's source Git repo, create the Heroku app and deploy the code to it with `git push`. 

For example, with `my-web-app`:

```
heroku apps:create my-web-app --stack cnb
git push heroku
```

Visit the app's `herokuapp.com` URL in a web browser.

## Additional Reading

* [Front-End Web Buildpack repo](https://github.com/heroku/buildpacks-frontend-web)
* [How the Front-End Web Cloud Native Buildpack Works](/articles/how-the-front-end-web-cloud-native-buildpack-works)
* [Migrating from the Nginx Buildpack to Front-End Web CNB](/articles/migrating-from-the-nginx-buildpack-to-front-end-web-cnb)