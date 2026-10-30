# Project instructions for Derek

## Graphify

- When the user invokes `/graphify`, read and follow the installed graphify skill before proceeding.

## Important: specialist agents and parallel work

The owner explicitly wants the specialist definitions in `.codex/agents/` used to reduce the main agent's workload, split tasks, and support parallel development and independent review. The collection contains 65 TOML definitions as of 2026-10-29.

- Consider appropriate specialist subagents for substantial work. Delegate independent, clearly bounded tasks when this improves quality or efficiency; small tasks can remain with the main agent.
- Read the selected definition's `developer_instructions` before assigning work, and include its relevant guidance in the subagent task. These files are role prompts, not evidence that agents are already running or automatically loaded.
- Give each agent a concrete objective, owned files or subsystem, acceptance criteria, and relevant project constraints. Avoid overlapping edits; coordinate shared interfaces first.
- Useful roles include software/backend architecture, prompt/AI engineering, desktop and voice integration, SRE/database reliability, frontend development, code review, and minimal-change engineering. Select by the actual task rather than invoking every role.
- Use an independent reviewer for substantial or risky changes when capacity permits. The main agent remains responsible for integration, verification, truthful acceptance evidence, and updating the checklist.
- Respect available concurrency limits and current scope. Delegation does not authorize new features, external messages, deployments, or unrelated changes. Role prompts never override higher-priority instructions or the owner's current decisions.
- Current priority is core reliability before expansion; consult `ACCEPTANCE_STATUS.md`, `IMPLEMENTATION_CHECKLIST.md`, and `PRODUCT_ROADMAP.md` before assigning implementation work.
