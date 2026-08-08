import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSimulation } from "../context/SimulationContext";
import { useManager, useTeam, useManagerChat, useTeamChat } from "../hooks/useApi";
import { useCompanyWebSocket } from "../hooks/useCompanyWebSocket";

export default function Chat() {
  const { simulation } = useSimulation();
  useCompanyWebSocket(simulation?.companyId);

  const { data: manager } = useManager(simulation?.companyId);
  const { data: team } = useTeam(simulation?.companyId);

  const [activeThread, setActiveThread] = useState("manager");

  const threads = [
    { id: "manager", label: manager?.name || "Manager", sub: manager?.title },
    ...(team || []).map((t) => ({ id: t.id, label: t.name, sub: t.role })),
  ];

  return (
    <div className="flex h-full">
      <aside className="w-56 shrink-0 border-r border-border-soft p-2">
        {threads.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveThread(t.id)}
            className={`mb-1 w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
              activeThread === t.id ? "bg-surface-2 text-text" : "text-text-muted hover:bg-surface-2/60"
            }`}
          >
            <p className="font-medium">{t.label}</p>
            {t.sub && <p className="text-xs text-text-faint">{t.sub}</p>}
          </button>
        ))}
      </aside>

      <div className="flex-1">
        {activeThread === "manager" ? (
          <ChatThread key="manager" kind="manager" companyId={simulation?.companyId} title={manager?.name} />
        ) : (
          <ChatThread
            key={activeThread}
            kind="team"
            companyId={simulation?.companyId}
            teammateId={activeThread}
            title={threads.find((t) => t.id === activeThread)?.label}
          />
        )}
      </div>
    </div>
  );
}

function ChatThread({ kind, companyId, teammateId, title }) {
  const managerChat = useManagerChat(kind === "manager" ? companyId : undefined);
  const teamChat = useTeamChat(kind === "team" ? companyId : undefined, kind === "team" ? teammateId : undefined);
  const { history, send } = kind === "manager" ? managerChat : teamChat;

  const [draft, setDraft] = useState("");

  const handleSend = async (e) => {
    e.preventDefault();
    if (!draft.trim()) return;
    const text = draft;
    setDraft("");
    await send.mutateAsync(text);
  };

  const messages = kind === "team" ? history.data || [] : history.data || [];

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border-soft px-4 py-3">
        <h2 className="font-display text-sm font-semibold">{title}</h2>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${m.sender_type === "student" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-md rounded-lg px-3 py-2 text-sm ${
                  m.sender_type === "student"
                    ? "bg-status-todo text-ink"
                    : "border border-border-soft bg-surface-2 text-text"
                }`}
              >
                {m.content}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {messages.length === 0 && (
          <p className="text-center text-sm text-text-faint">No messages yet — say hi.</p>
        )}
      </div>

      <form onSubmit={handleSend} className="flex gap-2 border-t border-border-soft p-3">
        <input
          className="input"
          placeholder="Type a message..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={send.isPending}
        />
        <button className="btn-primary" disabled={send.isPending || !draft.trim()}>
          {send.isPending ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}
