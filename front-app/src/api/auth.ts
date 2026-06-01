import { getJson, postJson } from "./client";

export interface UserOut {
  id: string;
  email: string;
  created_at: string;
}

export interface TokenOut {
  access_token: string;
  token_type: "bearer";
  user: UserOut;
}

export interface Credentials {
  email: string;
  password: string;
}

export function signup(body: Credentials): Promise<TokenOut> {
  return postJson<TokenOut>("/api/auth/signup", body);
}

export function login(body: Credentials): Promise<TokenOut> {
  return postJson<TokenOut>("/api/auth/login", body);
}

export function getMe(): Promise<UserOut> {
  return getJson<UserOut>("/api/me");
}
