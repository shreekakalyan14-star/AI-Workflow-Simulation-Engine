import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { motion } from "framer-motion";
import { PRIORITY_META } from "../lib/status";

export default function TaskCard({ task, onOpen }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
    data: { task },
  });

  const style = {
    transform: CSS.Translate.toString(transform),
  };

  const priority = PRIORITY_META[task.priority];
  const overdue =
    task.deadline && task.status !== "completed" && new Date(task.deadline) < new Date();

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      onClick={() => onOpen(task)}
      className={`cursor-grab select-none rounded-md border border-border bg-surface-2 p-3 text-sm shadow-sm transition-shadow hover:border-status-todo/60 active:cursor-grabbing ${
        isDragging ? "opacity-40" : ""
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span
          className="rounded px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wide"
          style={{ color: priority.color, backgroundColor: `color-mix(in srgb, ${priority.color} 15%, transparent)` }}
        >
          {priority.label}
        </span>
        {task.depends_on_task_ids?.length > 0 && (
          <span className="text-[10px] text-text-faint" title="Has dependencies">
            ⛓ {task.depends_on_task_ids.length}
          </span>
        )}
      </div>
      <p className="font-medium leading-snug text-text">{task.title}</p>
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
