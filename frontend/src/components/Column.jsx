import { useDroppable } from "@dnd-kit/core";
import { AnimatePresence } from "framer-motion";
import TaskCard from "./TaskCard";

export default function Column({ status, meta, tasks, onOpenTask }) {
  const { setNodeRef, isOver } = useDroppable({ id: status });

  return (
    <div
      ref={setNodeRef}
      className={`flex w-72 shrink-0 flex-col rounded-lg border transition-colors ${
        isOver ? "border-status-todo bg-surface-2/60" : "border-border-soft bg-surface/50"
      }`}
    >
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border-soft">
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: meta.color }} />
        <h3 className="font-display text-xs font-semibold uppercase tracking-wide text-text-muted">
          {meta.label}
        </h3>
        <span className="ml-auto rounded-full bg-surface-3 px-1.5 py-0.5 text-[10px] font-mono text-text-faint">
          {tasks.length}
        </span>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-2 min-h-[120px]">
        <AnimatePresence>
          {tasks.map((task) => (
            <TaskCard key={task.id} task={task} onOpen={onOpenTask} />
          ))}
        </AnimatePresence>
        {tasks.length === 0 && (
          <p className="px-2 py-6 text-center text-xs text-text-faint">No tasks here.</p>
        )}
      </div>
    </div>
  );
}
