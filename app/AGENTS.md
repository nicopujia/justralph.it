# app/ — Agent Notes

## GitHub Auth: Two Token Types

This app uses a **GitHub App** (not OAuth). There are two distinct token types:

1. **Installation token** (`ghs_...`): Obtained via the GitHub App installation. Stored in `session["installation_token"]`. Can read/write repos the app is installed on (`GET /repos/{owner}/{name}`, git clone/push). **Cannot** call user-scoped endpoints like `POST /user/repos` (returns 403).

2. **`gh` CLI PAT**: The `gh` CLI at `/home/linuxbrew/.linuxbrew/bin/gh` is authenticated as `nicopujia` with a personal access token that has `repo` scope. This **can** create repos via `gh repo create`.

### Repo creation flow

`create_github_repo()` in `projects.py` uses a two-step approach:
1. Calls `gh repo create` via subprocess (uses the PAT-authenticated CLI)
2. Fetches repo info via `GET /repos/nicopujia/{name}` using the installation token (to get `html_url`, `clone_url`)

### clone_repo

`clone_repo()` uses the installation token inserted into the clone URL (`x-access-token:{token}@`). This works because installation tokens can access repos the app is installed on.
