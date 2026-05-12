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

Install macOS autostart agents for backend, frontend, and mobile bridge:

```bash
./scripts/install_launch_agents.sh
```

Open:

- Desktop: `http://localhost:5173`
- Phone on same Wi-Fi: `http://<mac-local-ip>:5173`

## Configure Vault

Default vault:

```text
/Users/justalim/projects/obsidian-vault
```

You can also save it from the Settings screen.

## Local AI

Current installed fallback:

```bash
ollama run llama3:latest
```

Recommended larger local model:

```bash
ollama pull qwen3:14b
```

## LAN Security

Localhost works without a token. Phone/LAN clients must send `X-ObsidianAI-Token`.
The token is generated at:

```text
data/auth-token.txt
```

Open Settings in the web UI to save the token on the phone.

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
