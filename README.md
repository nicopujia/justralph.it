# Just Ralph It

> Rigorous intent. Autonomous execution.

Most vibe-coding tools start writing code after one or two prompts. Just Ralph It makes you think very, very rigorously first — so much that you might even discard the idea — and then lets an autonomous agent build the whole thing, unattended, with full power on a VPS (a.k.a. *god mode*).

## Prerequisites

- **Python 3.11+**
- **Dolt** (SQL database): https://docs.dolthub.com/introduction/installation
- **Git**
- **GitHub OAuth App**: Create one at https://github.com/settings/developers
- **opencode** (coding agent): Already installed at `~/.npm-global/bin/opencode`

## Environment Variables

Create `.env` in the project root:

```bash
# Required: GitHub OAuth credentials
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret

# Required: Flask session encryption
SECRET_KEY=your_cryptographically_secure_random_key

# Required: opencode server URL
OPENCODE_URL=http://127.0.0.1:4096

# Required: VAPID keys for push notifications
VAPID_PRIVATE_KEY_PATH=vapid_private.pem
VAPID_CLAIMS_EMAIL=mailto:your@email.com
```

Generate VAPID keys:
```bash
python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); v.save_key('vapid_private.pem'); v.save_public_key('vapid_public.pem')"
```

## Run Locally

1. **Clone and setup:**
```bash
git clone <repo-url>
cd just-ralph-it
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
source setup.sh  # Sets up Dolt shared server and pre-commit hook
```

2. **Start Dolt SQL server:**
```bash
dolt sql-server --config config.yaml
```

3. **In another terminal, start the app:**
```bash
source venv/bin/activate
python run.py
```

4. **Open:** http://localhost:8000

## Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app tests/

# Specific test file
pytest tests/test_app.py -v

# E2E tests (requires Playwright)
pytest tests/e2e/ -v
```

## Deploy

The app is designed to run on a single VPS:

1. **VPS Setup:** Clone repo, install prerequisites, create `.env`
2. **Database:** Dolt runs as a SQL server (see `config.yaml`)
3. **Process Manager:** Use systemd or supervisor to run:
   - Dolt SQL server: `dolt sql-server --config config.yaml`
   - Flask app: `gunicorn -w 4 -b 0.0.0.0:8000 'app:create_app()'`
   - opencode server: `opencode server --port 4096`
4. **Reverse Proxy:** Nginx with HTTPS (add HSTS header)
5. **GitHub OAuth:** Update callback URL to production domain

### Production Checklist

- [ ] HTTPS with HSTS header enabled
- [ ] `SECRET_KEY` is cryptographically secure (not "dev")
- [ ] VAPID keys generated and working
- [ ] GitHub OAuth app points to production domain
- [ ] Dolt database initialized (`bd init`)
- [ ] Pre-commit security hook installed (`source setup.sh`)

## Architecture

- **Backend:** Flask with SQLite (via Dolt)
- **Frontend:** HTMX with server-rendered HTML
- **Auth:** GitHub OAuth
- **Database:** Dolt (Git-like SQL database)
- **Issue Tracking:** beads (`bd` CLI)
- **Agent:** opencode with Kimi K2.5

## Agents

- **Ralphy:** The interviewer. Maps your mind to beads issues.
- **Ralph:** The builder. Solves issues autonomously via the Ralph loop.

## Project Structure

```
just-ralph-it/
├── app/                 # Flask application
│   ├── __init__.py      # App factory
│   ├── routes.py        # HTTP routes
│   ├── auth.py          # GitHub OAuth
│   ├── projects.py      # Project CRUD
│   └── ...
├── tests/               # Test suite
├── ralph.py             # Ralph loop for this repo
├── ralph_template.py    # Template for new projects
├── .opencode/agents/    # Ralphy system prompt
└── config.yaml          # Dolt SQL server config
```

## Security

- Pre-commit hook blocks `.env` files and secret patterns
- Sessions expire after 30 days of inactivity
- HSTS header enforces HTTPS
- OAuth tokens stored server-side only

## License

MIT
