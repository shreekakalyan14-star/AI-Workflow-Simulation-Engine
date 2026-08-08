import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../context/AuthContext";
import { useSimulation } from "../context/SimulationContext";
import { useGenerateSimulation } from "../hooks/useApi";
import LoadingScreen from "../components/LoadingScreen";

const COMPANY_TYPES = [
  ["startup", "Startup"],
  ["product_company", "Product Company"],
  ["mnc", "MNC"],
  ["healthcare", "Healthcare"],
  ["banking", "Banking"],
  ["ecommerce", "E-Commerce"],
  ["education", "Education"],
];

const DIFFICULTIES = [
  ["beginner", "Beginner"],
  ["intermediate", "Intermediate"],
  ["advanced", "Advanced"],
  ["expert", "Expert"],
];

const ROLE_SUGGESTIONS = [
  "Backend Developer",
  "Frontend Developer",
  "Full Stack Developer",
  "AI Engineer",
  "Data Engineer",
  "Cybersecurity",
  "DevOps Engineer",
  "Mobile Developer",
];

export default function Onboarding() {
  const { auth, login } = useAuth();
  const { setSimulation } = useSimulation();
  const navigate = useNavigate();

  const [studentId, setStudentId] = useState(auth?.studentId || "student_001");
  const [signInError, setSignInError] = useState(null);
  const [signingIn, setSigningIn] = useState(false);

  const [role, setRole] = useState("Backend Developer");
  const [stackInput, setStackInput] = useState("Python, FastAPI, PostgreSQL");
  const [difficulty, setDifficulty] = useState("intermediate");
  const [companyType, setCompanyType] = useState("startup");

  const generateMutation = useGenerateSimulation();

  const handleSignIn = async (e) => {
    e.preventDefault();
    setSignInError(null);
    setSigningIn(true);
    try {
      await login(studentId.trim());
    } catch (err) {
      setSignInError(err.message);
    } finally {
      setSigningIn(false);
    }
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    const technology_stack = stackInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const result = await generateMutation.mutateAsync({
      student_id: auth.studentId,
      role,
      technology_stack,
      difficulty,
      company_type: companyType,
    });

    setSimulation({ companyId: result.company_id, projectId: result.project_id });
    navigate("/dashboard");
  };

  if (generateMutation.isPending) {
    return <LoadingScreen />;
  }

  return (
    <div className="mx-auto flex h-full max-w-lg flex-col justify-center px-6 py-10">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <h1 className="font-display text-2xl font-semibold text-text">
          AI Workflow Simulation Engine
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Start an internship: pick a role, a stack, a difficulty, and a
          company type — the engine builds the rest.
        </p>

        {!auth?.token ? (
          <form onSubmit={handleSignIn} className="mt-8 space-y-3">
            <Field label="Student ID">
              <input
                className="input"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="student_001"
                required
              />
            </Field>
            <p className="text-xs text-text-faint">
              Dev-only sign-in — mints a test token locally. Module 1 issues
              real tokens once this is integrated into the full platform.
            </p>
            {signInError && <p className="text-xs text-status-blocked">{signInError}</p>}
            <button type="submit" className="btn-primary" disabled={signingIn}>
              {signingIn ? "Signing in..." : "Sign in"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleGenerate} className="mt-8 space-y-4">
            <Field label="Role">
              <input
                className="input"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                list="role-suggestions"
                required
              />
              <datalist id="role-suggestions">
                {ROLE_SUGGESTIONS.map((r) => (
                  <option key={r} value={r} />
                ))}
              </datalist>
            </Field>

            <Field label="Technology stack (comma-separated)">
              <input
                className="input"
                value={stackInput}
                onChange={(e) => setStackInput(e.target.value)}
                required
              />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Difficulty">
                <select
                  className="input"
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                >
                  {DIFFICULTIES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Company type">
                <select
                  className="input"
                  value={companyType}
                  onChange={(e) => setCompanyType(e.target.value)}
                >
                  {COMPANY_TYPES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            {generateMutation.isError && (
              <p className="text-xs text-status-blocked">{generateMutation.error.message}</p>
            )}

            <button type="submit" className="btn-primary w-full">
              Generate internship
            </button>
          </form>
        )}
      </motion.div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-faint">
        {label}
      </span>
      {children}
    </label>
  );
}
