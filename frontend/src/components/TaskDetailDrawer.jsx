import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { STATUS_META, PRIORITY_META } from "../lib/status";
import { useReportBug } from "../hooks/useApi";
import { useSimulation } from "../context/SimulationContext";

export default function TaskDetailDrawer({ task, allTasks, onClose, onUpdateStatus, isUpdating }) {
  const { simulation } = useSimulation();
  const [deliverableUrl, setDeliverableUrl] = useState("");
  const [blockedReason, setBlockedReason] = useState("");
  const [bugDescription, setBugDescription] = useState("");
  const reportBug = useReportBug(simulation?.projectId);

  if (!task) return null;

  const dependencies = (task.depends_on_task_ids || [])
    .map((id) => allTasks.find((t) => t.id === id))
    .filter(Boolean);

  const dependenciesIncomplete = dependencies.some((d) => d.status !== "completed");

  const act = (status, extra = {}) => onUpdateStatus({ taskId: task.id, status, ...extra });

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-40 bg-black/40"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        className="fixed right-0 top-0 z-50 h-full w-full max-w-md overflow-y-auto border-l border-border bg-surface p-5"
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 28, stiffness: 300 }}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wide"
              style={{ color: STATUS_META[task.status].color }}
            >
              {STATUS_META[task.status].label}
            </span>
            <h2 className="mt-2 font-display text-lg font-semibold leading-snug">{task.title}</h2>
          </div>
          <button onClick={onClose} className="btn-ghost">Close</button>
        </div>

        <p className="mt-4 text-sm leading-relaxed text-text-muted">{task.description}</p>

        <Section title="Acceptance criteria">
          <ul className="list-inside list-disc space-y-1 text-sm text-text-muted">
            {task.acceptance_criteria.map((c) => <li key={c}>{c}</li>)}
          </ul>
        </Section>

        <Section title="Details">
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-text-faint">Priority</dt>
            <dd style={{ color: PRIORITY_META[task.priority].color }}>{PRIORITY_META[task.priority].label}</dd>
            <dt className="text-text-faint">Estimated hours</dt>
            <dd>{task.estimated_hours}h</dd>
            <dt className="text-text-faint">Deadline</dt>
            <dd>{task.deadline ? new Date(task.deadline).toLocaleDateString() : "—"}</dd>
          </dl>
        </Section>

        {dependencies.length > 0 && (
          <Section title="Dependencies">
            <ul className="space-y-1 text-sm">
              {dependencies.map((d) => (
                <li key={d.id} className="flex items-center gap-2">
                  <span style={{ color: STATUS_META[d.status].color }}>●</span>
                  <span className={d.status === "completed" ? "text-text-muted" : "text-text"}>{d.title}</span>
                </li>
              ))}
            </ul>
            {dependenciesIncomplete && task.status === "backlog" && (
              <p className="mt-2 text-xs text-status-blocked">
                Cannot start until all dependencies are completed.
              </p>
            )}
          </Section>
        )}

        <Section title="Actions">
          <div className="flex flex-wrap gap-2">
            <ActionButton
              disabled={isUpdating || task.status === "in_progress" || dependenciesIncomplete}
              onClick={() => act("in_progress")}
            >
              Start
            </ActionButton>
            <ActionButton
              disabled={isUpdating || task.status !== "in_progress"}
              onClick={() => act("todo")}
            >
              Pause
            </ActionButton>
            <ActionButton
              disabled={isUpdating || task.status === "completed"}
              onClick={() => act("review")}
            >
              Send to review
            </ActionButton>
            <ActionButton
              disabled={isUpdating || task.status === "completed"}
              onClick={() => act("completed", deliverableUrl ? { deliverable_url: deliverableUrl } : {})}
              accent="var(--color-status-completed)"
            >
              Mark complete
            </ActionButton>
          </div>

          <div className="mt-3 space-y-2">
            <input
              className="input"
              placeholder="Deliverable link (repo, PR, doc...)"
              value={deliverableUrl}
              onChange={(e) => setDeliverableUrl(e.target.value)}
            />
            {task.deliverable_url && (
              <a
                href={task.deliverable_url}
                target="_blank"
                rel="noreferrer"
                className="block truncate text-xs text-status-todo underline"
              >
                {task.deliverable_url}
              </a>
            )}
          </div>

          <div className="mt-3 flex gap-2">
            <input
              className="input"
              placeholder="Why is this blocked?"
              value={blockedReason}
              onChange={(e) => setBlockedReason(e.target.value)}
            />
            <button
              className="btn-ghost shrink-0"
              disabled={isUpdating || !blockedReason}
              onClick={() => act("blocked", { blocked_reason: blockedReason })}
            >
              Mark blocked
            </button>
          </div>
          {task.blocked_reason && task.status === "blocked" && (
            <p className="mt-2 text-xs text-status-blocked">Blocked: {task.blocked_reason}</p>
          )}

          <div className="mt-4 flex gap-2 border-t border-border-soft pt-3">
            <input
              className="input"
              placeholder="Report a bug on this task"
              value={bugDescription}
              onChange={(e) => setBugDescription(e.target.value)}
            />
            <button
              className="btn-ghost shrink-0"
              style={{ borderColor: "var(--color-status-blocked)", color: "var(--color-status-blocked)" }}
              disabled={reportBug.isPending || !bugDescription}
              onClick={async () => {
                await reportBug.mutateAsync({ taskId: task.id, description: bugDescription });
                setBugDescription("");
              }}
            >
              Report bug
            </button>
          </div>
        </Section>
      </motion.div>
    </AnimatePresence>
  );
}

function Section({ title, children }) {
  return (
    <div className="mt-5 border-t border-border-soft pt-4">
      <h3 className="mb-2 font-display text-xs font-semibold uppercase tracking-wide text-text-faint">
        {title}
      </h3>
      {children}
    </div>
  );
}

function ActionButton({ children, disabled, onClick, accent }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="btn-ghost disabled:cursor-not-allowed disabled:opacity-40"
      style={accent && !disabled ? { borderColor: accent, color: accent } : undefined}
    >
      {children}
    </button>
  );
}
