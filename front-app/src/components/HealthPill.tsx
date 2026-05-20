import { useEffect, useState } from "react";

type Health =
  | { kind: "loading" }
  | { kind: "ok" }
  | { kind: "unhealthy"; detail: string }
  | { kind: "error" };

export function HealthPill({ agentId }: { agentId: string }): JSX.Element {
  const [state, setState] = useState<Health>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/agents/${encodeURIComponent(agentId)}/health`)
      .then(async (res) => {
        const body = (await res.json()) as {
          ok: boolean;
          details?: { error?: string };
        };
        if (cancelled) return;
        if (body.ok) setState({ kind: "ok" });
        else
          setState({
            kind: "unhealthy",
            detail: body.details?.error ?? "unhealthy",
          });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  if (state.kind === "loading") {
    return <Dot tone="muted" label="checking" pulse />;
  }
  if (state.kind === "ok") return <Dot tone="ok" label="healthy" />;
  if (state.kind === "unhealthy")
    return <Dot tone="warn" label="unhealthy" title={state.detail} />;
  return <Dot tone="error" label="unreachable" />;
}

function Dot({
  tone,
  label,
  title,
  pulse,
}: {
  tone: "ok" | "warn" | "error" | "muted";
  label: string;
  title?: string;
  pulse?: boolean;
}): JSX.Element {
  const colors = {
    ok: "bg-emerald-400 shadow-[0_0_0_3px_hsl(var(--background))]",
    warn: "bg-amber-400 shadow-[0_0_0_3px_hsl(var(--background))]",
    error: "bg-red-400 shadow-[0_0_0_3px_hsl(var(--background))]",
    muted: "bg-muted-foreground/50",
  }[tone];
  const text = {
    ok: "text-emerald-300",
    warn: "text-amber-300",
    error: "text-red-300",
    muted: "text-muted-foreground",
  }[tone];
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider ${text}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${colors} ${pulse ? "animate-pulse" : ""}`}
      />
      {label}
    </span>
  );
}
