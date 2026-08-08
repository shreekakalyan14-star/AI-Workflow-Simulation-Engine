import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const apiClient = axios.create({ baseURL });

let currentToken = null;

/** Called by AuthContext whenever the token changes. */
export function setAuthToken(token) {
  currentToken = token;
}

apiClient.interceptors.request.use((config) => {
  if (currentToken) {
    config.headers.Authorization = `Bearer ${currentToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Surface a consistent, readable message for the UI layer.
    const detail =
      error?.response?.data?.detail ||
      error?.message ||
      "Unexpected error talking to the simulation engine.";
    return Promise.reject(new Error(typeof detail === "string" ? detail : JSON.stringify(detail)));
  }
);
