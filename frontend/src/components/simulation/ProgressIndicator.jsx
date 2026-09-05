import { motion } from "framer-motion";

export default function ProgressIndicator({ simulation, progress, scenario, currentTask }) {
  if (!simulation || !progress) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-surface border-b border-border"
    >
      {/* Main Progress Bar */}
      <div className="px-4 py-2">
        <div className="flex items-center justify-between gap-4 mb-2">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-display text-xs font-semibold uppercase tracking-wide text-text-faint">
                Overall Progress
              </span>
              <span className="font-mono text-lg font-semibold text-status-todo">
                {progress.overall_progress}%
              </span>
            </div>
            <div className="h-3 bg-surface-2 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${progress.overall_progress}%` }}
                className="h-full bg-gradient-to-r from-status-todo to-status-completed rounded-full"
                transition={{ duration: 0.8, ease: "easeOut" }}
              />
            </div>
          </div>
          
          <div className="flex items-center gap-6 shrink-0 hidden sm:flex">
            <div className="text-center">
              <p className="text-xs text-text-faint">Completed</p>
              <p className="font-mono text-xl font-semibold text-status-completed">
                {progress.completed_tasks} / {progress.total_tasks}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-text-faint">Remaining</p>
              <p className="font-mono text-xl font-semibold text-text-muted">
                {progress.remaining_tasks}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Scenario Progress Tabs */}
      {progress.scenarios && progress.scenarios.length > 0 && (
        <div className="px-4 pb-3 border-t border-border/50">
          <div className="flex items-center gap-2 overflow-x-auto pb-2">
            {progress.scenarios.map((sc) => (
              <ScenarioProgressTab
                key={sc.scenario_id}
                scenario={sc}
                isActive={scenario?.id === sc.scenario_id}
                isCompleted={sc.status === "completed"}
              />
            ))}
          </div>
        </div>
      )}

      {/* Current Task Indicator */}
      {currentTask && (
        <div className="px-4 py-2 bg-surface-2/50 border-t border-border/50">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-status-todo" />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-text-faint">Current Task</p>
              <p className="font-medium text-sm truncate">{currentTask.title}</p>
            </div>
            {currentTask.remaining_time && (
              <div className="text-right shrink-0">
                <p className="text-xs text-text-faint">Time Left</p>
                <p className={`font-mono text-sm ${currentTask.deadline_missed ? "text-status-blocked" : "text-status-todo"}`}>
                  {currentTask.remaining_time.formatted}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </motion.div>
  );
}

function ScenarioProgressTab({ scenario, isActive, isCompleted }) {
  const progressPct = scenario.total_tasks > 0 
    ? Math.round((scenario.completed_tasks / scenario.total_tasks) * 100) 
    : 0;

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className={`flex-shrink-0 px-3 py-2 rounded-lg border transition-all ${
        isActive 
          ? "border-status-todo bg-status-todo/5 text-text" 
          : isCompleted 
            ? "border-status-completed bg-status-completed/5 text-status-completed" 
            : "border-border bg-surface-2 text-text-muted"
      }`}
      style={{ minWidth: "140px" }}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="font-medium text-sm truncate">
          {scenario.title.length > 20 ? scenario.title.slice(0, 20) + "..." : scenario.title}
        </span>
        {isCompleted && (
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        )}
      </div>
      <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${progressPct}%` }}
          className={`h-full rounded-full ${
            isCompleted ? "bg-status-completed" : "bg-status-todo"
          }`}
          transition={{ duration: 0.5 }}
        />
      </div>
      <p className="text-xs mt-1">
        {scenario.completed_tasks} / {scenario.total_tasks} tasks
      </p>
    </motion.button>
  );
}