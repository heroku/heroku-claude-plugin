<!-- Source: https://devcenter.heroku.com/articles/buildpacks — verified 2026-07-30 -->

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
- Specified in `app.json` `buildpacks` array

## Cloud Native Buildpacks (Fir)

- OCI image builds configured via `project.toml` (not `app.json`)
- Support arm64; auto-detect on every deploy
- Builders: `heroku/builder:24`, `heroku/builder:26`

## Specifying in app.json

```json
{
  "buildpacks": [
    { "url": "heroku/python" }
  ]
}
```

Use `heroku/<language>` shorthand for official buildpacks. For multiple buildpacks, order matters — primary language buildpack last.

## Auto-Detection Marker Files

| Language | Marker file |
|----------|-------------|
| Node.js | `package.json` |
| Python | `requirements.txt` |
| Ruby | `Gemfile` |
| Go | `go.mod` |
| Java | `pom.xml` / `build.gradle` |
| PHP | `composer.json` |
