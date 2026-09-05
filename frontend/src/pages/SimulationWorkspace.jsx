import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { useSimulation } from "../context/SimulationContext";
import { apiClient } from "../api/client";
import {
  useSimulation as useSimulationQuery,
  useCreateSimulation,
  useStartSimulation,
  useCurrentTask,
  useStartSimulationTask,
  useSubmitSimulationTask,
  useCompleteSimulationTask,
  useCurrentScenario,
  useSimulationProgress,
  useTaskEvents,
  useRespondToEvent,
} from "../hooks/useSimulationApi";
import { useCompany } from "../hooks/useApi";
import { useAuth } from "../context/AuthContext";
import LoadingScreen from "../components/LoadingScreen";
import ScenarioPanel from "../components/simulation/ScenarioPanel";
import TaskPanel from "../components/simulation/TaskPanel";
import WorkplaceEventPanel from "../components/simulation/WorkplaceEventPanel";
import ProgressIndicator from "../components/simulation/ProgressIndicator";
import SimulationChatPanel from "../components/simulation/SimulationChatPanel";

export default function SimulationWorkspace() {
  const { simulation, setSimulation, clearSimulation } = useSimulation();
  const simulationId = simulation?.id;
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Fetch simulation data
  const { data: simData, isLoading: simLoading } = useSimulationQuery(simulationId);
  const { data: scenarioData, isLoading: scenarioLoading } = useCurrentScenario(simulationId);
  const { data: currentTaskData, isLoading: taskLoading, isError: taskError } = useCurrentTask(simulationId);
  const { data: progressData, isLoading: progressLoading } = useSimulationProgress(simulationId);
  
  // Fetch company for context
  const { data: company } = useCompany(simulation?.companyId);

  // Mutations
  const startSimulation = useStartSimulation(simulationId);
  const startTask = useStartSimulationTask(simulationId);
  const submitTask = useSubmitSimulationTask(simulationId);
  const completeTask = useCompleteSimulationTask(simulationId);
  
  // Events
  const { data: eventsData, isLoading: eventsLoading } = useTaskEvents(
    simulationId,
    currentTaskData?.task_id
  );
  const respondToEvent = useRespondToEvent(simulationId, currentTaskData?.task_id);

  // Local state
  const [showSubmissionModal, setShowSubmissionModal] = useState(false);
  const [simulationCompleted, setSimulationCompleted] = useState(false);

  // Check if simulation is completed
  useEffect(() => {
    if (simData?.status === "completed" || progressData?.overall_progress === 100) {
      setSimulationCompleted(true);
    }
  }, [simData, progressData]);

  // Handle simulation start
  const handleStartSimulation = async (overrideSimulationId) => {
    const idToUse = overrideSimulationId || simulationId;
    if (!idToUse) {
      alert("No simulation to start. Please create one first.");
      return;
    }
    try {
      await apiClient.post(`/api/simulations/${idToUse}/start`);
      setSimulation(prev => ({ ...prev, id: idToUse, status: "in_progress" }));
      // Invalidate all relevant queries so the workspace fetches fresh data
      queryClient.invalidateQueries({ queryKey: ["simulation", idToUse] });
      queryClient.invalidateQueries({ queryKey: ["currentTask", idToUse] });
      queryClient.invalidateQueries({ queryKey: ["currentScenario", idToUse] });
      queryClient.invalidateQueries({ queryKey: ["simulationProgress", idToUse] });
      queryClient.invalidateQueries({ queryKey: ["board", simulation?.projectId] });
      // Navigate to the simulation workspace to show the current task
      navigate("/simulation");
    } catch (error) {
      console.error("Failed to start simulation:", error);
      // Even if start fails, still navigate to simulation workspace
      setSimulation(prev => ({ ...prev, id: idToUse, status: "in_progress" }));
      queryClient.invalidateQueries({ queryKey: ["simulation", idToUse] });
      queryClient.invalidateQueries({ queryKey: ["currentTask", idToUse] });
      navigate("/simulation");
    }
  };

  // Handle task start
  const handleStartTask = async (taskId) => {
    try {
      await startTask.mutateAsync(taskId);
    } catch (error) {
      console.error("Failed to start task:", error);
      alert("Failed to start task. Please try again.");
    }
  };

  // Handle task submission
  const handleSubmitTask = async (files, metadata) => {
    try {
      const result = await submitTask.mutateAsync({ taskId: currentTaskData.task_id, files, metadata });
      setShowSubmissionModal(false);
      // Invalidate queries to fetch next task
      queryClient.invalidateQueries({ queryKey: ["currentTask", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["currentScenario", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["simulationProgress", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["simulation", simulationId] });
      // Check if simulation completed
      if (result.simulation_completed || result.status === "simulation_completed") {
        setSimulationCompleted(true);
      }
      return result;
    } catch (error) {
      console.error("Failed to submit task:", error);
      alert("Failed to submit task. Please try again.");
    }
  };

  // Handle task completion (by evaluator)
  const handleCompleteTask = async () => {
    try {
      const result = await completeTask.mutateAsync(currentTaskData.task_id);
      if (result.status === "simulation_completed") {
        setSimulationCompleted(true);
      }
    } catch (error) {
      console.error("Failed to complete task:", error);
      alert("Failed to complete task. Please try again.");
    }
  };

  // Handle event response
  const handleEventResponse = async (eventId, response) => {
    try {
      await respondToEvent.mutateAsync({ eventId, response });
    } catch (error) {
      console.error("Failed to respond to event:", error);
      alert("Failed to record response. Please try again.");
    }
  };

  // If no simulation selected, show selection screen
  if (!simulationId) {
    return <SimulationSelectionScreen onStartSimulation={handleStartSimulation} />;
  }

  // Show loading while fetching
  if (simLoading || scenarioLoading || taskLoading || progressLoading) {
    return <LoadingScreen label="Loading simulation workspace" />;
  }

  const sim = simData;
  const scenario = scenarioData;
  const currentTask = currentTaskData;
  const progress = progressData;
  const events = eventsData?.events || [];
  const activeEvent = events.find(e => e.status === "pending" || e.status === "acknowledged");

  // Simulation completed view
  if (simulationCompleted || sim?.status === "completed") {
    return (
      <SimulationCompletionScreen
        simulation={sim}
        progress={progress}
        company={company}
        onNewSimulation={() => {
          clearSimulation();
          setSimulationCompleted(false);
        }}
      />
    );
  }

  // Simulation not yet started — show the start screen
  if (sim?.status === "not_started") {
    return <SimulationSelectionScreen onStartSimulation={handleStartSimulation} />;
  }

  // No active task — determine the correct state from backend data
  if (!currentTask) {
    // If simulation is completed, show completion screen
    if (sim?.status === "completed" || simulationCompleted || progressData?.overall_progress === 100) {
      return (
        <SimulationCompletionScreen
          simulation={sim}
          progress={progress}
          company={company}
          onNewSimulation={() => {
            clearSimulation();
            setSimulationCompleted(false);
          }}
        />
      );
    }

    // If backend confirms scenario is completed, show scenario-complete message
    if (scenario?.status === "completed") {
      return (
        <div className="mx-auto max-w-6xl p-6 text-center">
          <div className="card p-8 max-w-md mx-auto">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-status-completed/10 flex items-center justify-center">
              <svg className="w-8 h-8 text-status-completed" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="font-display text-xl font-semibold mb-2">Scenario Complete!</h2>
            <p className="text-text-muted mb-4">
              All tasks in this scenario have been completed. Preparing next scenario...
            </p>
            <div className="animate-pulse text-text-faint text-sm">Loading next task...</div>
          </div>
        </div>
      );
    }

    // Task fetch returned error (404 = no active task) — show retry state
    if (taskError && !taskLoading) {
      return (
        <div className="mx-auto max-w-6xl p-6 text-center">
          <div className="card p-8 max-w-md mx-auto">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-status-pending/10 flex items-center justify-center">
              <svg className="w-8 h-8 text-status-pending" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            </div>
            <h2 className="font-display text-xl font-semibold mb-2">Waiting for Task</h2>
            <p className="text-text-muted mb-4">
              No active task is currently assigned. The simulation may be transitioning between tasks.
            </p>
            <button
              className="btn-primary"
              onClick={() => queryClient.invalidateQueries({ queryKey: ["currentTask", simulationId] })}
            >
              Retry
            </button>
          </div>
        </div>
      );
    }

    // Scenario is still active but no task is assigned yet — show loading state
    // This can happen temporarily during task transitions
    return (
      <div className="mx-auto max-w-6xl p-6 text-center">
        <div className="card p-8 max-w-md mx-auto">
          <div className="animate-pulse text-text-faint text-sm">Loading next task...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl p-4 space-y-4 h-[calc(100vh-80px)] overflow-hidden flex flex-col">
      {/* Progress Bar at top */}
      <ProgressIndicator
        simulation={sim}
        progress={progress}
        scenario={scenario}
        currentTask={currentTask}
      />

      <div className="flex-1 flex overflow-hidden space-x-4">
        {/* Left Panel: Scenario Context */}
        <div className="w-96 flex-shrink-0">
          <ScenarioPanel
            scenario={scenario}
            simulation={sim}
            progress={progress}
            company={company}
          />
        </div>

        {/* Center Panel: Current Task */}
        <div className="flex-1 min-w-0 overflow-y-auto">
          <TaskPanel
            task={currentTask}
            scenario={scenario}
            simulation={sim}
            onStart={handleStartTask}
            onSubmit={handleSubmitTask}
            showSubmissionModal={showSubmissionModal}
            setShowSubmissionModal={setShowSubmissionModal}
            isStarting={startTask.isPending}
            isSubmitting={submitTask.isPending}
            canStart={currentTask.status === "todo"}
            canSubmit={currentTask.status === "in_progress"}
          />
        </div>

        {/* Right Panel: Workplace Events + Chat */}
        <div className="w-80 flex-shrink-0 flex flex-col space-y-4 overflow-hidden">
          <div className="flex-1 min-h-0">
            <WorkplaceEventPanel
              events={events}
              activeEvent={activeEvent}
              currentTask={currentTask}
              onRespond={handleEventResponse}
              isResponding={respondToEvent.isPending}
            />
          </div>
          <div className="h-64 flex-shrink-0">
            <SimulationChatPanel companyId={simulation?.companyId} />
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Simulation selection/start screen
 */
function SimulationSelectionScreen({ onStartSimulation }) {
  const { simulation, setSimulation } = useSimulation();
  const { auth } = useAuth();
  const createSimulation = useCreateSimulation();
  const [creating, setCreating] = useState(false);

  // If context has a simulation ID, we already have a simulation
  const hasSimulation = Boolean(simulation?.id);

  // If context only has companyId/projectId, create the simulation
  const handleCreateAndStart = async () => {
    if (!simulation?.companyId || !simulation?.projectId) return;
    setCreating(true);
    try {
      const result = await createSimulation.mutateAsync({
        companyId: simulation.companyId,
        projectId: simulation.projectId,
      });
      // Store full simulation data in context
      setSimulation({
        ...simulation,
        id: result.simulation_id,
        title: result.title,
        description: result.description,
        role: result.role,
        difficulty: result.difficulty,
        duration_weeks: result.duration_weeks,
        status: result.status,
      });
      // Now start it — pass the new ID directly since context update is async
      onStartSimulation(result.simulation_id);
    } catch (err) {
      console.error("Failed to create simulation:", err);
      alert("Failed to create simulation. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  if (hasSimulation) {
    return (
      <div className="mx-auto max-w-3xl p-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="card p-8"
        >
          <h1 className="font-display text-2xl font-semibold mb-4">
            Ready to Start Internship
          </h1>
          <p className="text-text-muted mb-6">
            You're about to begin your <strong>{simulation.role || "Internship"}</strong> simulation.
            This will take you through realistic workplace scenarios with tasks, deadlines, and unexpected events.
          </p>
          
          <div className="space-y-3 text-left mb-6">
            <div className="p-3 bg-surface-2 rounded">
              <p className="font-medium">{simulation.title}</p>
              <p className="text-sm text-text-muted">{simulation.description}</p>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <span>Role: <span className="font-medium">{simulation.role}</span></span>
              <span>Difficulty: <span className="font-medium capitalize">{simulation.difficulty}</span></span>
              <span>Duration: <span className="font-medium">{simulation.duration_weeks} weeks</span></span>
              <span>Tasks: <span className="font-medium">{simulation.total_tasks || "?"}</span></span>
            </div>
          </div>
          
          <button
            className="btn-primary w-full py-3 text-lg"
            onClick={() => onStartSimulation(simulation.id)}
            disabled={simulation.status !== "not_started"}
          >
            Start Internship Simulation
          </button>
        </motion.div>
      </div>
    );
  }

  // No simulation in context - show creation flow
  return (
    <div className="mx-auto max-w-3xl p-6 text-center">
      <div className="card p-8">
        <h1 className="font-display text-2xl font-semibold mb-4">No Active Simulation</h1>
        <p className="text-text-muted mb-6">
          Complete the onboarding process to generate your internship simulation.
        </p>
        {!simulation?.companyId ? (
          <a href="/" className="btn-primary">Go to Onboarding</a>
        ) : (
          <button
            className="btn-primary w-full py-3"
            onClick={handleCreateAndStart}
            disabled={creating || createSimulation.isPending}
          >
            {creating || createSimulation.isPending ? "Creating Simulation..." : "Create & Start Simulation"}
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Simulation completion screen
 */
function SimulationCompletionScreen({ simulation, progress, company, onNewSimulation }) {
  const durationMinutes = simulation?.started_at && simulation?.completed_at
    ? Math.round((new Date(simulation.completed_at) - new Date(simulation.started_at)) / 60000)
    : 0;

  return (
    <div className="mx-auto max-w-3xl p-6">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="card p-8 text-center"
      >
        <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-status-completed/10 flex items-center justify-center">
          <svg className="w-10 h-10 text-status-completed" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        
        <h1 className="font-display text-3xl font-semibold mb-2">Internship Completed!</h1>
        <p className="text-text-muted mb-6">
          Congratulations! You've successfully completed your <strong>{simulation?.role}</strong> internship simulation.
        </p>

        <div className="grid grid-cols-2 gap-4 mb-6 p-4 bg-surface-2 rounded">
          <div>
            <p className="text-sm text-text-faint">Total Duration</p>
            <p className="font-mono text-2xl font-semibold">{durationMinutes} minutes</p>
          </div>
          <div>
            <p className="text-sm text-text-faint">Tasks Completed</p>
            <p className="font-mono text-2xl font-semibold">
              {progress?.completed_tasks || 0} / {progress?.total_tasks || 0}
            </p>
          </div>
          <div>
            <p className="text-sm text-text-faint">Progress</p>
            <p className="font-mono text-2xl font-semibold">{progress?.overall_progress || 100}%</p>
          </div>
          <div>
            <p className="text-sm text-text-faint">Scenarios</p>
            <p className="font-mono text-2xl font-semibold">{progress?.scenarios?.length || 0}</p>
          </div>
        </div>

        <div className="space-y-3">
          <button className="btn-primary w-full py-3" onClick={onNewSimulation}>
            Start New Simulation
          </button>
          <a href="/dashboard" className="btn-ghost w-full py-3 block">
            View Dashboard
          </a>
        </div>
      </motion.div>
    </div>
  );
}