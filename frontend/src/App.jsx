import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import RequireSimulation from "./components/RequireSimulation";
import Onboarding from "./pages/Onboarding";
import Dashboard from "./pages/Dashboard";
import Board from "./pages/Board";
import Chat from "./pages/Chat";
import Timeline from "./pages/Timeline";
import SimulationWorkspace from "./pages/SimulationWorkspace";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Onboarding />} />
      <Route
        element={
          <RequireSimulation>
            <Layout />
          </RequireSimulation>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/board" element={<Board />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/timeline" element={<Timeline />} />
        <Route path="/simulation" element={<SimulationWorkspace />} />
      </Route>
    </Routes>
  );
}
