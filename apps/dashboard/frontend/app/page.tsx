"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Health } from "@/lib/api";

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
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z" />
      <circle cx="16.5" cy="7.5" r=".5" fill="currentColor" />
    </svg>
  ),
  arrow: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12h14" /><path d="m12 5 7 7-7 7" />
    </svg>
  ),
};

export default function Home() {
  const router = useRouter();
  const [casePrompt, setCasePrompt] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
    const saved = localStorage.getItem("stratagent_api_key");
    if (saved) {
      setApiKey(saved);
      setShowKey(true);
    }
  }, []);

  function updateKey(value: string) {
    setApiKey(value);
    if (value.trim()) localStorage.setItem("stratagent_api_key", value.trim());
    else localStorage.removeItem("stratagent_api_key");
  }

  async function submit() {
    setError(null);
    setSubmitting(true);
    try {
      const { id } = await api.createEngagement(casePrompt, apiKey.trim());
      router.push(`/engagements/${id}`);
    } catch (e) {
      setError((e as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <div>
      <section className="hero-dark">
        <div className="hero-inner">
          <span className="eyebrow">{ICONS.shield} Governed AI consulting</span>
          <h1>
            Board-quality analysis on
            <br />
            any business problem
          </h1>
          <p className="hero-lead">
            StratAgent runs a full consulting engagement: it classifies your
            case, dispatches specialist analysts, stress-tests every conclusion
            through mandatory reviewer and challenger gates, and returns an
            executive-ready report. Free to use — no account needed.
          </p>

          <div className="hero-stats" role="list">
            <div className="hero-stat" role="listitem">
              {ICONS.agents}
              <div><span className="num">16 specialists</span><span className="cap">analyst &amp; governance agents</span></div>
            </div>
            <div className="hero-stat" role="listitem">
              {ICONS.library}
              <div><span className="num">63 frameworks</span><span className="cap">governed knowledge vault</span></div>
            </div>
            <div className="hero-stat" role="listitem">
              {ICONS.shield}
              <div><span className="num">2 mandatory gates</span><span className="cap">reviewer + challenger</span></div>
            </div>
            <div className="hero-stat" role="listitem">
              {ICONS.trace}
              <div><span className="num">100% traceable</span><span className="cap">every number labeled</span></div>
            </div>
          </div>
        </div>
      </section>

      <section className="panel" aria-labelledby="case-heading">
        <h2 id="case-heading">Describe the business problem</h2>
        <p className="muted panel-hint">
          Write it as you would brief a consultant: the company, the numbers
          you have, and the decision that must be made.
        </p>
        <textarea
          value={casePrompt}
          onChange={(e) => setCasePrompt(e.target.value)}
          placeholder="The company, its market, the key figures you know, and the decision the leadership team needs to make…"
          aria-label="Business problem description"
        />

        <div className="key-zone">
          {!showKey ? (
            <button type="button" className="ghost" onClick={() => setShowKey(true)}>
              {ICONS.key} Add your API key for best results
            </button>
          ) : (
            <>
              <label htmlFor="api-key">Your API key (for best results)</label>
              <input
                id="api-key"
                type="password"
                value={apiKey}
                onChange={(e) => updateKey(e.target.value)}
                placeholder="sk-ant-… · sk-… · sk-or-… · gsk_… · AIza…"
                autoComplete="off"
              />
              <p className="muted key-hint">
                Works with an Anthropic, OpenAI, OpenRouter, Groq, or Google
                key — the whole engagement runs on that provider&apos;s top
                model, with no daily limit. The key stays in this browser,
                travels only with your run, and is never stored on the server.
                Leave empty to use the free tier
                {health?.free_tier_quota
                  ? ` (${health.free_tier_quota} engagements/day)`
                  : ""}.
              </p>
            </>
          )}
        </div>

        {error && <p className="error" role="alert">{error}</p>}
        <div className="run-row">
          <button onClick={submit} disabled={submitting || casePrompt.trim().length < 40}>
            {submitting ? "Starting…" : <>Run engagement {ICONS.arrow}</>}
          </button>
          <span className="muted run-meta">
            ~13 agents · 5–15 minutes · no account needed
          </span>
        </div>
      </section>

      <section className="how">
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
            <p>Financial, market, operations, strategy, and risk analysts work a MECE issue tree.</p>
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
        <p className="muted learn-note">
          After every engagement, the reviewer and challenger findings are
          distilled into durable process lessons that guard all future runs —
          the agent gets sharper with each case. See{" "}
          <Link href="/lessons">Lessons</Link> and your{" "}
          <Link href="/engagements">engagement history</Link> (kept per
          browser).
        </p>
      </section>
    </div>
  );
}
