# Ruby / Rails Coding Standards

*Idiomatic Ruby: expressive, convention-following, and secure*

---

## Core Philosophy

- **Convention over configuration**: Follow Rails conventions — don't fight the framework
- **Duck typing over class checks**: Ask what an object can do, not what it is
- **Follow the linter**: Let RuboCop encode the house style; write to it from the first draft
- **Thin controllers, fat models**: Business logic belongs in models and service objects

---

## Code Style

### Formatting & Linting
- Use `rubocop --autocorrect-all` before every commit
- Use `brakeman -q` for security scanning before every commit
- Never commit with RuboCop errors or Brakeman warnings

### Naming
- `snake_case` for methods, variables, symbols, files
- `PascalCase` for classes and modules
- `SCREAMING_SNAKE_CASE` for constants
- Predicate methods end in `?`: `user.active?`, `order.complete?`
- Dangerous methods end in `!`: `user.save!`, `record.destroy!`

### Language features
- Use Ruby's built-in query methods: `count.zero?` not `count == 0`
- Prefer `&.` (safe navigation) over `nil` checks
- Use `frozen_string_literal: true` at the top of every file
- Single-quoted strings unless interpolation is needed

---

## Testing (TDD)

- **Write the failing test first**, then implement
- Use `RSpec` — tests in `spec/` mirroring the app structure
- **Minimum 90% coverage** — use `simplecov` with `minimum_coverage 90`
- Use `FactoryBot` for test data — never fixtures for complex objects
- Use `DatabaseCleaner` for isolation between tests
- Test behavior, not implementation — test what the method does, not how

```ruby
# Good — behavior-focused
RSpec.describe "GET /api/catalog" do
  it "returns only active items" do
    create(:item, active: true)
    create(:item, active: false)
    get "/api/catalog"
    expect(response).to have_http_status(200)
    expect(json_body.count).to eq(1)
  end
end

# Bad — implementation detail
it "calls Item.where(active: true)" do
  expect(Item).to receive(:where).with(active: true)
  ...
end
```

---

## Code Quality

### Controllers
- Thin controllers — delegate to service objects or models
- Use strong parameters: `params.require(:order).permit(:name, :total)`
- Never put business logic in controllers

### Models
- Validate at the model layer — don't rely on the database alone
- Use scopes for common queries: `scope :active, -> { where(active: true) }`
- Avoid N+1 queries — use `.includes` / `.eager_load`

### Error handling
- Rescue specific exceptions, not `StandardError` globally
- Log with context before re-raising or surfacing to the user
- Never expose internal error details in API responses

### Security
- Strong parameters in every controller — no `params.permit!`
- No dynamic SQL — use ActiveRecord query methods or `sanitize_sql`
- `force_ssl = true` in `config/environments/production.rb`
- Never commit `config/master.key` or `config/credentials/*.key`
- Run `brakeman` before every deploy

---

## Heroku-Specific

- See `references/stacks/rails.md` for Procfile patterns, buildpack config, and gotchas
- `release:` process must run `rails db:migrate` before dynos start
- `RAILS_MASTER_KEY` via `heroku config:set` — never committed
- `RAILS_LOG_TO_STDOUT=enabled` required for `heroku logs` to work
- All secrets via `heroku config:set` — never in code or committed files
