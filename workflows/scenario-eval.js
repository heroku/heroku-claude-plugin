export const meta = {
  name: "scenario-eval",
  description: "Fan out one agent per scenario, execute full build-and-deploy, collect structured results",
  whenToUse: "Run from a session launched with: HEROKU_TOKEN_BUDGET_TRACKING=1 claude --plugin-dir /path/to/heroku-plugin --allowedTools \"Bash,Read,Write,Edit,Task\". Each scenario deploys a real Heroku app and runs teardown. Requires an authenticated Heroku account and moot-server running.",
  phases: [
    { title: "Load", detail: "Read scenarios.json and skill files" },
    { title: "Execute", detail: "Fan out one agent per scenario in worktree isolation" },
    { title: "Report", detail: "Collect results and print summary" },
  ],
};

// ---------------------------------------------------------------------------
// Phase 1 — Load scenarios and skill content
// ---------------------------------------------------------------------------
phase("Load");

const scenarioFilter = args && args.scenario ? args.scenario : null;

const PLUGIN_DIR = "/Users/jwinn/src/heroku-plugin";

const corpus = await agent(
  `Read the file at ${PLUGIN_DIR}/evals/scenarios/scenarios.json and return its full contents as a JSON array. ` +
  `Also read these skill files and return their contents: ` +
  `${PLUGIN_DIR}/skills/build-and-deploy/SKILL.md, ` +
  `${PLUGIN_DIR}/skills/scaffold-app/SKILL.md, ` +
  `${PLUGIN_DIR}/skills/deploy-anonymous/SKILL.md, ` +
  `${PLUGIN_DIR}/skills/check-deploy-status/SKILL.md, ` +
  `${PLUGIN_DIR}/skills/teardown/SKILL.md, ` +
  `${PLUGIN_DIR}/references/heroku/build-standards.md, ` +
  `${PLUGIN_DIR}/evals/scenarios/report-template.md. ` +
  `Return a JSON object with keys: scenarios (array), skills (object keyed by skill name), buildStandards (string), reportTemplate (string).`,
  {
    label: "load-corpus",
    schema: {
      type: "object",
      required: ["scenarios", "skills", "buildStandards", "reportTemplate"],
      properties: {
        scenarios: { type: "array" },
        skills: { type: "object" },
        buildStandards: { type: "string" },
        reportTemplate: { type: "string" },
      },
    },
  }
);

let scenarios = corpus.scenarios;

if (scenarioFilter) {
  scenarios = scenarios.filter(s => s.id === scenarioFilter);
  if (scenarios.length === 0) {
    log(`No scenario found with id: ${scenarioFilter}`);
    return { error: `unknown scenario: ${scenarioFilter}` };
  }
}

// Cap at 5 concurrent scenarios
const batch = scenarios.slice(0, 5);
log(`Running ${batch.length} scenario(s): ${batch.map(s => s.id).join(", ")}`);

// ---------------------------------------------------------------------------
// Phase 2 — Execute scenarios in parallel, each in an isolated worktree
// ---------------------------------------------------------------------------
phase("Execute");

const RESULT_SCHEMA = {
  type: "object",
  required: ["scenario_id", "stack", "assertions", "app_name", "app_url", "deploy_succeeded", "teardown_succeeded", "moot_saved", "token_usage", "notes"],
  properties: {
    scenario_id: { type: "string" },
    stack: { type: "string" },
    assertions: {
      type: "array",
      items: {
        type: "object",
        required: ["assertion", "passed", "notes"],
        properties: {
          assertion: { type: "string" },
          passed: { type: "boolean" },
          notes: { type: "string" },
        },
      },
    },
    app_name: { type: "string" },
    app_url: { type: "string" },
    deploy_succeeded: { type: "boolean" },
    teardown_succeeded: { type: "boolean" },
    moot_saved: { type: "boolean" },
    token_usage: {
      type: "object",
      properties: {
        skill: { type: "string" },
        estimated_tokens: { type: "number" },
      },
    },
    notes: { type: "string" },
  },
};

