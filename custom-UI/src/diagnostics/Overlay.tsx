import { useState } from "react";
import type { Diagnostic } from "./types.js";

export function DiagnosticsOverlay({
  diagnostics,
}: {
  diagnostics: Diagnostic[];
}): JSX.Element | null {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed || diagnostics.length === 0) return null;

  const errors = diagnostics.filter((d) => d.severity === "error").length;
  const warnings = diagnostics.filter((d) => d.severity === "warning").length;

  return (
    <div className="au-diagnostics">
      <div className="au-diagnostics-header">
        <strong>
          {errors} error{errors !== 1 ? "s" : ""}, {warnings} warning
          {warnings !== 1 ? "s" : ""}
        </strong>
        <button
          type="button"
          className="au-icon-button"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss diagnostics"
        >
          ×
        </button>
      </div>
      <ul className="au-diagnostics-list">
        {diagnostics.map((d, i) => (
          <li key={i} className={`au-diag au-diag-${d.severity}`}>
            <div className="au-diag-head">
              <span className="au-diag-code">{d.code}</span>
              {d.sourceLine !== undefined && (
                <span className="au-diag-loc">
                  line {d.sourceLine}
                  {d.sourceCol !== undefined && `:${d.sourceCol}`}
                </span>
              )}
            </div>
            <div className="au-diag-msg">{d.message}</div>
            {d.path.length > 0 && (
              <div className="au-diag-path">
                at {d.path.map((p) => String(p)).join(".")}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
