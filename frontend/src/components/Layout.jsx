import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useAuth } from "../context/AuthContext";
import { useSimulation } from "../context/SimulationContext";
import { useCompany, useManager, useProject, useProjectState } from "../hooks/useApi";
import { useCompanyWebSocket } from "../hooks/useCompanyWebSocket";
import StatusStrip from "./StatusStrip";
import NotificationsBell from "./NotificationsBell";

const TABS = [
  { to: "/simulation", label: "Simulation" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/board", label: "Board" },
  { to: "/chat", label: "Chat" },
  { to: "/timeline", label: "Timeline" },
];

export default function Layout() {
  const { auth, logout } = useAuth();
  const { simulation, clearSimulation } = useSimulation();
  const location = useLocation();
  const navigate = useNavigate();
  useCompanyWebSocket(simulation?.companyId);

  const { data: company } = useCompany(simulation?.companyId);
  const { data: manager } = useManager(simulation?.companyId);
  const { data: project } = useProject(simulation?.projectId);
  const { data: state } = useProjectState(simulation?.projectId);

  const handleNewSimulation = () => {
    clearSimulation();
    navigate("/");
  };

  return (
    <div className="flex h-screen flex-col bg-ink text-text">
      <StatusStrip
        company={company}
        project={project}
        sprintNumber={state?.current_sprint_number}
        managerScore={state?.manager_satisfaction}
        managerName={manager?.name}
      />

      <div className="flex items-center justify-between border-b border-border px-4">
        <nav className="flex gap-1">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                `px-3 py-2.5 text-sm font-display font-medium border-b-2 transition-colors ${
                  isActive
                    ? "border-status-todo text-text"
                    : "border-transparent text-text-muted hover:text-text"
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-3 py-2 text-xs text-text-faint font-mono">
          <NotificationsBell companyId={simulation?.companyId} />
          <span>{auth?.studentId}</span>
          <button
            onClick={handleNewSimulation}
            className="rounded border border-border px-2 py-1 text-text-muted hover:border-status-blocked hover:text-status-blocked transition-colors"
          >
            new simulation
          </button>
          <button onClick={logout} className="text-text-faint hover:text-text-muted transition-colors">
            sign out
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="h-full"
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
