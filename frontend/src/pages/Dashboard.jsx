import { motion } from "framer-motion";
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from "recharts";
import { useSimulation } from "../context/SimulationContext";
import {
  useCompany, useManager, useProject, useProjectState, useSprints, useBoard,
} from "../hooks/useApi";
import { STATUS_ORDER, STATUS_META } from "../lib/status";
import LoadingScreen from "../components/LoadingScreen";

export default function Dashboard() {
  const { simulation } = useSimulation();
  const { data: company, isLoading: companyLoading } = useCompany(simulation?.companyId);
  const { data: manager } = useManager(simulation?.companyId);
  const { data: project, isLoading: projectLoading } = useProject(simulation?.projectId);
  const { data: state } = useProjectState(simulation?.projectId);
  const { data: sprints } = useSprints(simulation?.projectId);
  const { data: board } = useBoard(simulation?.projectId);

  if (companyLoading || projectLoading || !company || !project) {
    return <LoadingScreen label="Loading dashboard" />;
  }

  const totalTasks = board ? Object.values(board).reduce((sum, arr) => sum + arr.length, 0) : 0;
  const completedTasks = board?.completed?.length || 0;
  const completionPct = totalTasks ? Math.round((completedTasks / totalTasks) * 100) : 0;

  const distributionData = STATUS_ORDER.map((s) => ({
    name: STATUS_META[s].label,
    value: board?.[s]?.length || 0,
    color: STATUS_META[s].color,
  })).filter((d) => d.value > 0);

  const burndownData = (sprints || []).map((s) => ({
    name: `S${s.sprint_number}`,
    status: s.status,
  }));

  const donutData = [
    { name: "Completed", value: completedTasks, color: STATUS_META.completed.color },
    { name: "Remaining", value: totalTasks - completedTasks, color: "var(--color-surface-3)" },
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="font-display text-xl font-semibold">{project.title}</h1>
        <p className="text-sm text-text-muted">
          {company.name} · {company.industry} · {project.role}
        </p>
      </motion.div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <StatCard label="Completion" value={`${completionPct}%`} accent="var(--color-status-completed)" />
        <StatCard label="Tasks completed" value={`${completedTasks} / ${totalTasks}`} />
        <StatCard label="Missed deadlines" value={state?.missed_deadlines ?? 0} accent="var(--color-status-blocked)" />
        <StatCard label="Current sprint" value={`${state?.current_sprint_number ?? 1} / 4`} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="card">
          <h2 className="mb-3 font-display text-sm font-medium text-text-muted">Completion %</h2>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={donutData} dataKey="value" innerRadius={50} outerRadius={75} paddingAngle={2}>
                {donutData.map((d, i) => (
                  <Cell key={i} fill={d.color} stroke="none" />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
          <p className="text-center font-mono text-2xl font-semibold">{completionPct}%</p>
        </div>

        <div className="card">
          <h2 className="mb-3 font-display text-sm font-medium text-text-muted">Task distribution</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={distributionData} layout="vertical" margin={{ left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-soft)" horizontal={false} />
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" width={90} tick={{ fill: "var(--color-text-muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--color-surface-2)" }} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {distributionData.map((d, i) => (
                  <Cell key={i} fill={d.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h2 className="mb-3 font-display text-sm font-medium text-text-muted">Sprint progress</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={burndownData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-soft)" />
              <XAxis dataKey="name" tick={{ fill: "var(--color-text-muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => [v, "status"]} />
              <Line
                type="monotone"
                dataKey={(d) => (d.status === "completed" ? 2 : d.status === "active" ? 1 : 0)}
                stroke="var(--color-status-todo)"
                strokeWidth={2}
                dot={{ fill: "var(--color-status-todo)", r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="card">
          <h2 className="mb-2 font-display text-sm font-medium text-text-muted">Manager</h2>
          {manager ? (
            <div className="text-sm">
              <p className="font-medium">{manager.name}</p>
              <p className="text-text-muted">{manager.title} · {manager.personality.replace("_", " ")}</p>
              <p className="mt-2 text-text-faint">Satisfaction: {manager.satisfaction_score}/100</p>
            </div>
          ) : (
            <p className="text-sm text-text-faint">No manager assigned.</p>
          )}
        </div>

        <div className="card">
          <h2 className="mb-2 font-display text-sm font-medium text-text-muted">Objectives</h2>
          <ul className="list-inside list-disc space-y-1 text-sm text-text-muted">
            {project.objectives.map((o) => (
              <li key={o}>{o}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

const tooltipStyle = {
  background: "var(--color-surface-2)",
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  fontSize: 12,
  color: "var(--color-text)",
};

function StatCard({ label, value, accent }) {
  return (
    <div className="card">
      <p className="text-xs uppercase tracking-wide text-text-faint">{label}</p>
      <p
        className="mt-1 font-mono text-2xl font-semibold"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </p>
    </div>
  );
}
