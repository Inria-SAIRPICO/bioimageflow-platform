---
orphan: true
---

# Restart the platform test campaign

Start a fresh session in this repository with **GPT-5.6 Sol**, reasoning **medium**.
The requested specialist is **GPT-6 Astra**, reasoning **high**; ordinary workers use Sol/medium.
Model selection is a runtime setting, not an effect of reading this file.
The current runtime exposes these model identifiers for delegated agents; if a new runtime does not, report the configuration blocker instead of substituting silently.

The installed Codex CLI supports `--model` and `--config`; from the repository root, this starts a new master rather than resuming the old conversation:

```bash
codex --model gpt-5.6-sol -c 'model_reasoning_effort="medium"' \
  'Read docs/developer/platform-test-start.md and execute its restart prompt.'
```

For the app, select the model and reasoning level in the session controls before sending the prompt below.
The command and controls request these settings; confirm the actual selected model in the client.
The `model` and `model_reasoning_effort` settings are described in the [official OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
This documentation change does not launch a new campaign session or alter global Codex settings.

## Restart prompt

```text
Execute the BioImageFlow Platform testing campaign in this repository.
Use GPT-5.6 Sol with medium reasoning as master and for focused ordinary workers.
For an issue that is difficult, unsafe, or unclear, delegate a bounded investigation to GPT-6 Astra with high reasoning.
If Astra still cannot establish the intended contract and a safe repair, stop the whole campaign, record the issue, and ask me one concrete question.
Otherwise implement and validate the established repair autonomously.

Read AGENTS.md and PLATFORM_CONTEXT.md, then docs/developer/platform-test-progress.md, docs/developer/platform-test-plan.md, and the open entries in docs/developer/platform-test-issues.md.
Read only the relevant coverage inventory and specifications for each assigned task.
Inspect git status/log and reconcile the checkpoint with actual files and installed library versions.
Do not assume historical workers still exist or temporary logs are available.
Do not repeat completed library releases, audits, or successful checks unless changes invalidate their evidence.

Continue from the next action in the progress file, initially the queued Astra assessment of ISSUE-001.
That issue is an unconfirmed code-inspection concern, not an established bug or an approved redesign.
Use disposable state for its reproduction; do not change test expectations to manufacture a pass.
Keep writes disjoint and use at most two ordinary workers alongside the master, leaving a slot for Astra.
Pass fresh, bounded task packets with explicit model/reasoning overrides rather than full-history forks.

Exclude parallel scheduling, HPC, Parsl, managed remote execution, and distributed engines from platform certification.
Keep Direct and test real Wetlands workers sequentially with one worker.
Comprehensive Chromium/Firefox GUI acceptance is opt-in after large changes, not part of every development edit.
Use scripts/test and its documented focused/completion gates with audited per-case exclusions.
Make clean changes without backward-compatibility shims; update affected specifications, documentation, fixtures, and tests.
Commit each coherent validated task separately, including its durable progress update, without staging unrelated files.
Maintain the progress file, issue decisions, and feature inventories so another fresh session can continue without this conversation.
Proceed until the campaign is complete or an escalation genuinely requires my decision.
```
