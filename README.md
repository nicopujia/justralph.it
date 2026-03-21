# justralph.it

## Setup

### 1. Clone

```sh
git clone https://github.com/nicopujia/just-ralph-it.git justralph.it
cd justralph.it
```

### 2. Install dependencies

Prerequisites: Python 3.13+, [uv](https://docs.astral.sh/uv/), Node.js 18+ with npm.

```sh
uv sync
npm install -g ralphy-cli
```

### 3. Initialize project

```sh
ralph init
```

This creates `.ralphy/` (config, hooks, rules) and `tasks.yaml`.

### 4. Create tasks

```sh
ralph task create "Implement auth endpoint" --body "JWT-based auth" --priority 1
ralph task list
```

### 5. Run the loop

```sh
ralph run --engine claude
```

Ralphy processes each task through the configured AI engine.

### 6. Run the services

Server:

```bash
fastapi dev ./server/main.py
```

Client:

```bash
cd ./client
bun dev
```

## Test

```sh
uv run pytest
```
