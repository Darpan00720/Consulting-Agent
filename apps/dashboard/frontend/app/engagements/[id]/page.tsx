"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type Engagement, type EngagementEvent } from "@/lib/api";


// ---------------------------------------------------------------------------
// Engagement lifecycle model — mirrored from the backend PHASES list, grouped
// into the three acts of a real consulting engagement so the timeline reads
// like a story, not a log.
// ---------------------------------------------------------------------------

type PhaseDef = {
  id: string;
  label: string;
  agent: string;
  blurb: string;
};

type StageDef = {
  id: string;
  title: string;
  caption: string;
  phases: PhaseDef[];
};

const STAGES: StageDef[] = [
  {
    id: "scope",
    title: "Scope",
    caption: "Understand the problem before solving it",
    phases: [
      {
        id: "classify",
        label: "Classify the case",
        agent: "case-classifier",
        blurb: "Archetype, known facts, and the real question",
      },
      {
        id: "gap_analysis",
        label: "Find the gaps",
        agent: "information-gap",
        blurb: "Load-bearing unknowns become a labeled assumption ledger",
      },
      {
        id: "planning",
        label: "Plan the engagement",
        agent: "planner",
        blurb: "Ordered steps, dependencies, analyst assignments",
      },
      {
        id: "framing",
        label: "Select frameworks",
        agent: "framework-selector",
        blurb: "Primary and supporting frameworks, adapted to this case",
      },
      {
        id: "issue_tree",
        label: "Build the issue tree",
        agent: "issue-tree-generator",
        blurb: "MECE decomposition into owned, testable sub-questions",
      },
    ],
  },
  {
    id: "analyze",
    title: "Analyze",
    caption: "Five specialists work the tree",
    phases: [
      {
        id: "analysis",
        label: "Specialist analysis",
        agent: "5 specialist analysts",
        blurb: "Financial, market, operations, strategy, and risk",
      },
      {
        id: "reconcile",
        label: "Reconcile findings",
        agent: "engagement-manager",
        blurb: "Cross-checks numbers and resolves contradictions",
      },
    ],
  },
  {
    id: "govern",
    title: "Challenge & report",
    caption: "Nothing ships without surviving attack",
    phases: [
      {
        id: "review",
        label: "Independent review",
        agent: "reviewer",
        blurb: "MECE coverage, traceability, internal consistency",
      },
      {
        id: "challenge",
        label: "Stress-test",
        agent: "challenger",
        blurb: "The strongest counter-case against the recommendation",
      },
      {
        id: "reporting",
        label: "Executive report",
        agent: "report-writer",
        blurb: "Board-ready deliverable, every caveat carried through",
      },
    ],
  },
];

const ALL_PHASES = STAGES.flatMap((s) => s.phases.map((p) => p.id));

const ANALYSTS: { id: string; label: string }[] = [
  { id: "financial-analyst", label: "Financial" },
  { id: "market-analyst", label: "Market" },
  { id: "operations-analyst", label: "Operations" },
  { id: "strategy-analyst", label: "Strategy" },
  { id: "risk-analyst", label: "Risk" },
];

type PhaseState = "pending" | "running" | "done" | "failed";
type AnalystState = "pending" | "running" | "done";

type Governance = {
  review?: string;
  challenge?: string;
  reworks: number;
  reviewReady?: boolean;
};

type Paused = {
  resumeAt: number; // epoch seconds
  attempt: number;
  reason: string;
};

// ---------------------------------------------------------------------------

const ICONS = {
  check: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  ),
  alert: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><path d="M12 8v4" /><path d="M12 16h.01" />
    </svg>
  ),
  pause: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" />
    </svg>
  ),
  shield: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
    </svg>
  ),
  print: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 9V2h12v7" /><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><rect x="6" y="14" width="12" height="8" rx="1" />
    </svg>
  ),
  download: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M7 10l5 5 5-5" /><path d="M12 15V3" />
    </svg>
  ),
};

