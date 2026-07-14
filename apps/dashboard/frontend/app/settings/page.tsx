"use client";

import { useEffect, useState } from "react";
import { clearApiKey, getApiKey, setApiKey } from "@/lib/api";

const KeyIcon = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z" />
    <circle cx="16.5" cy="7.5" r=".5" fill="currentColor" />
  </svg>
);

export default function SettingsPage() {
  const [hint, setHint] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const key = getApiKey();
    setHint(key ? `…${key.slice(-4)}` : null);
  }, []);

  function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    const key = keyInput.trim();
    if (!key.startsWith("sk-ant-")) {
      setError("That doesn't look like an Anthropic API key (should start with sk-ant-)");
      return;
    }
    setApiKey(key);
    setHint(`…${key.slice(-4)}`);
    setKeyInput("");
    setSaved(true);
  }

  function remove() {
    clearApiKey();
    setHint(null);
    setSaved(false);
  }

  return (
    <div style={{ maxWidth: 640 }}>
      <h1>API key</h1>

      <h2 style={{ display: "flex", alignItems: "center", gap: ".5rem" }}>
        {KeyIcon} Your Anthropic API key
      </h2>
      <p className="muted" style={{ fontSize: ".92rem", marginBottom: "1rem" }}>
        The key is stored <strong>only in this browser</strong> (localStorage).
        It is sent to the server when you run an engagement, used for that run,
        and never stored there. Create a key at{" "}
        <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer">
          console.anthropic.com
        </a>
        .
      </p>

      {hint ? (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
            <div>
              <strong>Key in this browser:</strong>{" "}
              <code style={{ background: "var(--color-muted)", padding: ".15rem .5rem", borderRadius: 4 }}>
                sk-ant-{hint}
              </code>
              <p className="muted" style={{ fontSize: ".85rem", marginTop: ".4rem" }}>
                Engagements run on your account with no daily limit.
              </p>
            </div>
            <button className="danger" onClick={remove}>
              Remove key
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={save} className="card">
          <label htmlFor="api-key">API key</label>
          <input
            id="api-key"
            type="password"
            placeholder="sk-ant-…"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            autoComplete="off"
            required
            minLength={20}
          />
          <button type="submit" disabled={keyInput.trim().length < 20} style={{ marginTop: ".9rem" }}>
            Save in this browser
          </button>
        </form>
      )}
      {saved && <p className="success">API key saved in this browser.</p>}
      {error && <p className="error">{error}</p>}

      <h2>Without a key</h2>
      <div className="card">
        <p style={{ fontSize: ".92rem" }}>
          If the server operator has configured a shared key, you can run a
          small number of free engagements per day without adding your own.
          Adding your key removes that limit — your key, your account, no
          markup.
        </p>
      </div>
    </div>
  );
}
