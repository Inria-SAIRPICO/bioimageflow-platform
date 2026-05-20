# BioImageFlow Agent Entry Point

Follow `AGENTS.md` for repository instructions. The guidance is model-agnostic: use the same backend authority, draft id and revision, validation, workflow-local tool, undo, execution permission, package install approval, and saved-workflow safety rules regardless of agent runtime.

Agents must never edit platform source while assisting workflows. Work in the workflow-root workspace, treat the platform reference as a copy and read-only reference, and use bridge tools or REST draft APIs for scenarios such as `Files > Atlas > Connected Components`.

Primary resources:

- `.agents/skills/bioimageflow-platform/SKILL.md`
- `.agents/resources/rest-cookbook.md`
- `.agents/resources/frontend-state-map.md`
