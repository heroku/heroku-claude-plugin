# Scenario Eval Report Template

Every scenario agent MUST save exactly two moot memories at teardown (Step 5 of the teardown
skill). Use the formats below verbatim — consistent structure lets us compare runs side by side.

---

## Memory 1 — Run steps (`--kind context --scope user`)

**Title format:** `heroku-plugin scenario: <scenario-id> (<date>)`

**Keywords:** `heroku scenario-eval <stack> <addons-space-separated>`

**Content format:**

```
Date: <YYYY-MM-DD>. Scenario: <scenario-id>. Stack: <stack>/<variant if any>. Addons: <addon list>. Result: <SUCCESS|FAILED>.

Assertions (<N passed> / <total>):
✅ Skill confirms requirements and presents implementation plan before writing code
✅ UI is implemented (HTML views or template layer — not API-only)
✅ At least one database model relevant to the domain
✅ Database is seeded with demo data
✅ Pre-commit checklist was run and all items passed
✅ Test coverage is >=90% — actual: <N>%
✅ Procfile exists with correct web command
✅ app.json exists with correct addons
✅ Stack dependency file exists (<package.json|requirements.txt|go.mod|Gemfile>)
✅ .gitignore contains correct entry for stack
✅ docker-compose.yml exists for local dev
✅ App deploys successfully to Heroku
✅ Deployed app returns HTTP 200 on the root URL — confirmed: <yes|no>
✅ App URL returned in final output — URL: <url>
✅ Teardown completes and session saved to moot

Token usage: <skill>: <N> tokens / <budget> budget (<pct>%)
Subagent usage: subagent_tokens=<N> tool_uses=<N> duration_ms=<N>
  (scan ALL subagent and skill responses for these fields before writing — treat as required)

Step-by-step:
1. preflight — <summary of what happened>
2. scaffold-app — <summary: stack confirmed, notable decisions, workarounds>
3. deploy-anonymous — <summary: buildpacks, addons, push result>
4. check-deploy-status — <web.1 status, HTTP check result>
5. teardown — <app destroyed, session cleared>

Notable issues: <none | brief description — cross-reference to learning memories by ID>
```

---

## Memory 2 — Issues (`--kind learning --scope user`) — one per distinct issue

Only create this memory if something went wrong or deviated from expected behavior.

**Title format:** `heroku-plugin scenario: <scenario-id>: <short issue description>`

**Keywords:** `heroku scenario-eval <stack> <issue-keywords>`

**Content format:**

```
Scenario: <scenario-id>. Date: <YYYY-MM-DD>.

What failed: <one sentence>
Root cause: <one sentence>
Workaround used: <what the agent did to continue>
Recommended fix: <file path and what should change>
Assertion failed: <assertion text>
Cross-reference: <title of run steps memory> id=<moot-id>
```

---

## If moot is unavailable

Print the full report content to stdout using the formats above so it appears in the workflow
summary. Do not block teardown or skip the report — surface it inline instead.
