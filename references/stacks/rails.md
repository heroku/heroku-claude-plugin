<!-- Source: https://devcenter.heroku.com/articles/ruby-support — verified 2026-07-30 -->

# Ruby on Rails on Heroku

## Supported Ruby Versions

| Version | Status |
|---------|--------|
| 4.0.6 | Supported |
| 3.4.10 | Supported |
| 3.3.12 | Supported (default: 3.3.9) |

Version is read from `Gemfile.lock` `RUBY VERSION` section. Always declare in `Gemfile`:
```ruby
ruby "3.3.12"
```

## Required Files

| File | Purpose |
|------|---------|
| `Gemfile` | Ruby dependencies |
| `Gemfile.lock` | Locked deps (must include RUBY VERSION and BUNDLED WITH) |
| `Procfile` | Process types |
| `config/puma.rb` | Puma web server config |

## Procfile

```
web: bundle exec puma -t 5:5 -p ${PORT:-3000} -e ${RACK_ENV:-production}
release: bundle exec rails db:migrate
```

- `release:` runs before new dynos start — never skip on a Postgres app
- `worker:` for Sidekiq: `worker: bundle exec sidekiq`

## Buildpack

Specified in `project.toml` (CNB on Cedar) — do not use `app.json` `buildpacks` array.

```toml
[[io.buildpacks.group]]
id = "heroku/ruby"

[[io.buildpacks.group]]
id = "heroku/procfile"
```

Primary language buildpack last, `heroku/procfile` always last.

## Default Addons

Rails apps should include `heroku-postgresql` by default.

## Gemfile Minimums

```ruby
# Gemfile
gem "rails"
gem "pg"           # Postgres adapter
gem "puma"         # Web server
gem "bootsnap"     # Boot time optimizations

group :production do
  # No sqlite3 in production
end
```

## app.json env

```json
"env": {
  "RAILS_MASTER_KEY": {
    "description": "Rails credentials master key",
    "required": true
  },
  "RAILS_LOG_TO_STDOUT": {
    "value": "enabled"
  },
  "RAILS_SERVE_STATIC_FILES": {
    "value": "enabled"
  }
}
```

## Heroku-Specific Gotchas

- `RAILS_MASTER_KEY` must be set as a config var — never commit `config/master.key`
- `RAILS_LOG_TO_STDOUT=enabled` required for logs to appear in `heroku logs`
- `RAILS_SERVE_STATIC_FILES=enabled` required if not using a CDN
- Always run `rails assets:precompile` as a release step or commit compiled assets
- Database: always `pg`, never `sqlite3` in production
- Bundler version must match `BUNDLED WITH` in `Gemfile.lock`

## Best Practices

### Formatting & Linting

Use RuboCop:

```bash
gem install rubocop rubocop-rails rubocop-performance
rubocop
rubocop -a   # auto-fix safe offenses
```

`.rubocop.yml`:

```yaml
require:
  - rubocop-rails
  - rubocop-performance

AllCops:
  NewCops: enable
  TargetRubyVersion: 3.3
  Exclude:
    - 'db/schema.rb'
    - 'bin/**/*'
    - 'vendor/**/*'
```

### Security

Use Brakeman for static security analysis:

```bash
gem install brakeman
brakeman -q
```

Key rules:
- Never commit `config/master.key` or `config/credentials/*.key`
- Use strong parameters in all controllers — `params.require(:model).permit(:field)`
- No dynamic SQL — always use ActiveRecord query methods or parameterized queries
- Set `force_ssl = true` in `config/environments/production.rb`
- `SECRET_KEY_BASE` and `RAILS_MASTER_KEY` via Heroku config vars only
- **Rails version:** Brakeman reports EOL Rails versions as High confidence warnings — always use the latest stable Rails (`gem "rails"` with no version pin, or `gem "rails", "~> 8.1"`) so `bundle install` pulls the current release. Never pin to a specific patch version in the Gemfile.

### Testing

Use RSpec (or Rails Minitest):

```bash
gem 'rspec-rails', group: [:development, :test]
rails generate rspec:install
bundle exec rspec
```

Factory Bot for test data (`factory_bot_rails`). Database Cleaner for isolation.

### Code Quality

- Thin controllers — business logic in service objects or models, not in controllers
- One responsibility per class/module
- Avoid N+1 queries — use `.includes` / `.eager_load`
- No dead code — remove unused methods, routes, and models

### Pre-commit

A `.pre-commit-config.yaml` is scaffolded into every app using the `pre-commit` framework:

```bash
gem install overcommit   # alternative: use pre-commit framework
pre-commit install
```

Hooks on `git commit`: RuboCop (auto-fix), Brakeman security scan, secret detection, large file check.
