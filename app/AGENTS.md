# app/ — Agent Notes

## GitHub Auth: OAuth Token

This app uses **GitHub OAuth** (not a GitHub App). Users sign in with GitHub and receive an OAuth access token stored in the session. This single token is used for all GitHub API operations.

### Repo creation flow

`create_github_repo()` in `projects.py` calls `POST /user/repos` with the user's OAuth token. This creates the repo under the authenticated user and returns the full repo JSON (including `html_url`, `clone_url`).

### clone_repo

`clone_repo()` uses the OAuth token inserted into the clone URL (`x-access-token:{token}@`). This works because OAuth tokens with `repo` scope can access the user's repos.

### Repo existence / deletion

`check_repo_exists_on_github()` and `delete_github_repo()` both accept a `username` parameter and hit `GET/DELETE /repos/{username}/{repo_name}` with the OAuth token.
