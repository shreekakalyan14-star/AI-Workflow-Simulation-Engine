export const STATUS_ORDER = ["backlog", "todo", "in_progress", "review", "blocked", "completed"];

export const STATUS_META = {
  backlog: { label: "Backlog", color: "var(--color-status-backlog)" },
  todo: { label: "To Do", color: "var(--color-status-todo)" },
  in_progress: { label: "In Progress", color: "var(--color-status-progress)" },
  review: { label: "Review", color: "var(--color-status-review)" },
  blocked: { label: "Blocked", color: "var(--color-status-blocked)" },
  completed: { label: "Completed", color: "var(--color-status-completed)" },
};

export const PRIORITY_META = {
  low: { label: "Low", color: "var(--color-priority-low)" },
  medium: { label: "Medium", color: "var(--color-priority-medium)" },
  high: { label: "High", color: "var(--color-priority-high)" },
  critical: { label: "Critical", color: "var(--color-priority-critical)" },
};

export function moodColor(score) {
  if (score >= 65) return "var(--color-mood-good)";
  if (score >= 40) return "var(--color-mood-ok)";
  return "var(--color-mood-bad)";
}

export function moodLabel(score) {
  if (score >= 65) return "satisfied";
  if (score >= 40) return "watching closely";
  return "unhappy";
}
