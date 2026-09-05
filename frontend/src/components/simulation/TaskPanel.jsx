import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import SubmissionModal from "./SubmissionModal";
import CodeEditor from "./CodeEditor";
import DiffViewer from "./DiffViewer";

const CODING_TASK_TYPES = ["coding", "debugging", "database", "api_development", "testing"];
const CODE_REVIEW_TYPES = ["debugging"];

export default function TaskPanel({
  task,
  scenario,
  simulation,
  onStart,
  onSubmit,
  showSubmissionModal,
  setShowSubmissionModal,
  isStarting,
  isSubmitting,
  canStart,
  canSubmit,
}) {
  const [remainingTime, setRemainingTime] = useState(task?.remaining_time);
  const [deadlineMissed, setDeadlineMissed] = useState(task?.deadline_missed);

  useEffect(() => {
    if (!task?.started_at || !task?.deadline) {
      setRemainingTime(null);
      return;
    }

    const updateTimer = () => {
      const now = new Date();
      const deadline = new Date(task.deadline);
      const diffMs = deadline - now;

      if (diffMs <= 0) {
        setRemainingTime({
          seconds: 0,
          minutes: 0,
          hours: 0,
          formatted: "Expired",
        });
        setDeadlineMissed(true);
        return;
      }

      const hours = Math.floor(diffMs / 3600000);
      const minutes = Math.floor((diffMs % 3600000) / 60000);
      const seconds = Math.floor((diffMs % 60000) / 1000);

      let formatted = "";
      if (hours > 0) formatted = `${hours}h ${minutes}m ${seconds}s`;
      else if (minutes > 0) formatted = `${minutes}m ${seconds}s`;
      else formatted = `${seconds}s`;

      if (minutes < 5 && hours === 0) {
        formatted = `Warning: ${formatted}`;
      }

      setRemainingTime({
        seconds,
        minutes,
        hours,
        formatted,
      });
      setDeadlineMissed(false);
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [task?.deadline, task?.started_at]);

  useEffect(() => {
    if (task?.remaining_time) {
      setRemainingTime(task.remaining_time);
    }
    setDeadlineMissed(task?.deadline_missed || false);
  }, [task?.remaining_time, task?.deadline_missed]);

  if (!task) {
    return (
      <div className="card h-full flex items-center justify-center">
        <p className="text-text-muted">No active task</p>
      </div>
    );
  }

  const statusColors = {
    backlog: "bg-surface-2 text-text-muted",
    todo: "bg-status-todo/10 text-status-todo border-status-todo",
    in_progress: "bg-status-todo/10 text-status-todo border-status-todo",
    submitted: "bg-status-review/10 text-status-review border-status-review",
    under_review: "bg-status-review/10 text-status-review border-status-review",
    completed: "bg-status-completed/10 text-status-completed border-status-completed",
    changes_requested: "bg-status-blocked/10 text-status-blocked border-status-blocked",
    blocked: "bg-status-blocked/10 text-status-blocked border-status-blocked",
  };

  const statusLabels = {
    backlog: "Backlog",
    todo: "Ready to Start",
    in_progress: "In Progress",
    submitted: "Submitted",
    under_review: "Under Review",
    completed: "Completed",
    changes_requested: "Changes Requested",
    blocked: "Blocked",
  };

  return (
    <div className="card h-full flex flex-col overflow-hidden">
      <div className="p-4 border-b border-border bg-surface-2/50">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className={`px-2 py-0.5 rounded text-xs font-mono uppercase tracking-wide border ${statusColors[task.status]}`}>
                {statusLabels[task.status] || task.status}
              </span>
              {task.difficulty && (
                <span className="px-2 py-0.5 rounded text-xs bg-surface-2 text-text-muted">
                  {task.difficulty}
                </span>
              )}
              {task.task_type && (
                <span className="px-2 py-0.5 rounded text-xs bg-surface-2 text-text-muted">
                  {task.task_type.replace("_", " ")}
                </span>
              )}
            </div>
            <h2 className="font-display text-xl font-semibold">{task.title}</h2>
          </div>

          <div className="shrink-0">
            {remainingTime && (
              <div className="text-right">
                <p className="text-xs text-text-faint">Time Remaining</p>
                <p className={`font-mono text-2xl font-semibold tabular-nums ${deadlineMissed || (remainingTime.minutes < 5 && remainingTime.hours === 0) ? "text-status-blocked" : "text-status-todo"}`}>
                  {remainingTime.formatted}
                </p>
                {deadlineMissed && (
                  <p className="text-xs text-status-blocked">DEADLINE MISSED</p>
                )}
              </div>
            )}
            {!remainingTime && task.deadline && !task.started_at && (
              <div className="text-right">
                <p className="text-xs text-text-faint">Estimated Duration</p>
                <p className="font-mono text-xl font-semibold text-text-muted">{task.estimated_hours}h</p>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4 text-sm text-text-muted">
          {task.started_at && (
            <span>Started: {new Date(task.started_at).toLocaleTimeString()}</span>
          )}
          {task.deadline && (
            <span>Deadline: {new Date(task.deadline).toLocaleString()}</span>
          )}
          {task.estimated_hours && (
            <span>Est. {task.estimated_hours}h</span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <section>
          <h3 className="font-display text-xs font-semibold uppercase tracking-wide text-text-faint mb-3">
            Instructions
          </h3>
          <div className="prose prose-sm text-text-muted bg-surface-2/50 p-4 rounded">
            {task.instructions?.split("\n").map((paragraph, i) => (
              <p key={i} className="mb-2">{paragraph}</p>
            ))}
          </div>
        </section>

        {task.expected_output && task.expected_output.length > 0 && (
          <section>
            <h3 className="font-display text-xs font-semibold uppercase tracking-wide text-text-faint mb-3">
              Expected Output
            </h3>
            <ul className="space-y-2">
              {task.expected_output.map((criterion, i) => (
                <li key={i} className="flex items-start gap-2 p-3 bg-surface-2 rounded border border-border">
                  <svg className="w-5 h-5 text-status-todo shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="text-sm text-text">{criterion}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {scenario?.required_skills && scenario.required_skills.length > 0 && (
          <section>
            <h3 className="font-display text-xs font-semibold uppercase tracking-wide text-text-faint mb-3">
              Required Skills
            </h3>
            <div className="flex flex-wrap gap-1">
              {scenario.required_skills.map((skill, i) => (
                <span
                  key={i}
                  className="px-2 py-1 rounded bg-status-todo/10 text-status-todo text-sm border border-status-todo/20"
                >
                  {skill}
                </span>
              ))}
            </div>
          </section>
        )}

        <section>
          <h3 className="font-display text-xs font-semibold uppercase tracking-wide text-text-faint mb-3">
            Task Details
          </h3>
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-text-faint">Task ID</dt>
            <dd className="font-mono text-xs">{task.task_id?.slice(0, 8)}...</dd>
            <dt className="text-text-faint">Simulation</dt>
            <dd className="font-mono text-xs">{simulation?.title}</dd>
            <dt className="text-text-faint">Scenario</dt>
            <dd>{scenario?.title}</dd>
            <dt className="text-text-faint">Difficulty</dt>
            <dd className="capitalize">{task.difficulty}</dd>
            <dt className="text-text-faint">Type</dt>
            <dd>{task.task_type?.replace("_", " ")}</dd>
          </dl>
        </section>

        {CODING_TASK_TYPES.includes(task.task_type) && task.status !== "completed" && (
          <section className="min-h-[300px]">
            <h3 className="font-display text-xs font-semibold uppercase tracking-wide text-text-faint mb-3">
              {CODE_REVIEW_TYPES.includes(task.task_type) ? "Code Review" : "Code Editor"}
            </h3>
            {CODE_REVIEW_TYPES.includes(task.task_type) ? (
              <div className="h-[300px]">
                <DiffViewer />
              </div>
            ) : (
              <div className="h-[300px]">
                <CodeEditor task={task} onCodeChange={setEditorCode} />
              </div>
            )}
          </section>
        )}
      </div>

      <div className="p-4 border-t border-border bg-surface-2/50 space-y-3">
        {canStart && (
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onStart(task.task_id)}
            disabled={isStarting}
            className="btn-primary w-full py-3 text-lg flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9 9 4.03 9 9z" />
            </svg>
            {isStarting ? "Starting..." : "Start Task"}
          </motion.button>
        )}

        {canSubmit && (
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setShowSubmissionModal(true)}
            disabled={isSubmitting}
            className="btn-secondary w-full py-3 text-lg flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            {isSubmitting ? "Submitting..." : "Submit Work"}
          </motion.button>
        )}

        {task.status === "submitted" && (
          <div className="p-3 bg-status-review/10 border border-status-review/20 rounded text-center">
            <p className="text-sm text-status-review">
              Submitted for review. Waiting for evaluation...
            </p>
          </div>
        )}

        {task.status === "under_review" && (
          <div className="p-3 bg-status-review/10 border border-status-review/20 rounded text-center">
            <p className="text-sm text-status-review">
              Under evaluation by your manager...
            </p>
          </div>
        )}

        {task.status === "changes_requested" && (
          <div className="p-3 bg-status-blocked/10 border border-status-blocked/20 rounded">
            <p className="text-sm text-status-blocked font-medium">Changes Requested</p>
            <p className="text-xs text-text-muted mt-1">
              Your submission needs revisions. Review the feedback and resubmit.
            </p>
          </div>
        )}

        {task.status === "completed" && (
          <div className="p-3 bg-status-completed/10 border border-status-completed/20 rounded text-center">
            <p className="text-sm text-status-completed font-medium">
              Task Completed!
            </p>
            <p className="text-xs text-text-muted mt-1">
              Great work! Progressing to next task...
            </p>
          </div>
        )}

        {deadlineMissed && (
          <div className="p-3 bg-status-blocked/10 border border-status-blocked/20 rounded">
            <p className="text-sm text-status-blocked font-medium">Deadline Missed</p>
            <p className="text-xs text-text-muted mt-1">
              You can still submit your work, but it will be marked as late.
            </p>
          </div>
        )}
      </div>

      {showSubmissionModal && (
        <SubmissionModal
          task={task}
          onClose={() => setShowSubmissionModal(false)}
          onSubmit={onSubmit}
          isSubmitting={isSubmitting}
        />
      )}
    </div>
  );
}
