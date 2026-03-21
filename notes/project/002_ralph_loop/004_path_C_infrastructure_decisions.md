# Path C: Infrastructure & VPS Decisions

Date: 2026-03-20

## C9. VPS Provisioning

**Decision:** VPS is provided for the demo. Ralph Loop has no provisioning code.

- Ralph Loop is machine-agnostic -- runs on whatever machine it's given
- VPS provisioning is the backend/infra team's concern
- Our guarantees: `ralph init` bootstraps any fresh machine, `ralph loop` runs headlessly
- Resource awareness: loop already monitors CPU/RAM/disk via `_check_resources()` and stops if threshold exceeded (default 95%, configurable via `--vm-res-threshold`)

## C10. Hackathon Scope

**Decision:** Single VPS for the demo. No dynamic provisioning.

- Everything runs on one provided VPS: FastAPI server, Ralph Loop, bd, OpenCode
- Architecturally identical to production -- just without the provisioning step
- Ralph Loop doesn't care whether it's on a VPS or localhost

## C11. What Triggers `ralph init`

**Decision:** The "Just Ralph It" button triggers the full initialization sequence.

Precondition: the button is only available when Ralphy's confidence criteria determines that all information recon is sufficiently clarified.

Sequence when clicked:
1. Ralphy's confidence criteria is met -> "Just Ralph It" button becomes available
2. User clicks -> backend creates GitHub repo (via `gh repo create` or GitHub API)
3. Backend calls `ralph init --base-dir /sessions/<id> --remote <github-url>`
4. `ralph init` scaffolds local bare repo + worktrees + adds GitHub remote
5. Ralphy pushes `bd` issues scoped to that `base_dir`
6. Backend starts `ralph loop --base-dir /sessions/<id>`
7. Ralph processes issues, commits locally, pushes to GitHub on merge-to-main

### bd issue scoping

- bd issues are scoped per-session (per `base_dir`), not global
- Multiple sessions on the same machine do not share issue pools

## C12. Git Repo Creation

**Decision:** The "Just Ralph It" button creates the GitHub repo. Non-negotiable.

- Backend creates GitHub repo (backend's responsibility)
- Backend passes the repo URL to `ralph init --remote <url>`
- `ralph init` adds the remote after scaffolding the local bare repo

### Required changes to ralph init

- Add `--remote` flag to `InitConfig`
- After `init_bare()`, run `git remote add origin <url>` if `--remote` is provided
- Agent pushes to GitHub naturally during its Deployment step (PROMPT.xml merge-to-main)
- Optional: `post_iter` hook can push after each completed issue for real-time GitHub visibility
