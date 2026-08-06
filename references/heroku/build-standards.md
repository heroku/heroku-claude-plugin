# Heroku Plugin Build Standards

These rules apply to every build session without exception. They are not optional steps —
they are the contract between Claude and the user.

---

## ALWAYS Rules

**ALWAYS confirm requirements before starting any work.**
Ask: what stack, what features, what addons. If a framework is mentioned that the plugin
doesn't support, surface the supported options and confirm. Never assume. Never start
building until the user has confirmed the plan.

**ALWAYS confirm exactly what will be built — never assume functionality.**
Before writing code, present a concrete implementation plan and get explicit user approval:
- List every feature, endpoint, model, and integration you intend to build
- List what is explicitly NOT included (e.g. "no authentication", "no admin panel")
- Do not add functionality that was not confirmed — not authentication, not email, not logging pipelines, not anything beyond what the user approved
- If you think something is needed (e.g. seed data, health endpoint), ask — do not assume
- The user's confirmation is the contract. Build exactly that, nothing more./

**ALWAYS read the stack reference and coding standards before writing code.**
Before writing a single line:
- Read `${CLAUDE_PLUGIN_ROOT}/references/stacks/<stack>.md`
- Read `${CLAUDE_PLUGIN_ROOT}/references/heroku/deploy-contract.md`
- Read `${CLAUDE_PLUGIN_ROOT}/references/standards/<language>.md`

**ALWAYS follow coding standards.**
Standards are not a checklist to run at the end — they are applied throughout.
See `references/standards/` for the language-specific guide.

**ALWAYS use TDD — write the failing test first, then implement.**
For each feature:
1. Write a test that describes the expected behavior
2. Run it — confirm it fails
3. Implement the minimum code to make it pass
4. Refactor if needed
5. Move to the next feature

Never write implementation code without a corresponding test.

**ALWAYS record token usage at the end of every skill response.**
If `HEROKU_TOKEN_BUDGET_TRACKING=1` is set in the environment, run the following as the
final step of every skill, substituting the actual skill name and your estimated output
token count:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/token_usage.py record --skill <skill-name> --tokens <estimated-count>
```
The script will print a utilization line to the user and log the record to
`.heroku-plugin-token-usage.jsonl`. If the env var is not set, the script is a silent
no-op — always safe to call.

**ALWAYS run the pre-commit checklist before committing.**
See `references/heroku/pre-commit-checklist.md`. Every item must pass.
Tests must pass at 90%+ coverage. No lint errors. No security warnings.
Never commit broken or untested code.

**ALWAYS build the simplest thing first.**
Start with the minimal working version. No premature abstractions, no speculative features.
If the user asks for "a SaaS app," start with a working API endpoint, not a full platform.
Clarify scope before expanding it.

---

## Supported Stacks (v1)

| Stack | Language standards |
|-------|--------------------|
| `python` (fastapi / django / flask) | `references/standards/python.md` |
| `node` (express) | `references/standards/javascript.md` |
| `rails` | `references/standards/ruby.md` |
| `go` | `references/standards/go.md` |

If the user requests a stack not in this list, surface the supported options and ask for
a preference. Do not attempt to scaffold an unsupported stack.

---

## Build Flow

Every build session follows this sequence — no skipping steps:

```
1. Confirm requirements       ← stack, features, addons, confirmed by user
2. Read references            ← stack ref + deploy contract + language standards
3. For each feature:
   a. Write failing test
   b. Implement
   c. Pass test
4. Run pre-commit checklist   ← lint, format, security, 90% coverage
5. Commit
6. Deploy
```

---

## Scope Boundaries

The plugin builds **one stack per app**. If a user requests multiple technologies
(e.g. "Vue.js + Python"), clarify:
- Is Vue.js the frontend for a Python API? (two-stack — confirm this is needed for MVP)
- Or is this a Python-only app? (single-stack — simpler, preferred for v1)

Default to the simplest interpretation unless the user explicitly confirms multi-stack scope.
