import { useState } from "react";

const SAMPLE_ORIGINAL = `// Original code
function calculateTotal(items) {
  let total = 0;
  for (let i = 0; i < items.length; i++) {
    total += items[i].price;
  }
  return total;
}`;

const SAMPLE_CHANGES = `// Updated code
function calculateTotal(items) {
  return items.reduce((sum, item) => sum + item.price, 0);
}`;

function computeDiff(original, updated) {
  const origLines = original.split("\n");
  const updLines = updated.split("\n");
  const result = [];
  let oi = 0;
  let ui = 0;

  while (oi < origLines.length || ui < updLines.length) {
    if (oi < origLines.length && ui < updLines.length) {
      if (origLines[oi] === updLines[ui]) {
        result.push({ type: "same", orig: origLines[oi], upd: updLines[ui], origNum: oi + 1, updNum: ui + 1 });
        oi++;
        ui++;
      } else {
        let foundInUpd = -1;
        for (let k = ui + 1; k < Math.min(ui + 10, updLines.length); k++) {
          if (updLines[k] === origLines[oi]) { foundInUpd = k; break; }
        }
        let foundInOrig = -1;
        for (let k = oi + 1; k < Math.min(oi + 10, origLines.length); k++) {
          if (origLines[k] === updLines[ui]) { foundInOrig = k; break; }
        }
        if (foundInUpd === -1 && foundInOrig === -1) {
          result.push({ type: "changed", orig: origLines[oi], upd: updLines[ui], origNum: oi + 1, updNum: ui + 1 });
          oi++;
          ui++;
        } else if (foundInOrig !== -1 && (foundInUpd === -1 || foundInOrig - oi <= foundInUpd - ui)) {
          while (ui < foundInUpd) {
            result.push({ type: "added", orig: null, upd: updLines[ui], updNum: ui + 1 });
            ui++;
          }
        } else {
          while (oi < foundInUpd) {
            result.push({ type: "removed", orig: origLines[oi], upd: null, origNum: oi + 1 });
            oi++;
          }
        }
      }
    } else if (oi < origLines.length) {
      result.push({ type: "removed", orig: origLines[oi], upd: null, origNum: oi + 1 });
      oi++;
    } else {
      result.push({ type: "added", orig: null, upd: updLines[ui], updNum: ui + 1 });
      ui++;
    }
  }
  return result;
}

export default function DiffViewer({ original, updated }) {
  const [origText, setOrigText] = useState(original || SAMPLE_ORIGINAL);
  const [updText, setUpdText] = useState(updated || SAMPLE_CHANGES);
  const diff = computeDiff(origText, updText);

  const stats = diff.reduce((acc, d) => {
    if (d.type === "removed") acc.removed++;
    if (d.type === "added") acc.added++;
    if (d.type === "changed") { acc.removed++; acc.added++; }
    return acc;
  }, { added: 0, removed: 0 });

  return (
    <div className="card flex flex-col overflow-hidden" style={{ height: "100%" }}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface-2/50">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-text">Diff Viewer</span>
          <span className="text-[10px] text-status-completed">+{stats.added}</span>
          <span className="text-[10px] text-status-blocked">-{stats.removed}</span>
        </div>
        <div className="flex gap-2 text-[10px]">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-status-blocked/40 inline-block" /> Removed</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-status-completed/40 inline-block" /> Added</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-surface-2 inline-block" /> Unchanged</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-[#1e1e1e] text-[12px] font-mono">
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-[10px] text-text-faint border-b border-border/20">
              <th className="w-10 px-2 py-1 text-right">#</th>
              <th className="px-2 py-1 text-left w-[45%]">Original</th>
              <th className="w-10 px-2 py-1 text-right">#</th>
              <th className="px-2 py-1 text-left w-[45%]">Updated</th>
            </tr>
          </thead>
          <tbody>
            {diff.map((d, i) => (
              <tr
                key={i}
                className={
                  d.type === "removed"
                    ? "bg-[#3d1f1f]"
                    : d.type === "added"
                      ? "bg-[#1f3d2a]"
                      : d.type === "changed"
                        ? "bg-[#3d3a1f]"
                        : ""
                }
              >
                <td className="px-2 py-0.5 text-right text-text-faint/40 select-none">{d.origNum || ""}</td>
                <td className="px-2 py-0.5 text-[#d4d4d4] whitespace-pre">{d.orig ?? ""}</td>
                <td className="px-2 py-0.5 text-right text-text-faint/40 select-none">{d.updNum || ""}</td>
                <td className="px-2 py-0.5 text-[#d4d4d4] whitespace-pre">{d.upd ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-border bg-surface-2/50 p-2 flex gap-2">
        <textarea
          value={origText}
          onChange={(e) => setOrigText(e.target.value)}
          placeholder="Original code..."
          className="flex-1 bg-[#1a1a2e] text-[#d4d4d4] p-2 rounded text-[11px] font-mono resize-none border border-border/20 outline-none"
          rows={3}
        />
        <textarea
          value={updText}
          onChange={(e) => setUpdText(e.target.value)}
          placeholder="Updated code..."
          className="flex-1 bg-[#1a1a2e] text-[#d4d4d4] p-2 rounded text-[11px] font-mono resize-none border border-border/20 outline-none"
          rows={3}
        />
      </div>
    </div>
  );
}
