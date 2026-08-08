import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";

export function useGenerateSimulation() {
  return useMutation({
    mutationFn: async (payload) => {
      const res = await apiClient.post("/api/generate", payload);
      return res.data;
    },
  });
}

export function useCompany(companyId) {
  return useQuery({
    queryKey: ["company", companyId],
    queryFn: async () => (await apiClient.get(`/api/companies/${companyId}`)).data,
    enabled: Boolean(companyId),
  });
}

export function useManager(companyId) {
  return useQuery({
    queryKey: ["manager", companyId],
    queryFn: async () => (await apiClient.get(`/api/companies/${companyId}/manager`)).data,
    enabled: Boolean(companyId),
  });
}

export function useProject(projectId) {
  return useQuery({
    queryKey: ["project", projectId],
    queryFn: async () => (await apiClient.get(`/api/projects/${projectId}`)).data,
    enabled: Boolean(projectId),
  });
}

export function useProjectState(projectId) {
  return useQuery({
    queryKey: ["projectState", projectId],
    queryFn: async () => (await apiClient.get(`/api/projects/${projectId}/state`)).data,
    enabled: Boolean(projectId),
    refetchInterval: 5000,
  });
}

export function useSprints(projectId) {
  return useQuery({
    queryKey: ["sprints", projectId],
    queryFn: async () => (await apiClient.get(`/api/projects/${projectId}/sprints`)).data,
    enabled: Boolean(projectId),
  });
}

export function useBoard(projectId) {
  return useQuery({
    queryKey: ["board", projectId],
    queryFn: async () => (await apiClient.get(`/api/projects/${projectId}/board`)).data,
    enabled: Boolean(projectId),
    refetchInterval: 8000,
  });
}

export function useUpdateTaskStatus(projectId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ taskId, ...body }) => {
      const res = await apiClient.patch(`/api/tasks/${taskId}/status`, body);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["board", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projectState", projectId] });
      queryClient.invalidateQueries({ queryKey: ["events", projectId] });
      queryClient.invalidateQueries({ queryKey: ["timeline", projectId] });
    },
  });
}

export function useReportBug(projectId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ taskId, description }) => {
      const res = await apiClient.post(`/api/tasks/${taskId}/report-bug`, { description });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projectState", projectId] });
      queryClient.invalidateQueries({ queryKey: ["events", projectId] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useTeam(companyId) {
  return useQuery({
    queryKey: ["team", companyId],
    queryFn: async () => (await apiClient.get(`/api/companies/${companyId}/team`)).data,
    enabled: Boolean(companyId),
  });
}

export function useManagerChat(companyId) {
  const queryClient = useQueryClient();
  const history = useQuery({
    queryKey: ["chat", "manager", companyId],
    queryFn: async () => (await apiClient.get(`/api/companies/${companyId}/chat/manager`)).data,
    enabled: Boolean(companyId),
  });
  const send = useMutation({
    mutationFn: async (content) =>
      (await apiClient.post(`/api/companies/${companyId}/chat/manager`, { content })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat", "manager", companyId] }),
  });
  return { history, send };
}

export function useTeamChat(companyId, teammateId) {
  const queryClient = useQueryClient();
  const history = useQuery({
    queryKey: ["chat", "team", companyId, teammateId],
    queryFn: async () => (await apiClient.get(`/api/companies/${companyId}/chat/team/${teammateId}`)).data,
    enabled: Boolean(companyId) && Boolean(teammateId),
  });
  const send = useMutation({
    mutationFn: async (content) =>
      (await apiClient.post(`/api/companies/${companyId}/chat/team/${teammateId}`, { content })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat", "team", companyId, teammateId] }),
  });
  return { history, send };
}

export function useNotifications(companyId) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["notifications", companyId],
    queryFn: async () => (await apiClient.get(`/api/companies/${companyId}/notifications`)).data,
    enabled: Boolean(companyId),
    refetchInterval: 10000,
  });
  const markRead = useMutation({
    mutationFn: async (notificationId) =>
      (await apiClient.patch(`/api/companies/${companyId}/notifications/${notificationId}/read`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications", companyId] }),
  });
  return { ...query, markRead };
}

export function useEvents(projectId) {
  return useQuery({
    queryKey: ["events", projectId],
    queryFn: async () => (await apiClient.get(`/api/projects/${projectId}/events`)).data,
    enabled: Boolean(projectId),
  });
}

export function useActivity(companyId) {
  return useQuery({
    queryKey: ["activity", companyId],
    queryFn: async () => (await apiClient.get(`/api/companies/${companyId}/activity`)).data,
    enabled: Boolean(companyId),
  });
}

export function useMeetings(projectId) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["meetings", projectId],
    queryFn: async () => (await apiClient.get(`/api/projects/${projectId}/meetings`)).data,
    enabled: Boolean(projectId),
  });
  const complete = useMutation({
    mutationFn: async ({ meetingId, ...body }) =>
      (await apiClient.patch(`/api/projects/${projectId}/meetings/${meetingId}/complete`, body)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["meetings", projectId] }),
  });
  return { ...query, complete };
}

export function useTimeline(projectId) {
  return useQuery({
    queryKey: ["timeline", projectId],
    queryFn: async () => (await apiClient.get(`/api/projects/${projectId}/timeline`)).data,
    enabled: Boolean(projectId),
    refetchInterval: 8000,
  });
}
