import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  Bot,
  Brain,
  Check,
  CircleDot,
  ClipboardList,
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
  PackageCheck,
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
  Terminal,
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
  { id: "plans", label: "Plans", icon: ClipboardList },
  { id: "projects", label: "Projects", icon: FolderKanban },
  { id: "vault", label: "Vault", icon: FileSearch },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "learning", label: "Learning", icon: Brain },
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
  const { timeoutMs = 60000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(apiUrl(path), {
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-ObsidianAI-Token": token } : {}),
        ...(fetchOptions.headers || {}),
      },
      ...fetchOptions,
      signal: fetchOptions.signal || controller.signal,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status} ${text || res.statusText}`);
    }
    return res.json();
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Запрос занял слишком много времени. Попробуй короче задачу или переключись в Chat для обычного вопроса.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function isSimpleConversation(text) {
  const normalized = text.trim().toLowerCase();
  if (!normalized) return false;
  const actionWords = [
    "создай",
    "сделай",
    "напиши",
    "исправь",
    "добавь",
    "удали",
    "переименуй",
    "обнови",
    "измени",
    "запиши",
    "create",
    "write",
    "fix",
    "add",
    "delete",
    "update",
    "rename",
  ];
  if (actionWords.some((word) => normalized.includes(word))) return false;
  return normalized.length < 120;
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
  const [contextPack, setContextPack] = useState(null);
  const [contextHealth, setContextHealth] = useState(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setWorkspace(settings?.working_directory || "");
  }, [settings?.working_directory]);

  useEffect(() => {
    if (!workspace) return;
    let cancelled = false;
    setContextLoading(true);
    api(`/api/context/workspace?path=${encodeURIComponent(workspace)}`, { timeoutMs: 20000 })
      .then((data) => {
        if (!cancelled) setContextPack(data.context_pack || null);
        if (!cancelled) setContextHealth(data.health || null);
      })
      .catch(() => {
        if (!cancelled) setContextPack(null);
        if (!cancelled) setContextHealth(null);
      })
      .finally(() => {
        if (!cancelled) setContextLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspace]);

  async function sendChat() {
    const text = input.trim();
    if (!text || busy) return;
    const effectiveMode = mode === "actions" && isSimpleConversation(text) ? "chat" : mode;
    const next = [...messages, { role: "user", content: text }, { role: "assistant", content: "" }];
    setMessages(next);
    setInput("");
    setBusy(true);
    try {
      if (effectiveMode === "actions") {
        const data = await api("/api/ai/actions/propose", {
          method: "POST",
          timeoutMs: 70000,
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

      if (mode === "plan") {
        const data = await api("/api/plans/propose", {
          method: "POST",
          timeoutMs: 90000,
          body: JSON.stringify({
            goal: text,
            provider: "ollama",
            model: settings?.default_model || "qwen3:latest",
            working_directory: workspace,
          }),
        });
        const plan = data.plan;
        const planText = [
          `Создал execution plan: ${plan?.title || "Plan"}`,
          plan?.summary || "",
          ...(plan?.steps || []).map((step) => `- ${step.position}. ${step.title}`),
        ].filter(Boolean).join("\n");
        setMessages((current) => {
          const copy = [...current];
          copy[copy.length - 1] = { role: "assistant", content: planText };
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
        signal: AbortSignal.timeout(70000),
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
      const message = String(error.message || error);
      const workspaceHint = message.includes("Selected workspace is a container with nested projects")
        ? "Выбран общий контейнер проектов. Сначала переключи Active Workspace на одну из concrete project folders справа, потом повтори действие."
        : null;
      setMessages((current) => {
        const copy = [...current];
        copy[copy.length - 1] = {
          role: "assistant",
          content: workspaceHint
            ? `Ошибка: ${message}\n\n${workspaceHint}`
            : `Ошибка: ${message}\n\nЯ снял зависший запрос. Для простого общения включи Chat, для изменения файлов оставь Actions.`,
        };
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

  async function useWorkspace(path) {
    setWorkspace(path);
    await saveSettings({ ...settings, working_directory: path });
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
            <button className={mode === "plan" ? "active" : ""} onClick={() => setMode("plan")}>
              <ClipboardList size={14} />
              Plan
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
            placeholder={mode === "chat" ? "Спроси про vault, проект, план реализации..." : mode === "plan" ? "Опиши большую задачу, чтобы ИИ сначала создал пошаговый план..." : "Опиши действие: создать заметку, обновить проект, подготовить файл..."}
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
        <ContextPackCard
          contextPack={contextPack}
          health={contextHealth}
          loading={contextLoading}
          useWorkspace={useWorkspace}
        />
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

function ContextPackCard({ contextPack, health, loading, useWorkspace }) {
  const project = contextPack?.project;
  const runtime = contextPack?.runtime || {};
  const git = contextPack?.git || {};
  const risks = contextPack?.risks || [];
  const nestedCandidates = contextPack?.nested_workspace_candidates || [];
  return (
    <div className="panel context-panel">
      <div className="panel-head compact">
        <h2>Context Pack</h2>
        <PackageCheck size={18} />
      </div>
      {loading && <p className="muted">Loading workspace context...</p>}
      {!loading && !contextPack && <p className="muted">No workspace context loaded.</p>}
      {contextPack && (
        <div className="context-stack">
          <div className="context-main">
            <span>Mapped project</span>
            <strong>{project?.title || "not mapped"}</strong>
          </div>
          <div className="context-grid">
            <div>
              <span>Runtime</span>
              <strong>{runtime.signals?.join(", ") || "unknown"}</strong>
            </div>
            <div>
              <span>Git</span>
              <strong>{git.available ? `${git.branch || "repo"} · ${git.dirty || 0} changes` : git.reason || "unknown"}</strong>
            </div>
          </div>
          {health && (
            <div className="context-grid">
              <div>
                <span>Health</span>
                <strong>{health.score}/100</strong>
              </div>
              <div>
                <span>Checks</span>
                <strong>{health.verification_commands?.length || 0} detected</strong>
              </div>
            </div>
          )}
          {!!health?.verification_commands?.length && (
            <div className="command-chip-row">
              {health.verification_commands.slice(0, 5).map((item) => (
                <span key={item.command}>
                  <Terminal size={13} />
                  {item.command}
                </span>
              ))}
            </div>
          )}
          {!!runtime.scripts?.length && (
            <div className="signal-row compact">
              {runtime.scripts.slice(0, 8).map((script) => <span key={script}>{script}</span>)}
            </div>
          )}
          {!!risks.length && (
            <div className="risk-list">
              {risks.map((risk) => <span key={risk}>{risk}</span>)}
            </div>
          )}
          {!!nestedCandidates.length && (
            <div className="nested-workspace-box">
              <div className="nested-workspace-head">
                <span>Concrete project folders</span>
                <strong>{nestedCandidates.length}</strong>
              </div>
              <div className="nested-workspace-list">
                {nestedCandidates.slice(0, 8).map((item) => (
                  <button
                    type="button"
                    className="nested-workspace-item"
                    key={item.path}
                    onClick={() => useWorkspace?.(item.path)}
                    title={item.path}
                  >
                    <strong>{item.relative}</strong>
                    <span>{item.signals?.join(", ") || "project"}</span>
                    {!!item.scripts?.length && <small>{item.scripts.slice(0, 3).join(" · ")}</small>}
                  </button>
                ))}
              </div>
            </div>
          )}
          <details className="tree-preview">
            <summary>Workspace tree</summary>
            <pre>{(contextPack.tree || []).slice(0, 50).join("\n")}</pre>
          </details>
        </div>
      )}
    </div>
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

function PlansView({ plans, commands, actions, settings, workspaces, refreshAll }) {
  const [goal, setGoal] = useState("");
  const [workspace, setWorkspace] = useState(settings?.working_directory || "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => setWorkspace(settings?.working_directory || ""), [settings?.working_directory]);

  async function createPlan() {
    const clean = goal.trim();
    if (!clean || busy) return;
    setBusy(true);
    setMessage("Создаю план...");
    try {
      const data = await api("/api/plans/propose", {
        method: "POST",
        timeoutMs: 90000,
        body: JSON.stringify({
          goal: clean,
          provider: "ollama",
          model: settings?.default_model || "qwen3:latest",
          working_directory: workspace,
        }),
      });
      setGoal("");
      setMessage(`План готов: ${data.plan?.title || "Execution plan"}`);
      await refreshAll();
    } catch (error) {
      setMessage(error.message || String(error));
    } finally {
      setBusy(false);
    }
  }

  async function setPlanStatus(planId, action) {
    await api(`/api/plans/${planId}/${action}`, { method: "POST" });
    await refreshAll();
  }

  async function setStepStatus(stepId, status) {
    await api(`/api/plans/steps/${stepId}/${status}`, { method: "POST" });
    await refreshAll();
  }

  async function runCheck(plan, step, command) {
    const proposed = await api("/api/commands/propose", {
      method: "POST",
      body: JSON.stringify({
        command,
        working_directory: plan.workspace,
        session_id: plan.session_id,
        plan_id: plan.id,
        step_id: step.id,
      }),
    });
    await api(`/api/commands/${proposed.command.id}/run`, { method: "POST", timeoutMs: 130000 });
    await refreshAll();
  }

  async function generateStepActions(step) {
    setBusy(true);
    setMessage(`Генерирую pending actions для шага: ${step.title}`);
    try {
      const data = await api(`/api/plan-steps/${step.id}/actions/propose`, {
        method: "POST",
        timeoutMs: 90000,
        body: JSON.stringify({
          provider: "ollama",
          model: settings?.default_model || "qwen3:latest",
          max_actions: 3,
        }),
      });
      setMessage(`Создано pending actions: ${data.actions?.length || 0}`);
      await refreshAll();
    } catch (error) {
      setMessage(error.message || String(error));
    } finally {
      setBusy(false);
    }
  }

  const actionsById = useMemo(() => {
    const map = new Map();
    actions.forEach((action) => map.set(action.id, action));
    return map;
  }, [actions]);

  return (
    <section className="view plans-layout">
      <div className="panel wide">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Agent OS</p>
            <h2>Execution Plans</h2>
          </div>
          <ClipboardList size={20} />
        </div>
        <div className="plan-composer">
          <textarea
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            placeholder="Большая задача: что нужно спланировать, проверить и выполнить через approval-first процесс"
          />
          <div className="form-stack">
            <label>
              Workspace
              <select value={workspace} onChange={(event) => setWorkspace(event.target.value)}>
                {workspaces.map((item) => (
                  <option value={item.path} key={item.path}>{item.name}</option>
                ))}
              </select>
            </label>
            <button onClick={createPlan} disabled={busy || !goal.trim()}>
              <WandSparkles size={16} />
              Create plan
            </button>
            {message && <p className="muted">{message}</p>}
          </div>
        </div>
      </div>

      <div className="plans-list">
        {plans.map((plan) => (
          <article className="panel plan-card" key={plan.id}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">{plan.status} · {plan.risk_level} risk</p>
                <h2>{plan.title}</h2>
              </div>
              <span className="project-status">{plan.steps?.length || 0} steps</span>
            </div>
            <p className="project-summary">{plan.summary || plan.goal}</p>
            <div className="plan-meta">
              <span>{plan.workspace}</span>
            </div>
            <div className="decision-row">
              <button onClick={() => setPlanStatus(plan.id, "approve")} disabled={plan.status === "approved"}>
                <Check size={16} />
                Approve plan
              </button>
              <button className="ghost danger" onClick={() => setPlanStatus(plan.id, "reject")} disabled={plan.status === "rejected"}>
                <X size={16} />
                Reject
              </button>
            </div>
            <div className="step-list">
              {(plan.steps || []).map((step) => (
                <div className="step-card" key={step.id}>
                  <div className="step-head">
                    <strong>{step.position}. {step.title}</strong>
                    <span>{step.status}</span>
                  </div>
                  <p>{step.objective || step.expected_result}</p>
                  {!!step.files?.length && <small>Files: {step.files.join(", ")}</small>}
                  {!!step.risks?.length && <small>Risks: {step.risks.join(", ")}</small>}
                  {!!step.action_ids?.length && (
                    <div className="step-actions-linked">
                      {step.action_ids.map((actionId) => {
                        const action = actionsById.get(actionId);
                        return (
                          <span key={actionId}>
                            <ShieldCheck size={13} />
                            {action ? `${action.title} · ${action.status}` : actionId}
                          </span>
                        );
                      })}
                    </div>
                  )}
                  <div className="decision-row">
                    <button className="ghost" onClick={() => setStepStatus(step.id, "approved")}>
                      <Check size={15} />
                      Step approve
                    </button>
                    <button
                      className="ghost"
                      onClick={() => generateStepActions(step)}
                      disabled={busy || plan.status !== "approved" || !["approved", "actions_ready"].includes(step.status)}
                    >
                      <WandSparkles size={15} />
                      Generate actions
                    </button>
                    <button className="ghost" onClick={() => setStepStatus(step.id, "completed")}>
                      <CircleDot size={15} />
                      Complete
                    </button>
                    <button className="ghost danger" onClick={() => setStepStatus(step.id, "rejected")}>
                      <X size={15} />
                      Reject
                    </button>
                  </div>
                  {!!step.checks?.length && (
                    <div className="command-chip-row">
                      {step.checks.map((check) => (
                        <button className="ghost command-chip-button" key={check} onClick={() => runCheck(plan, step, check)}>
                          <Terminal size={13} />
                          {check}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </article>
        ))}
        {!plans.length && <div className="panel"><p className="muted">No execution plans yet.</p></div>}
      </div>

      <div className="panel wide">
        <div className="panel-head compact">
          <h2>Command Runs</h2>
        </div>
        <div className="commands-list">
          {commands.slice(0, 10).map((item) => (
            <div key={item.id}>
              <Terminal size={15} />
              <strong>{item.command}</strong>
              <span>{item.status}{item.exit_code !== null && item.exit_code !== undefined ? ` · exit ${item.exit_code}` : ""}</span>
            </div>
          ))}
          {!commands.length && <p className="muted">No command runs yet.</p>}
        </div>
      </div>
    </section>
  );
}

function LearningView({ learningItems, learningSettings, settings, refreshAll }) {
  const [draft, setDraft] = useState({
    kind: "preference",
    title: "",
    content: "",
    scope: "global",
  });
  const [feedback, setFeedback] = useState("");
  const [config, setConfig] = useState(learningSettings);
  const [message, setMessage] = useState("");

  useEffect(() => setConfig(learningSettings), [learningSettings]);

  function updateDraft(key, value) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function saveMemory() {
    if (!draft.title.trim() || !draft.content.trim()) return;
    await api("/api/learning/items", {
      method: "POST",
      body: JSON.stringify({
        ...draft,
        workspace: draft.scope === "workspace" ? settings?.working_directory : null,
      }),
    });
    setDraft({ kind: "preference", title: "", content: "", scope: "global" });
    setMessage("Memory saved for review.");
    await refreshAll();
  }

  async function saveFeedback() {
    if (!feedback.trim()) return;
    await api("/api/learning/feedback", {
      method: "POST",
      body: JSON.stringify({
        feedback,
        title: "User correction",
        workspace: settings?.working_directory,
        rating: 1,
      }),
    });
    setFeedback("");
    setMessage("Feedback converted into learning memory.");
    await refreshAll();
  }

  async function saveConfig() {
    await api("/api/learning/settings", {
      method: "PUT",
      body: JSON.stringify(config),
    });
    setMessage("Learning settings saved.");
    await refreshAll();
  }

  async function itemAction(id, action) {
    await api(`/api/learning/items/${id}/${action}`, { method: "POST" });
    await refreshAll();
  }

  const active = learningItems.filter((item) => item.status === "active");
  const pending = learningItems.filter((item) => item.status === "pending");

  return (
    <section className="view learning-layout">
      <div className="metrics-row">
        <StatTile icon={Brain} label="Active Memory" value={formatNumber(active.length)} />
        <StatTile icon={Clock3} label="Review Queue" value={formatNumber(pending.length)} tone="amber" />
        <StatTile icon={Database} label="All Items" value={formatNumber(learningItems.length)} tone="blue" />
        <StatTile icon={ShieldCheck} label="Mode" value={config?.mode || "review"} tone="violet" />
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Controlled Learning</p>
            <h2>Add Memory</h2>
          </div>
        </div>
        <div className="form-stack">
          <label>
            Kind
            <select value={draft.kind} onChange={(event) => updateDraft("kind", event.target.value)}>
              <option value="preference">Preference</option>
              <option value="correction">Correction</option>
              <option value="pattern">Pattern</option>
              <option value="decision">Decision</option>
              <option value="project-note">Project note</option>
            </select>
          </label>
          <label>
            Scope
            <select value={draft.scope} onChange={(event) => updateDraft("scope", event.target.value)}>
              <option value="global">Global</option>
              <option value="workspace">Current workspace</option>
            </select>
          </label>
          <label>
            Title
            <input value={draft.title} onChange={(event) => updateDraft("title", event.target.value)} />
          </label>
          <label>
            Content
            <textarea value={draft.content} onChange={(event) => updateDraft("content", event.target.value)} />
          </label>
          <button onClick={saveMemory}>
            <Brain size={16} />
            Save memory
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Feedback</p>
            <h2>Teach Assistant</h2>
          </div>
        </div>
        <div className="form-stack">
          <label>
            Correction or instruction
            <textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="Например: в моих Flutter проектах сначала всегда запускай flutter analyze" />
          </label>
          <button onClick={saveFeedback}>
            <Sparkles size={16} />
            Convert to memory
          </button>
          <div className="settings-list">
            <div>
              <span>Mode</span>
              <select value={config?.mode || "review"} onChange={(event) => setConfig((current) => ({ ...current, mode: event.target.value }))}>
                <option value="review">Review before active</option>
                <option value="auto">Auto active</option>
              </select>
            </div>
            <div>
              <span>Max context items</span>
              <input type="number" value={config?.max_context_items || 12} onChange={(event) => setConfig((current) => ({ ...current, max_context_items: Number(event.target.value) }))} />
            </div>
          </div>
          <label className="checkbox-line">
            <input type="checkbox" checked={!!config?.include_in_chat} onChange={(event) => setConfig((current) => ({ ...current, include_in_chat: event.target.checked }))} />
            Include active memory in chat
          </label>
          <label className="checkbox-line">
            <input type="checkbox" checked={!!config?.auto_promote_feedback} onChange={(event) => setConfig((current) => ({ ...current, auto_promote_feedback: event.target.checked }))} />
            Auto-promote feedback
          </label>
          <button className="ghost" onClick={saveConfig}>
            <SlidersHorizontal size={16} />
            Save learning settings
          </button>
          {message && <p className="muted">{message}</p>}
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-head compact">
          <h2>Memory Items</h2>
        </div>
        <div className="memory-list">
          {learningItems.map((item) => (
            <div className="memory-item" key={item.id}>
              <div>
                <strong>{item.title}</strong>
                <span>{item.kind} · {item.scope} · {item.status}</span>
              </div>
              <p>{item.content}</p>
              <div className="decision-row">
                <button className="ghost" onClick={() => itemAction(item.id, "activate")}>
                  <Check size={15} />
                  Activate
                </button>
                <button className="ghost danger" onClick={() => itemAction(item.id, "archive")}>
                  <X size={15} />
                  Archive
                </button>
              </div>
            </div>
          ))}
          {!learningItems.length && <p className="muted">No learning memory yet.</p>}
        </div>
      </div>
    </section>
  );
}

function ActionQueue({ actions, refreshAll, compact = false }) {
  const retryable = actions.filter((item) => ["pending", "failed"].includes(item.status));
  const visible = compact ? retryable.slice(0, 3) : actions;
  const [error, setError] = useState("");

  async function decide(id, action) {
    setError("");
    try {
      await api(`/api/actions/${id}/${action}`, {
        method: "POST",
        body: JSON.stringify(action === "reject" ? { reason: "Rejected from UI" } : {}),
      });
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      await refreshAll();
    }
  }

  return (
    <div className="panel action-panel">
      <div className="panel-head compact">
        <h2>Approval Queue</h2>
      </div>
      <div className="actions-list">
        {error && <p className="form-error">{error}</p>}
        {visible.map((item) => (
          <div className="action-item" key={item.id}>
            <div className="action-title">
              <ShieldCheck size={16} />
              <strong>{item.title}</strong>
              <span>{item.status}</span>
            </div>
            {!compact && <pre className="diff">{item.diff_preview || item.summary}</pre>}
            {item.error && <p className="action-error">{item.error}</p>}
            {["pending", "failed"].includes(item.status) && (
              <div className="decision-row">
                <button onClick={() => decide(item.id, "approve")}>
                  <Check size={16} />
                  {item.status === "failed" ? "Retry approve" : "Approve"}
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
  const [plans, setPlans] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [commands, setCommands] = useState([]);
  const [learningItems, setLearningItems] = useState([]);
  const [learningSettings, setLearningSettings] = useState({
    mode: "review",
    include_in_chat: true,
    auto_promote_feedback: false,
    max_context_items: 12,
  });
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
      const [
        settingsData,
        statsData,
        notesData,
        actionsData,
        projectsData,
        tasksData,
        overviewData,
        workspacesData,
        plansData,
        sessionsData,
        commandsData,
        learningData,
        learningSettingsData,
      ] = await Promise.all([
        api("/api/settings"),
        api("/api/vault/stats"),
        api("/api/notes?limit=200"),
        api("/api/actions?limit=100"),
        api("/api/projects"),
        api("/api/projects/tasks"),
        api("/api/analytics/overview"),
        api("/api/workspaces"),
        api("/api/plans?limit=30"),
        api("/api/sessions?limit=30"),
        api("/api/commands?limit=50"),
        api("/api/learning/items?limit=100"),
        api("/api/learning/settings"),
      ]);
      setSettings(settingsData);
      setStats(statsData);
      setNotes(notesData.notes || []);
      setActions(actionsData.actions || []);
      setPlans(plansData.plans || []);
      setSessions(sessionsData.sessions || []);
      setCommands(commandsData.commands || []);
      setLearningItems(learningData.items || []);
      setLearningSettings(learningSettingsData);
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
    if (active === "plans") {
      return (
        <PlansView
          plans={plans}
          commands={commands}
          actions={actions}
          settings={settings}
          workspaces={workspaces}
          refreshAll={refreshAll}
        />
      );
    }
    if (active === "analytics") {
      return <AnalyticsView stats={stats} hubs={hubs} orphans={orphans} actions={actions} refreshAll={refreshAll} />;
    }
    if (active === "learning") {
      return (
        <LearningView
          learningItems={learningItems}
          learningSettings={learningSettings}
          settings={settings}
          refreshAll={refreshAll}
        />
      );
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
  }, [active, actions, authStatus, commands, health, hubs, learningItems, learningSettings, notes, orphans, overview, plans, projectTasks, projects, query, ragResults, searchResults, selectedNote, settings, stats, workspaces]);

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
