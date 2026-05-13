export type DiagnosticSeverity = "error" | "warning";

export type Diagnostic = {
  severity: DiagnosticSeverity;
  code: string;
  message: string;
  path: (string | number)[];
  sourceLine?: number;
  sourceCol?: number;
};

export type Result<T, E = Diagnostic[]> =
  | { ok: true; value: T }
  | { ok: false; errors: E };

export function ok<T>(value: T): Result<T, never> {
  return { ok: true, value };
}

export function err<E>(errors: E): Result<never, E> {
  return { ok: false, errors };
}

export function hasErrors(diagnostics: Diagnostic[]): boolean {
  return diagnostics.some((d) => d.severity === "error");
}
