# Scenario Eval Report Template

Every scenario agent MUST produce two reports at the end of its run and return them in its
result `notes`. Use the formats below verbatim — consistent structure lets us compare runs side
by side.

---

## Report 1 — Run steps

**Title:** `heroku-plugin scenario: <scenario-id> (<date>)`

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
✅ .heroku-plugin-scaffold.json lists the correct addons
✅ Stack dependency file exists (<package.json|requirements.txt|go.mod|Gemfile>)
✅ .gitignore contains correct entry for stack
✅ docker-compose.yml exists for local dev
✅ App deploys successfully to Heroku
✅ Deployed app returns HTTP 200 on the root URL — confirmed: <yes|no>
✅ App URL returned in final output — URL: <url>
✅ Session state holds app_id and claim_url, and is cleared at cleanup

Token usage: <skill>: <N> tokens / <budget> budget (<pct>%)
Subagent usage: subagent_tokens=<N> tool_uses=<N>
  (scan ALL subagent and skill responses for these fields before writing — treat as required)
Duration: measured by orchestrator and included in workflow result — write "see workflow result" here

Step-by-step:
1. preflight — <summary of what happened>
2. scaffold-app — <summary: stack confirmed, notable decisions, workarounds>
3. deploy-anonymous — <summary: buildpacks, addons, push result>
4. check-deploy-status — <web.1 status, HTTP check result>
5. cleanup — <what was cleaned up, and whether the preview app was discarded or left to expire>

Notable issues: <none | brief description — cross-reference to the issue reports by title>
```

---

## Report 2 — Issues — one per distinct issue

Only create this report if something went wrong or deviated from expected behavior.

**Title:** `heroku-plugin scenario: <scenario-id>: <short issue description>`

**Keywords:** `heroku scenario-eval <stack> <issue-keywords>`

**Content format:**

```
Scenario: <scenario-id>. Date: <YYYY-MM-DD>.

What failed: <one sentence>
Root cause: <one sentence>
Workaround used: <what the agent did to continue>
Recommended fix: <file path and what should change>
Assertion failed: <assertion text>
Cross-reference: <title of run steps report>
```

---
