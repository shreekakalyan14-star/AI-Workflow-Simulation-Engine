import { useMemo, useState } from "react";
import { DndContext, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { useSimulation } from "../context/SimulationContext";
import { useBoard, useUpdateTaskStatus } from "../hooks/useApi";
import { STATUS_ORDER, STATUS_META } from "../lib/status";
import Column from "../components/Column";
import TaskDetailDrawer from "../components/TaskDetailDrawer";
import LoadingScreen from "../components/LoadingScreen";

export default function Board() {
  const { simulation } = useSimulation();
  const { data: board, isLoading, error } = useBoard(simulation?.projectId);
  const updateStatus = useUpdateTaskStatus(simulation?.projectId);
  const [selectedTask, setSelectedTask] = useState(null);
  const [banner, setBanner] = useState(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const allTasks = useMemo(
    () => (board ? Object.values(board).flat() : []),
    [board]
  );

  if (isLoading) return <LoadingScreen label="Loading the board" />;
  if (error) return <ErrorState message={error.message} />;

  const handleDragEnd = async (event) => {
    const { active, over } = event;
    if (!over) return;
    const task = active.data.current?.task;
    const newStatus = over.id;
    if (!task || task.status === newStatus) return;

    try {
      await updateStatus.mutateAsync({ taskId: task.id, status: newStatus });
      setBanner(null);
    } catch (err) {
      setBanner(err.message);
      setTimeout(() => setBanner(null), 4000);
    }
  };

  const openTask = (task) => {
    // Re-find the freshest copy in case the board refetched since render.
    const fresh = allTasks.find((t) => t.id === task.id) || task;
    setSelectedTask(fresh);
  };

  return (
    <div className="flex h-full flex-col">
      {banner && (
        <div className="border-b border-status-blocked/40 bg-status-blocked/10 px-4 py-2 text-sm text-status-blocked">
          {banner}
        </div>
      )}
      <div className="flex-1 overflow-x-auto p-4">
        <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
          <div className="flex h-full gap-3">
            {STATUS_ORDER.map((status) => (
              <Column
                key={status}
                status={status}
                meta={STATUS_META[status]}
                tasks={board?.[status] || []}
                onOpenTask={openTask}
              />
            ))}
          </div>
        </DndContext>
      </div>

      <TaskDetailDrawer
        task={selectedTask}
        allTasks={allTasks}
        onClose={() => setSelectedTask(null)}
        isUpdating={updateStatus.isPending}
        onUpdateStatus={async (payload) => {
          try {
            const updated = await updateStatus.mutateAsync(payload);
            setSelectedTask(updated);
          } catch (err) {
            setBanner(err.message);
            setTimeout(() => setBanner(null), 4000);
          }
        }}
      />
    </div>
  );
}

function ErrorState({ message }) {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="card max-w-sm text-center">
        <p className="font-display text-sm font-semibold text-status-blocked">Couldn't load the board</p>
        <p className="mt-2 text-sm text-text-muted">{message}</p>
      </div>
    </div>
  );
}
