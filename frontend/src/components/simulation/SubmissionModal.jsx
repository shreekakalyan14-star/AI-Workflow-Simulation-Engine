import { useState } from "react";
import { motion } from "framer-motion";

/**
 * SubmissionModal - File upload and response submission for tasks.
 *
 * Props:
 *   task          - current task object
 *   onClose       - () => void - close the modal
 *   onSubmit      - (files, metadata) => Promise - submit handler
 *   isSubmitting  - boolean - loading state
 */
export default function SubmissionModal({ task, onClose, onSubmit, isSubmitting }) {
  const [files, setFiles] = useState([]);
  const [response, setResponse] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const maxFiles = 10;

  const addFiles = (nextFiles) => {
    if (!nextFiles?.length) {
      return;
    }

    setFiles((currentFiles) => {
      const existingKeys = new Set(
        currentFiles.map((file) => `${file.name}-${file.size}-${file.lastModified}`)
      );

      const uniqueFiles = nextFiles.filter((file) => {
        const key = `${file.name}-${file.size}-${file.lastModified}`;
        return !existingKeys.has(key);
      });

      return [...currentFiles, ...uniqueFiles].slice(0, maxFiles);
    });
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files) {
      addFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files));
      e.target.value = "";
    }
  };

  const removeFile = (index) => {
    setFiles((currentFiles) => currentFiles.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const result = await onSubmit(files, { response: response.trim() });
    if (result) {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div
        className="fixed inset-0 bg-black/50"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="bg-surface border border-border rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col"
      >
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold">
            Submit Task: {task?.title || "Current Task"}
          </h2>
          <button onClick={onClose} className="btn-ghost">
            Close
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-muted mb-2">
              Response / Notes (optional)
            </label>
            <textarea
              className="input w-full min-h-[100px]"
              placeholder="Describe your approach, any challenges faced, or notes for the reviewer..."
              value={response}
              onChange={(e) => setResponse(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-muted mb-2">
              Attach Files (code, documents, screenshots, etc.)
            </label>
            <div
              className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
                dragActive ? "border-status-todo bg-status-todo/5" : "border-border"
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                type="file"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                id="file-upload"
                accept=".py,.js,.ts,.jsx,.tsx,.java,.cpp,.cs,.go,.rs,.json,.yaml,.yml,.md,.txt,.pdf,.zip,.png,.jpg,.jpeg"
              />
              <label htmlFor="file-upload" className="cursor-pointer">
                <svg
                  className="w-12 h-12 mx-auto text-text-faint mb-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                <p className="text-text-muted">
                  Drag & drop files here, or{" "}
                  <span className="text-status-todo underline">click to browse</span>
                </p>
                <p className="text-xs text-text-faint mt-1">Max 10 files - 10MB each</p>
              </label>
            </div>

            {files.length > 0 && (
              <div className="mt-3 space-y-2">
                {files.map((file, index) => (
                  <div
                    key={`${file.name}-${file.size}-${file.lastModified}-${index}`}
                    className="flex items-center justify-between p-2 bg-surface-2 rounded border border-border"
                  >
                    <div className="flex items-center gap-2">
                      <svg
                        className="w-5 h-5 text-text-muted"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M15.172 7l-6.586 6.586a.5.5 0 00.707.708L13 11.707l5.586 5.586a.5.5 0 00.707-.708L14.414 7H9.414a1 1 0 01-.707-1.707L13.293 3.293A1 1 0 0114 2h5a2 2 0 012 2v6h-2z"
                        />
                      </svg>
                      <span className="text-sm truncate max-w-[200px]">{file.name}</span>
                    </div>
                    <span className="text-xs text-text-faint">
                      {(file.size / 1024).toFixed(1)} KB
                    </span>
                    <button
                      type="button"
                      onClick={() => removeFile(index)}
                      className="text-text-faint hover:text-status-blocked p-1"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="pt-4 border-t border-border flex gap-3 justify-end">
            <button type="button" onClick={onClose} className="btn-ghost" disabled={isSubmitting}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? "Submitting..." : "Submit for Review"}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
