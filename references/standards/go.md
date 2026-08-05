# Go Coding Standards

*Idiomatic Go: simple, explicit, and readable*

---

## Core Philosophy

- **Clarity over cleverness**: Go favors straightforward code over elegant abstractions
- **Explicit over implicit**: Make behavior and error paths obvious
- **Standard library first**: Reach for stdlib before adding a dependency
- **Small interfaces**: Prefer composing small interfaces over large ones
- **Errors are values**: Handle them explicitly — never discard

---

## Code Style

### Formatting
- Run `gofmt -w .` before every commit — non-negotiable
- Run `goimports -w .` to fix imports
- Run `go vet ./...` to catch common errors
- Run `golangci-lint run` for comprehensive static analysis
- Never commit with vet errors or lint failures

### Naming
- Short, descriptive names — context provides meaning (`u` for user in a user function)
- Acronyms are all-caps: `userID`, `httpClient`, `parseURL`
- Unexported names for package-internal use; only export what callers need
- Receiver names: short and consistent (`func (u *User) Save()` — not `self` or `this`)

### Package design
- Package names: lowercase, single words, no underscores
- Package name describes what it provides, not what it contains (`http` not `httputils`)
- Avoid `util`, `common`, `misc` — signs of poor factoring

---

## Testing (TDD)

- **Write the failing test first**, then implement
- Use `go test ./...` — standard toolchain, no external framework needed
- **Minimum 90% coverage** — `go test -cover ./...`; enforce with `-coverprofile` in CI
- Run `go test -race ./...` to catch data races
- Use table-driven tests for related cases:

```go
// Good — table-driven, behavior-focused
func TestHealthHandler(t *testing.T) {
    tests := []struct {
        name       string
        method     string
        wantStatus int
    }{
        {"GET returns 200", http.MethodGet, http.StatusOK},
        {"POST returns 405", http.MethodPost, http.StatusMethodNotAllowed},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            ...
        })
    }
}
```

---

## Code Quality

### Error handling
- Check and handle every error — never assign to `_` in production code
- Wrap errors with context: `fmt.Errorf("loading config: %w", err)`
- Return errors to the caller; log at the top level only

### Functions
- One responsibility per function
- Keep `main.go` thin — wire dependencies and start the server; business logic in packages
- Prefer explicit parameters over global state

### Security
- Never hardcode secrets — read from `os.Getenv` only
- Use `crypto/rand` for anything security-sensitive — never `math/rand`
- Validate and sanitize all external input at the boundary
- Use `gosec` rules — `golangci-lint` runs it by default with our `.golangci.yml`

### Dependencies
- Always commit `go.sum` — it is the reproducible build lock
- Vet new dependencies: active maintenance, minimal transitive deps
- `go mod tidy` before committing any dependency change

---

## Heroku-Specific

- See `references/stacks/go.md` for Procfile patterns, buildpack config, and gotchas
- Always read `$PORT` from `os.Getenv("PORT")` — never hardcode
- Binary placed at `bin/<app-name>` by buildpack — Procfile must reference this path
- All secrets via `heroku config:set` — never in code or committed files
