import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { apiClient, setAuthFailureHandler, setAuthToken } from "../api/client";

const AuthContext = createContext(null);

const STORAGE_KEY = "aiwse:auth";

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    setAuthToken(auth?.token || null);
  }, [auth]);

  useEffect(() => {
    setAuthFailureHandler((error) => {
      if (error?.response?.status !== 401) {
        return;
      }

      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem("aiwse:simulation");
      setAuth(null);
    });

    return () => {
      setAuthFailureHandler(null);
    };
  }, []);

  const login = useCallback(async (studentId) => {
    const res = await apiClient.post("/api/dev/token", { student_id: studentId, role: "student" });
    const next = { token: res.data.access_token, studentId };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setAuth(next);
    return next;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem("aiwse:simulation");
    setAuth(null);
  }, []);

  return (
    <AuthContext.Provider value={{ auth, login, logout, isAuthenticated: Boolean(auth?.token) }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
