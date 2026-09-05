import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";

/**
 * Simulation API hooks for Member 2 workflow
 */

export function useCreateSimulation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ companyId, projectId }) => {
      const res = await apiClient.post(`/api/simulations`, {
        company_id: companyId,
        project_id: projectId,
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["simulation"] });
    },
  });
}

export function useSimulation(simulationId) {
  return useQuery({
    queryKey: ["simulation", simulationId],
    queryFn: async () => (await apiClient.get(`/api/simulations/${simulationId}`)).data,
    enabled: Boolean(simulationId),
    refetchInterval: 10000,
  });
}

export function useStartSimulation(simulationId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post(`/api/simulations/${simulationId}/start`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["simulation", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["simulationProgress", simulationId] });
    },
  });
}

export function useSimulationProgress(simulationId) {
  return useQuery({
    queryKey: ["simulationProgress", simulationId],
    queryFn: async () => (await apiClient.get(`/api/simulations/${simulationId}/progress`)).data,
    enabled: Boolean(simulationId),
    refetchInterval: 10000,
  });
}

export function useCurrentScenario(simulationId) {
  return useQuery({
    queryKey: ["currentScenario", simulationId],
    queryFn: async () => (await apiClient.get(`/api/simulations/${simulationId}/scenario`)).data,
    enabled: Boolean(simulationId),
    refetchInterval: 10000,
  });
}

export function useSimulationTasks(simulationId) {
  return useQuery({
    queryKey: ["simulationTasks", simulationId],
    queryFn: async () => (await apiClient.get(`/api/simulations/${simulationId}/tasks`)).data,
    enabled: Boolean(simulationId),
    refetchInterval: 10000,
  });
}

export function useCurrentTask(simulationId) {
  return useQuery({
    queryKey: ["currentTask", simulationId],
    queryFn: async () => (await apiClient.get(`/api/simulations/${simulationId}/tasks/current`)).data,
    enabled: Boolean(simulationId),
    refetchInterval: 5000, // More frequent for timer
  });
}

export function useStartSimulationTask(simulationId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (taskId) => {
      const res = await apiClient.post(`/api/simulations/${simulationId}/tasks/${taskId}/start`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["currentTask", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["currentScenario", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["simulation", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["taskEvents", simulationId] });
    },
  });
}

export function useSubmitSimulationTask(simulationId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ taskId, files, metadata }) => {
      const formData = new FormData();
      if (files) {
        files.forEach((file) => formData.append("files", file));
      }
      if (metadata) {
        formData.append("metadata", JSON.stringify(metadata));
      }
      const res = await apiClient.post(`/api/simulations/${simulationId}/tasks/${taskId}/submit`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["currentTask", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["currentScenario", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["simulation", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["simulationProgress", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["taskEvents", simulationId] });
    },
  });
}

export function useCompleteSimulationTask(simulationId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (taskId) => {
      const res = await apiClient.post(`/api/simulations/${simulationId}/tasks/${taskId}/complete`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["currentTask", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["currentScenario", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["simulation", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["simulationProgress", simulationId] });
      queryClient.invalidateQueries({ queryKey: ["taskEvents", simulationId] });
    },
  });
}

export function useTaskEvents(simulationId, taskId) {
  return useQuery({
    queryKey: ["taskEvents", simulationId, taskId],
    queryFn: async () => (await apiClient.get(`/api/simulations/${simulationId}/tasks/${taskId}/events`)).data,
    enabled: Boolean(simulationId) && Boolean(taskId),
    refetchInterval: 5000,
  });
}

export function useRespondToEvent(simulationId, taskId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ eventId, response }) => {
      const formData = new URLSearchParams();
      formData.append("response", response);
      const res = await apiClient.post(
        `/api/simulations/${simulationId}/tasks/${taskId}/events/${eventId}/respond`,
        formData,
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["taskEvents", simulationId, taskId] });
      queryClient.invalidateQueries({ queryKey: ["currentTask", simulationId] });
    },
  });
}

export function useSimulationList() {
  // For now, get from the generated simulations (could be extended later)
  return useQuery({
    queryKey: ["simulationList"],
    queryFn: async () => {
      // This would need a new endpoint to list simulations for a student
      // For now, we'll use a local storage approach or the existing generation
      return [];
    },
    enabled: false,
  });
}