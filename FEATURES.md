# justralph.it — Agreed Features

## Core concept

A web app that automates the Ralph Wiggum technique end-to-end. Sign in with GitHub, create a project, get interviewed by Ralphy (AI interviewer), click "Just Ralph It," and watch Ralph autonomously build and push the project to a new GitHub repo.

---

## Auth

- GitHub OAuth (scopes: `repo`, `read:user`)
- Single-user restriction in v1: only `nicopujia` can sign in. Anyone else sees: "Not available yet."
- Sessions expire after 30 days of inactivity
- Logout clears the server-side session and redirects to `/`

---

## Pages

### `/` — Landing page
- Shows app name/description and "Sign in with GitHub" button
- If already logged in: shows "Go to dashboard" button instead (no redirect)
- Title: `justralph.it`

### `/projects` — Projects list
- Lists all user's projects
- "New Project" button
- Requires auth; unauthenticated users redirected to `/`
- Title: `Projects • justralph.it`

### `/projects/new` — New project form
- Fields: "Repo name" (GitHub-valid chars only, enforced client-side) + "Description" (placeholder: "What do you want to build?", markdown supported hint, file attachments supported)
- Optional: GitHub repo URL for legacy codebase rebuild (description becomes "What do you want different in the rebuild?")
- On submit: creates GitHub repo, clones to `~/projects/<repo_name>/`, initializes beads, starts Ralphy session, redirects to `/projects/:slug`
- Rejects duplicate repo names
- Header: "Back to projects" button
- Title: `New Project • justralph.it`

### `/projects/:slug` — Project page
- Two-panel layout, full viewport, no scrolling
- Left panel (50%): Ralphy chat
- Right panel (50%): tabs — Spec / Issues / Terminal
- Header: breadcrumb "All projects / [project name]" with "All projects" linking to `/projects`
- Title: `[project name] • justralph.it`

### `/pricing` — Pricing page
- Free vs Pro tier comparison
- Free: Ralphy chat only, max 3 projects, issues locked in (no export)
- Pro: $50/mo base + $10/mo/project VPS + $30/1M tokens
- "Upgrade" button → Stripe checkout (or sign-in if unauthenticated)
- Title: `Pricing • justralph.it`

### `/prd` — Redirect
- 301 redirect to `https://nicolaspujia.com/ralph`

---

## Ralphy chat (left panel)

- Persistent opencode session per project (one `opencode serve` instance in `~/projects/just-ralph-it/`, one session per project)
- Project description sent as first message automatically on project creation
- Full chat history preserved across browser sessions
- Ralphy's responses rendered as markdown
- User messages are plain text
- File attachments: stored in `~/projects/<project_name>/assets/`, only filename shown in context by default; Ralphy uses a subagent to read files when needed; max 5MB; audio/video stored but never read
- `<system_reminder>` injected server-side into every user message (concise, a few lines) to maintain rigor
- Automatic session compaction when context gets large (silent, no user notification)
- Ralphy can only create/update open unclaimed issues — never in-progress or closed ones
- Issues tab is read-only for users — all issue management through Ralphy
- When spec is complete, Ralphy calls `show_just_ralph_it_button` tool → "Just Ralph It" button appears in chat
- After HUMAN_NEEDED stop: Ralphy notifies in chat, right panel switches to Issues tab; user resolves externally, tells Ralphy "done", Ralphy calls `show_just_ralph_it_button` again
- Multi-user (post-v1): single group chat, each message shows sender's GitHub username, Ralphy flags contradictions

---

## Right panel tabs

### Spec tab
- Displays `~/projects/<project_name>/AGENTS.md` rendered as markdown
- Updates live (file-watch or poll)
- Placeholder if file doesn't exist: "Continue chatting to let Ralphy create the spec"

### Issues tab
- Custom-styled read-only issue visualization (fetches from bdui sidecar API)
- Updates live
- Placeholder if no issues: "Continue chatting to let Ralphy create the spec"
- Users cannot create/edit/delete issues from this tab

### Terminal tab
- Streams `ralph.log` in real-time, rendered as markdown
- Placeholder before first run: "When the Ralph loop starts, you'll see its stdout here"
- Visual separator between issues (issue ID + timestamp)
- On ALL_DONE: shows "Ralph is done."
- On HUMAN_NEEDED: Ralphy sends chat message, right panel switches to Issues tab

