<!-- Source: https://devcenter.heroku.com/articles/heroku-postgresql — verified 2026-07-30 -->
<!-- Source: https://devcenter.heroku.com/articles/heroku-redis — verified 2026-07-30 -->

# Heroku Addons (Plugin Supported)

## Heroku PostgreSQL

**Slug:** `heroku-postgresql`
**Config var:** `DATABASE_URL`

### Plans

| Tier | Notes |
|------|-------|
| Essential | Entry-level, shared infrastructure |
| Standard | Dedicated, rollback, HA optional |
| Premium | HA, continuous protection, read replicas |
| Private | VPN-capable, compliance-ready |
| Shield | HIPAA/PCI-eligible |

### Key Facts

- Provisioning: `heroku addons:create heroku-postgresql`
- Multiple databases per app supported; designate one as primary
- Databases can be shared between apps
- Supports Heroku Dataclips, PGBackups, continuous protection

---

## Heroku Key-Value Store (Redis)

**Slug:** `heroku-redis`
**Config var:** `REDIS_URL` (first instance); `HEROKU_REDIS_<COLOR>_URL` for additional instances

> Note: Heroku Key-Value Store runs on Valkey (Redis-compatible). API and client libraries are unchanged.

### Plans

| Plan | Persistence | HA | Notes |
|------|-------------|-----|-------|
| mini | None | No | Dev/test only |
| premium-0 to premium-7 | AOF | Yes | Production |
| private | AOF | Yes | VPN-capable |
| shield | AOF | Yes | Compliance |

### Key Facts

- **TLS required** on all plans — use `rediss://` URL scheme
- Valkey 8.1 default (EOL Q4 2027); 7.2 available (EOL Q4 2026)
- Bloom filters and ValkeyJSON available on v8.1+
- Custom attachment name: `heroku addons:create heroku-redis --as CACHE` → `HEROKU_REDIS_CACHE_URL`

---

## Unsupported Addons (v1)

| Addon | Status |
|-------|--------|
| Apache Kafka on Heroku | Not supported in v1 — planned |

---

## Config Var Reference

| Slug | Config Var | Notes |
|------|------------|-------|
| `heroku-postgresql` | `DATABASE_URL` | Standard postgres:// URL |
| `heroku-redis` | `REDIS_URL` | Must use TLS (rediss://) |