const results = await parallel(
  batch.map(scenario => async () => {
    const skillContent = corpus.skills["build-and-deploy"] || "";
    const scaffoldContent = corpus.skills["scaffold-app"] || "";
    const deployContent = corpus.skills["deploy-anonymous"] || "";
    const statusContent = corpus.skills["check-deploy-status"] || "";
    const teardownContent = corpus.skills["teardown"] || "";
    const standards = corpus.buildStandards || "";
    const reportTemplate = corpus.reportTemplate || "";

    const prompt = `
You are a Claude Code agent executing a plugin scenario eval. You are NOT Bob — do not load any
global persona or CLAUDE.md instructions. You are a plain Claude Code agent executing skill
instructions exactly as written.

## Your task

Execute the following scenario end-to-end and return a structured result.

## Scenario

ID: ${scenario.id}
Prompt: "${scenario.prompt}"
Stack: ${scenario.stack}${scenario.variant ? ` (${scenario.variant})` : ""}
Expected addons: ${scenario.addons.join(", ")}

## Assertions to evaluate

${scenario.assertions.map((a, i) => `${i + 1}. ${a}`).join("\n")}

## Build standards (apply throughout)

${standards}

## Skill instructions

### build-and-deploy
${skillContent}

### scaffold-app
${scaffoldContent}

### deploy-anonymous
${deployContent}

### check-deploy-status
${statusContent}

### teardown
${teardownContent}

## Report template (use exactly this format when saving moot memories at teardown)

${reportTemplate}

## Execution instructions

1. Generate a unique 8-character hex run ID: run \`openssl rand -hex 4\` and capture the output.
   Scaffold into \`/tmp/scenario-${scenario.id}-<run-id>\` where <run-id> is the hex string.
   Create this directory first. All file writes, git init, and Heroku operations happen inside
   this directory. The unique suffix prevents collisions with leftover directories from prior runs.

2. Execute the build-and-deploy skill for the scenario prompt above. Follow the skill
   instructions exactly. Confirm requirements internally (no user to ask — use the scenario
   prompt as the full specification). Select the stack and variant from the scenario metadata.

3. After the skill completes (success or failure), evaluate each assertion as passed or failed
   based on what actually happened. Be honest — if a step was skipped or failed, mark it failed.

4. Run the teardown skill to destroy the Heroku app and save the session record to moot.
   If moot is unavailable, note it and continue.

5. Delete the scaffold directory: \`rm -rf /tmp/scenario-${scenario.id}-<run-id>\`.
   Do this regardless of whether the scenario succeeded or failed.

6. Return the structured result. Include the app name, app URL (empty string if deploy failed),
   whether deploy and teardown succeeded, whether moot saved, an estimated output token count
   for the full build-and-deploy skill execution, and any notes about deviations or issues.
`;

    return agent(prompt, {
      label: `scenario:${scenario.id}`,
      phase: "Execute",
      schema: RESULT_SCHEMA,
      // No worktree isolation — agents scaffold into unique /tmp dirs per scenario,
      // so there is no filesystem collision between parallel runs.
    });
  })
);

// ---------------------------------------------------------------------------
// Phase 3 — Collect and print summary
// ---------------------------------------------------------------------------
phase("Report");

const passed = results.filter(Boolean).filter(r => r.deploy_succeeded);
const failed = results.filter(Boolean).filter(r => !r.deploy_succeeded);
const nulled = results.filter(r => r === null);

log(`Completed: ${results.filter(Boolean).length}/${batch.length} scenarios (${nulled.length} agent errors)`);

const summary = {
  run_at: args && args.run_at ? args.run_at : "unknown",
  total: batch.length,
  deploy_succeeded: passed.length,
  deploy_failed: failed.length,
  agent_errors: nulled.length,
  scenarios: results.filter(Boolean).map(r => ({
    id: r.scenario_id,
    stack: r.stack,
    deploy_succeeded: r.deploy_succeeded,
    teardown_succeeded: r.teardown_succeeded,
    moot_saved: r.moot_saved,
    app_url: r.app_url,
    token_usage: r.token_usage,
    assertions_passed: r.assertions.filter(a => a.passed).length,
    assertions_total: r.assertions.length,
    failed_assertions: r.assertions.filter(a => !a.passed).map(a => ({
      assertion: a.assertion,
      notes: a.notes,
    })),
    notes: r.notes,
  })),
};

return summary;
