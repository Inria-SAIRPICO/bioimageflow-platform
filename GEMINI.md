# BioImageFlow Agent Entry Point

Follow `AGENTS.md` for repository instructions. The guidance is model-agnostic and should not override platform behavior or API validation.

Agents must never edit platform source while assisting workflows. Work in the workflow-root workspace, treat the platform reference as a copy and read-only reference, and use bridge tools or REST draft APIs with the current draft id and revision. Keep undo available, request package install approval, and ask for execution permission before running scenarios such as `Files > Atlas > Connected Components`.

Primary resources:

- `.agents/skills/bioimageflow-platform/SKILL.md`
- `.agents/resources/rest-cookbook.md`
- `.agents/resources/frontend-state-map.md`
