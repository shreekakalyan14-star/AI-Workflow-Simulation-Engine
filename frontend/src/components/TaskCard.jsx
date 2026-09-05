import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { motion } from "framer-motion";
import { PRIORITY_META } from "../lib/status";

export default function TaskCard({ task, onOpen }) {
  const isLocked = task.locked === true;

  const draggable = useDraggable({
    id: task.id,
    data: { task },
    disabled: isLocked,
  });

  const style = {
    transform: CSS.Translate.toString(draggable.transform),
  };

  const priority = PRIORITY_META[task.priority];
  const overdue =
    task.deadline && task.status !== "completed" && new Date(task.deadline) < new Date();

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      ref={draggable.setNodeRef}
      style={style}
      {...(isLocked ? {} : { ...draggable.listeners, ...draggable.attributes })}
      onClick={() => onOpen(task)}
      className={`select-none rounded-md border bg-surface-2 p-3 text-sm shadow-sm transition-shadow ${
        isLocked
          ? "border-border/40 opacity-50 cursor-not-allowed"
          : "border-border cursor-grab hover:border-status-todo/60 active:cursor-grabbing"
      } ${draggable.isDragging ? "opacity-40" : ""}`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[10px] text-text-faint font-mono">#{task.sequence}</span>
        {isLocked ? (
          <svg className="w-3.5 h-3.5 text-text-faint" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        ) : (
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wide"
            style={{ color: priority.color, backgroundColor: `color-mix(in srgb, ${priority.color} 15%, transparent)` }}
          >
            {priority.label}
          </span>
        )}
        {!isLocked && task.depends_on_task_ids?.length > 0 && (
          <span className="text-[10px] text-text-faint" title="Has dependencies">
            ⛓ {task.depends_on_task_ids.length}
          </span>
        )}
      </div>
      <p className={`font-medium leading-snug ${isLocked ? "text-text-muted" : "text-text"}`}>{task.title}</p>
      <div className="mt-2 flex items-center justify-between text-[11px] text-text-faint font-mono">
        <span>{task.estimated_hours}h est.</span>
        {task.deadline && (
          <span className={overdue ? "text-status-blocked" : ""}>
            {new Date(task.deadline).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
          </span>
        )}
      </div>
    </motion.div>
  );
}
