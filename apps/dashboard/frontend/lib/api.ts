// Thin client for the dashboard API. No accounts:
//  - identity = anonymous per-browser id (localStorage, sent as X-Client-Id)
//  - the user's Anthropic API key lives ONLY in localStorage and is sent
//    per-request when running an engagement; the server never stores it.

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function clientId(): string {
  if (typeof window === "undefined") return "server-render";
  let id = localStorage.getItem("stratagent_client_id");
  if (!id) {
    id = `web-${crypto.randomUUID()}`;
    localStorage.setItem("stratagent_client_id", id);
  }
  return id;
}

export function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("stratagent_api_key");
}

export function setApiKey(key: string) {
  localStorage.setItem("stratagent_api_key", key);
}

export function clearApiKey() {
  localStorage.removeItem("stratagent_api_key");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Client-Id": clientId(),
      ...init.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return res.json();
}

export interface EngagementSummary {
  id: string;
  case_prompt: string;
  status: string;
  created_at: number;
  completed_at: number | null;
}

export interface Engagement extends EngagementSummary {
  report_md: string | null;
  error: string | null;
  review_verdict: string | null;
  challenge_verdict: string | null;
  review_ready: number | null; // 1 | 0 | null (SQLite boolean)
}

export interface EngagementEvent {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
  created_at: number;
}

export interface ModelChoice {
  id: string;
  label: string;
  tier: string;
}

export interface Health {
  ok: boolean;
  model: string;
  models: ModelChoice[];
  mock: boolean;
  free_tier: boolean;
  free_tier_quota: number;
}

export interface Lesson {
  id: number;
  text: string;
  created_at: number;
}

export interface CaseSummary {
  id: string;
  title: string;
  created_at: number;
  latest_score: number | null;
  eval_count: number;
}

export interface EvalRun {
  id: string;
  engagement_id: string | null;
  status: string; // running | completed | failed
  score: number | null;
  detail: string | null;
  created_at: number;
  completed_at: number | null;
}

export const api = {
  health: () => request<Health>("/api/health"),
  listLessons: () => request<Lesson[]>("/api/lessons"),
  deleteLesson: (id: number) =>
    fetch(`${API_URL}/api/lessons/${id}`, { method: "DELETE" }),
  createEngagement: (casePrompt: string, model?: string) =>
    request<{ id: string; status: string; phases: string[] }>(
      "/api/engagements",
      {
        method: "POST",
        body: JSON.stringify({
          case_prompt: casePrompt,
          api_key: getApiKey() ?? undefined,
          model: model || undefined,
        }),
      },
    ),
  listEngagements: () => request<EngagementSummary[]>("/api/engagements"),
  // Golden-case benchmark: {case, official answer} pairs the agent is graded
  // against — the gaps become lessons, the scores prove improvement.
  listCases: () => request<CaseSummary[]>("/api/cases"),
  createCase: (title: string, prompt: string, rubric: string) =>
    request<{ id: string; title: string }>("/api/cases", {
      method: "POST",
      body: JSON.stringify({ title, prompt, rubric }),
    }),
  deleteCase: (id: string) =>
    fetch(`${API_URL}/api/cases/${id}`, {
      method: "DELETE",
      headers: { "X-Client-Id": clientId() },
    }),
  listEvals: (caseId: string) => request<EvalRun[]>(`/api/cases/${caseId}/evals`),
  runEval: (caseId: string, model?: string) =>
    request<{ eval_id: string; engagement_id: string; status: string }>(
      `/api/cases/${caseId}/run`,
      {
        method: "POST",
        body: JSON.stringify({
          api_key: getApiKey() ?? undefined,
          model: model || undefined,
        }),
      },
    ),
  getEngagement: (id: string) => request<Engagement>(`/api/engagements/${id}`),
  // EventSource can't send headers — client id goes in the query string.
  eventsUrl: (id: string) =>
    `${API_URL}/api/engagements/${id}/events?client=${clientId()}`,
};
