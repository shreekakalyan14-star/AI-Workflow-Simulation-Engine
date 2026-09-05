import { useState, useRef, useEffect } from "react";

const DEFAULT_CODE = `// Write your solution here
function solution() {
  // TODO: Implement
}
`;

const LANG_MAP = {
  coding: "javascript",
  debugging: "javascript",
  database: "sql",
  api_development: "javascript",
  testing: "javascript",
  documentation: "markdown",
  requirement_analysis: "markdown",
  design: "markdown",
  decision_making: "markdown",
};

export default function CodeEditor({ task, onCodeChange, initialCode }) {
  const [code, setCode] = useState(initialCode || DEFAULT_CODE);
  const [language] = useState(LANG_MAP[task?.task_type] || "javascript");
  const [fontSize, setFontSize] = useState(14);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (onCodeChange) onCodeChange(code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [code]);

  const handleKeyDown = (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const start = e.target.selectionStart;
      const end = e.target.selectionEnd;
      const newCode = code.substring(0, start) + "  " + code.substring(end);
      setCode(newCode);
      setTimeout(() => {
        e.target.selectionStart = e.target.selectionEnd = start + 2;
      }, 0);
    }
  };

  const lines = code.split("\n");

  return (
    <div className="card flex flex-col overflow-hidden" style={{ height: "100%" }}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface-2/50">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wide bg-status-todo/10 text-status-todo">
            {language}
          </span>
          <span className="text-xs text-text-faint">{lines.length} lines</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFontSize((s) => Math.max(10, s - 2))}
            className="w-6 h-6 flex items-center justify-center rounded text-text-faint hover:bg-surface-2"
          >
            A-
          </button>
          <span className="text-[10px] text-text-faint font-mono">{fontSize}px</span>
          <button
            onClick={() => setFontSize((s) => Math.min(24, s + 2))}
            className="w-6 h-6 flex items-center justify-center rounded text-text-faint hover:bg-surface-2"
          >
            A+
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-auto bg-[#1e1e1e]">
        <div className="py-3 px-2 text-right select-none bg-[#1a1a2e] border-r border-border/20">
          {lines.map((_, i) => (
            <div key={i} className="text-[11px] font-mono leading-[1.6] text-text-faint/50">
              {i + 1}
            </div>
          ))}
        </div>
        <textarea
          ref={textareaRef}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          className="flex-1 bg-transparent text-[#d4d4d4] p-3 font-mono resize-none outline-none leading-[1.6]"
          style={{ fontSize: `${fontSize}px`, tabSize: 2, minHeight: "100%" }}
        />
      </div>
    </div>
  );
}
