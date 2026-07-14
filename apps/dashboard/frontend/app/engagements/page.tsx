"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type EngagementSummary } from "@/lib/api";

export default function EngagementsPage() {
  const [items, setItems] = useState<EngagementSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listEngagements()
      .then(setItems)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (items === null) return <p className="muted">Loading…</p>;

  return (
    <div>
      <h1>My engagements</h1>
      <p className="muted" style={{ marginTop: ".3rem", fontSize: ".88rem" }}>
        History is kept per browser — no account required.
      </p>
      {items.length === 0 && (
        <p className="muted" style={{ marginTop: "1rem" }}>
          No engagements yet. <Link href="/">Run one</Link>.
        </p>
      )}
      <div style={{ marginTop: "1.2rem" }}>
        {items.map((e) => (
          <Link key={e.id} href={`/engagements/${e.id}`} style={{ textDecoration: "none" }}>
            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
                <span style={{ color: "var(--text)" }}>
                  {e.case_prompt.slice(0, 140)}
                  {e.case_prompt.length > 140 ? "…" : ""}
                </span>
                <span className={`status-pill ${e.status}`}>{e.status}</span>
              </div>
              <div className="muted" style={{ fontSize: ".82rem", marginTop: ".4rem" }}>
                {new Date(e.created_at * 1000).toLocaleString()}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
