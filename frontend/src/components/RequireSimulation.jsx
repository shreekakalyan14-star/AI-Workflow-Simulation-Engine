import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useSimulation } from "../context/SimulationContext";

export default function RequireSimulation({ children }) {
  const { isAuthenticated } = useAuth();
  const { simulation } = useSimulation();

  if (!isAuthenticated || !simulation?.companyId || !simulation?.projectId) {
    return <Navigate to="/" replace />;
  }

  return children;
}
