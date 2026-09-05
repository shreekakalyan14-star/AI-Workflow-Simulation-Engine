import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useManager, useTeam, useManagerChat, useTeamChat } from "../../hooks/useApi";

export default function SimulationChatPanel({ companyId }) {
  const [activeThread, setActiveThread] = useState("manager");
  const [collapsed, setCollapsed] = useState(false);

  const { data: manager } = useManager(companyId);
  const { data: team } = useTeam(companyId);

  const threads = [
    { id: "manager", label: manager?.name || "Manager", sub: manager?.title, icon: "M" },
    ...(team || []).map((t, i) => ({ id: t.id, label: t.name, sub: t.role, icon: t.name?.[0] || `T${i + 1}` })),
  ];

  if (collapsed) {
    return (
      <div className="card p-2">
        <button
          onClick={() => setCollapsed(false)}
          className="w-full flex items-center gap-2 px-2 py-1 rounded hover:bg-surface-2 text-sm"
        >
          <svg className="w-4 h-4 text-status-todo" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <span className="font-medium text-text-muted">Chat</span>
          <span className="ml-auto text-text-faint text-xs">+</span>
        </button>
      </div>
    );
  }

  return (
    <div className="card flex flex-col overflow-hidden" style={{ height: "100%" }}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface-2/50">
        <span className="text-xs font-semibold text-text">Team Chat</span>
        <button
          onClick={() => setCollapsed(true)}
          className="w-5 h-5 flex items-center justify-center rounded text-text-faint hover:bg-surface-2"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      <div className="flex border-b border-border bg-surface-2/30">
        {threads.slice(0, 4).map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveThread(t.id)}
            className={`flex-1 px-2 py-1.5 text-[10px] font-medium transition-colors ${
              activeThread === t.id
                ? "text-status-todo border-b-2 border-status-todo"
                : "text-text-faint hover:text-text-muted"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0">
        <ChatThread
          kind={activeThread === "manager" ? "manager" : "team"}
          companyId={companyId}
          teammateId={activeThread !== "manager" ? activeThread : undefined}
        />
      </div>
    </div>
  );
}

function ChatThread({ kind, companyId, teammateId }) {
  const managerChat = useManagerChat(kind === "manager" ? companyId : undefined);
  const teamChat = useTeamChat(kind === "team" ? companyId : undefined, kind === "team" ? teammateId : undefined);
  const { history, send } = kind === "manager" ? managerChat : teamChat;
  const messagesRef = useRef(null);
  const [draft, setDraft] = useState("");

  const messages = history.data || [];

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages.length]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!draft.trim()) return;
    const text = draft;
    setDraft("");
    await send.mutateAsync(text);
  };

  return (
    <div className="flex h-full flex-col">
      <div ref={messagesRef} className="flex-1 overflow-y-auto p-2 space-y-2">
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${m.sender_type === "student" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded px-2 py-1.5 text-xs ${
                  m.sender_type === "student"
                    ? "bg-status-todo/20 text-text"
                    : "bg-surface-2 text-text-muted border border-border/50"
                }`}
              >
                {m.content}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {messages.length === 0 && (
          <p className="text-center text-[10px] text-text-faint py-4">No messages yet</p>
        )}
      </div>

      <form onSubmit={handleSend} className="flex gap-1 border-t border-border p-2">
        <input
          className="flex-1 bg-surface-2 border border-border rounded px-2 py-1 text-xs outline-none focus:border-status-todo"
          placeholder="Type..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={send.isPending}
        />
        <button
          className="px-2 py-1 rounded bg-status-todo/20 text-status-todo text-xs font-medium hover:bg-status-todo/30 disabled:opacity-50"
          disabled={send.isPending || !draft.trim()}
        >
          {send.isPending ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}
