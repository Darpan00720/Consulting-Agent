// Thin client for the dashboard API. No accounts required.
//  - Identity = anonymous per-browser id (localStorage, sent as X-Client-Id)
//  - Free tier: the server's own provider keys serve the run (daily quota).
//  - Premium (BYOK): the user's own API key travels in the request body for
//    that run only — kept in localStorage, never stored on the server.

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
  retention_days?: number;
}

export interface Lesson {
  id: number;
  text: string;
  created_at: number;
}

export interface Feedback {
  id: number;
  rating: string | null;
  comment: string;
  created_at: number;
}

export interface AdminOverview {
  total: number;
  users: number;
  completed: number;
  failed: number;
  in_flight: number;
  byok_runs: number;
  free_runs: number;
  shipped_final: number;
  interim_only: number;
  feedback_count: number;
  lessons_learned: number;
}

export interface AdminEngagement {
  id: string;
  client_id: string;
  case_prompt: string;
  status: string;
  error: string | null;
  review_verdict: string | null;
  challenge_verdict: string | null;
  review_ready: number | null;
  used_byok: number;
  created_at: number;
  completed_at: number | null;
  failed_at: string | null;
  phases_completed: number;
  pauses: number;
  feedback_count: number;
  feedback: Feedback[];
}

export const api = {
  health: () => request<Health>("/api/health"),
  addFeedback: (id: string, comment: string, rating?: string) =>
    request<{ id: number; status: string }>(`/api/engagements/${id}/feedback`, {
      method: "POST",
      body: JSON.stringify({ comment, rating: rating || undefined }),
    }),
  listFeedback: (id: string) =>
    request<Feedback[]>(`/api/engagements/${id}/feedback`),
  // Operator console. The token is supplied per call and kept only in the
  // admin page's own state — never in localStorage, so it can't leak from a
  // shared browser.
  adminOverview: (token: string) =>
    request<AdminOverview>("/api/admin/overview", {
      headers: { "X-Admin-Token": token },
    }),
  adminEngagements: (token: string) =>
    request<AdminEngagement[]>("/api/admin/engagements", {
      headers: { "X-Admin-Token": token },
    }),
  adminLessons: (token: string) =>
    request<Lesson[]>("/api/admin/lessons", {
      headers: { "X-Admin-Token": token },
    }),
  createEngagement: (casePrompt: string, apiKey?: string, images?: string[]) =>
    request<{ id: string; status: string; phases: string[] }>(
      "/api/engagements",
      {
        method: "POST",
        body: JSON.stringify({
          case_prompt: casePrompt,
          api_key: apiKey || undefined,
          images: images && images.length ? images : undefined,
        }),
      },
    ),
  listEngagements: () => request<EngagementSummary[]>("/api/engagements"),
  getEngagement: (id: string) => request<Engagement>(`/api/engagements/${id}`),
  // EventSource can't send headers — client id goes in the query string.
  eventsUrl: (id: string) =>
    `${API_URL}/api/engagements/${id}/events?client=${clientId()}`,
};
