import { useState } from "react";
import { motion } from "framer-motion";
import { useSimulation } from "../context/SimulationContext";
import { useTimeline, useMeetings } from "../hooks/useApi";
import { useCompanyWebSocket } from "../hooks/useCompanyWebSocket";
import LoadingScreen from "../components/LoadingScreen";

const KIND_META = {
  task_completed: { icon: "✓", color: "var(--color-status-completed)" },
  event: { icon: "⚡", color: "var(--color-status-progress)" },
  meeting: { icon: "◷", color: "var(--color-status-review)" },
  message: { icon: "◇", color: "var(--color-status-todo)" },
};

export default function Timeline() {
  const { simulation } = useSimulation();
  useCompanyWebSocket(simulation?.companyId);

  const { data: timeline, isLoading } = useTimeline(simulation?.projectId);
  const { data: meetings, complete } = useMeetings(simulation?.projectId);
  const [notesById, setNotesById] = useState({});

  if (isLoading) return <LoadingScreen label="Loading timeline" />;

  const pendingMeetings = (meetings || []).filter((m) => !m.completed);

  return (
    <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 p-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <h1 className="mb-4 font-display text-lg font-semibold">Timeline</h1>
        <div className="space-y-3">
          {(timeline || []).slice().reverse().map((entry, i) => {
            const meta = KIND_META[entry.kind] || KIND_META.event;
            return (
              <motion.div
                key={`${entry.kind}-${entry.timestamp}-${i}`}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: Math.min(i * 0.02, 0.4) }}
                className="flex gap-3 rounded-md border border-border-soft bg-surface/60 p-3"
              >
                <span
                  className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs"
                  style={{ color: meta.color, backgroundColor: `color-mix(in srgb, ${meta.color} 15%, transparent)` }}
                >
                  {meta.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{entry.title}</p>
                  {entry.detail && <p className="truncate text-xs text-text-muted">{entry.detail}</p>}
                </div>
                <span className="shrink-0 font-mono text-[11px] text-text-faint">
                  {new Date(entry.timestamp).toLocaleString(undefined, {
                    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                  })}
                </span>
              </motion.div>
            );
          })}
          {(!timeline || timeline.length === 0) && (
            <p className="text-sm text-text-faint">Nothing has happened yet.</p>
          )}
        </div>
      </div>

      <div>
        <h2 className="mb-4 font-display text-lg font-semibold">Upcoming meetings</h2>
        <div className="space-y-3">
          {pendingMeetings.map((m) => (
            <div key={m.id} className="card">
              <p className="font-display text-xs font-semibold uppercase tracking-wide text-text-faint">
                {m.meeting_type.replace(/_/g, " ")}
              </p>
              <p className="mt-1 text-sm text-text">{m.agenda}</p>
              <p className="mt-1 text-xs text-text-faint">
                {m.scheduled_at && new Date(m.scheduled_at).toLocaleDateString()}
              </p>
              <textarea
                className="input mt-2 text-xs"
                placeholder="Meeting notes..."
                rows={2}
                value={notesById[m.id] || ""}
                onChange={(e) => setNotesById((s) => ({ ...s, [m.id]: e.target.value }))}
              />
              <button
                className="btn-ghost mt-2 w-full"
                disabled={complete.isPending}
                onClick={() =>
                  complete.mutateAsync({
                    meetingId: m.id,
                    notes: notesById[m.id] || "",
                    attendance: m.participants,
                    action_items: [],
                  })
                }
              >
                Mark completed
              </button>
            </div>
          ))}
          {pendingMeetings.length === 0 && (
            <p className="text-sm text-text-faint">No upcoming meetings.</p>
          )}
        </div>
      </div>
    </div>
  );
}
