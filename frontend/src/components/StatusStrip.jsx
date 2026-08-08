import { moodColor, moodLabel } from "../lib/status";

/**
 * The one memorable, deliberate visual choice for this app: a status strip
 * styled like a terminal prompt / CI build status line, because the whole
 * product simulates being a software engineer — this is the artifact those
 * users see every day. Everything else in the UI stays quiet by comparison.
 */
export default function StatusStrip({ company, project, sprintNumber, managerScore, managerName }) {
  const path = company && project
    ? `${slugify(company.name)}/${slugify(project.title)}`
    : "no-active-simulation";

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-surface border-b border-border font-mono text-[13px] overflow-x-auto whitespace-nowrap">
      <span className="text-text-faint select-none">aiwse@sim</span>
      <span className="text-text-faint select-none">:</span>
      <span className="text-status-todo">~/{path}</span>
      {sprintNumber ? (
        <span className="text-text-muted">
          (sprint {sprintNumber}/4)
        </span>
      ) : null}
      <span className="cursor-blink text-text">▍</span>

      {managerScore != null && (
        <span className="ml-auto flex items-center gap-2 text-text-muted">
          <span
            className="relative inline-flex h-2 w-2 rounded-full pulse-dot"
            style={{ backgroundColor: moodColor(managerScore), color: moodColor(managerScore) }}
          />
          manager {managerName ? `${managerName} ` : ""}
          <span style={{ color: moodColor(managerScore) }}>{moodLabel(managerScore)}</span>
        </span>
      )}
    </div>
  );
}

function slugify(str) {
  return str
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}
