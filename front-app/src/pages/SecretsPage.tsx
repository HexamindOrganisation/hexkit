import { Construction, KeyRound } from "lucide-react";
import { PageHeader } from "../components/PageHeader.js";

export function SecretsPage(): JSX.Element {
  return (
    <>
      <PageHeader
        title="Secrets"
        subtitle="Framework API keys, injected into worker processes at spawn time."
      />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-6 py-12">
          <div className="overflow-hidden rounded-lg border border-border bg-card/30">
            <div className="border-b border-border bg-card/40 px-6 py-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <KeyRound className="h-4 w-4 text-muted-foreground" />
                Vault
              </div>
            </div>
            <div className="flex flex-col items-center px-8 py-12 text-center">
              <span className="mb-3 grid h-10 w-10 place-items-center rounded-full bg-muted/40 text-muted-foreground ring-1 ring-inset ring-border">
                <Construction className="h-5 w-5" />
              </span>
              <p className="text-sm font-medium">Coming in Slice 4</p>
              <p className="mt-1 max-w-sm text-xs text-muted-foreground">
                The runtime gains a secret store with four endpoints
                (<code className="mono">GET / PUT / DELETE /secrets/&#123;key&#125;</code>);
                this page becomes the CRUD UI with masked values and
                per-manifest declared key hints.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
