"use client";

/** Operator console — private, token-gated.
 *
 * Answers the four questions an operator actually has:
 *   1. Is it working?          → completed / failed / interim split
 *   2. Where does it break?    → failing step, from the event log
 *   3. Who is using it?        → distinct clients, free vs BYOK
 *   4. What do they say?       → verbatim feedback, attached to its run
 *
 * The token lives in component state only — never localStorage — so it cannot
 * be recovered from a shared browser after the tab closes. Every fetch sends it
 * explicitly. A wrong token 404s, identically to an unconfigured server.
 */

import { useCallback, useEffect, useState } from "react";
import {
  api,
  type AdminEngagement,
  type AdminOverview,
  type Lesson,
} from "@/lib/api";

/** Which engagements a stat card drills into. A number on a dashboard should be
 *  a door: clicking "Failed" must show you the failures, not just count them. */
type FilterKey =
  | "all"
  | "completed"
  | "failed"
  | "in_flight"
  | "shipped_final"
  | "interim_only"
  | "free"
  | "byok"
  | "feedback";

const FILTERS: Record<FilterKey, (r: AdminEngagement) => boolean> = {
  all: () => true,
  completed: (r) => r.status === "completed",
  failed: (r) => r.status === "failed",
  in_flight: (r) => ["running", "queued", "paused"].includes(r.status),
  shipped_final: (r) => r.review_ready === 1,
  interim_only: (r) => r.status === "completed" && r.review_ready === 0,
  free: (r) => !r.used_byok,
  byok: (r) => !!r.used_byok,
  feedback: (r) => r.feedback_count > 0,
};

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [authed, setAuthed] = useState(false);
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [rows, setRows] = useState<AdminEngagement[]>([]);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");

  const load = useCallback(
    async (t: string) => {
      setLoading(true);
      setError(null);
      try {
        const [o, e, l] = await Promise.all([
          api.adminOverview(t),
          api.adminEngagements(t),
          api.adminLessons(t),
        ]);
        setOverview(o);
        setRows(e);
        setLessons(l);
        setAuthed(true);
      } catch {
        // The API 404s on a bad token by design, so don't parrot "not found".
        setError("Invalid token, or the admin console is not enabled on this server.");
        setAuthed(false);
      }
      setLoading(false);
    },
    [],
  );

  // Refresh while the page is open — an operator leaves this on a second screen.
  useEffect(() => {
    if (!authed) return;
    const t = setInterval(() => void load(token), 15000);
    return () => clearInterval(t);
  }, [authed, token, load]);

  if (!authed) {
    return (
      <div className="admin-gate">
        <h1>Operator console</h1>
        <p className="muted">
          Private. Requires the <code>STRATAGENT_ADMIN_TOKEN</code> configured on
          the server.
        </p>
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void load(token)}
          placeholder="Admin token"
          autoComplete="off"
          aria-label="Admin token"
        />
        {error && <p className="error" role="alert">{error}</p>}
        <button onClick={() => void load(token)} disabled={!token || loading}>
          {loading ? "Checking…" : "Open console"}
        </button>
      </div>
    );
  }

  const failing = rows.filter((r) => r.status === "failed");
  const withFeedback = rows.filter((r) => r.feedback_count > 0);
  const visible = rows.filter(FILTERS[filter]);

  return (
    <div className="admin">
      <header className="admin-head">
        <h1>Operator console</h1>
        <button className="ghost sm" onClick={() => void load(token)}>
          Refresh
        </button>
      </header>

      {overview && (
        <div className="admin-stats">
          <Stat label="Engagements" value={overview.total} filter="all" active={filter} onPick={setFilter} />
          <Stat label="Users" value={overview.users} hint="distinct browsers" />
          <Stat
            label="Completed"
            value={overview.completed}
            tone={overview.completed > 0 ? "ok" : undefined}
            filter="completed"
            active={filter}
            onPick={setFilter}
          />
          <Stat
            label="Failed"
            value={overview.failed}
            tone={overview.failed > 0 ? "bad" : undefined}
            filter="failed"
            active={filter}
            onPick={setFilter}
          />
          <Stat label="In flight" value={overview.in_flight} filter="in_flight" active={filter} onPick={setFilter} />
          <Stat
            label="Shipped final"
            value={overview.shipped_final}
            hint="cleared both gates"
            filter="shipped_final"
            active={filter}
            onPick={setFilter}
          />
          <Stat
            label="Interim only"
            value={overview.interim_only}
            hint="governance refused"
            tone={overview.interim_only > 0 ? "warn" : undefined}
            filter="interim_only"
            active={filter}
            onPick={setFilter}
          />
          <Stat label="Free tier" value={overview.free_runs} filter="free" active={filter} onPick={setFilter} />
          <Stat label="Own API key" value={overview.byok_runs} filter="byok" active={filter} onPick={setFilter} />
          <Stat label="Feedback" value={overview.feedback_count} filter="feedback" active={filter} onPick={setFilter} />
          <Stat
            label="Lessons learned"
            value={overview.lessons_learned}
            onJump={() =>
              document
                .getElementById("admin-lessons")
                ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
          />
        </div>
      )}

      {failing.length > 0 && (
        <section className="admin-section">
          <h2>Failing — where it breaks</h2>
          <table className="admin-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Failed at</th>
                <th>Phases done</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {failing.map((r) => (
                <tr key={r.id}>
                  <td>{when(r.created_at)}</td>
                  <td>
                    <code>{r.failed_at ?? "—"}</code>
                  </td>
                  <td className="num">{r.phases_completed}/10</td>
                  <td className="admin-err">{r.error ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {withFeedback.length > 0 && (
        <section className="admin-section">
          <h2>What users said</h2>
          {withFeedback.map((r) => (
            <div key={r.id} className="admin-fb">
              {r.feedback.map((f) => (
                <div key={f.id} className="admin-fb-item">
                  {f.rating && (
                    <span className={`fb-tag ${f.rating}`}>
                      {f.rating === "helpful" ? "Useful" : "Not useful"}
                    </span>
                  )}
                  <p>{f.comment}</p>
                  <span className="muted admin-fb-meta">
                    {when(f.created_at)} · {r.case_prompt.slice(0, 70)}…
                  </span>
                </div>
              ))}
            </div>
          ))}
        </section>
      )}

      <section className="admin-section" id="admin-engagements">
        <div className="admin-section-head">
          <h2>
            {filter === "all" ? "All engagements" : "Engagements"}{" "}
            <span className="muted admin-count">
              ({visible.length}
              {filter !== "all" ? ` of ${rows.length}` : ""})
            </span>
          </h2>
          {filter !== "all" && (
            <button className="ghost sm" onClick={() => setFilter("all")}>
              Clear filter: {FILTER_LABELS[filter]} ✕
            </button>
          )}
        </div>
        {visible.length === 0 && (
          <p className="muted">No engagements match this filter.</p>
        )}
        <table className="admin-table">
          <thead>
            <tr>
              <th>When</th>
              <th>User</th>
              <th>Tier</th>
              <th>Status</th>
              <th>Governance</th>
              <th>Pauses</th>
              <th>Feedback</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <>
                <tr
                  key={r.id}
                  onClick={() => setOpen(open === r.id ? null : r.id)}
                  className="admin-row"
                >
                  <td>{when(r.created_at)}</td>
                  <td>
                    <code className="admin-cid">{r.client_id.slice(0, 12)}</code>
                  </td>
                  <td>
                    <span className={`tier ${r.used_byok ? "byok" : "free"}`}>
                      {r.used_byok ? "BYOK" : "Free"}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill ${r.status}`}>{r.status}</span>
                    {r.failed_at && (
                      <code className="admin-failed-at">@{r.failed_at}</code>
                    )}
                  </td>
                  <td className="admin-gov">
                    {r.review_verdict ? (
                      <>
                        {r.review_verdict} / {r.challenge_verdict ?? "—"}
                        {r.review_ready === 0 && (
                          <span className="fb-tag not_helpful">interim</span>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="num">{r.pauses || ""}</td>
                  <td className="num">{r.feedback_count || ""}</td>
                </tr>
                {open === r.id && (
                  <tr key={`${r.id}-detail`}>
                    <td colSpan={7} className="admin-detail">
                      <strong>Case:</strong> {r.case_prompt}
                      {r.error && (
                        <p className="admin-err">
                          <strong>Error:</strong> {r.error}
                        </p>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </section>

      <section className="admin-section" id="admin-lessons">
        <h2>Lessons learned ({lessons.length})</h2>
        <p className="muted">
          Distilled automatically after every engagement and injected into all
          future runs.
        </p>
        <ul className="admin-lessons">
          {lessons.map((l) => (
            <li key={l.id}>{l.text}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

const FILTER_LABELS: Record<FilterKey, string> = {
  all: "All",
  completed: "Completed",
  failed: "Failed",
  in_flight: "In flight",
  shipped_final: "Shipped final",
  interim_only: "Interim only",
  free: "Free tier",
  byok: "Own API key",
  feedback: "With feedback",
};

/** A stat card. When given `filter` or `onJump` it becomes a real <button> —
 *  keyboard-reachable and announced as pressed — so the number is a door, not
 *  decoration. "Users" has nothing to drill into, so it stays inert. */
function Stat({
  label,
  value,
  hint,
  tone,
  filter,
  active,
  onPick,
  onJump,
}: {
  label: string;
  value: number;
  hint?: string;
  tone?: "ok" | "bad" | "warn";
  filter?: FilterKey;
  active?: FilterKey;
  onPick?: (f: FilterKey) => void;
  onJump?: () => void;
}) {
  const isActive = !!filter && active === filter;
  const clickable = !!filter || !!onJump;
  const cls = `admin-stat${tone ? ` ${tone}` : ""}${clickable ? " clickable" : ""}${
    isActive ? " active" : ""
  }`;

  const body = (
    <>
      <span className="admin-stat-v">{value}</span>
      <span className="admin-stat-l">{label}</span>
      {hint && <span className="admin-stat-h">{hint}</span>}
    </>
  );

  if (!clickable) return <div className={cls}>{body}</div>;

  return (
    <button
      type="button"
      className={cls}
      aria-pressed={filter ? isActive : undefined}
      onClick={() => {
        if (onJump) return onJump();
        if (!filter || !onPick) return;
        // Clicking the active filter clears it — a toggle, not a trap.
        onPick(isActive ? "all" : filter);
        document
          .getElementById("admin-engagements")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      }}
    >
      {body}
    </button>
  );
}

function when(ts: number): string {
  return new Date(ts * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
