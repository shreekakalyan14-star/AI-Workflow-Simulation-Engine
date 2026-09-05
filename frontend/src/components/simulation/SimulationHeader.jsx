import { motion } from "framer-motion";

export default function SimulationHeader({ simulation, progress }) {
  if (!simulation) return null;

  const statusColors = {
    not_started: "text-text-faint",
    in_progress: "text-status-todo",
    completed: "text-status-completed",
    abandoned: "text-status-blocked",
  };

  const statusLabels = {
    not_started: "Not Started",
    in_progress: "In Progress",
    completed: "Completed",
    abandoned: "Abandoned",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center justify-between gap-4 p-4 bg-surface border-b border-border"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="font-display text-lg font-semibold truncate">{simulation.title}</h1>
          <span
            className={`px-2 py-0.5 rounded text-xs font-mono uppercase tracking-wide ${statusColors[simulation.status]}`}
          >
            {statusLabels[simulation.status] || simulation.status}
          </span>
          <span className="px-2 py-0.5 rounded text-xs bg-surface-2 text-text-muted">
            {simulation.role}
          </span>
          <span className="px-2 py-0.5 rounded text-xs bg-surface-2 text-text-muted">
            {simulation.difficulty}
          </span>
        </div>
        <p className="mt-1 text-sm text-text-muted truncate">{simulation.description}</p>
      </div>

      <div className="flex items-center gap-4 shrink-0">
        {/* Timer/Progress */}
        <div className="text-right hidden sm:block">
          <p className="text-xs text-text-faint">Overall Progress</p>
          <p className="font-mono text-xl font-semibold text-status-todo">{progress?.overall_progress || 0}%</p>
        </div>
        
        {/* Time elapsed */}
        {simulation.started_at && (
          <div className="text-right hidden md:block">
            <p className="text-xs text-text-faint">Time Elapsed</p>
            <p className="font-mono text-lg font-semibold" id="elapsed-timer">
              {formatElapsedTime(simulation.started_at)}
            </p>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function formatElapsedTime(startedAt) {
  const start = new Date(startedAt);
  const now = new Date();
  const diffMs = now - start;
  
  const hours = Math.floor(diffMs / 3600000);
  const minutes = Math.floor((diffMs % 3600000) / 60000);
  const seconds = Math.floor((diffMs % 60000) / 1000);
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  return `${minutes}m ${seconds}s`;
}

// Add a timer effect
import { useEffect, useState } from "react";

export function SimulationHeaderWithTimer({ simulation, progress }) {
  const [elapsed, setElapsed] = useState("");

  useEffect(() => {
    if (!simulation?.started_at) {
      setElapsed("");
      return;
    }
    
    const updateElapsed = () => {
      const start = new Date(simulation.started_at);
      const now = new Date();
      const diffMs = now - start;
      
      const hours = Math.floor(diffMs / 3600000);
      const minutes = Math.floor((diffMs % 3600000) / 60000);
      const seconds = Math.floor((diffMs % 60000) / 1000);
      
      if (hours > 0) {
        setElapsed(`${hours}h ${minutes}m ${seconds}s`);
      } else {
        setElapsed(`${minutes}m ${seconds}s`);
      }
    };
    
    updateElapsed();
    const interval = setInterval(updateElapsed, 1000);
    return () => clearInterval(interval);
  }, [simulation?.started_at]);

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center justify-between gap-4 p-4 bg-surface border-b border-border"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="font-display text-lg font-semibold truncate">{simulation?.title}</h1>
          <span
            className={`px-2 py-0.5 rounded text-xs font-mono uppercase tracking-wide ${statusColors[simulation?.status]}`}
          >
            {statusLabels[simulation?.status] || simulation?.status}
          </span>
          <span className="px-2 py-0.5 rounded text-xs bg-surface-2 text-text-muted">
            {simulation?.role}
          </span>
          <span className="px-2 py-0.5 rounded text-xs bg-surface-2 text-text-muted">
            {simulation?.difficulty}
          </span>
        </div>
        <p className="mt-1 text-sm text-text-muted truncate">{simulation?.description}</p>
      </div>

      <div className="flex items-center gap-4 shrink-0">
        <div className="text-right hidden sm:block">
          <p className="text-xs text-text-faint">Overall Progress</p>
          <p className="font-mono text-xl font-semibold text-status-todo">{progress?.overall_progress || 0}%</p>
        </div>
        
        {simulation?.started_at && (
          <div className="text-right hidden md:block">
            <p className="text-xs text-text-faint">Time Elapsed</p>
            <p className="font-mono text-lg font-semibold">{elapsed || formatElapsedTime(simulation.started_at)}</p>
          </div>
        )}
      </div>
    </motion.div>
  );
}

const statusColors = {
  not_started: "text-text-faint",
  in_progress: "text-status-todo",
  completed: "text-status-completed",
  abandoned: "text-status-blocked",
};

const statusLabels = {
  not_started: "Not Started",
  in_progress: "In Progress",
  completed: "Completed",
  abandoned: "Abandoned",
};