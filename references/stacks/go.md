<!-- Source: https://devcenter.heroku.com/articles/go-support — verified 2026-09-10 -->

# Go on Heroku

## Supported Versions

Last 2 major versions of Go. Set version in `go.mod`:
```
go 1.24
```

Or via `GOVERSION` environment variable. Version spec like `go1.22` expands to the latest `1.22.x` release.

## Required Files

| File | Purpose |
|------|---------|
| `go.mod` | Go module definition (triggers Go detection) |
| `go.sum` | Dependency checksums |
| `Procfile` | Process types (optional — auto-generated if absent) |

## Procfile

```
web: bin/<app-name>
```

Or if building in place:
```
web: go run main.go
```

App must bind to `$PORT`:
```go
port := os.Getenv("PORT")
if port == "" {
    port = "8080"
}
http.ListenAndServe(":"+port, nil)
```

## Buildpack

Auto-detected from `go.mod`. Explicit: `heroku/go`

## go.mod Minimum

```
module github.com/user/myapp

go 1.24
```

## Default Addons

Go apps have no default addons. Postgres and Redis are opt-in.

## Heroku-Specific Gotchas

- Always read `$PORT` from the environment — never hardcode
- Go toolchain is **not** included in the compiled slug — only the binary
- Build happens at deploy time; ensure all dependencies are in `go.sum`
- If using database, import `database/sql` and read `DATABASE_URL` from env
- `CGO_ENABLED=0` is set by default for portability — avoid CGo unless necessary
- Binary is placed in `bin/<module-name>` by the buildpack; Procfile `web:` must reference this path

## Best Practices

### Formatting & Linting

Go enforces formatting as part of the toolchain:

```bash
gofmt -w .          # format in place
goimports -w .      # format + fix imports (install: go install golang.org/x/tools/cmd/goimports@latest)
go vet ./...        # catch common errors
```

Use `golangci-lint` for comprehensive static analysis:

```bash
# install
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
golangci-lint run
```

`.golangci.yml`:

```yaml
linters:
  enable:
    - errcheck
    - gosimple
    - govet
    - ineffassign
    - staticcheck
    - unused
    - gosec
```

### Testing

Use the standard `go test`:

```bash
go test ./...
go test -race ./...         # detect data races
go test -cover ./...        # coverage report
```

Table-driven tests are the Go idiom — group related cases in a `tests []struct{...}` slice.

**Reaching 90% coverage on handler/db packages:** Go handler and DB packages have many error branches (rows.Err(), scan errors, mid-transaction failures, template render errors) that are unreachable via normal happy-path tests. Write these from the start — do not wait for a coverage shortfall:

- **DB error paths** — use PostgreSQL CHECK constraint or BEFORE INSERT trigger violations to force errors inside transactions:
  ```sql
  -- in a test helper
  _, _ = db.Exec(`ALTER TABLE products ADD CONSTRAINT test_fail CHECK (false)`)
  // then call your DB function — it will error predictably
  _, _ = db.Exec(`ALTER TABLE products DROP CONSTRAINT test_fail`)
  ```
- **Template render errors** — pass a `failWriter` (implements `io.Writer`, always returns an error) to `templates.ExecuteTemplate` to cover the render error branch.
- **Form parse errors** — wrap the request body in an `errReader` (always returns an error) to trigger `r.ParseForm()` failures.
- **rows.Err() and scan errors** — covered naturally when the constraint-injection tests force early exits from query loops.

Write these tests during the TDD cycle, not as a retrofit. Starting below 90% on Go and trying to reach it afterwards is expensive.

### Security

Use `gosec` for security scanning:

```bash
go install github.com/securego/gosec/v2/cmd/gosec@latest
gosec ./...
```

Key rules:
- Never hardcode secrets — read all credentials from `os.Getenv`
- Always check and handle errors — no `_` on error returns in production code
- Validate and sanitize external input before use
- Use `crypto/rand` not `math/rand` for anything security-sensitive
- Database: read `DATABASE_URL` from env; parse with `url.Parse` before use

### Code Quality

- Explicit error handling at every call site — never discard errors
- Small, focused functions — Go convention is short names in small scopes
- Keep `main.go` thin — wire up dependencies and start the server; business logic in packages
- `go.sum` must be committed — it is the reproducible build lock

### Pre-commit

A `.pre-commit-config.yaml` is scaffolded into every app:

```bash
pip install pre-commit   # pre-commit framework is Python-based
pre-commit install
```

Hooks on `git commit`: `gofmt` check, `go vet`, `golangci-lint`, secret detection, large file check.
