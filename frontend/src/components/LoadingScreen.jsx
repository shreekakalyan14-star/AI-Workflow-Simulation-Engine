import { motion } from "framer-motion";

const LINES = [
  "resolving internship brief...",
  "provisioning company...",
  "assigning manager...",
  "scoping project...",
  "splitting into sprints...",
  "writing tickets...",
];

export default function LoadingScreen({ label = "Generating your internship simulation" }) {
  return (
    <div className="flex h-full min-h-[60vh] items-center justify-center">
      <div className="w-full max-w-md rounded-lg border border-border bg-surface p-6 font-mono text-sm">
        <p className="mb-4 text-text-muted">{label}</p>
        <div className="space-y-2">
          {LINES.map((line, i) => (
            <motion.div
              key={line}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.35, duration: 0.3 }}
              className="flex items-center gap-2"
            >
              <span className="text-status-completed">✓</span>
              <span className="text-text-muted">{line}</span>
            </motion.div>
          ))}
        </div>
        <motion.div
          className="mt-4 h-1 w-full overflow-hidden rounded-full bg-surface-3"
        >
          <motion.div
            className="h-full bg-status-todo"
            initial={{ width: "0%" }}
            animate={{ width: "100%" }}
            transition={{ duration: LINES.length * 0.35 + 0.5, ease: "easeInOut" }}
          />
        </motion.div>
      </div>
    </div>
  );
}
