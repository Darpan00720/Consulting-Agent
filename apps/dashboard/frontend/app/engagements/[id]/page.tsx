"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type Engagement, type EngagementEvent } from "@/lib/api";

const PHASES: [string, string][] = [
  ["classify", "case-classifier"],
  ["gap_analysis", "information-gap"],
  ["planning", "planner"],
  ["framing", "framework-selector"],
  ["issue_tree", "issue-tree-generator"],
  ["analysis", "5 analysts in parallel"],
  ["reconcile", "engagement-manager"],
  ["review", "reviewer"],
  ["challenge", "challenger"],
  ["reporting", "report-writer"],
];

type PhaseState = "pending" | "running" | "done" | "failed";

type Governance = {
  review?: string;
  challenge?: string;
  reworks: number;
  reviewReady?: boolean;
};

export default function EngagementPage() {
  const { id } = useParams<{ id: string }>();
  const [engagement, setEngagement] = useState<Engagement | null>(null);
  const [phaseStates, setPhaseStates] = useState<Record<string, PhaseState>>({});
  const [durations, setDurations] = useState<Record<string, number>>({});
  const [report, setReport] = useState<string | null>(null);
  const [gov, setGov] = useState<Governance>({ reworks: 0 });
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    api
      .getEngagement(id)
      .then((e) => {
        setEngagement(e);
        if (e.review_verdict || e.challenge_verdict) {
          setGov((g) => ({
            ...g,
            review: e.review_verdict ?? g.review,
            challenge: e.challenge_verdict ?? g.challenge,
            reviewReady:
              e.review_ready === null ? undefined : e.review_ready === 1,
          }));
        }
        if (e.status === "completed" && e.report_md) {
          setReport(e.report_md);
          setPhaseStates(Object.fromEntries(PHASES.map(([p]) => [p, "done"])));
          return; // no need to stream
        }
        if (e.status === "failed") {
          setError(e.error ?? "Engagement failed");
          return;
        }
        openStream();
      })
      .catch((e) => setError(e.message));

    function openStream() {
      const source = new EventSource(api.eventsUrl(id));
      sourceRef.current = source;
      source.onmessage = (msg) => {
        const event: EngagementEvent = JSON.parse(msg.data);
        const p = event.payload as Record<string, any>;
        switch (event.type) {
          case "phase_started":
            setPhaseStates((s) => ({ ...s, [p.phase]: "running" }));
            break;
          case "phase_completed":
            setPhaseStates((s) => ({ ...s, [p.phase]: "done" }));
            if (p.duration_ms)
              setDurations((d) => ({ ...d, [p.phase]: p.duration_ms }));
            break;
          case "review_verdict":
            setGov((g) => ({ ...g, review: p.verdict as string }));
            break;
          case "challenge_verdict":
            setGov((g) => ({ ...g, challenge: p.verdict as string }));
            break;
          case "rework_started":
            setGov((g) => ({ ...g, reworks: g.reworks + 1 }));
            break;
          case "engagement_completed":
            setReport(p.report);
            setGov((g) => ({
              ...g,
              review: (p.review_verdict as string) ?? g.review,
              challenge: (p.challenge_verdict as string) ?? g.challenge,
              reviewReady: p.review_ready as boolean,
            }));
            source.close();
            break;
          case "engagement_failed":
            setError(p.error);
            setPhaseStates((s) => {
              const next = { ...s };
              for (const key of Object.keys(next))
                if (next[key] === "running") next[key] = "failed";
              return next;
            });
            source.close();
            break;
        }
      };
      source.onerror = () => {
        // EventSource auto-reconnects; nothing to do unless closed.
      };
    }

    return () => sourceRef.current?.close();
  }, [id]);

  const running = !report && !error;

  return (
    <div>
      <h1>Engagement</h1>
      {engagement && (
        <p className="muted" style={{ marginBottom: "1.4rem" }}>
          {engagement.case_prompt.slice(0, 220)}
          {engagement.case_prompt.length > 220 ? "…" : ""}
        </p>
      )}

      {error && (
        <div className="notice error-notice" role="alert">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" /><path d="M12 8v4" /><path d="M12 16h.01" />
          </svg>
          <div>
            <strong>The engagement couldn&apos;t complete.</strong>
            <p style={{ margin: ".3rem 0 0" }}>{error}</p>
            {/(credit|billing)/i.test(error) && (
              <p style={{ margin: ".5rem 0 0" }}>
                <a href="https://console.anthropic.com/settings/billing" target="_blank" rel="noreferrer">
                  Open Anthropic Plans &amp; Billing →
                </a>
              </p>
            )}
          </div>
        </div>
      )}

      {!report && (
        <div className="card">
          {PHASES.map(([phase, agent]) => {
            const state = phaseStates[phase] ?? "pending";
            return (
              <div key={phase} className={`phase ${state}`}>
                <span className="dot" />
                <span className="label">{phase.replace("_", " ")}</span>
                <span className="agent">{agent}</span>
                <span className="time">
                  {durations[phase]
                    ? `${(durations[phase] / 1000).toFixed(1)}s`
                    : state === "running"
                      ? "running…"
                      : ""}
                </span>
              </div>
            );
          })}
          {running && (
            <p className="muted" style={{ marginTop: ".8rem", fontSize: ".85rem" }}>
              You can leave this page — the engagement keeps running and the
              report will be saved to your history.
            </p>
          )}
        </div>
      )}

      {(gov.review || gov.challenge) && (
        <div className="governance">
          <span className="gov-label">Governance</span>
          <span className={`gov-gate ${gov.review === "approved" ? "ok" : "warn"}`}>
            Reviewer: {(gov.review ?? "—").replace(/_/g, " ")}
          </span>
          <span
            className={`gov-gate ${
              gov.challenge === "stands" || gov.challenge === "stands_with_caveats"
                ? "ok"
                : "warn"
            }`}
          >
            Challenger: {(gov.challenge ?? "—").replace(/_/g, " ")}
          </span>
          {gov.reworks > 0 && (
            <span className="gov-gate rework">
              {gov.reworks} reconciliation pass{gov.reworks > 1 ? "es" : ""}
            </span>
          )}
        </div>
      )}

      {report && gov.reviewReady === false && (
        <div className="notice error-notice" role="alert">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" /><path d="M12 8v4" /><path d="M12 16h.01" />
          </svg>
          <div>
            <strong>Interim report — not a final recommendation.</strong>
            <p style={{ margin: ".3rem 0 0" }}>
              The analysis did not clear both governance gates even after
              reconciliation. Read this as a status memo on where the work
              stands, not a decision document. This is the platform refusing to
              ship contradictory numbers — the honest outcome.
            </p>
          </div>
        </div>
      )}

      {report && (
        <article className="deliverable">
          <header className="deliverable-bar">
            <span className="confidential">Confidential · Prepared by StratAgent</span>
            <div className="deliverable-actions">
              <button
                className="ghost sm"
                onClick={() => window.print()}
                aria-label="Print report"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M6 9V2h12v7" /><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><rect x="6" y="14" width="12" height="8" rx="1" />
                </svg>
                Print
              </button>
              <button
                className="ghost sm"
                onClick={() => downloadMarkdown(id, report)}
                aria-label="Download report as Markdown"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M7 10l5 5 5-5" /><path d="M12 15V3" />
                </svg>
                Download
              </button>
            </div>
          </header>
          <div className="report">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
          </div>
        </article>
      )}
    </div>
  );
}

function downloadMarkdown(id: string, md: string) {
  const blob = new Blob([md], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `stratagent-${id.slice(0, 12)}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
