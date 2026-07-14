"use client";

import { useEffect, useState } from "react";
import { api, type Lesson } from "@/lib/api";

export default function LessonsPage() {
  const [lessons, setLessons] = useState<Lesson[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api
      .listLessons()
      .then(setLessons)
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function remove(id: number) {
    await api.deleteLesson(id);
    load();
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <h1>What the agent has learned</h1>
      <p className="lead" style={{ marginTop: ".5rem" }}>
        After a blocked engagement, StratAgent distils the reviewer&apos;s and
        challenger&apos;s findings into durable <strong>process lessons</strong>{" "}
        — method only, never case facts. Every future engagement gets these
        injected as guardrails, so the same class of mistake is not repeated.
      </p>

      {error && <p className="error">{error}</p>}
      {lessons === null && !error && <p className="muted">Loading…</p>}

      {lessons?.length === 0 && (
        <div className="card" style={{ marginTop: "1.2rem" }}>
          <p className="muted">
            No lessons yet. They accumulate automatically as engagements run —
            especially the ones that get blocked at a governance gate.
          </p>
        </div>
      )}

      <div style={{ marginTop: "1.2rem" }}>
        {lessons?.map((l) => (
          <div key={l.id} className="card">
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "flex-start" }}>
              <span style={{ fontSize: ".95rem" }}>{l.text}</span>
              <button
                className="danger sm"
                onClick={() => remove(l.id)}
                aria-label="Delete this lesson"
              >
                Remove
              </button>
            </div>
            <div className="muted" style={{ fontSize: ".8rem", marginTop: ".4rem" }}>
              Learned {new Date(l.created_at * 1000).toLocaleDateString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
