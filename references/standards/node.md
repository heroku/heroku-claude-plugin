# JavaScript / Node.js Coding Standards

*The Good Parts style: clarity, composition, and avoiding common pitfalls*

---

## Core Philosophy

- **Clarity over cleverness**: Prefer readable, obvious code over elegant tricks
- **Composition over inheritance**: Favor small composable functions
- **Explicit over implicit**: No hidden state, no surprising side effects
- **Standard library first**: Reach for Node.js built-ins before adding a package

---

## Code Style

### Formatting
- Use `prettier` — single quotes, trailing commas (es5), enforced via `npm run format`
- Use `eslint` — run `npm run lint` before every commit
- Never commit with lint errors

### Naming
- `camelCase` for variables, functions, methods
- `PascalCase` for classes and constructors
- `SCREAMING_SNAKE_CASE` for module-level constants
- Prefix private/internal helpers with `_` as a convention signal

### Language features
- Always `const` first; use `let` only when reassignment is needed; never `var`
- Use `===` and `!==` — never `==` or `!=`
- Arrow functions for callbacks and short expressions; named functions for top-level definitions
- Async/await over raw Promise chains — makes control flow readable
- Destructure early to clarify intent: `const { id, name } = user`

---

## Testing (TDD)

- **Write the failing test first**, then implement
- Use `jest` — tests in `__tests__/` or colocated as `*.test.js`
- **Minimum 90% coverage** — configure `jest --coverage --coverageThreshold='{"global":{"lines":90}}'`
- Test behavior, not implementation — test what the function does, not how
- One concept per test; use descriptive test names

```javascript
// Good — tests behavior
test('GET / returns 200 with status ok', async () => {
  const res = await request(app).get('/');
  expect(res.status).toBe(200);
  expect(res.body.status).toBe('ok');
});

// Bad — tests implementation detail
test('index handler calls res.json', () => {
  ...
});
```

---

## Code Quality

### Functions
- One responsibility per function
- Keep route handlers thin — business logic in separate modules, not inline
- No silent `catch (() => {})` — always handle or rethrow errors with context

### Error handling
- Use `try/catch` with async/await — never let unhandled rejections escape
- Log errors with context before surfacing to the user
- Never expose internal error details in HTTP responses

### Security
- Use `helmet` middleware — sets secure HTTP headers
- Never hardcode secrets — read from `process.env` only
- Validate and sanitize all external input at the boundary
- Set `ssl: { rejectUnauthorized: false }` for Heroku Postgres connections
- Run `npm audit` before deploy — fix high/critical before shipping

### Dependencies
- Separate `devDependencies` from `dependencies` — build tools (Vite, TypeScript, Jest) are dev-only
- **Exception**: any tool needed at Heroku build time (e.g. `vite build` in `heroku-postbuild`) must be in `dependencies`, not `devDependencies` — Heroku prunes devDependencies before running build scripts
- Keep `package-lock.json` committed

---

## Heroku-Specific

- See `references/stacks/node.md` for Procfile patterns, buildpack config, and gotchas
- Always read port from `process.env.PORT` — never hardcode
- `npm start` must be defined in `package.json` scripts
- All secrets via `heroku config:set` — never in code or committed files
