import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  Bot,
  Check,
  CircleDot,
  Clock3,
  Database,
  FileSearch,
  FolderOpen,
  FolderKanban,
  GitBranch,
  Inbox,
  KeyRound,
  Layers3,
  LayoutDashboard,
  LockKeyhole,
  Network,
  Palette,
  Play,
  RefreshCcw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Smartphone,
  WandSparkles,
  WifiOff,
  X,
} from "lucide-react";
import "./styles.css";

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || (window.location.protocol.startsWith("http") ? "" : "http://127.0.0.1:8765");
const DEFAULT_VAULT = "/Users/justalim/projects/obsidian-vault";
const AUTH_TOKEN_KEY = "obsidian_ai_token";
const API_BASE_KEY = "obsidian_ai_api_base";

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "command", label: "Command", icon: Bot },
  { id: "projects", label: "Projects", icon: FolderKanban },
  { id: "vault", label: "Vault", icon: FileSearch },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "settings", label: "Settings", icon: Settings },
];

function formatNumber(value) {
  if (value === null || value === undefined) return "0";
  return new Intl.NumberFormat("ru-RU").format(value);
}

function formatTime(epoch) {
  if (!epoch) return "";
  return new Date(epoch * 1000).toLocaleString("ru-RU", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getApiBase() {
  return localStorage.getItem(API_BASE_KEY) || DEFAULT_API_BASE;
}

function setApiBase(value) {
  const clean = value.trim().replace(/\/$/, "");
  if (clean) {
    localStorage.setItem(API_BASE_KEY, clean);
  } else {
    localStorage.removeItem(API_BASE_KEY);
  }
}

function apiUrl(path) {
  return `${getApiBase()}${path}`;
}

async function api(path, options = {}) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  const res = await fetch(apiUrl(path), {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-ObsidianAI-Token": token } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text || res.statusText}`);
  }
  return res.json();
}

function StatTile({ icon: Icon, label, value, tone = "teal" }) {
  return (
    <div className="metric">
      <div className={`metric-icon ${tone}`}>
        <Icon size={18} />
      </div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function Sidebar({ active, setActive }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <Sparkles size={18} />
        </div>
        <div>
          <strong>ObsidianAI</strong>
          <span>Control Center</span>
        </div>
      </div>
      <nav>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={active === item.id ? "active" : ""}
              onClick={() => setActive(item.id)}
              title={item.label}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

function Header({ health, refreshAll }) {
  const local = health?.local_ai;
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">Vault-aware local agent</p>
        <h1>AI workspace for Obsidian and projects</h1>
      </div>
      <div className="top-actions">
        <div className={local?.reachable ? "status ok" : "status warn"}>
          <CircleDot size={14} />
          <span>{local?.reachable ? "Ollama online" : "Ollama offline"}</span>
        </div>
        <button className="icon-button" onClick={refreshAll} title="Обновить">
          <RefreshCcw size={18} />
        </button>
      </div>
    </header>
  );
}

function AccessPanel({ authStatus, onSave }) {
  const [token, setToken] = useState("");
  const [error, setError] = useState("");

  async function loadLocalToken() {
    try {
      const data = await api("/api/auth/local-token");
      setToken(data.token);
      setError("");
    } catch {
      setError("Токен можно показать только с Mac на localhost. На телефоне вставь токен из файла data/auth-token.txt или из настроек на Mac.");
    }
  }

  return (
    <section className="access-shell">
      <div className="access-card">
        <div className="brand-mark">
          <LockKeyhole size={20} />
        </div>
        <h1>Secure LAN Access</h1>
        <p>
          Для доступа с телефона нужен локальный токен. На Mac его можно получить
          автоматически, а на телефоне вставить один раз.
        </p>
        {authStatus?.phone_url && (
          <div className="phone-hint">
            <Smartphone size={16} />
            <span>{authStatus.phone_url}</span>
          </div>
        )}
        <div className="settings-list">
          <div>
            <span>Fingerprint</span>
            <strong>{authStatus?.token_fingerprint || "unknown"}</strong>
          </div>
          <div>
            <span>Header</span>
            <code>X-ObsidianAI-Token</code>
          </div>
        </div>
        <label className="token-input">
          Access token
          <input value={token} onChange={(event) => setToken(event.target.value)} />
        </label>
        <div className="button-row">
          <button onClick={() => onSave(token)}>
            <KeyRound size={16} />
            Save token
          </button>
          <button className="ghost" onClick={loadLocalToken}>
            <ShieldCheck size={16} />
            Load on Mac
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
      </div>
    </section>
  );
}

function ConnectionPanel({ error, onRetry }) {
  const [base, setBase] = useState(getApiBase());

  async function saveAndRetry() {
    setApiBase(base);
    try {
      await onRetry();
    } catch {
      /* refreshAll stores the visible connection error */
    }
  }

  return (
    <section className="access-shell">
      <div className="access-card">
        <div className="brand-mark">
          <WifiOff size={20} />
        </div>
        <h1>Backend connection</h1>
        <p>
          Веб-интерфейс открыт, но API сейчас недоступен. Для телефона основной
          режим — открыть веб на Mac IP и оставить поле ниже пустым: тогда `/api`
          пройдет через безопасный proxy на порт 5173.
        </p>
        <label className="token-input">
          API base override
          <input
            value={base}
            onChange={(event) => setBase(event.target.value)}
            placeholder="Пусто = /api через веб-порт, либо http://192.168.0.219:8765"
          />
        </label>
        <div className="settings-list">
          <div>
            <span>Current mode</span>
            <strong>{getApiBase() || "same-origin /api proxy"}</strong>
          </div>
          <div>
            <span>Error</span>
            <code>{error || "Network request failed"}</code>
          </div>
        </div>
        <div className="button-row">
          <button onClick={saveAndRetry}>
            <RefreshCcw size={16} />
            Retry
          </button>
          <button className="ghost" onClick={async () => { setBase(""); setApiBase(""); try { await onRetry(); } catch {} }}>
            <Network size={16} />
            Use proxy
          </button>
        </div>
      </div>
    </section>
  );
}

function Dashboard({ stats, health, notes, actions, overview, runIndex }) {
  const recent = notes.slice(0, 6);
  const pending = actions.filter((item) => item.status === "pending");
  return (
    <section className="view dashboard-grid">
      <div className="metrics-row">
        <StatTile icon={Database} label="Notes" value={formatNumber(stats?.total_notes)} />
        <StatTile icon={Activity} label="Words" value={formatNumber(stats?.total_words)} tone="blue" />
        <StatTile icon={Network} label="Links" value={formatNumber(stats?.total_links)} tone="violet" />
        <StatTile icon={ShieldCheck} label="Pending" value={formatNumber(pending.length)} tone="amber" />
      </div>

      <div className="panel wide">
        <div className="panel-head">
          <div>
            <p className="eyebrow">System</p>
            <h2>Runtime Status</h2>
          </div>
          <button onClick={runIndex}>
            <Play size={16} />
            Index vault
          </button>
        </div>
        <div className="runtime">
          <div>
            <span>Vault</span>
            <strong>{health?.vault_path || "not configured"}</strong>
          </div>
          <div>
            <span>Watcher</span>
            <strong>{health?.watcher_running ? "running" : "stopped"}</strong>
          </div>
          <div>
            <span>Local model</span>
            <strong>{health?.local_ai?.models?.[0] || "qwen3:latest"}</strong>
          </div>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-head compact">
          <h2>System Health</h2>
          <div className="health-score">{overview?.quality_score ?? 0}</div>
        </div>
        <div className="health-grid">
          <div><span>Active projects</span><strong>{overview?.projects?.active ?? 0}</strong></div>
          <div><span>Dirty repos</span><strong>{overview?.projects?.dirty ?? 0}</strong></div>
          <div><span>Open tasks</span><strong>{overview?.tasks?.open ?? 0}</strong></div>
          <div><span>Unmapped</span><strong>{overview?.projects?.unmapped ?? 0}</strong></div>
        </div>
        <div className="recommendations">
          {(overview?.recommendations || []).map((item) => <span key={item}>{item}</span>)}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head compact">
          <h2>Recent Notes</h2>
        </div>
        <div className="note-list">
          {recent.map((note) => (
            <div className="note-row" key={note.id}>
              <strong>{note.title}</strong>
              <span>{note.folder || "root"} · {formatTime(note.modified_at)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head compact">
          <h2>Approval Queue</h2>
        </div>
        <div className="action-mini">
          {pending.slice(0, 5).map((action) => (
            <div key={action.id}>
              <Clock3 size={16} />
              <span>{action.title}</span>
            </div>
          ))}
          {!pending.length && <p className="muted">No pending actions.</p>}
        </div>
      </div>
    </section>
  );
}

function CommandCenter({ actions, refreshAll, settings, saveSettings, workspaces }) {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Готов. Я отвечаю с учетом vault и создаю изменения только через очередь подтверждений." },
  ]);
  const [input, setInput] = useState("");
  const [remoteTask, setRemoteTask] = useState("");
  const [mode, setMode] = useState("chat");
  const [workspace, setWorkspace] = useState(settings?.working_directory || "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setWorkspace(settings?.working_directory || "");
  }, [settings?.working_directory]);

  async function sendChat() {
    const text = input.trim();
    if (!text || busy) return;
    const next = [...messages, { role: "user", content: text }, { role: "assistant", content: "" }];
    setMessages(next);
    setInput("");
    setBusy(true);
    try {
      if (mode === "actions") {
        const data = await api("/api/ai/actions/propose", {
          method: "POST",
          body: JSON.stringify({
            goal: text,
            provider: "ollama",
            model: settings?.default_model || "qwen3:latest",
            max_actions: 5,
            working_directory: workspace,
          }),
        });
        const actionText = [
          `Создал pending actions: ${data.actions?.length || 0}`,
          ...(data.actions || []).map((item) => `- ${item.title}`),
          ...(data.errors || []).map((item) => `- Ошибка: ${item.title}: ${item.error}`),
        ].join("\n");
        setMessages((current) => {
          const copy = [...current];
          copy[copy.length - 1] = { role: "assistant", content: actionText };
          return copy;
        });
        await refreshAll();
        return;
      }

      const res = await fetch(apiUrl("/api/ai/chat/stream"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(localStorage.getItem(AUTH_TOKEN_KEY)
            ? { "X-ObsidianAI-Token": localStorage.getItem(AUTH_TOKEN_KEY) }
            : {}),
        },
        body: JSON.stringify({
          provider: "ollama",
          model: settings?.default_model || "qwen3:latest",
          messages: next.filter((m) => m.content).map((m) => ({ role: m.role, content: m.content })),
          include_vault_context: true,
          working_directory: workspace,
        }),
      });
      if (!res.ok || !res.body) {
        throw new Error(`${res.status} ${await res.text()}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          if (payload === "[DONE]") continue;
          const data = JSON.parse(payload);
          assistantText += data.text || "";
          setMessages((current) => {
            const copy = [...current];
            copy[copy.length - 1] = { role: "assistant", content: assistantText };
            return copy;
          });
        }
      }
    } catch (error) {
      setMessages((current) => {
        const copy = [...current];
        copy[copy.length - 1] = { role: "assistant", content: `Ошибка: ${error.message || error}` };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  async function queueRemoteTask() {
    const task = remoteTask.trim();
    if (!task) return;
    await api("/api/remote/tasks", {
      method: "POST",
      body: JSON.stringify({ task }),
    });
    setRemoteTask("");
  }

  async function saveWorkspace() {
    await saveSettings({ ...settings, working_directory: workspace });
  }

  return (
    <section className="view command-layout">
      <div className="panel chat-panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">AI</p>
            <h2>Command Center</h2>
          </div>
          <div className="segmented">
            <button className={mode === "chat" ? "active" : ""} onClick={() => setMode("chat")}>
              <Bot size={14} />
              Chat
            </button>
            <button className={mode === "actions" ? "active" : ""} onClick={() => setMode("actions")}>
              <WandSparkles size={14} />
              Actions
            </button>
          </div>
        </div>
        <div className="chat-log">
          {messages.map((message, index) => (
            <div className={`bubble ${message.role}`} key={`${message.role}-${index}`}>
              {message.content || (busy ? "..." : "")}
            </div>
          ))}
        </div>
        <div className="composer">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) sendChat();
            }}
            placeholder={mode === "chat" ? "Спроси про vault, проект, план реализации..." : "Опиши действие: создать заметку, обновить проект, подготовить файл..."}
          />
          <button onClick={sendChat} disabled={busy || !input.trim()} title="Отправить">
            <Send size={18} />
          </button>
        </div>
      </div>

      <div className="side-stack">
        <div className="panel workspace-panel">
          <div className="panel-head compact">
            <h2>Active Workspace</h2>
            <FolderOpen size={18} />
          </div>
          <div className="form-stack">
            <label>
              Directory
              <select
                value={workspace}
                onChange={(event) => setWorkspace(event.target.value)}
              >
                {workspaces.map((item) => (
                  <option value={item.path} key={item.path}>
                    {item.name}{item.markers?.length ? ` · ${item.markers.join(", ")}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Custom path
              <input value={workspace} onChange={(event) => setWorkspace(event.target.value)} />
            </label>
            <button onClick={saveWorkspace}>
              <SlidersHorizontal size={16} />
              Save workspace
            </button>
            <p className="muted path-hint">{workspace || "No workspace selected"}</p>
          </div>
        </div>
        <div className="panel">
          <div className="panel-head compact">
            <h2>Mobile Inbox</h2>
          </div>
          <div className="remote-box">
            <textarea
              value={remoteTask}
              onChange={(event) => setRemoteTask(event.target.value)}
              placeholder="Задача для локального агента с телефона"
            />
            <button onClick={queueRemoteTask}>
              <Inbox size={16} />
              Queue task
            </button>
          </div>
        </div>
        <ActionQueue actions={actions} refreshAll={refreshAll} compact />
      </div>
    </section>
  );
}

function VaultView({ notes, searchResults, ragResults, query, setQuery, runSearch, runRagSearch, selectNote, selectedNote }) {
  return (
    <section className="view vault-layout">
      <div className="panel vault-list-panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Knowledge</p>
            <h2>Vault Explorer</h2>
          </div>
        </div>
        <div className="searchbar">
          <Search size={18} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && runSearch()}
            placeholder="Поиск по заметкам, тегам и содержимому"
          />
          <button onClick={runSearch}>FTS</button>
          <button className="ghost" onClick={runRagSearch}>RAG</button>
        </div>
        {!!ragResults.length && (
          <div className="rag-strip">
            <Layers3 size={16} />
            <span>Hybrid semantic results</span>
          </div>
        )}
        <div className="note-list scroll">
          {(ragResults.length ? ragResults : query ? searchResults : notes).map((note) => (
            <button className="note-row selectable" key={note.id} onClick={() => selectNote(note.path)}>
              <strong>{note.title}</strong>
              <span>{note.path}{note.score ? ` · score ${note.score}` : ""}</span>
              {note.snippet && <small>{note.snippet}</small>}
            </button>
          ))}
        </div>
      </div>
      <div className="panel note-preview">
        <div className="panel-head compact">
          <h2>{selectedNote?.path || "Preview"}</h2>
        </div>
        <pre>{selectedNote?.content || "Выбери заметку слева."}</pre>
      </div>
    </section>
  );
}

function ProjectsView({ projects, projectTasks }) {
  const active = projects.filter((project) => project.group.includes("Активные"));
  const dirty = projects.filter((project) => project.git?.dirty > 0);
  const withPaths = projects.filter((project) => project.path);
  const [selectedId, setSelectedId] = useState(projects[0]?.id || null);
  useEffect(() => {
    if (!selectedId && projects[0]?.id) setSelectedId(projects[0].id);
  }, [projects, selectedId]);
  const selected = projects.find((project) => project.id === selectedId) || projects[0];

  return (
    <section className="view projects-layout">
      <div className="metrics-row">
        <StatTile icon={FolderKanban} label="Projects" value={formatNumber(projects.length)} />
        <StatTile icon={Activity} label="Active" value={formatNumber(active.length)} tone="blue" />
        <StatTile icon={GitBranch} label="Dirty Git" value={formatNumber(dirty.length)} tone="amber" />
        <StatTile icon={Check} label="Known Paths" value={formatNumber(withPaths.length)} tone="violet" />
      </div>

      <div className="projects-grid">
        {projects.map((project) => (
          <article
            className={`project-card ${selected?.id === project.id ? "selected" : ""}`}
            key={project.id}
            onClick={() => setSelectedId(project.id)}
          >
            <div className="project-card-head">
              <div>
                <p className="eyebrow">{project.group.replace("📁 ", "")}</p>
                <h2>{project.title}</h2>
              </div>
              <span className="project-status">{project.status}</span>
            </div>
            <p className="project-summary">{project.summary}</p>
            <div className="project-meta">
              <div>
                <span>Stack</span>
                <strong>{project.stack}</strong>
              </div>
              <div>
                <span>Path</span>
                <strong>{project.path || "not mapped"}</strong>
              </div>
            </div>
            <div className="signal-row">
              {(project.runtime?.signals || []).map((signal) => (
                <span key={signal}>{signal}</span>
              ))}
              {project.github && <span>GitHub</span>}
              {project.git?.available && <span>{project.git.branch || "git"}</span>}
            </div>
            {project.git?.available ? (
              <div className={project.git.dirty ? "git-box warn" : "git-box ok"}>
                <GitBranch size={16} />
                <span>
                  {project.git.dirty ? `${project.git.dirty} local changes` : "clean working tree"}
                </span>
              </div>
            ) : (
              <div className="git-box">
                <GitBranch size={16} />
                <span>{project.git?.reason || "git unavailable"}</span>
              </div>
            )}
            <div className="task-stack">
              {(project.tasks || []).slice(0, 4).map((task) => (
                <div key={task}>
                  <Clock3 size={14} />
                  <span>{task}</span>
                </div>
              ))}
              {!project.task_count && <p className="muted">No open tasks in project note.</p>}
            </div>
          </article>
        ))}
      </div>

      {selected && (
        <div className="panel wide project-detail">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Project Workspace</p>
              <h2>{selected.title}</h2>
            </div>
            <span className="project-status">{selected.status}</span>
          </div>
          <div className="project-detail-grid">
            <div>
              <span>Vault Note</span>
              <strong>{selected.note_path}</strong>
            </div>
            <div>
              <span>Local Path</span>
              <strong>{selected.path || "not mapped"}</strong>
            </div>
            <div>
              <span>Repository</span>
              <strong>{selected.github || "not recorded"}</strong>
            </div>
            <div>
              <span>Git</span>
              <strong>{selected.git?.branch || selected.git?.reason || "unknown"}</strong>
            </div>
          </div>
          {!!selected.status_details?.length && (
            <div className="task-stack">
              {selected.status_details.map((item) => (
                <div key={item}>
                  <Check size={14} />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          )}
          {!!selected.git?.changes?.length && (
            <pre className="diff compact-diff">{selected.git.changes.join("\n")}</pre>
          )}
        </div>
      )}

      <div className="panel wide">
        <div className="panel-head compact">
          <h2>Open Tasks From Vault</h2>
        </div>
        <div className="tasks-table">
          {projectTasks.slice(0, 18).map((item, index) => (
            <div key={`${item.project_id}-${index}`}>
              <strong>{item.project}</strong>
              <span>{item.task}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ActionQueue({ actions, refreshAll, compact = false }) {
  const pending = actions.filter((item) => item.status === "pending");
  const visible = compact ? pending.slice(0, 3) : actions;

  async function decide(id, action) {
    await api(`/api/actions/${id}/${action}`, {
      method: "POST",
      body: JSON.stringify(action === "reject" ? { reason: "Rejected from UI" } : {}),
    });
    await refreshAll();
  }

  return (
    <div className="panel action-panel">
      <div className="panel-head compact">
        <h2>Approval Queue</h2>
      </div>
      <div className="actions-list">
        {visible.map((item) => (
          <div className="action-item" key={item.id}>
            <div className="action-title">
              <ShieldCheck size={16} />
              <strong>{item.title}</strong>
              <span>{item.status}</span>
            </div>
            {!compact && <pre className="diff">{item.diff_preview || item.summary}</pre>}
            {item.status === "pending" && (
              <div className="decision-row">
                <button onClick={() => decide(item.id, "approve")}>
                  <Check size={16} />
                  Approve
                </button>
                <button className="ghost danger" onClick={() => decide(item.id, "reject")}>
                  <X size={16} />
                  Reject
                </button>
              </div>
            )}
          </div>
        ))}
        {!visible.length && <p className="muted">No actions yet.</p>}
      </div>
    </div>
  );
}

function AnalyticsView({ stats, hubs, orphans, actions, refreshAll }) {
  return (
    <section className="view analytics-layout">
      <div className="metrics-row">
        <StatTile icon={GitBranch} label="Hubs" value={formatNumber(hubs.length)} />
        <StatTile icon={Network} label="Orphans" value={formatNumber(orphans.length)} tone="amber" />
        <StatTile icon={Database} label="Folders" value={formatNumber(stats?.total_folders)} tone="blue" />
      </div>
      <div className="panel">
        <div className="panel-head compact">
          <h2>Top Connected Notes</h2>
        </div>
        <div className="note-list">
          {hubs.map((hub) => (
            <div className="note-row" key={hub.id}>
              <strong>{hub.title}</strong>
              <span>{hub.connections} connections · {hub.path}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <div className="panel-head compact">
          <h2>Orphans</h2>
        </div>
        <div className="note-list">
          {orphans.slice(0, 12).map((note) => (
            <div className="note-row" key={note.id}>
              <strong>{note.title}</strong>
              <span>{note.path}</span>
            </div>
          ))}
        </div>
      </div>
      <ActionQueue actions={actions} refreshAll={refreshAll} />
    </section>
  );
}

function SettingsView({ health, settings, authStatus, setupVault, runIndex, saveSettings, workspaces }) {
  const [vaultPath, setVaultPath] = useState(health?.vault_path || DEFAULT_VAULT);
  const [draft, setDraft] = useState(settings);
  useEffect(() => {
    if (health?.vault_path) setVaultPath(health.vault_path);
  }, [health?.vault_path]);
  useEffect(() => setDraft(settings), [settings]);

  function updateDraft(key, value) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  return (
    <section className="view settings-layout">
      <div className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Vault</p>
            <h2>Connection</h2>
          </div>
        </div>
        <div className="form-stack">
          <label>
            Vault path
            <input value={vaultPath} onChange={(event) => setVaultPath(event.target.value)} />
          </label>
          <div className="button-row">
            <button onClick={() => setupVault(vaultPath)}>
              <Database size={16} />
              Save vault
            </button>
            <button className="ghost" onClick={runIndex}>
              <RefreshCcw size={16} />
              Reindex
            </button>
          </div>
        </div>
      </div>
      <div className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Interface</p>
            <h2>Personalization</h2>
          </div>
          <Palette size={20} />
        </div>
        <div className="form-stack">
          <label>
            Theme
            <select value={draft.theme || "system"} onChange={(event) => updateDraft("theme", event.target.value)}>
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="focus">Focus</option>
            </select>
          </label>
          <label>
            Density
            <select value={draft.density || "comfortable"} onChange={(event) => updateDraft("density", event.target.value)}>
              <option value="comfortable">Comfortable</option>
              <option value="compact">Compact</option>
            </select>
          </label>
          <label>
            Accent
            <select value={draft.accent || "emerald"} onChange={(event) => updateDraft("accent", event.target.value)}>
              <option value="emerald">Emerald</option>
              <option value="blue">Blue</option>
              <option value="violet">Violet</option>
              <option value="amber">Amber</option>
            </select>
          </label>
          <label>
            Default local model
            <input value={draft.default_model || "qwen3:latest"} onChange={(event) => updateDraft("default_model", event.target.value)} />
          </label>
          <label>
            Working directory
            <select value={draft.working_directory || ""} onChange={(event) => updateDraft("working_directory", event.target.value)}>
              {workspaces.map((item) => (
                <option value={item.path} key={item.path}>
                  {item.name}{item.has_git ? " · git" : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            Custom working directory
            <input value={draft.working_directory || ""} onChange={(event) => updateDraft("working_directory", event.target.value)} />
          </label>
          <button onClick={() => saveSettings(draft)}>
            <SlidersHorizontal size={16} />
            Save interface
          </button>
        </div>
      </div>
      <div className="panel">
        <div className="panel-head compact">
          <h2>Local AI</h2>
        </div>
        <div className="settings-list">
          <div>
            <span>Installed</span>
            <strong>{health?.local_ai?.models?.join(", ") || "none"}</strong>
          </div>
          <div>
            <span>Recommended</span>
            <strong>qwen3:latest</strong>
          </div>
          <div>
            <span>Install</span>
            <code>ollama pull qwen3</code>
          </div>
          <div>
            <span>Active workspace</span>
            <code>{settings?.working_directory || "not selected"}</code>
          </div>
          <div>
            <span>LAN token</span>
            <code>{authStatus?.token_fingerprint || "unknown fingerprint"}</code>
          </div>
          <div>
            <span>Mobile bridge</span>
            <code>python3 scripts/obsidian_local_agent.py</code>
          </div>
        </div>
      </div>
    </section>
  );
}

function App() {
  const [active, setActive] = useState("dashboard");
  const [health, setHealth] = useState(null);
  const [authStatus, setAuthStatus] = useState(null);
  const [authLocked, setAuthLocked] = useState(false);
  const [settings, setSettings] = useState({
    theme: "system",
    density: "comfortable",
    accent: "emerald",
    default_model: "qwen3:latest",
    working_directory: "/Users/justalim/projects/новый проект",
  });
  const [overview, setOverview] = useState(null);
  const [stats, setStats] = useState(null);
  const [notes, setNotes] = useState([]);
  const [actions, setActions] = useState([]);
  const [projects, setProjects] = useState([]);
  const [projectTasks, setProjectTasks] = useState([]);
  const [workspaces, setWorkspaces] = useState([]);
  const [hubs, setHubs] = useState([]);
  const [orphans, setOrphans] = useState([]);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [ragResults, setRagResults] = useState([]);
  const [selectedNote, setSelectedNote] = useState(null);
  const [toast, setToast] = useState("");
  const [connectionError, setConnectionError] = useState("");

  async function refreshAll() {
    let healthData;
    let authData;
    try {
      [healthData, authData] = await Promise.all([
        api("/api/health"),
        api("/api/auth/status"),
      ]);
    } catch (error) {
      setConnectionError(error.message || String(error));
      throw error;
    }
    setConnectionError("");
    setHealth(healthData);
    setAuthStatus(authData);

    try {
      const [settingsData, statsData, notesData, actionsData, projectsData, tasksData, overviewData, workspacesData] = await Promise.all([
        api("/api/settings"),
        api("/api/vault/stats"),
        api("/api/notes?limit=200"),
        api("/api/actions?limit=100"),
        api("/api/projects"),
        api("/api/projects/tasks"),
        api("/api/analytics/overview"),
        api("/api/workspaces"),
      ]);
      setSettings(settingsData);
      setStats(statsData);
      setNotes(notesData.notes || []);
      setActions(actionsData.actions || []);
      setProjects(projectsData.projects || []);
      setProjectTasks(tasksData.tasks || []);
      setOverview(overviewData);
      setWorkspaces(workspacesData.workspaces || []);
      setAuthLocked(false);
    } catch (error) {
      if (String(error.message || error).includes("401")) {
        setAuthLocked(true);
        return;
      }
      throw error;
    }

    Promise.all([api("/api/graph/hubs?n=10"), api("/api/graph/orphans")])
      .then(([hubData, orphanData]) => {
        setHubs(hubData.hubs || []);
        setOrphans(orphanData.orphans || []);
      })
      .catch(() => {});
  }

  async function setupVault(path) {
    await api("/api/config/vault", {
      method: "POST",
      body: JSON.stringify({ vault_path: path }),
    });
    setToast("Vault saved and indexing started.");
    await refreshAll();
  }

  async function runIndex() {
    await api("/api/vault/index", { method: "POST" });
    setToast("Indexing started.");
    setTimeout(refreshAll, 1200);
  }

  async function runSearch() {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    const data = await api(`/api/notes/search?q=${encodeURIComponent(query)}&limit=80`);
    setSearchResults(data.results || []);
    setRagResults([]);
  }

  async function runRagSearch() {
    if (!query.trim()) {
      setRagResults([]);
      return;
    }
    const data = await api(`/api/rag/search?q=${encodeURIComponent(query)}&limit=40`);
    setRagResults(data.results || []);
  }

  async function selectNote(path) {
    const data = await api(`/api/notes/content?path=${encodeURIComponent(path)}`);
    setSelectedNote(data);
  }

  useEffect(() => {
    refreshAll().catch(() => {
      setToast("Backend is not reachable yet.");
    });
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = settings.theme || "system";
    document.documentElement.dataset.accent = settings.accent || "emerald";
    document.documentElement.dataset.density = settings.density || "comfortable";
  }, [settings]);

  async function saveSettings(next) {
    const data = await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify(next),
    });
    setSettings(data);
    setToast("Interface settings saved.");
  }

  function saveToken(token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token.trim());
    setAuthLocked(false);
    refreshAll().catch((error) => setToast(error.message || "Token saved, retry failed."));
  }

  const view = useMemo(() => {
    if (active === "command") {
      return (
        <CommandCenter
          actions={actions}
          refreshAll={refreshAll}
          settings={settings}
          saveSettings={saveSettings}
          workspaces={workspaces}
        />
      );
    }
    if (active === "vault") {
      return (
        <VaultView
          notes={notes}
          searchResults={searchResults}
          ragResults={ragResults}
          query={query}
          setQuery={setQuery}
          runSearch={runSearch}
          runRagSearch={runRagSearch}
          selectNote={selectNote}
          selectedNote={selectedNote}
        />
      );
    }
    if (active === "projects") return <ProjectsView projects={projects} projectTasks={projectTasks} />;
    if (active === "analytics") {
      return <AnalyticsView stats={stats} hubs={hubs} orphans={orphans} actions={actions} refreshAll={refreshAll} />;
    }
    if (active === "settings") {
      return (
        <SettingsView
          health={health}
          settings={settings}
          authStatus={authStatus}
          setupVault={setupVault}
          runIndex={runIndex}
          saveSettings={saveSettings}
          workspaces={workspaces}
        />
      );
    }
    return <Dashboard stats={stats} health={health} notes={notes} actions={actions} overview={overview} runIndex={runIndex} />;
  }, [active, actions, authStatus, health, hubs, notes, orphans, overview, projectTasks, projects, query, ragResults, searchResults, selectedNote, settings, stats, workspaces]);

  if (connectionError && !health) {
    return <ConnectionPanel error={connectionError} onRetry={refreshAll} />;
  }

  if (authLocked) {
    return <AccessPanel authStatus={authStatus} onSave={saveToken} />;
  }

  return (
    <div className={`app-shell theme-${settings.theme || "system"} density-${settings.density || "comfortable"} accent-${settings.accent || "emerald"}`}>
      <Sidebar active={active} setActive={setActive} />
      <main>
        <Header health={health} refreshAll={refreshAll} />
        {view}
        {toast && (
          <button className="toast" onClick={() => setToast("")}>
            {toast}
          </button>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