---

## Ralph loop

- Triggered by "Just Ralph It" button
- Spawns `ralph.py` with `cwd=~/projects/<project_name>/`
- Status indicator: "Ralph is building..." while running
- Graceful stop: create `~/projects/just-ralph-it/.stop` → Ralph finishes current issue then exits
- Force stop: kills ralph.py immediately + hard resets repo to origin (requires confirmation dialog)
- Stop/Continue buttons in UI
- Resource check at start of each iteration: stops at 90% RAM or disk, sends push notification
- Self-reload: if `ralph.py` is modified between issues, re-execs itself to pick up changes
- Process recovery: on app restart, resumes any interrupted loop from DB state

---

## Notifications

- Browser push notifications (requested when user clicks "Just Ralph It")
- Triggers: HUMAN_NEEDED ("Ralph is blocked — check the Issues tab") and ALL_DONE ("Ralph is done building your project.")
- VPS resource exhaustion also triggers a push notification

---

## Secret injection

- Ralph always looks for secrets in `~/projects/<project_name>/.env`
- Web UI has "Add secret" input (key + value) that appends to `.env` on the VPS
- If a secret is missing, Ralph files a HUMAN_NEEDED issue with the exact env var name

---

## Asset files

- Uploaded via chat attachment or `/projects/new` form
- Stored in `~/projects/<project_name>/assets/`
- Max 5MB per file
- Audio/video: stored but never read by Ralphy
- Images/PDFs/text: Ralphy uses a subagent to read and summarize when relevant

---

## Project files

- `~/projects/<project_name>/` — project directory
- `~/projects/<project_name>/AGENTS.md` — spec (written by Ralphy)
- `~/projects/<project_name>/ralph.py` — copied from `ralph_template.py` at project creation
- `~/projects/<project_name>/assets/` — uploaded files
- `~/projects/<project_name>/.env` — secrets (never committed)
- `ralph.py` — justralph.it-specific Ralph loop (may be tuned by Ralph)
- `ralph_template.py` — virgin generic Ralph loop (never modified for justralph.it purposes)

---

## GitHub integration

- GitHub OAuth token used for all GitHub API calls
- Each project gets a new GitHub repo named after the project, auto-created on project creation
- Ralph pushes to the repo as it builds
- No GitHub repo deletion (removed from v1)

---

## Free tier enforcement

- No "Just Ralph It" (button visible but redirects to `/pricing`)
- Max 3 projects (4th redirects to `/pricing`)
- Issues not exportable (no issues.jsonl in repo)

---

## Security

- HTTPS only, HSTS header
- SECRET_KEY must be set; app refuses to start if missing or set to "dev"
- `.env` and `*.pem` in `.gitignore`; git pre-commit hook rejects secret patterns in code/config files (not in `.beads/` or docs)
- Sessions expire after 30 days of inactivity

---

## UI

- Functional only — minimal CSS for layout
- Light/dark mode via `prefers-color-scheme` (no toggle)
- Content centered with max-width on all pages except `/projects/:slug` (full-width)
- Message input is a textarea, visually integrated with chat panel (border-top only)

---

## Post-v1 (deferred)

- **Per-project VPS provisioning** (Hetzner, one VPS per project, provisioned on first "Just Ralph It")
  - VPS snapshot with all tooling
  - controller.py (VPS ↔ central comms, watchdog, self-update)
  - SSH key generation + user download
  - AI API proxy (key never on VPS, token tracking for billing)
  - VPS auto-scaling (checkbox, Hetzner resize API)
- **Stripe payments** ($50 base + $10/project + $30/1M tokens, monthly billing)
  - Free tier: Ralphy only, max 3 projects, issues locked in
  - Pricing page
- **Legacy codebase input** (GitHub repo URL → Ralphy interviews about delta → Ralph analyzes exhaustively → fresh rebuild)
- **Multi-user collaboration** (teams, project sharing, group chat, Ralphy conflict detection)
- **Google OAuth** (VPS-only projects, no GitHub required)
- **Skills for Ralph** (post-deploy, based on observed gaps)
