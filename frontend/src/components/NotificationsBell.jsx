import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useNotifications } from "../hooks/useApi";

export default function NotificationsBell({ companyId }) {
  const [open, setOpen] = useState(false);
  const { data: notifications, markRead } = useNotifications(companyId);
  const unread = (notifications || []).filter((n) => !n.is_read);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative rounded border border-border px-2 py-1 text-text-muted hover:border-status-todo hover:text-text transition-colors"
      >
        <span className="font-mono text-xs">notifications</span>
        {unread.length > 0 && (
          <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-status-blocked px-1 text-[10px] font-semibold text-ink">
            {unread.length}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="absolute right-0 top-full z-50 mt-2 w-80 max-h-96 overflow-y-auto rounded-lg border border-border bg-surface p-2 shadow-xl"
            >
              {(notifications || []).length === 0 && (
                <p className="p-3 text-center text-xs text-text-faint">No notifications yet.</p>
              )}
              {(notifications || []).map((n) => (
                <button
                  key={n.id}
                  onClick={() => !n.is_read && markRead.mutate(n.id)}
                  className={`mb-1 block w-full rounded-md p-2 text-left text-xs transition-colors ${
                    n.is_read ? "text-text-faint" : "bg-surface-2 text-text"
                  }`}
                >
                  <p className="font-medium">{n.notification_type.replace(/_/g, " ")}</p>
                  <p className="mt-0.5 text-text-muted">{n.message}</p>
                </button>
              ))}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
