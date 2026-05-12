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
  GitBranch,
  Inbox,
  LayoutDashboard,
  Network,
  Play,
  RefreshCcw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  X,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || `${window.location.protocol}//${window.location.hostname}:8765`;
const DEFAULT_VAULT = "/Users/justalim/projects/obsidian-vault";

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "command", label: "Command", icon: Bot },
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

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
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

function Dashboard({ stats, health, notes, actions, runIndex }) {
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
            <strong>{health?.local_ai?.models?.[0] || "llama3:latest"}</strong>
          </div>
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

function CommandCenter({ actions, refreshAll }) {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Готов. Я отвечаю с учетом vault и создаю изменения только через очередь подтверждений." },
  ]);
  const [input, setInput] = useState("");
  const [remoteTask, setRemoteTask] = useState("");
  const [busy, setBusy] = useState(false);

  async function sendChat() {
    const text = input.trim();
    if (!text || busy) return;
    const next = [...messages, { role: "user", content: text }, { role: "assistant", content: "" }];
    setMessages(next);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/ai/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: "ollama",
          model: "llama3:latest",
          messages: next.filter((m) => m.content).map((m) => ({ role: m.role, content: m.content })),
          include_vault_context: true,
        }),
      });
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

  return (
    <section className="view command-layout">
      <div className="panel chat-panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">AI</p>
            <h2>Command Center</h2>
          </div>
          <div className="pill">
            <Bot size={14} />
            Ollama
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
            placeholder="Спроси про vault, проект, план реализации..."
          />
          <button onClick={sendChat} disabled={busy || !input.trim()} title="Отправить">
            <Send size={18} />
          </button>
        </div>
      </div>

      <div className="side-stack">
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

function VaultView({ notes, searchResults, query, setQuery, runSearch, selectNote, selectedNote }) {
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
          <button onClick={runSearch}>Search</button>
        </div>
        <div className="note-list scroll">
          {(query ? searchResults : notes).map((note) => (
            <button className="note-row selectable" key={note.id} onClick={() => selectNote(note.path)}>
              <strong>{note.title}</strong>
              <span>{note.path}</span>
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

function SettingsView({ health, setupVault, runIndex }) {
  const [vaultPath, setVaultPath] = useState(health?.vault_path || DEFAULT_VAULT);
  useEffect(() => {
    if (health?.vault_path) setVaultPath(health.vault_path);
  }, [health?.vault_path]);

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
            <strong>qwen3:14b</strong>
          </div>
          <div>
            <span>Install</span>
            <code>ollama pull qwen3:14b</code>
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
  const [stats, setStats] = useState(null);
  const [notes, setNotes] = useState([]);
  const [actions, setActions] = useState([]);
  const [hubs, setHubs] = useState([]);
  const [orphans, setOrphans] = useState([]);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [selectedNote, setSelectedNote] = useState(null);
  const [toast, setToast] = useState("");

  async function refreshAll() {
    const [healthData, statsData, notesData, actionsData] = await Promise.all([
      api("/api/health"),
      api("/api/vault/stats"),
      api("/api/notes?limit=200"),
      api("/api/actions?limit=100"),
    ]);
    setHealth(healthData);
    setStats(statsData);
    setNotes(notesData.notes || []);
    setActions(actionsData.actions || []);

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

  const view = useMemo(() => {
    if (active === "command") return <CommandCenter actions={actions} refreshAll={refreshAll} />;
    if (active === "vault") {
      return (
        <VaultView
          notes={notes}
          searchResults={searchResults}
          query={query}
          setQuery={setQuery}
          runSearch={runSearch}
          selectNote={selectNote}
          selectedNote={selectedNote}
        />
      );
    }
    if (active === "analytics") {
      return <AnalyticsView stats={stats} hubs={hubs} orphans={orphans} actions={actions} refreshAll={refreshAll} />;
    }
    if (active === "settings") return <SettingsView health={health} setupVault={setupVault} runIndex={runIndex} />;
    return <Dashboard stats={stats} health={health} notes={notes} actions={actions} runIndex={runIndex} />;
  }, [active, actions, health, hubs, notes, orphans, query, searchResults, selectedNote, stats]);

  return (
    <div className="app-shell">
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
