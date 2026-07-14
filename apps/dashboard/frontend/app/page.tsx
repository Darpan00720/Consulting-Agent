"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  api,
  clearApiKey,
  getApiKey,
  setApiKey,
  type Health,
} from "@/lib/api";

const EXAMPLE =
  "A mid-sized regional grocery chain ($800M revenue) has seen margins compress from 4% to 2% over 3 years as Walmart and Amazon expand delivery in its markets. The CEO wants to know whether to double down on private label, exit low-density stores, or explore a merger with a regional competitor.";

const ICONS = {
  agents: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  shield: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  ),
  library: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
    </svg>
  ),
  trace: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><path d="m9 12 2 2 4-4" />
    </svg>
  ),
  key: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z" />
      <circle cx="16.5" cy="7.5" r=".5" fill="currentColor" />
    </svg>
  ),
};

export default function Home() {
  const router = useRouter();
  const [casePrompt, setCasePrompt] = useState("");
  const [keyInput, setKeyInput] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [model, setModel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setHasKey(getApiKey() !== null);
    api
      .health()
      .then((h) => {
        setHealth(h);
        setModel(h.model); // default to the server's configured model
      })
      .catch(() => {});
  }, []);

  async function submit() {
    setError(null);
    const trimmedKey = keyInput.trim();
    if (trimmedKey) {
      if (!trimmedKey.startsWith("sk-ant-")) {
        setError("That doesn't look like an Anthropic API key (should start with sk-ant-)");
        return;
      }
      setApiKey(trimmedKey); // remembered in this browser only
      setHasKey(true);
      setKeyInput("");
    }
    setSubmitting(true);
    try {
      const { id } = await api.createEngagement(casePrompt, model);
      router.push(`/engagements/${id}`);
    } catch (e) {
      setError((e as Error).message);
      setSubmitting(false);
    }
  }

  const freeTier = health?.free_tier ?? false;
  const keyRank = hasKey
    ? "your API key"
    : health?.mock
      ? "the demo pipeline (canned output — add your key for real analysis)"
      : freeTier
        ? "the free tier"
        : null;

  return (
    <div>
      <section className="hero">
        <span className="eyebrow">{ICONS.shield} Governed AI consulting</span>
        <h1>Board-quality analysis on any business problem</h1>
        <p className="lead" style={{ marginTop: ".7rem" }}>
          StratAgent runs a full consulting engagement: it classifies the case,
          scopes it, dispatches specialist analysts, stress-tests every
          conclusion through mandatory reviewer and challenger gates, and
          returns an executive-ready report. No account needed.
        </p>

        <div className="trust-strip">
          <div className="trust-item">
            {ICONS.agents}
            <div><span className="num">16 specialists</span><span className="cap">analyst &amp; governance agents</span></div>
          </div>
          <div className="trust-item">
            {ICONS.library}
            <div><span className="num">63 frameworks</span><span className="cap">governed knowledge vault</span></div>
          </div>
          <div className="trust-item">
            {ICONS.shield}
            <div><span className="num">2 mandatory gates</span><span className="cap">reviewer + challenger</span></div>
          </div>
          <div className="trust-item">
            {ICONS.trace}
            <div><span className="num">100% traceable</span><span className="cap">every number labeled</span></div>
          </div>
        </div>
      </section>

      <section>
        <h2>1 · Describe the business problem</h2>
        <textarea
          value={casePrompt}
          onChange={(e) => setCasePrompt(e.target.value)}
          placeholder={EXAMPLE}
          aria-label="Business problem description"
        />
        <div style={{ marginTop: ".6rem" }}>
          <button className="ghost" onClick={() => setCasePrompt(EXAMPLE)}>
            Use example case
          </button>
        </div>
      </section>

      <section>
        <h2 style={{ display: "flex", alignItems: "center", gap: ".5rem" }}>
          {ICONS.key} 2 · Your Anthropic API key
        </h2>
        {hasKey ? (
          <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
            <span style={{ fontSize: ".92rem" }}>
              Key saved in this browser — engagements run on your account.
            </span>
            <button
              className="danger"
              onClick={() => {
                clearApiKey();
                setHasKey(false);
              }}
            >
              Remove key
            </button>
          </div>
        ) : (
          <>
            <p className="muted" style={{ fontSize: ".9rem", marginBottom: ".6rem" }}>
              Stays in your browser (localStorage), sent only to run your
              engagements, never stored on our server. Create one at{" "}
              <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer">
                console.anthropic.com
              </a>
              {freeTier && (
                <> — or leave it empty to try {health?.free_tier_quota ?? 5} free
                engagements/day on the shared key</>
              )}
              .
            </p>
            <input
              type="password"
              placeholder="sk-ant-…  (optional if free tier is available)"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              autoComplete="off"
              aria-label="Anthropic API key"
            />
          </>
        )}
      </section>

      <section>
        <h2>3 · Run</h2>
        {health && health.models?.length > 0 && (
          <div style={{ marginBottom: ".9rem", maxWidth: 460 }}>
            <label htmlFor="model">Model</label>
            <select
              id="model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              {health.models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
            <p className="muted" style={{ fontSize: ".82rem", marginTop: ".35rem" }}>
              Iterating on many cases? Use Haiku (~5× cheaper) to test structure,
              then re-run the keepers on Opus for final quality.
            </p>
          </div>
        )}
        {error && <p className="error">{error}</p>}
        <div style={{ display: "flex", gap: ".8rem", alignItems: "center", flexWrap: "wrap" }}>
          <button onClick={submit} disabled={submitting || casePrompt.trim().length < 40}>
            {submitting ? "Starting…" : "Run engagement"}
          </button>
          {keyRank && (
            <span className="muted" style={{ fontSize: ".85rem" }}>
              Runs on {keyRank} · ~13 agents · 5–15 minutes
            </span>
          )}
        </div>
      </section>

      <section>
        <h2>How it works</h2>
        <div className="steps">
          <div className="step">
            <span className="n">1</span>
            <h3>Scope</h3>
            <p>Case classified by archetype; load-bearing unknowns become a labeled assumption ledger with breakevens.</p>
          </div>
          <div className="step">
            <span className="n">2</span>
            <h3>Analyze</h3>
            <p>Financial, market, operations, strategy, and risk analysts work a MECE issue tree in parallel.</p>
          </div>
          <div className="step">
            <span className="n">3</span>
            <h3>Challenge</h3>
            <p>An independent reviewer checks the work; a challenger attacks the load-bearing assumptions. Always.</p>
          </div>
          <div className="step">
            <span className="n">4</span>
            <h3>Report</h3>
            <p>An executive-ready deliverable with every assumption preserved and every caveat carried through.</p>
          </div>
        </div>
        <p className="muted" style={{ marginTop: "1rem", fontSize: ".85rem" }}>
          Engagement history is kept per browser — see{" "}
          <Link href="/engagements">Engagements</Link>.
        </p>
      </section>
    </div>
  );
}
