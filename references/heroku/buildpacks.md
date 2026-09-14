<!-- Source: https://devcenter.heroku.com/articles/buildpacks — verified 2026-09-10 -->

# Heroku Buildpacks

## Officially Supported Languages

Ruby, Python, Java, Clojure, Node.js, Scala, Go, PHP, .NET

## Buildpack Slugs (Shorthand)

| Language | Slug |
|----------|------|
| Node.js | `heroku/nodejs` |
| Python | `heroku/python` |
| Ruby | `heroku/ruby` |
| Go | `heroku/go` |
| Java | `heroku/java` |
| PHP | `heroku/php` |
| Scala | `heroku/scala` |
| Clojure | `heroku/clojure` |
| .NET | `heroku/dotnet` |

## Classic Buildpacks (Cedar)

- Auto-detected from marker files (`package.json`, `go.mod`, `Gemfile`, `requirements.txt`, etc.)
- Once set on an app, locked for future deploys unless changed
- **Not used by this plugin** — this plugin targets CNB on Cedar via `project.toml`

## Cloud Native Buildpacks (CNB)

- OCI image builds configured via `project.toml` (not `app.json`)
- Available on Fir (GA) and Cedar (not yet GA)
- This plugin targets CNB on Cedar: `project.toml` is generated for every scaffolded app

## Specifying in project.toml (CNB)

```toml
[_]
schema-version = "0.2"

[io.buildpacks]

[[io.buildpacks.group]]
id = "heroku/nodejs"

[[io.buildpacks.group]]
id = "heroku/procfile"
```

Use `heroku/<language>` shorthand for official buildpacks. Always include `heroku/procfile` last
when a `Procfile` is present. Do not specify buildpacks in `app.json` — `project.toml` is
authoritative for CNB builds.

## Auto-Detection Marker Files

| Language | Marker file |
|----------|-------------|
| Node.js | `package.json` |
| Python | `requirements.txt` |
| Ruby | `Gemfile` |
| Go | `go.mod` |
| Java | `pom.xml` / `build.gradle` |
| PHP | `composer.json` |
