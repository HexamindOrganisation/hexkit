/**
 * Authed fetch wrapper.
 *
 * One place to attach `Authorization: Bearer …`, one place to react to 401s.
 * Every other api/* module calls these helpers — components never call
 * `fetch` directly so a future migration to httpOnly cookies or an OAuth
 * flow is a one-file change.
 */

const TOKEN_KEY = "platform_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class HttpError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function parseError(resp: Response): Promise<HttpError> {
  let body: unknown = null;
  try {
    body = await resp.json();
  } catch {
    try {
      body = await resp.text();
    } catch {
      /* ignore */
    }
  }
  const detail =
    (body && typeof body === "object" && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : null) ?? `HTTP ${resp.status}`;
  return new HttpError(resp.status, body, detail);
}

/**
 * On 401, clear the token and hard-nav to /login. A hard nav (not a
 * react-router push) is intentional: it tears down any stale React state
 * that assumed an authenticated session.
 */
function on401(): void {
  clearToken();
  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

export async function authedFetch(
  input: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const resp = await fetch(input, { ...init, headers });
  if (resp.status === 401) {
    on401();
  }
  return resp;
}

// JSON helpers ---------------------------------------------------------------

export async function getJson<T>(path: string): Promise<T> {
  const resp = await authedFetch(path);
  if (!resp.ok) throw await parseError(resp);
  return (await resp.json()) as T;
}

export async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const resp = await authedFetch(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!resp.ok) throw await parseError(resp);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export async function patchJson<T>(path: string, body: unknown): Promise<T> {
  const resp = await authedFetch(path, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw await parseError(resp);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export async function putJson<T>(path: string, body: unknown): Promise<T> {
  const resp = await authedFetch(path, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw await parseError(resp);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export async function del(path: string): Promise<void> {
  const resp = await authedFetch(path, { method: "DELETE" });
  if (!resp.ok && resp.status !== 204) throw await parseError(resp);
}
