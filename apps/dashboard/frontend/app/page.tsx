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
  image: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect width="18" height="18" x="3" y="3" rx="2" ry="2" /><circle cx="9" cy="9" r="2" />
      <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
    </svg>
  ),
  close: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 6 6 18" /><path d="m6 6 12 12" />
    </svg>
  ),
};

const MAX_IMAGES = 6;
const MAX_EDGE = 1568; // Anthropic/OpenAI vision sweet spot — downscale to fit

// Read an image file, downscale its longest edge to MAX_EDGE, and return a
// JPEG data URL. Keeps payloads small (server caps each at ~5 MB) and strips
// nothing the model needs to read a chart or screenshot.
function downscaleImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read image"));
    reader.onload = () => {
      const img = new window.Image();
      img.onerror = () => reject(new Error("Could not decode image"));
      img.onload = () => {
        const scale = Math.min(1, MAX_EDGE / Math.max(img.width, img.height));
        const w = Math.max(1, Math.round(img.width * scale));
        const h = Math.max(1, Math.round(img.height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) return reject(new Error("Canvas unavailable"));
        ctx.drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL("image/jpeg", 0.85));
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  });
}

export default function Home() {
  const router = useRouter();
  const [casePrompt, setCasePrompt] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [images, setImages] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);

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

  async function addFiles(files: File[]) {
    const pics = files.filter((f) => f.type.startsWith("image/"));
    if (!pics.length) return;
    setError(null);
    const room = MAX_IMAGES - images.length;
    if (room <= 0) {
      setError(`You can attach up to ${MAX_IMAGES} images.`);
      return;
    }
    try {
      const encoded = await Promise.all(pics.slice(0, room).map(downscaleImage));
      setImages((prev) => [...prev, ...encoded].slice(0, MAX_IMAGES));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function onPaste(e: React.ClipboardEvent) {
    const files = Array.from(e.clipboardData.files);
    if (files.some((f) => f.type.startsWith("image/"))) {
      e.preventDefault(); // keep binary out of the text box
      void addFiles(files);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    void addFiles(Array.from(e.dataTransfer.files));
  }

  function removeImage(idx: number) {
    setImages((prev) => prev.filter((_, i) => i !== idx));
  }

  async function submit() {
    setError(null);
    setSubmitting(true);
    try {
      const { id } = await api.createEngagement(
        casePrompt,
        apiKey.trim(),
        images,
      );
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
        {health?.mock && (
          <div className="demo-banner" role="status">
            <strong>Demo mode — output will not be real analysis.</strong> The
            server is running with <code>STRATAGENT_MOCK=1</code>: no AI model
            is called and every engagement returns canned placeholder text. Add
            a provider API key and restart without the mock flag for real runs.
          </div>
        )}
        <h2 id="case-heading">Describe the business problem</h2>
        <p className="muted panel-hint">
          Write it as you would brief a consultant: the company, the numbers
          you have, and the decision that must be made. You can also paste
          charts, graphs, or screenshots directly into the box — the analysts
          will read them.
        </p>
        <div
          className={`case-input${dragging ? " dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <textarea
            value={casePrompt}
            onChange={(e) => setCasePrompt(e.target.value)}
            onPaste={onPaste}
            placeholder="The company, its market, the key figures you know, and the decision the leadership team needs to make… (paste a chart or screenshot anytime)"
            aria-label="Business problem description"
          />
          {images.length > 0 && (
            <div className="thumb-strip" aria-label="Attached images">
              {images.map((src, i) => (
                <div className="thumb" key={i}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={src} alt={`Attached image ${i + 1}`} />
                  <button
                    type="button"
                    className="thumb-remove"
                    onClick={() => removeImage(i)}
                    aria-label={`Remove image ${i + 1}`}
                  >
                    {ICONS.close}
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="case-input-foot">
            <label className="attach-btn">
              {ICONS.image} Add images
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => {
                  void addFiles(Array.from(e.target.files ?? []));
                  e.target.value = "";
                }}
                hidden
              />
            </label>
            <span className="muted attach-hint">
              {images.length > 0
                ? `${images.length} of ${MAX_IMAGES} attached`
                : "Paste or drag to attach charts & screenshots"}
            </span>
          </div>
        </div>

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
                placeholder="sk-ant-… · sk-… · sk-or-… · csk-… · gsk_… · AIza…"
                autoComplete="off"
              />
              <p className="muted key-hint">
                Works with an Anthropic, OpenAI, OpenRouter, Cerebras, Groq, or
                Google key — the whole engagement runs on that provider&apos;s
                top model, with no daily limit. The key stays in this browser,
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
        <p className="muted privacy-note">
          Privacy: no account, no tracking. Your problem statement and the
          report are stored only to show you the result, then automatically
          deleted after {health?.retention_days ?? 5} days. API keys are never
          stored. Don&apos;t paste anything you can&apos;t share with a
          third-party AI provider.
        </p>
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
