"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  type CaseSummary,
  type EvalRun,
  type ModelChoice,
} from "@/lib/api";

function scoreColor(score: number): string {
  if (score >= 85) return "#15803d"; // green
  if (score >= 70) return "#a16207"; // amber
  return "#b91c1c"; // red
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="muted">not scored</span>;
  return (
    <span
      style={{
        fontWeight: 700,
        fontVariantNumeric: "tabular-nums",
        color: scoreColor(score),
      }}
    >
      {score}/100
    </span>
  );
}

function CaseRow({
  c,
  model,
  onDeleted,
}: {
  c: CaseSummary;
  model: string;
  onDeleted: () => void;
}) {
  const [evals, setEvals] = useState<EvalRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const load = useCallback(() => {
    api.listEvals(c.id).then(setEvals).catch(() => {});
  }, [c.id]);

  useEffect(load, [load]);

  // Poll while a run is in flight so the score appears without a refresh.
  const running = evals.some((e) => e.status === "running");
  useEffect(() => {
    if (!running) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [running, load]);

  async function run() {
    setError(null);
    setStarting(true);
    try {
      await api.runEval(c.id, model);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start the run");
    } finally {
      setStarting(false);
    }
  }

  const scored = evals.filter((e) => e.status === "completed" && e.score !== null);
  const unscored = evals.filter(
    (e) => e.status === "completed" && e.score === null,
  ).length;
  const latest = evals[evals.length - 1];

  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: "1rem",
          alignItems: "baseline",
          flexWrap: "wrap",
        }}
      >
        <strong>{c.title}</strong>
        <div style={{ display: "flex", gap: ".6rem", alignItems: "center" }}>
          <button onClick={run} disabled={starting || running} className="sm">
            {running ? "Running…" : starting ? "Starting…" : "Run benchmark"}
          </button>
          <button className="danger sm" onClick={() => api.deleteCase(c.id).then(onDeleted)}>
            Remove
          </button>
        </div>
      </div>

      <div className="muted" style={{ fontSize: ".85rem", marginTop: ".5rem" }}>
        {scored.length === 0 && unscored === 0 && !running && "No graded runs yet."}
        {scored.length === 0 && unscored > 0 && !running && (
          <span>
            {unscored} run{unscored > 1 ? "s" : ""} completed, ungraded (the
            grader returned no score).
          </span>
        )}
        {scored.length > 0 && (
          <>
            Score history:{" "}
            {scored.map((e, i) => (
              <span key={e.id}>
                {i > 0 && " → "}
                <ScoreBadge score={e.score} />
              </span>
            ))}
          </>
        )}
        {running && <span> Grading in progress — this runs a full engagement…</span>}
      </div>

      {latest?.engagement_id && latest.status !== "running" && (
        <div style={{ fontSize: ".85rem", marginTop: ".4rem" }}>
          <Link href={`/engagements/${latest.engagement_id}`}>
            View the graded report →
          </Link>
        </div>
      )}
      {latest?.status === "failed" && latest.detail && (
        <p className="error" style={{ marginTop: ".4rem" }}>{latest.detail}</p>
      )}
      {error && <p className="error" style={{ marginTop: ".4rem" }}>{error}</p>}
    </div>
  );
}

export default function BenchmarkPage() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [models, setModels] = useState<ModelChoice[]>([]);
  const [model, setModel] = useState("claude-haiku-4-5");
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [rubric, setRubric] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    api
      .listCases()
      .then(setCases)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    api.health().then((h) => setModels(h.models)).catch(() => {});
  }, [load]);

  async function addCase(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await api.createCase(title, prompt, rubric);
      setTitle("");
      setPrompt("");
      setRubric("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save the case");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ maxWidth: 760 }}>
      <h1>Benchmark: train with your own cases &amp; answers</h1>
      <p className="lead" style={{ marginTop: ".5rem" }}>
        Paste a case <em>and its official model answer</em>. StratAgent runs the
        case, a grader scores the report against your answer (0–100), and every
        gap is distilled into a durable{" "}
        <Link href="/lessons">process lesson</Link> that guards all future
        engagements. The model&apos;s weights never change — the method memory
        does, and the score history proves it.
      </p>

      <form onSubmit={addCase} className="card" style={{ marginTop: "1.2rem" }}>
        <h2 style={{ fontSize: "1rem" }}>Add a golden case</h2>
        <label htmlFor="bm-title">Case title</label>
        <input
          id="bm-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. GlobaPharm / BioFuture acquisition"
          required
          minLength={3}
        />
        <label htmlFor="bm-prompt">Case prompt</label>
        <textarea
          id="bm-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={6}
          placeholder="The full case as you would give it to a consultant…"
          required
          minLength={40}
        />
        <label htmlFor="bm-rubric">Official model answer / grading rubric</label>
        <textarea
          id="bm-rubric"
          value={rubric}
          onChange={(e) => setRubric(e.target.value)}
          rows={6}
          placeholder="What a good answer must include — the report is graded against this…"
          required
          minLength={40}
        />
        <div style={{ display: "flex", gap: ".8rem", alignItems: "center", marginTop: ".6rem" }}>
          <button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save case"}
          </button>
          <label htmlFor="bm-model" className="muted" style={{ fontSize: ".85rem" }}>
            Run on
          </label>
          <select id="bm-model" value={model} onChange={(e) => setModel(e.target.value)}>
            {(models.length
              ? models
              : [{ id: "claude-haiku-4-5", label: "Haiku 4.5 — cheapest", tier: "cheap" }]
            ).map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
        <p className="muted" style={{ fontSize: ".8rem", marginTop: ".5rem" }}>
          Tip: benchmark on Haiku while iterating (~5× cheaper); the grader
          always runs on Haiku. No API key needed.
        </p>
      </form>

      {error && <p className="error" style={{ marginTop: "1rem" }}>{error}</p>}
      {cases === null && !error && <p className="muted">Loading…</p>}
      {cases?.length === 0 && (
        <div className="card" style={{ marginTop: "1.2rem" }}>
          <p className="muted">
            No golden cases yet. Add a case with its official answer above —
            each run makes the agent measurably better.
          </p>
        </div>
      )}

      <div style={{ marginTop: "1.2rem" }}>
        {cases?.map((c) => (
          <CaseRow key={c.id} c={c} model={model} onDeleted={load} />
        ))}
      </div>
    </div>
  );
}
