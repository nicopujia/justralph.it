# Path G: Session & Multi-tenancy Decisions

Date: 2026-03-21

## G25. Single User for Demo

**Decision:** One user = one loop instance on the VPS.

- Multi-tenancy is out of scope for the hackathon
- Architecture supports isolation via `--base-dir` if ever needed (per-session git repo, per-session bd state, per-session loop process)
- Resource monitoring prevents any single loop from consuming the VPS

## G26. API Key Provisioning

**Decision:** Environment variables on the VPS. User brings their own keys.

Flow:
1. User provides API keys through the UI (settings panel or Ralphy session)
2. Backend stores them as env vars for the Ralph Loop process
3. `ralph loop` subprocess inherits the environment
4. If Ralph needs keys mid-run, it files a HELP issue -> UI notifies user -> user provides -> loop restarts

No secrets storage system for the demo. Process environment only.
