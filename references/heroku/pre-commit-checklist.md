# Pre-Commit Checklist

Run this before every `git commit`. Every item must pass. This is a gate, not a retrospective.

---

## 1. Tests pass at 90%+ coverage

```bash
# Python
pytest --cov=. --cov-fail-under=90

# Node
npm test -- --coverage --coverageThreshold='{"global":{"lines":90}}'

# Go
go test -cover ./...

# Rails
bundle exec rspec
```

If coverage is below 90%, write the missing tests before committing.

## 2. No lint errors

```bash
# Python
ruff check .

# Node
npm run lint

# Go
go vet ./... && golangci-lint run

# Rails
bundle exec rubocop
```

## 3. Code is formatted

```bash
# Python
ruff format --check .

# Node
npm run format -- --check

# Go
gofmt -l .   # must output nothing

# Rails
bundle exec rubocop --autocorrect-all
```

## 4. Security scan passes

```bash
# Python (ruff S rules cover this — already in lint step)

# Node
npm audit --audit-level=high

# Go
gosec ./...   # already in golangci-lint step

# Rails
bundle exec brakeman -q
```

## 5. No unnecessary code

Review staged changes before committing:
- No dead code (unused functions, unreachable branches)
- No commented-out code
- No debug logging or `print`/`console.log` statements left in
- No empty implementations (e.g. empty migration `upgrade()`, empty test bodies)
- No TODO comments for things that should be done before shipping

## 6. All tests are meaningful

For each test:
- Does the description match what it actually asserts?
- Is there any dead setup (mocks configured but never used)?
- Is the assertion specific enough to catch a regression?
- Does it test behavior, not implementation?

## 7. No secrets committed

Check staged files for:
- Hardcoded API keys, tokens, passwords
- `.env` files
- `config/master.key` or `config/credentials/*.key`
- Any string that looks like a secret

## 8. deploy-readiness-reviewer passes

Before deploying, the deploy-readiness-reviewer agent must find no blockers:
- `web:` process defined in Procfile, binding to `$PORT`
- `.heroku-plugin-scaffold.json` valid — addons and secret_env_vars present
- `DATABASE_URL` / `REDIS_URL` not hardcoded
- No empty migration `upgrade()` bodies
- `.gitignore` excludes secrets and build artifacts
