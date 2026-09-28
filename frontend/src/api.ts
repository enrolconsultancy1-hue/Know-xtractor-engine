// Thin API client for the KNOX backend.

import type { AnalysisStatus, Graph, KnowledgePackage, Project } from "./types";

const BASE = "/api";
const TOKEN_KEY = "knox_api_token";

export function getAuthToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setAuthToken(token: string): void {
  if (token && token.trim()) {
    localStorage.setItem(TOKEN_KEY, token.trim());
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) {
    const text = await res.text();
    if (res.status === 401) {
      throw new Error(`401 Unauthorized: Invalid or missing API key. Set your Bearer token in Settings / API Key.`);
    }
    throw new Error(`${res.status}: ${text.slice(0, 300)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listProjects: () => req<Project[]>("/projects"),
  getProject: (id: number) => req<Project>(`/projects/${id}`),
  createProject: (body: { repository_url: string; name?: string; branch?: string }) =>
    req<{ id: number }>("/projects", { method: "POST", body: JSON.stringify(body) }),
  analyze: (id: number, body: { branch: string; commit_ref?: string }) =>
    req<{ analysis_id: number }>(`/projects/${id}/analyze`, { method: "POST", body: JSON.stringify(body) }),
  getAnalysis: (id: number) => req<AnalysisStatus>(`/analysis/${id}`),
  getKnowledge: (id: number) => req<KnowledgePackage>(`/projects/${id}/knowledge`),
  getGraph: (id: number) => req<Graph>(`/projects/${id}/graph`),
  customize: (id: number, body: Record<string, string>) =>
    req<Record<string, unknown>>(`/projects/${id}/architecture/customize`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  implementationPrompt: (id: number, body?: Record<string, string>) =>
    req<{ prompt: string }>(`/projects/${id}/implementation-prompt`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
};
