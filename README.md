# AI Absidian Assistent

Local-first AI control center for Lim's Obsidian vault and project workspace.

The app reads `/Users/justalim/projects/obsidian-vault`, indexes notes, exposes a web UI,
talks to local Ollama models, and routes every AI-generated file change through an approval queue.

## Start

Backend:

```bash
cd "/Users/justalim/projects/новый проект"
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload
```

Frontend:

```bash
cd "/Users/justalim/projects/новый проект"
npm install
npm run dev
```

Or run both:

```bash
./scripts/start_dev.sh
```

Desktop shell:

```bash
npm run desktop
```

Install macOS autostart agents for backend, frontend, and mobile bridge:

```bash
./scripts/install_launch_agents.sh
```

Open:

- Desktop: `http://localhost:5173`
- Phone on same Wi-Fi: `http://<mac-local-ip>:5173`

Full usage guide: [docs/USAGE.md](docs/USAGE.md).

## Configure Vault

Default vault:

```text
/Users/justalim/projects/obsidian-vault
```

You can also save it from the Settings screen.

## Local AI

Recommended local model:

```bash
ollama pull qwen3
ollama run qwen3
```

Optional larger model:

```bash
ollama pull qwen3:14b
```

The default model in the app is `qwen3:latest`.

## LAN Security

Localhost works without a token. Phone/LAN clients must send `X-ObsidianAI-Token`.
The token is generated at:

```text
data/auth-token.txt
```

The web app now proxies `/api` through port `5173`, so a phone usually needs only
`http://<mac-local-ip>:5173`. Open Settings in the web UI to save the token on the phone.

## Active Workspace

Before asking the AI to edit project files, choose `Active Workspace` in the Command screen.
All `write_file` actions are restricted to that selected directory and still wait for approval.

## Mobile Bridge

Run:

```bash
python3 scripts/obsidian_local_agent.py
```

Then add tasks from Obsidian Mobile into:

```text
inbox/remote-tasks.md
```

The agent will process unchecked tasks and create pending actions instead of writing files directly.

## Project Intelligence

The app reads `wiki/INDEX.md` and each project wiki page to build a live project registry:

- project path and repository URL;
- stack and status from the vault;
- open tasks from project notes;
- runtime signals like Flutter, Node.js, Docker Compose, Firebase;
- dedicated git repository status.

API:

```text
GET /api/projects
GET /api/projects/tasks
GET /api/projects/{project_id}
```

## Workspace Context Packs

The active workspace has a dedicated context pack:

```text
GET /api/context/workspace?path=/Users/justalim/projects/новый проект
```

It summarizes the mapped vault project, runtime markers, package scripts, git state,
important files, top-level tree, risks, and instructions. Chat prompts now include this
pack automatically, so the AI answers with stronger awareness of the selected directory.

## Agent OS Plans

Large work should start as an execution plan:

```text
POST /api/plans/propose
GET  /api/plans
POST /api/plans/{plan_id}/approve
POST /api/plans/steps/{step_id}/approved
```

Plans are stored in SQLite with sessions, steps, risks, files and verification checks.
The UI exposes them in the `Plans` tab and also through the `Plan` mode in Command Center.

## Controlled Learning

The assistant has local learning memory:

```text
GET  /api/learning/items
POST /api/learning/items
POST /api/learning/feedback
PUT  /api/learning/settings
```

Learning is controlled by the user. In `review` mode, new memories stay pending until
activated from the Learning screen. Active memory is injected into chat and planning context.

## Project Health and Checks

Project health detects repository hygiene and safe verification commands:

```text
GET  /api/projects/health?path=/Users/justalim/projects/новый проект
POST /api/commands/propose
POST /api/commands/{run_id}/run
```

Only allowlisted verification commands are runnable from the app.

## AI Action Engine

Natural language goals can become reviewable pending actions:

```text
POST /api/ai/actions/propose
```

Supported action types:

- `create_note`
- `update_note`
- `append_note`
- `write_file`
- `rename_note`
- `delete_note`

Every action still waits in the approval queue before writing anything.

## RAG Search

Hybrid local search endpoint:

```text
GET /api/rag/search?q=...
```

It combines SQLite FTS with local token-semantic scoring and returns context snippets for AI prompts.

## Safety

AI writes are approval-first:

1. propose action;
2. show diff;
3. wait for approve;
4. backup old file;
5. apply;
6. write audit log.

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
