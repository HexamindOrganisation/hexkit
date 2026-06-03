import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Trash2, Upload } from "lucide-react";

import {
  deleteFile,
  fileContentUrl,
  listFiles,
  uploadFile,
  type FileMeta,
} from "../api/files";

function fmtSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/**
 * The Files library — every file the user has uploaded, flat and unordered (no
 * folders yet). Upload here or via the chat composer's attach button; reuse any
 * file as an attachment from the composer.
 */
export function FilesPage() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const { data: files = [], isLoading } = useQuery({
    queryKey: ["files"],
    queryFn: listFiles,
  });

  const uploadMut = useMutation({
    mutationFn: async (picked: File[]) => {
      for (const f of picked) await uploadFile(f);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["files"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteFile(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["files"] }),
  });

  return (
    <div className="mx-auto h-full max-w-2xl overflow-auto p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Files</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Your uploaded files. Attach any of them to a conversation from the
            composer.
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => {
            const picked = Array.from(e.target.files ?? []);
            e.target.value = "";
            if (picked.length) uploadMut.mutate(picked);
          }}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploadMut.isPending}
          className="hx-srow flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
          style={{ background: "var(--accent-color, hsl(var(--primary)))" }}
        >
          <Upload className="h-4 w-4" />
          {uploadMut.isPending ? "Uploading…" : "Upload"}
        </button>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : files.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
          No files yet. Upload one, or attach files from the chat composer.
        </div>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
          {files.map((f: FileMeta) => (
            <li
              key={f.id}
              className="hx-srow flex items-center gap-3 px-3 py-2.5 hover:bg-secondary/50"
            >
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
              <a
                href={fileContentUrl(f.id)}
                target="_blank"
                rel="noreferrer"
                className="min-w-0 flex-1 truncate text-sm hover:underline"
                title={f.name}
              >
                {f.name}
              </a>
              <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
                {fmtSize(f.size)}
              </span>
              <button
                type="button"
                onClick={() => deleteMut.mutate(f.id)}
                aria-label={`Delete ${f.name}`}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-card hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
