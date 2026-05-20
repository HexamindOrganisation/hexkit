import { Construction, Settings } from "lucide-react";
import { PageHeader } from "../components/PageHeader.js";
import { useTheme } from "../state/theme.js";

export function SettingsPage(): JSX.Element {
  const { theme, resolved } = useTheme();
  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="App-level preferences and runtime info."
      />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-6 py-8 space-y-4">
          <section className="overflow-hidden rounded-lg border border-border bg-card/30">
            <div className="border-b border-border bg-card/40 px-6 py-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Settings className="h-4 w-4 text-muted-foreground" />
                Appearance
              </div>
            </div>
            <dl className="divide-y divide-border">
              <Row label="Theme preference" value={theme} />
              <Row label="Resolved theme" value={resolved} />
            </dl>
          </section>

          <section className="overflow-hidden rounded-lg border border-border bg-card/30">
            <div className="border-b border-border bg-card/40 px-6 py-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Construction className="h-4 w-4 text-muted-foreground" />
                Coming in Slice 5
              </div>
            </div>
            <div className="px-6 py-6 text-xs text-muted-foreground">
              Runtime URL override, log verbosity, and a read-only view of
              the runtime's <code className="mono">GET /config</code>{" "}
              (version, isolation mode, agents dir, supported frameworks).
            </div>
          </section>
        </div>
      </div>
    </>
  );
}

function Row({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}): JSX.Element {
  return (
    <div className="flex items-center justify-between px-6 py-3 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mono text-foreground">{value}</dd>
    </div>
  );
}