export default function EngagementPage() {
  const { id } = useParams<{ id: string }>();
  const [engagement, setEngagement] = useState<Engagement | null>(null);
  const [phaseStates, setPhaseStates] = useState<Record<string, PhaseState>>({});
  const [durations, setDurations] = useState<Record<string, number>>({});
  const [analystStates, setAnalystStates] = useState<Record<string, AnalystState>>({});
  const [report, setReport] = useState<string | null>(null);
  const [gov, setGov] = useState<Governance>({ reworks: 0 });
  const [paused, setPaused] = useState<Paused | null>(null);
  const [countdown, setCountdown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // Mock mode produces a run that LOOKS governed — green reviewer/challenger
  // badges and all. Only the report body admits it is canned, which is easy to
  // miss. Surface it unmistakably rather than let a demo pass for analysis.
  const [isMock, setIsMock] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    api
      .health()
      .then((h) => setIsMock(h.mock))
      .catch(() => {});
  }, []);

  // Live countdown while paused — recomputed from the wall-clock resume time
  // so it survives tab-switches and never drifts.
  useEffect(() => {
    if (!paused) return;
    const tick = () =>
      setCountdown(Math.max(0, Math.round(paused.resumeAt - Date.now() / 1000)));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [paused]);

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
          setPhaseStates(Object.fromEntries(ALL_PHASES.map((p) => [p, "done"])));
          setAnalystStates(
            Object.fromEntries(ANALYSTS.map((a) => [a.id, "done"])),
          );
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
            setPaused(null);
            setPhaseStates((s) => ({ ...s, [p.phase]: "running" }));
            break;
          case "phase_completed":
            setPhaseStates((s) => ({ ...s, [p.phase]: "done" }));
            if (p.duration_ms)
              setDurations((d) => ({ ...d, [p.phase]: p.duration_ms }));
            break;
          case "analyst_started":
            setPaused(null);
            setAnalystStates((s) => ({ ...s, [p.agent]: "running" }));
            break;
          case "analyst_completed":
            setAnalystStates((s) => ({ ...s, [p.agent]: "done" }));
            break;
          case "engagement_paused":
            setPaused({
              resumeAt: p.resume_at as number,
              attempt: (p.attempt as number) ?? 1,
              reason: (p.reason as string) ?? "",
            });
            setPhaseStates((s) => {
              const next = { ...s };
              for (const key of Object.keys(next))
                if (next[key] === "running") next[key] = "pending";
              return next;
            });
            setAnalystStates((s) => {
              const next = { ...s };
              for (const key of Object.keys(next))
                if (next[key] === "running") next[key] = "pending";
              return next;
            });
            break;
          case "engagement_resumed":
            setPaused(null);
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
            setPaused(null);
            setReport(p.report);
            setPhaseStates(
              Object.fromEntries(ALL_PHASES.map((ph) => [ph, "done"])),
            );
            setGov((g) => ({
              ...g,
              review: (p.review_verdict as string) ?? g.review,
              challenge: (p.challenge_verdict as string) ?? g.challenge,
              reviewReady: p.review_ready as boolean,
            }));
            source.close();
            break;
          case "engagement_failed":
            setPaused(null);
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

  const doneCount = ALL_PHASES.filter((p) => phaseStates[p] === "done").length;
  const progress = report ? 100 : Math.round((doneCount / ALL_PHASES.length) * 100);
  const running = !report && !error;
  const currentPhase = useMemo(() => {
    for (const stage of STAGES)
      for (const phase of stage.phases)
        if (phaseStates[phase.id] === "running") return phase;
    return null;
  }, [phaseStates]);

  const analystsDone = ANALYSTS.filter(
    (a) => analystStates[a.id] === "done",
  ).length;

  return (
    <div className="engagement-page">
      {/* ------------------------------------------------ header ---------- */}
      {isMock && (
        <div className="demo-banner" role="status">
          <strong>Demo mode — this is not real analysis.</strong> The server is
          running with <code>STRATAGENT_MOCK=1</code>, so no AI model was
          called and every output below (including the governance verdicts) is
          canned placeholder text. Add a provider API key and restart without
          the mock flag to run a real engagement.
        </div>
      )}

      <header className="eng-hero">
        <div className="eng-hero-top">
          <span className="eng-badge">
            {ICONS.shield}
            Governed engagement
          </span>
          <span
            className={`eng-status ${
              report
                ? "done"
                : error
                  ? "failed"
                  : paused
                    ? "paused"
                    : "running"
            }`}
          >
            {report
              ? "Complete"
              : error
                ? "Stopped"
                : paused
                  ? "Auto-resuming"
                  : currentPhase
                    ? currentPhase.label
                    : "Starting…"}
          </span>
        </div>
        {engagement && (
          <p className="eng-case">
            {engagement.case_prompt.slice(0, 260)}
            {engagement.case_prompt.length > 260 ? "…" : ""}
          </p>
        )}
        {!report && !error && (
          <div
            className="eng-progress"
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Engagement progress"
          >
            <div className="eng-progress-fill" style={{ width: `${progress}%` }} />
          </div>
        )}
      </header>

      {/* --------------------------------------------- paused banner ------ */}
      {paused && !report && !error && (
        <div className="notice pause-notice" role="status" aria-live="polite">
          {ICONS.pause}
          <div>
            <strong>
              Paused for provider capacity — resuming in {formatCountdown(countdown)}
            </strong>
            <p style={{ margin: ".3rem 0 0" }}>
              Every completed step is saved. The engagement will pick up
              exactly where it left off — no action needed, and you can leave
              this page.
            </p>
          </div>
        </div>
      )}

      {/* ------------------------------------------------ error ----------- */}
      {error && (
        <div className="notice error-notice" role="alert">
          {ICONS.alert}
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

      {/* --------------------------------------------- timeline ----------- */}
      {!report && (
        <div className="eng-stages">
          {STAGES.map((stage, si) => {
            const stageDone = stage.phases.every(
              (p) => phaseStates[p.id] === "done",
            );
            const stageActive = stage.phases.some(
              (p) => phaseStates[p.id] === "running",
            );
            return (
              <section
                key={stage.id}
                className={`eng-stage${stageDone ? " done" : ""}${stageActive ? " active" : ""}`}
                aria-label={stage.title}
              >
                <header className="eng-stage-head">
                  <span className="eng-stage-n">{si + 1}</span>
                  <div>
                    <h2>{stage.title}</h2>
                    <p className="muted">{stage.caption}</p>
                  </div>
                </header>
                <ol className="eng-phase-list">
                  {stage.phases.map((phase) => {
                    const state = phaseStates[phase.id] ?? "pending";
                    return (
                      <li key={phase.id} className={`eng-phase ${state}`}>
                        <span className="eng-phase-marker" aria-hidden="true">
                          {state === "done" ? (
                            ICONS.check
                          ) : state === "running" ? (
                            <span className="eng-spinner" />
                          ) : null}
                        </span>
                        <div className="eng-phase-body">
                          <div className="eng-phase-row">
                            <span className="eng-phase-label">{phase.label}</span>
                            <span className="eng-phase-time">
                              {durations[phase.id]
                                ? `${(durations[phase.id] / 1000).toFixed(1)}s`
                                : state === "running"
                                  ? "working…"
                                  : ""}
                            </span>
                          </div>
                          <span className="eng-phase-blurb">{phase.blurb}</span>
                          {phase.id === "analysis" &&
                            (state === "running" ||
                              (state === "pending" && analystsDone > 0)) && (
                              <div className="eng-analysts" aria-label={`Analysts: ${analystsDone} of ${ANALYSTS.length} complete`}>
                                {ANALYSTS.map((a) => {
                                  const astate = analystStates[a.id] ?? "pending";
                                  return (
                                    <span key={a.id} className={`eng-analyst ${astate}`}>
                                      {astate === "done" && ICONS.check}
                                      {astate === "running" && (
                                        <span className="eng-spinner sm" />
                                      )}
                                      {a.label}
                                    </span>
                                  );
                                })}
                              </div>
                            )}
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </section>
            );
          })}
          {running && !paused && (
            <p className="muted eng-leave-note">
              You can leave this page — the engagement keeps running and the
              report will be saved to your history.
            </p>
          )}
        </div>
      )}

      {/* --------------------------------------------- governance --------- */}
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
          {ICONS.alert}
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

      {/* --------------------------------------------- deliverable -------- */}
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
                {ICONS.print}
                Print
              </button>
              <button
                className="ghost sm"
                onClick={() => downloadMarkdown(id, report)}
                aria-label="Download report as Markdown"
              >
                {ICONS.download}
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

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return "a moment";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
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
