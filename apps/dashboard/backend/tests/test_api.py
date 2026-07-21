"""Dashboard API tests — run entirely in mock mode (no provider API calls).

No accounts: identity is the anonymous X-Client-Id header.
The server holds the provider keys; users need no key to run cases.
"""

from __future__ import annotations

import asyncio
import json
import os

os.environ["STRATAGENT_MOCK"] = "1"
os.environ["STRATAGENT_DAILY_QUOTA"] = "3"

import pytest
from fastapi.testclient import TestClient

from app import config, db
from app.main import app
from app.pipeline import prompts
from app.pipeline.engine import ANALYSTS, PHASES, run_engagement

CASE = (
    "A regional grocery chain with $800M revenue has seen margins compress "
    "from 4% to 2% over three years. Should it double down on private label, "
    "exit low-density stores, or merge with a competitor?"
)

CID_A = {"X-Client-Id": "browser-aaaa-1111"}
CID_B = {"X-Client-Id": "browser-bbbb-2222"}

# A minimal VALID quant ledger (ADR-009). The quant gate fails closed on a
# missing block, so every fake engagement-manager output must carry one or the
# engagement degrades to an interim memo and burns the deterministic fix budget.
QUANT = (
    "\n```quant\n"
    "[\n"
    ' {"id":"F1","kind":"fact","label":"Revenue","value":800,'
    '"unit":"USD_M","basis":"annual","source":"case prompt"},\n'
    ' {"id":"A1","kind":"assumption","label":"Margin uplift","value":0.01,'
    '"unit":"RATIO","basis":"annual","source":"benchmark","low":0.005,"high":0.02},\n'
    ' {"id":"D1","kind":"derived","label":"EBITDA uplift","value":8,'
    '"unit":"USD_M","basis":"annual","formula":"F1 * A1"}\n'
    "]\n"
    "```\n"
)


def fake_output(agent: str) -> str:
    """Default fake agent output: parseable verdicts for governance agents and
    a valid quant ledger for the engagement manager."""
    if agent == "reviewer":
        return "Verdict: approved"
    if agent == "challenger":
        return "Verdict: stands"
    if agent == "engagement-manager":
        return f"output-of-{agent}" + QUANT
    return f"output-of-{agent}"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.reset_for_tests()
    with TestClient(app) as test_client:
        yield test_client
    db.reset_for_tests()


def test_health(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True and body["mock"] is True and body["free_tier"] is True


def test_golden_case_grading_route_is_not_mounted(client):
    """2026-07-19 RC1 adversarial review finding: an earlier ADR-014 draft
    claimed `app.pipeline.grading` (golden-case grading) is "already live,
    wired into app/routers/cases.py" — but `cases.router` is never
    `include_router`'d in app/main.py (only `engagements` and `admin` are),
    matching main.py's own comment that the cases/evals surface was
    deliberately removed from the public product. This test pins that fact
    structurally: if `cases.router` is ever mounted, this test starts
    failing, which is the correct signal to also update ADR-014 §3.5/§6.
    """
    response = client.post("/api/cases", json={"case": "x", "official_answer": "y"})
    assert response.status_code == 404


def test_requires_client_id(client):
    assert client.get("/api/engagements").status_code == 400
    assert (
        client.post("/api/engagements", json={"case_prompt": CASE}).status_code == 400
    )
    bad = client.get("/api/engagements", headers={"X-Client-Id": "x!"})
    assert bad.status_code == 400


def test_agent_prompts_load():
    # engagement-manager uses an inline system prompt (no agents/*.md file);
    # the analyst-group phase label isn't a single agent either.
    inline = {"engagement-manager", "5 specialist analysts"}
    for _, agent in PHASES:
        if agent in inline:
            continue
        assert len(prompts.agent_system_prompt(agent)) > 100
    for agent in ANALYSTS:
        assert len(prompts.agent_system_prompt(agent)) > 100
    assert "profit" in prompts.vault_framework_index()


def test_governance_prompts_keep_the_vocabulary_the_parsers_need():
    """The prompts are the core IP and have no other regression gate. The
    dashboard's verdict parsers key off specific tokens — a prompt edit that
    drops them silently breaks governance (verdicts stop parsing → fail closed
    → every run goes interim). Pin the contract between prompt and parser."""
    reviewer = prompts.agent_system_prompt("reviewer").lower()
    assert "verdict" in reviewer
    assert "approved" in reviewer and "needs_rework" in reviewer

    challenger = prompts.agent_system_prompt("challenger").lower()
    assert "verdict" in challenger
    assert "stands" in challenger and "needs_rework" in challenger

    report = prompts.agent_system_prompt("report-writer").lower()
    assert "recommendation" in report and "assumption" in report

    # Analysts must still instruct labeled assumptions — the evidence-
    # traceability guarantee depends on it.
    for analyst in ANALYSTS:
        assert "assumption" in prompts.agent_system_prompt(analyst).lower()


def test_full_engagement_mock_no_signup(client):
    """The whole flow works with nothing but a client id — no account."""
    created = client.post("/api/engagements", json={"case_prompt": CASE}, headers=CID_A)
    assert created.status_code == 202
    engagement_id = created.json()["id"]

    for _ in range(100):
        body = client.get(f"/api/engagements/{engagement_id}", headers=CID_A).json()
        if body["status"] in ("completed", "failed"):
            break
    assert body["status"] == "completed", body.get("error")
    assert "report-writer" in body["report_md"]

    events = db.list_events(engagement_id)
    types = [e["type"] for e in events]
    assert types[0] == "engagement_started"
    assert types[-1] == "engagement_completed"
    assert types.count("phase_completed") == len(PHASES)
    assert types.count("analyst_completed") == len(ANALYSTS)


def test_concurrency_cap_limits_simultaneous_engagements(tmp_path, monkeypatch):
    """No more than MAX_CONCURRENT_ENGAGEMENTS run their pipeline at once —
    excess work waits its turn rather than piling onto the single SQLite writer
    and shared provider quota."""
    import app.pipeline.engine as engine

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "conc.db")
    monkeypatch.setattr(config, "MAX_CONCURRENT_ENGAGEMENTS", 2)
    monkeypatch.setattr(engine, "_engagement_semaphore", None)  # rebuild at new cap
    db.reset_for_tests()

    live = 0
    peak = 0
    gate = asyncio.Event()

    async def fake_call(agent, system, user, **kw):
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        if agent == "case-classifier":
            await gate.wait()  # hold the first phase so runs overlap
        live -= 1
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands"
        return fake_output(agent)

    async def drive():
        ids = [db.create_engagement("browser-x", CASE) for _ in range(5)]
        tasks = [
            asyncio.create_task(run_engagement(i, CASE, call=fake_call)) for i in ids
        ]
        await asyncio.sleep(0.1)  # let admitted runs reach the gate
        admitted = peak
        gate.set()  # release everyone
        await asyncio.gather(*tasks)
        return admitted

    admitted = asyncio.run(drive())
    assert admitted <= 2, f"{admitted} engagements ran at once, cap was 2"
    db.reset_for_tests()


def test_telemetry_records_spans_for_every_phase_and_analyst(tmp_path, monkeypatch):
    """The dashboard emits real operational telemetry via packages/telemetry.

    Before this wiring the shipping product had none — incidents were diagnosed
    by grepping docker logs. Spans must cover each phase AND each analyst (the
    analysts are the slow stretch an operator needs visibility into).
    """
    from app import telemetry_bridge

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "tel.db")
    monkeypatch.setattr(config, "TELEMETRY_ENABLED", True)
    monkeypatch.setattr(config, "TELEMETRY_DIR", str(tmp_path / "telemetry"))
    monkeypatch.setattr(config, "TELEMETRY_SAMPLE_RATE", 1.0)
    telemetry_bridge.reset_for_tests()
    db.reset_for_tests()

    async def fake_call(agent, system, user, **kw):
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid, CASE, call=fake_call))

    trace = tmp_path / "telemetry" / f"{eid}.jsonl"
    assert trace.exists(), "no telemetry trace written for the engagement"
    events = [json.loads(line) for line in trace.read_text().splitlines() if line]
    agents = {e["agent_name"] for e in events}
    phases = {e["phase"] for e in events}

    # every analyst got its own span
    assert set(ANALYSTS) <= agents, f"analysts missing from telemetry: {agents}"
    # and the governance phases are visible to an operator
    assert {"review", "challenge", "reporting"} <= phases
    # spans carry real durations and terminal statuses
    finished = [e for e in events if e["status"] == "finished"]
    assert finished and all(e["duration_ms"] is not None for e in finished)
    telemetry_bridge.reset_for_tests()
    db.reset_for_tests()


def test_telemetry_feeds_the_cores_quality_analytics(tmp_path, monkeypatch):
    """The dashboard's traces must be consumable by the core's analytics, not
    just well-formed. quality_analytics() computes reviewer_pass_rate from
    metadata['verdict'] on terminal REVIEW events — pin that contract, since a
    silent break turns the ops dashboard into zeros that look like health."""
    from app import telemetry_bridge
    from telemetry import JSONLSink, quality_analytics

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "qual.db")
    monkeypatch.setattr(config, "TELEMETRY_ENABLED", True)
    monkeypatch.setattr(config, "TELEMETRY_DIR", str(tmp_path / "telemetry"))
    monkeypatch.setattr(config, "TELEMETRY_SAMPLE_RATE", 1.0)
    telemetry_bridge.reset_for_tests()
    db.reset_for_tests()

    async def fake_call(agent, system, user, **kw):
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands_with_caveats"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid, CASE, call=fake_call))

    events = JSONLSink(tmp_path / "telemetry").read(eid)
    analytics = quality_analytics(events)
    # The governance outcome is legible to the core's analytics, not zeros.
    assert analytics.reviewer_pass_rate == 1.0
    assert analytics.challenger_intervention_rate == 1.0  # stands_with_caveats
    assert analytics.needs_rework_frequency == 0.0
    telemetry_bridge.reset_for_tests()
    db.reset_for_tests()


def test_telemetry_failure_never_breaks_an_engagement(tmp_path, monkeypatch):
    """Observability is best-effort. If the recorder explodes, the engagement
    must still complete — telemetry may never become load-bearing."""
    from app import telemetry_bridge

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "telfail.db")
    telemetry_bridge.reset_for_tests()
    db.reset_for_tests()

    class Exploding:
        def span(self, **kw):
            raise RuntimeError("sink on fire")

        def emit(self, **kw):
            raise RuntimeError("sink on fire")

    monkeypatch.setattr(telemetry_bridge, "recorder", lambda: Exploding())

    async def fake_call(agent, system, user, **kw):
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid, CASE, call=fake_call))
    assert db.get_engagement(eid)["status"] == "completed"
    telemetry_bridge.reset_for_tests()
    db.reset_for_tests()


def test_engine_direct_with_fake_agent(tmp_path, monkeypatch):
    """The engine accepts an injectable call — verify context threading."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "engine.db")
    db.reset_for_tests()
    seen: list[str] = []

    async def fake_call(agent, system, user, **kw):
        seen.append(agent)
        assert len(system) > 100  # real prompt loaded
        return fake_output(agent)

    engagement_id = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(engagement_id, CASE, call=fake_call))

    engagement = db.get_engagement(engagement_id)
    assert engagement["status"] == "completed"
    assert engagement["report_md"] == "output-of-report-writer"
    # governance ran before the report and after the analysts
    assert seen.index("reviewer") > max(seen.index(a) for a in ANALYSTS)
    assert seen.index("challenger") > seen.index("reviewer")
    assert seen.index("report-writer") > seen.index("challenger")
    db.reset_for_tests()


def test_rework_loop_reconciles_then_completes(tmp_path, monkeypatch):
    """Reviewer fails once; the Engagement Manager re-reconciles (NOT the
    individual analysts); review passes on the retry and completes review-ready."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "rework.db")
    monkeypatch.setattr(config, "MAX_REWORK", 1)
    db.reset_for_tests()
    calls: list[str] = []
    review_calls = {"n": 0}

    async def fake_call(agent, system, user, **kw):
        calls.append(agent)
        if agent == "reviewer":
            review_calls["n"] += 1
            if review_calls["n"] == 1:
                return "Verdict: needs_rework — AL-10 collision unresolved"
            return (
                "Verdict: approved — all five checks pass against the canonical ledger"
            )
        if agent == "challenger":
            return "Verdict: stands_with_caveats"
        return fake_output(agent)

    engagement_id = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(engagement_id, CASE, call=fake_call))

    engagement = db.get_engagement(engagement_id)
    assert engagement["status"] == "completed"
    # reviewer ran twice; the EM reconciled twice (proactive + 1 rework);
    # the individual analysts ran ONCE (not re-dispatched — that would re-collide)
    assert calls.count("reviewer") == 2
    assert calls.count("engagement-manager") == 2
    assert calls.count("financial-analyst") == 1
    assert calls.count("market-analyst") == 1

    events = db.list_events(engagement_id)
    types = [e["type"] for e in events]
    assert "rework_started" in types
    assert "rework_completed" in types
    completed = next(e for e in events if e["type"] == "engagement_completed")
    assert completed["payload"]["review_ready"] is True
    assert completed["payload"]["review_verdict"] == "approved"
    db.reset_for_tests()


def test_rework_gives_up_and_writes_interim(tmp_path, monkeypatch):
    """Reviewer never approves; after MAX_REWORK the engagement still completes
    but is flagged not review-ready (honest interim report)."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "interim.db")
    monkeypatch.setattr(config, "MAX_REWORK", 1)
    db.reset_for_tests()

    async def fake_call(agent, system, user, **kw):
        if agent == "reviewer":
            return "Verdict: needs_rework\n[financial-analyst]: still contradictory"
        if agent == "challenger":
            return "Verdict: needs_rework"
        return fake_output(agent)

    engagement_id = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(engagement_id, CASE, call=fake_call))

    engagement = db.get_engagement(engagement_id)
    assert engagement["status"] == "completed"  # still delivers a memo, not a crash
    completed = next(
        e for e in db.list_events(engagement_id) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is False
    db.reset_for_tests()


def test_reflection_learns_lessons_on_blocked_run(tmp_path, monkeypatch):
    """A blocked engagement distils LESSON: lines into the lessons store; the
    next engagement injects them as guardrails."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "learn.db")
    monkeypatch.setattr(config, "MAX_REWORK", 0)
    db.reset_for_tests()
    seen_prompts: list[str] = []

    async def fake_call(agent, system, user, **kw):
        seen_prompts.append(user)
        if agent == "reviewer":
            return "Verdict: needs_rework"
        if agent == "challenger":
            return "Verdict: needs_rework"
        if agent == "reflector":
            return (
                "LESSON: For acquisition cases, include a commercial"
                " go-to-market branch.\n"
                "LESSON: Assign globally-unique assumption IDs across all analysts.\n"
                "NONE"
            )
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid, CASE, call=fake_call))

    lessons = db.list_lessons()
    assert len(lessons) == 2
    texts = {row["text"] for row in lessons}
    assert any("commercial go-to-market" in t for t in texts)

    events = db.list_events(eid)
    assert any(e["type"] == "lesson_learned" for e in events)

    # a second engagement injects the learned lessons into the issue-tree prompt
    seen_prompts.clear()
    eid2 = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid2, CASE, call=fake_call))
    assert any("Standing lessons from past engagements" in p for p in seen_prompts)
    db.reset_for_tests()


def test_standing_lessons_reach_engagement_manager_and_report_writer(
    tmp_path, monkeypatch
):
    """2026-07-21 finding: _standing_lessons() was only ever injected into the
    issue-tree-generator prompt — the one phase with no ability to act on a
    lesson like "never introduce an orphan number", since it builds the MECE
    tree, not ledger atoms or report prose. The Engagement Manager (who
    authors the ledger and Breakeven column) and report-writer (who carries
    numbers into the final report) never saw stored lessons at all, so the
    learning loop could capture a correct insight and still have no way to
    act on it next run. Fixed by also injecting into reconcile_context (EM)
    and final_context (challenger + report-writer)."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "lessons_reach_em.db")
    db.reset_for_tests()
    assert db.add_lesson("Never introduce an orphan number not in the ledger.")
    captured: dict[str, str] = {}

    async def fake_call(agent, system, user, **kw):
        if agent in ("engagement-manager", "report-writer", "challenger"):
            captured[agent] = user
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid, CASE, call=fake_call))

    for agent in ("engagement-manager", "report-writer", "challenger"):
        assert "Standing lessons from past engagements" in captured[agent], agent
        assert "orphan number" in captured[agent]
    db.reset_for_tests()


def test_reflection_dedupes_lessons(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "dedupe.db")
    db.reset_for_tests()
    assert db.add_lesson("Assign unique assumption IDs.") is True
    assert db.add_lesson("Assign unique assumption IDs.") is False  # duplicate
    assert len(db.list_lessons()) == 1
    db.reset_for_tests()


def test_reflection_learns_on_every_engagement(tmp_path, monkeypatch):
    """The learning loop runs on approved engagements too — every engagement
    can mint lessons that improve future runs."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "clean.db")
    db.reset_for_tests()
    reflector_prompts: list[str] = []

    async def fake_call(agent, system, user, **kw):
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands_with_caveats"
        if agent == "reflector":
            reflector_prompts.append(user)
            return "LESSON: State the breakeven for every load-bearing assumption."
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid, CASE, call=fake_call))
    assert len(reflector_prompts) == 1
    # approved runs get the "gates cleared" framing, not the failure framing
    assert "gates cleared" in reflector_prompts[0]
    lessons = db.list_lessons()
    assert len(lessons) == 1
    assert "breakeven" in lessons[0]["text"]
    db.reset_for_tests()


def test_parse_lessons_leakage_guard():
    from app.pipeline.engine import _parse_lessons

    parsed = _parse_lessons(
        "LESSON: Include a commercial branch for M&A.\n"
        "some noise line\n"
        "LESSON: NONE\n"
        "LESSON:   \n"
        "lesson: assign unique ids"  # lowercase prefix still caught
    )
    assert "Include a commercial branch for M&A." in parsed
    assert "assign unique ids" in parsed
    assert all(p and p.upper() != "NONE" for p in parsed)


def test_verdict_parsers():
    from app.pipeline.engine import _challenger_verdict, _reviewer_verdict

    assert (
        _reviewer_verdict("Final verdict: needs_rework, 2 checks fail")
        == "needs_rework"
    )
    assert _reviewer_verdict("VERDICT: APPROVED") == "approved"
    # Fail closed: an unreadable governance verdict is NOT a pass. It yields an
    # interim memo (review_ready=False), never a report claiming a gate cleared.
    assert _reviewer_verdict("no token here") == "needs_rework"
    assert _challenger_verdict("no token here") == "needs_rework"
    assert _challenger_verdict("Verdict: stands_with_caveats") == "stands_with_caveats"
    assert _challenger_verdict("verdict: stands") == "stands"
    assert _challenger_verdict("verdict: needs_rework") == "needs_rework"


def test_engine_failure_marks_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "fail.db")
    db.reset_for_tests()

    async def broken_call(agent, system, user, **kw):
        raise RuntimeError("api exploded")

    engagement_id = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(engagement_id, CASE, call=broken_call))
    engagement = db.get_engagement(engagement_id)
    assert engagement["status"] == "failed"
    assert "api exploded" in engagement["error"]
    db.reset_for_tests()


def test_rate_limit_pauses_then_resumes_from_checkpoint(tmp_path, monkeypatch):
    """When all providers are rate-limited mid-run, the engagement pauses
    (not fails); a resume reconstructs completed phases/analysts from the event
    checkpoint and finishes WITHOUT re-running them."""
    from app.pipeline.providers import AllProvidersRateLimitedError

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "resume.db")
    monkeypatch.setattr(
        config, "AUTO_RESUME", False
    )  # resume manually, deterministically
    db.reset_for_tests()
    calls: list[str] = []
    trip = {"fired": False}

    async def fake_call(agent, system, user, **kw):
        calls.append(agent)
        if agent == "engagement-manager" and not trip["fired"]:
            trip["fired"] = True  # fail once, at reconcile — after all analysts
            raise AllProvidersRateLimitedError(30.0)
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid, CASE, call=fake_call))

    assert db.get_engagement(eid)["status"] == "paused"
    types = [e["type"] for e in db.list_events(eid)]
    assert "engagement_paused" in types
    assert "engagement_failed" not in types
    assert sorted(c for c in calls if c in ANALYSTS) == sorted(ANALYSTS)

    calls.clear()
    asyncio.run(run_engagement(eid, CASE, call=fake_call, resume_count=1))

    engagement = db.get_engagement(eid)
    assert engagement["status"] == "completed"
    assert engagement["report_md"] == "output-of-report-writer"
    # nothing before reconcile was re-run — served from the checkpoint
    assert not any(c in ANALYSTS for c in calls)
    assert "case-classifier" not in calls and "issue-tree-generator" not in calls
    # reconcile onward DID run on resume (that's where it had paused)
    assert "engagement-manager" in calls
    events = db.list_events(eid)
    assert any(e["type"] == "engagement_resumed" for e in events)
    assert events[-1]["type"] == "engagement_completed"
    db.reset_for_tests()


def test_max_auto_resumes_eventually_fails(tmp_path, monkeypatch):
    """A permanently rate-limited chain fails only after exhausting retries —
    and even then reports saved progress, never a lost run."""
    from app.pipeline.providers import AllProvidersRateLimitedError

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "giveup.db")
    monkeypatch.setattr(config, "AUTO_RESUME", False)
    monkeypatch.setattr(config, "MAX_AUTO_RESUMES", 2)
    db.reset_for_tests()

    async def always_limited(agent, system, user, **kw):
        raise AllProvidersRateLimitedError(30.0)

    eid = db.create_engagement("browser-x", CASE)
    # resume_count already at the cap → this attempt gives up
    asyncio.run(run_engagement(eid, CASE, call=always_limited, resume_count=2))
    engagement = db.get_engagement(eid)
    assert engagement["status"] == "failed"
    assert "progress is saved" in engagement["error"].lower()
    db.reset_for_tests()


def test_resume_delay_backs_off_exponentially():
    """A spent retry-after must not mean retrying every 20s until the attempt
    budget is gone — each attempt waits longer, so a provider window that needs
    minutes to refill actually gets them."""
    from app.pipeline.engine import _resume_delay

    delays = [_resume_delay(0.0, n) for n in range(config.MAX_AUTO_RESUMES)]
    # Each attempt is meaningfully longer than the last (jitter is ±25%, so
    # compare against the doubling rather than exact values).
    for earlier, later in zip(delays, delays[1:], strict=False):
        assert later > earlier
    assert delays[0] >= config.MIN_RESUME_DELAY * 0.75
    assert all(d <= config.MAX_RESUME_DELAY for d in delays)
    # total patience across the budget is minutes, not seconds
    assert sum(delays) > 600
    # A long advertised retry-after is honoured but MUST stay capped. Sampled
    # many times because jitter is random — a single draw would let an
    # over-cap bug pass ~60% of the time (it did).
    capped = [_resume_delay(10_000.0, 0) for _ in range(200)]
    assert max(capped) <= config.MAX_RESUME_DELAY, "jitter broke the max-delay cap"
    assert max(capped) > config.MAX_RESUME_DELAY * 0.7
    # ...and the cap holds at every attempt, not just the first
    for n in range(config.MAX_AUTO_RESUMES + 3):
        assert _resume_delay(10_000.0, n) <= config.MAX_RESUME_DELAY


def test_resume_delay_is_jittered_against_thundering_herd():
    """Concurrent engagements share one provider quota, so they hit the limit
    together. Identical delays would wake them in lockstep to collide again —
    the waits must be spread out."""
    from app.pipeline.engine import _resume_delay

    delays = {_resume_delay(30.0, 1) for _ in range(20)}
    assert len(delays) > 1, "resume delays are identical — herd will re-collide"
    # but still anchored near the intended backoff, not wild
    assert all(30.0 * 2 * 0.7 <= d <= 30.0 * 2 * 1.3 for d in delays)


def test_restart_recovery_resumes_free_tier_run(tmp_path, monkeypatch):
    """A run left paused by a server stop is adopted on the next startup and
    finishes from its checkpoint — not left on a countdown that never fires."""
    from app.pipeline.engine import recover_interrupted

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "recover.db")
    db.reset_for_tests()

    eid = db.create_engagement("browser-x", CASE)
    db.set_engagement_status(eid, "paused")

    # recover_interrupted schedules run_engagement as a task; await it so the
    # assertions see the finished run rather than racing the loop teardown.
    async def recover_and_drain():
        await recover_interrupted()
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        await asyncio.gather(*pending)

    asyncio.run(recover_and_drain())
    engagement = db.get_engagement(eid)
    assert engagement["status"] == "completed"  # mock mode runs the full pipeline
    assert engagement["report_md"]
    db.reset_for_tests()


def test_restart_recovery_does_not_silently_downgrade_byok(tmp_path, monkeypatch):
    """A BYOK run can't be resumed (the key was never stored). It must be closed
    honestly rather than quietly re-run on the free chain at lower quality."""
    from app.pipeline.engine import recover_interrupted

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "recover_byok.db")
    db.reset_for_tests()

    eid = db.create_engagement("browser-x", CASE, used_byok=True)
    db.set_engagement_status(eid, "paused")

    asyncio.run(recover_interrupted())
    engagement = db.get_engagement(eid)
    assert engagement["status"] == "failed"
    assert engagement["report_md"] is None  # never resumed on the free chain
    assert "never stored" in engagement["error"]
    assert any(e["type"] == "engagement_failed" for e in db.list_events(eid))
    db.reset_for_tests()


def test_used_byok_flag_stores_no_key_material(client):
    """The recovery flag must be a boolean, never the key itself."""
    key = "sk-ant-supersecret-recovery-key"
    client.post(
        "/api/engagements",
        json={"case_prompt": CASE, "api_key": key},
        headers=CID_A,
    )
    raw = (config.DB_PATH).read_bytes()
    assert b"supersecret" not in raw
    row = (
        db.connect()
        .execute("SELECT used_byok FROM engagements ORDER BY created_at DESC LIMIT 1")
        .fetchone()
    )
    assert row["used_byok"] == 1


def test_engagement_accepts_pasted_images(client):
    img = "data:image/png;base64," + "A" * 200
    created = client.post(
        "/api/engagements",
        json={"case_prompt": CASE, "images": [img]},
        headers=CID_A,
    )
    assert created.status_code == 202


def test_engagement_rejects_malformed_images(client):
    bad = client.post(
        "/api/engagements",
        json={"case_prompt": CASE, "images": ["https://example.com/x.png"]},
        headers=CID_A,
    )
    assert bad.status_code == 422


def test_aggregate_payload_ceiling(client):
    """Per-field caps allow ~42 MB in aggregate; the whole-request ceiling must
    reject that so one request can't pin memory or starve concurrent runs.

    This ~26 MB request still reaches Pydantic (under the 32 MB coarse ASGI
    backstop) and is rejected there with a precise 422 — the accurate limit for
    a "slightly too large" request stays intact after the backstop was added."""
    big = [
        "data:image/png;base64," + "A" * 6_500_000 for _ in range(4)
    ]  # ~26 MB total, each image individually under the 7 MB per-image cap
    resp = client.post(
        "/api/engagements",
        json={"case_prompt": CASE, "images": big},
        headers=CID_A,
    )
    assert resp.status_code == 422


def test_asgi_body_ceiling_rejects_unbounded_body_before_buffering():
    """The ASGI backstop rejects an over-large body at the transport layer with
    a 413 — for both a declared Content-Length and a chunked/streamed body that
    lies about (or omits) its length — so a multi-GB body can never buffer into
    memory ahead of Pydantic's caps. Uses a tiny cap and a raw ASGI harness so
    the test is fast and does not allocate real gigabytes."""
    import asyncio

    from app.main import MaxBodySizeMiddleware

    async def ok_app(scope, receive, send):
        # Drain the body, then 200 — the middleware must let small bodies through.
        while True:
            msg = await receive()
            if not msg.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = MaxBodySizeMiddleware(ok_app, max_bytes=1000)

    async def call(headers, chunks):
        sent = []
        chunk_iter = iter(chunks)

        async def receive():
            try:
                body = next(chunk_iter)
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": True,
                }
            except StopIteration:
                return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        scope = {"type": "http", "headers": headers}
        await app(scope, receive, send)
        start = next(m for m in sent if m["type"] == "http.response.start")
        return start["status"]

    # Fast path: honest, over-large Content-Length → 413 before any body read.
    status = asyncio.run(call([(b"content-length", b"5000")], [b"x" * 5000]))
    assert status == 413

    # Streamed / lying length: no Content-Length, body crosses the cap mid-stream.
    status = asyncio.run(call([], [b"x" * 400, b"x" * 400, b"x" * 400]))
    assert status == 413

    # Legitimate small body passes through untouched.
    status = asyncio.run(call([], [b"x" * 200]))
    assert status == 200


def test_cors_does_not_advertise_credentials(client):
    """Auth is header-based (X-Client-Id / X-Admin-Token), so credentialed CORS
    is off — a misconfigured '*' origin can never be paired with credentials."""
    resp = client.options(
        "/api/engagements",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-credentials" not in {k.lower() for k in resp.headers}


def test_framework_note_rejects_path_traversal():
    """framework_note joins a name onto a filesystem path; a traversal name must
    be refused (defense in depth — names come from globbed vault files today)."""
    from app.pipeline import prompts

    for evil in ["../config", "../../etc/passwd", "a/b", "..\\..\\x", ".."]:
        assert prompts.framework_note(evil) is None


def test_pasted_images_never_persisted(client, tmp_path):
    """Like API keys, pasted images travel per-run and never touch the DB."""
    marker = "UNIQUEIMGMARKERZZZ"
    img = "data:image/png;base64," + marker + "A" * 60
    eid = client.post(
        "/api/engagements",
        json={"case_prompt": CASE, "images": [img]},
        headers=CID_A,
    ).json()["id"]
    client.get(f"/api/engagements/{eid}/events", headers=CID_A)
    raw = (tmp_path / "test.db").read_bytes()
    assert marker.encode() not in raw


def test_feedback_roundtrip_and_isolation(client):
    """A reader can comment on their own report; nobody else can write to it.

    Feedback is the only channel through which a real user tells us the analysis
    was wrong, so it is stored verbatim.
    """
    eid = client.post(
        "/api/engagements", json={"case_prompt": CASE}, headers=CID_A
    ).json()["id"]

    posted = client.post(
        f"/api/engagements/{eid}/feedback",
        json={
            "comment": "A24 says the downside is €900k but the whole project "
            "costs €17k — the risk numbers never met the model.",
            "rating": "not_helpful",
        },
        headers=CID_A,
    )
    assert posted.status_code == 201

    listed = client.get(f"/api/engagements/{eid}/feedback", headers=CID_A).json()
    assert len(listed) == 1
    assert "A24" in listed[0]["comment"] and listed[0]["rating"] == "not_helpful"

    # another browser can neither read nor write this engagement's feedback
    assert (
        client.get(f"/api/engagements/{eid}/feedback", headers=CID_B).status_code == 404
    )
    assert (
        client.post(
            f"/api/engagements/{eid}/feedback",
            json={"comment": "injected"},
            headers=CID_B,
        ).status_code
        == 404
    )

    # a comment is never gated behind picking a rating
    assert (
        client.post(
            f"/api/engagements/{eid}/feedback",
            json={"comment": "no rating supplied"},
            headers=CID_A,
        ).status_code
        == 201
    )
    # but a bogus rating is rejected
    assert (
        client.post(
            f"/api/engagements/{eid}/feedback",
            json={"comment": "x", "rating": "amazing"},
            headers=CID_A,
        ).status_code
        == 422
    )


def test_admin_requires_token_and_404s_when_unconfigured(client, monkeypatch):
    """The operator console exposes every client's data. With no token
    configured the routes must not exist at all; with a wrong token they must
    look identical to a probe."""
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    assert client.get("/api/admin/overview").status_code == 404

    monkeypatch.setattr(config, "ADMIN_TOKEN", "s3cret-operator-token")
    assert client.get("/api/admin/overview").status_code == 404  # no token
    assert (
        client.get(
            "/api/admin/overview", headers={"X-Admin-Token": "wrong"}
        ).status_code
        == 404
    )  # wrong token → 404, not 403: reveal nothing
    ok = client.get(
        "/api/admin/overview", headers={"X-Admin-Token": "s3cret-operator-token"}
    )
    assert ok.status_code == 200


def test_admin_sees_all_clients_and_answers_the_operator_questions(client, monkeypatch):
    """Is it working, for whom, and where does it break?"""
    monkeypatch.setattr(config, "ADMIN_TOKEN", "tok")
    hdr = {"X-Admin-Token": "tok"}

    a = client.post(
        "/api/engagements", json={"case_prompt": CASE}, headers=CID_A
    ).json()["id"]
    client.post("/api/engagements", json={"case_prompt": CASE}, headers=CID_B)
    client.post(
        f"/api/engagements/{a}/feedback",
        json={"comment": "conversion assumption looks 2x too high"},
        headers=CID_A,
    )

    overview = client.get("/api/admin/overview", headers=hdr).json()
    assert overview["total"] == 2
    assert overview["users"] == 2  # how many people used it
    assert overview["free_runs"] == 2  # free vs BYOK split
    assert overview["byok_runs"] == 0
    assert overview["feedback_count"] == 1

    rows = client.get("/api/admin/engagements", headers=hdr).json()
    assert {r["client_id"] for r in rows} == {"browser-aaaa-1111", "browser-bbbb-2222"}
    mine = next(r for r in rows if r["id"] == a)
    assert mine["feedback"][0]["comment"].startswith("conversion")
    assert "failed_at" in mine and "phases_completed" in mine


def test_admin_reports_the_failing_step(tmp_path, monkeypatch):
    """'At what step is it failing' — derived from the event log, so it works
    for runs that failed before this view existed."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "fail.db")
    db.reset_for_tests()

    async def die_at_issue_tree(agent, system, user, **kw):
        if agent == "issue-tree-generator":
            raise RuntimeError("provider exploded")
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid, CASE, call=die_at_issue_tree))

    row = next(r for r in db.admin_engagements() if r["id"] == eid)
    assert row["status"] == "failed"
    assert row["failed_at"] == "issue_tree", f"wrong failing step: {row['failed_at']}"
    assert row["phases_completed"] == 4  # classify..framing landed before the break
    db.reset_for_tests()


def test_byok_run_is_visible_to_admin_without_storing_the_key(client, monkeypatch):
    """Admin can answer 'who used their own key' — from a boolean, never a key."""
    monkeypatch.setattr(config, "ADMIN_TOKEN", "tok")
    client.post(
        "/api/engagements",
        json={"case_prompt": CASE, "api_key": "sk-ant-never-stored-anywhere"},
        headers=CID_A,
    )
    overview = client.get(
        "/api/admin/overview", headers={"X-Admin-Token": "tok"}
    ).json()
    assert overview["byok_runs"] == 1 and overview["free_runs"] == 0
    raw = config.DB_PATH.read_bytes()
    assert b"never-stored-anywhere" not in raw


def test_public_benchmark_and_lessons_routes_are_gone(client):
    """Removed for everyone: every engagement now feeds the learning loop
    automatically, so there was nothing for a user to do on those pages."""
    assert client.get("/api/cases", headers=CID_A).status_code == 404
    assert client.get("/api/lessons", headers=CID_A).status_code == 404


STRUCTURED_CASE = """Client: A premium European coffee chain, 320 stores.
Annual Revenue: EUR640M. Current Profit: EUR32M.

Section 1 - Problem Structuring

Question 1

How would you structure the problem?

Question 2

What hypotheses would you develop before requesting data?

Section 10 - Quantitative Analysis

Question 38

Each store serves 600 customers/day.
Traffic falls 8%.
Average ticket is EUR9.
Estimate annual revenue impact.

Question 39

Delivery commissions equal 28%.
Store margin is 18%.
Is delivery profitable?

Question 50

The CEO asks, "What would you do if this were your own company?"
How would you answer?
"""


def test_extracts_the_questions_the_client_actually_asked():
    """A structured case interview is a question list, not a narrative brief.

    Regression from a real run: a 50-question case produced a fluent memo that
    answered ~5 of them, and the reviewer approved — because it graded coverage
    against the issue tree, which the pipeline generates itself.
    """
    asked = prompts.explicit_questions(STRUCTURED_CASE)
    assert len(asked) == 5, asked

    # Multi-line arithmetic asks must survive INTACT, with their numbers — a
    # naive "lines ending in ?" scan drops them (Q38 ends in a period) and those
    # are exactly the questions with one verifiable right answer.
    q38 = next(q for q in asked if "600 customers" in q)
    assert "8%" in q38 and "EUR9" in q38 and "Estimate annual revenue impact" in q38

    # Section headers must not leak in as questions.
    assert not any(q.lower().startswith("section") for q in asked)
    # A judgement question keeps its full text.
    assert any("your own company" in q for q in asked)

    checklist = prompts.question_checklist(STRUCTURED_CASE)
    assert checklist.startswith("Q1.") and "Q5." in checklist


def test_narrative_brief_does_not_trigger_the_question_checklist():
    """The Readmio/bookstore shape — prose with an embedded question — must
    still run the normal issue-tree pipeline, not a Q&A checklist."""
    assert prompts.question_checklist(CASE) == ""
    assert len(prompts.explicit_questions(CASE)) < prompts.EXPLICIT_QUESTION_THRESHOLD


def test_structured_case_puts_the_questions_in_front_of_every_gate(
    tmp_path, monkeypatch
):
    """The client's questions must reach the issue tree, the reconciliation, the
    reviewer AND the report-writer. The reviewer especially: judging coverage by
    our own issue tree is grading our own homework."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "asked.db")
    db.reset_for_tests()
    seen: dict[str, str] = {}

    async def fake_call(agent, system, user, **kw):
        seen[agent] = user
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", STRUCTURED_CASE)
    asyncio.run(run_engagement(eid, STRUCTURED_CASE, call=fake_call))

    marker = "QUESTIONS THE CLIENT ASKED"
    for agent in (
        "issue-tree-generator",
        "engagement-manager",
        "reviewer",
        "report-writer",
    ):
        assert marker in seen[agent], f"{agent} never saw the client's questions"

    # The reviewer is told, explicitly, that coverage outranks its other checks.
    assert "COVERAGE OF THE CLIENT'S QUESTIONS" in seen["reviewer"]
    assert "needs_rework" in seen["reviewer"]
    # The report-writer is told to answer them and to show arithmetic.
    assert "Answer EVERY ONE" in seen["report-writer"]
    assert "SHOW THE CALCULATION" in seen["report-writer"]
    db.reset_for_tests()


def test_narrative_brief_leaves_the_gates_unchanged(tmp_path, monkeypatch):
    """No checklist => no coverage instructions anywhere. The existing pipeline
    behaviour for prose briefs must not shift."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "narr.db")
    db.reset_for_tests()
    seen: dict[str, str] = {}

    async def fake_call(agent, system, user, **kw):
        seen[agent] = user
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid, CASE, call=fake_call))
    for agent in ("issue-tree-generator", "reviewer", "report-writer"):
        assert "QUESTIONS THE CLIENT ASKED" not in seen[agent]
    assert "COVERAGE OF THE CLIENT'S QUESTIONS" not in seen["reviewer"]
    db.reset_for_tests()


def test_free_tier_quota(client):
    """After DAILY_ENGAGEMENT_QUOTA runs, the next one is rate-limited."""
    for _ in range(3):
        assert (
            client.post(
                "/api/engagements", json={"case_prompt": CASE}, headers=CID_A
            ).status_code
            == 202
        )
    over = client.post("/api/engagements", json={"case_prompt": CASE}, headers=CID_A)
    assert over.status_code == 429
    assert "limit" in over.json()["detail"].lower()


def test_byok_bypasses_quota(client):
    """A user-supplied API key is the premium path — no daily quota."""
    for _ in range(4):  # one past the quota of 3
        response = client.post(
            "/api/engagements",
            json={"case_prompt": CASE, "api_key": "sk-ant-test-premium-key"},
            headers=CID_A,
        )
        assert response.status_code == 202


def test_api_key_never_persisted(client, tmp_path):
    """The BYOK key must not survive the request: not in the DB, not in events."""
    key = "sk-ant-secret-do-not-store-me"
    engagement_id = client.post(
        "/api/engagements",
        json={"case_prompt": CASE, "api_key": key},
        headers=CID_A,
    ).json()["id"]
    # Drain the run, then inspect everything the server persisted.
    client.get(f"/api/engagements/{engagement_id}/events", headers=CID_A)
    raw = (tmp_path / "test.db").read_bytes()
    assert key.encode() not in raw


def test_ownership_isolation(client):
    engagement_id = client.post(
        "/api/engagements", json={"case_prompt": CASE}, headers=CID_A
    ).json()["id"]
    assert (
        client.get(f"/api/engagements/{engagement_id}", headers=CID_B).status_code
        == 404
    )
    assert (
        client.get(f"/api/engagements/{engagement_id}", headers=CID_A).status_code
        == 200
    )


def test_mock_mode_returns_canned_output():
    """In mock mode (no GROQ_API_KEY set), call_agent returns demo text."""
    from app.pipeline import claude as claude_mod

    output = asyncio.run(claude_mod.call_agent("financial-analyst", "s" * 200, "case"))
    assert "demo" in output.lower()


def test_friendly_error():
    from app.pipeline.claude import friendly_error

    class Fake:
        def __init__(self, status: int, msg: str) -> None:
            self.status_code = status
            self.message = msg

        def __str__(self) -> str:
            return self.message

    assert "rate" in friendly_error(Fake(429, "rate limit exceeded")).lower()
    assert "rejected" in friendly_error(Fake(401, "invalid api key"))
    # Never leak raw JSON blobs to the user
    assert "{" not in friendly_error(Fake(401, '{"error": "invalid_api_key"}'))
    assert "temporary" in friendly_error(Fake(500, "internal server error")).lower()


# --- golden-case benchmark ----------------------------------------------------

RUBRIC = (
    "A good answer would include: pipeline value and probability of success; "
    "the target's commercial capabilities and KOL relationships; existing "
    "partnerships; price vs synergies; strategic alternatives to the deal."
)


def test_eval_grades_report_and_learns_lessons(tmp_path, monkeypatch):
    """The full golden-case loop: run engagement → grade vs the model answer →
    store the score → distil MISSED items into durable lessons."""
    from app.pipeline.grading import run_case_eval

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "eval.db")
    db.reset_for_tests()
    grader_inputs: list[str] = []

    async def fake_call(agent, system, user, **kw):
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands"
        if agent == "grader":
            grader_inputs.append(user)
            return (
                "SCORE: 72\n"
                "GOT: pipeline value sized with probability of success\n"
                "MISSED: no analysis of the target's KOL relationships\n"
                "MISSED: strategic alternatives to the acquisition not considered"
            )
        if agent == "reflector":
            return (
                "LESSON: Always evaluate strategic alternatives, not only"
                " the proposed move."
            )
        return fake_output(agent)

    case_id = db.create_case("browser-x", "M&A case", CASE, RUBRIC)
    engagement_id = db.create_engagement("browser-x", CASE)
    eval_id = db.create_eval(case_id, engagement_id)
    asyncio.run(run_case_eval(eval_id, engagement_id, CASE, RUBRIC, call=fake_call))

    evals = db.list_evals(case_id)
    assert len(evals) == 1
    assert evals[0]["status"] == "completed" and evals[0]["score"] == 72
    # the grader saw both the rubric and the report
    assert RUBRIC[:40] in grader_inputs[0]
    assert "output-of-report-writer" in grader_inputs[0]
    # gaps became a durable lesson
    assert any("strategic alternatives" in row["text"] for row in db.list_lessons())
    # score surfaces on the case list
    cases = db.list_cases("browser-x")
    assert cases[0]["latest_score"] == 72 and cases[0]["eval_count"] == 1
    db.reset_for_tests()


def test_eval_failed_engagement_marks_eval_failed(tmp_path, monkeypatch):
    from app.pipeline.grading import run_case_eval

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "evalfail.db")
    db.reset_for_tests()

    async def broken_call(agent, system, user, **kw):
        raise RuntimeError("api exploded")

    case_id = db.create_case("browser-x", "t", CASE, RUBRIC)
    engagement_id = db.create_engagement("browser-x", CASE)
    eval_id = db.create_eval(case_id, engagement_id)
    asyncio.run(run_case_eval(eval_id, engagement_id, CASE, RUBRIC, call=broken_call))

    evals = db.list_evals(case_id)
    assert evals[0]["status"] == "failed"
    assert evals[0]["detail"]  # a human-readable reason, not empty
    db.reset_for_tests()


def test_parse_grade():
    from app.pipeline.grading import _parse_grade

    score, missed = _parse_grade(
        "SCORE: 85\nGOT: covered synergies\nMISSED: no KOL analysis\n"
        "MISSED: \nmissed: alternatives"
    )
    assert score == 85
    assert missed == ["no KOL analysis", "alternatives"]
    assert _parse_grade("no structure at all") == (None, [])
    assert _parse_grade("SCORE: 400")[0] == 100  # clamped


def test_structured_case_mandates_an_answers_section_and_budgets_for_it():
    """The first cut of this fix failed live: reconcile built the Q1-Q11 closure
    table and the reviewer verified coverage, but the REPORT still shipped a
    standard memo with zero Q-numbers. The answer instruction was a paragraph
    sitting above an enumerated section spec — and the enumerated spec won.

    So the section must be part of the mandated structure, and the token budget
    must have room for it, or the model spends the whole budget on the memo and
    silently drops the answers.
    """
    from app.pipeline import prompts

    asked = prompts.explicit_questions(STRUCTURED_CASE)
    assert len(asked) >= prompts.EXPLICIT_QUESTION_THRESHOLD
    # budget scales with the number of questions rather than a flat cap
    budget = config.REPORT_MAX_TOKENS + 220 * len(asked)
    assert budget > config.REPORT_MAX_TOKENS


def test_report_writer_gets_the_answers_section_in_its_structure_spec(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "ans.db")
    db.reset_for_tests()
    seen: dict[str, str] = {}

    async def fake_call(agent, system, user, **kw):
        seen[agent] = user
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", STRUCTURED_CASE)
    asyncio.run(run_engagement(eid, STRUCTURED_CASE, call=fake_call))
    spec = seen["report-writer"]
    # the section is mandated INSIDE the structure list, not merely requested
    assert "## Answers to your questions" in spec
    assert "MANDATORY" in spec
    assert "Client question closure" in spec  # sourced from the canonical table

    # and a narrative brief must not get it
    db.reset_for_tests()
    seen.clear()
    eid2 = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid2, CASE, call=fake_call))
    assert "## Answers to your questions" not in seen["report-writer"]
    db.reset_for_tests()


def test_ip_quota_closes_the_client_id_bypass(client, monkeypatch):
    """X-Client-Id is caller-asserted, so the per-browser quota is a courtesy
    limit: a fresh id per request bypasses it entirely. On a public deployment
    that is the whole free-tier budget gone in an afternoon. The IP quota keys
    off something the caller cannot choose.
    """
    monkeypatch.setattr(config, "DAILY_ENGAGEMENT_QUOTA", 2)
    monkeypatch.setattr(config, "DAILY_IP_QUOTA", 3)

    # The attack: a brand-new client id every time.
    codes = []
    for i in range(5):
        r = client.post(
            "/api/engagements",
            json={"case_prompt": CASE},
            headers={"X-Client-Id": f"fresh-identity-{i:04d}"},
        )
        codes.append(r.status_code)

    assert codes[:3] == [202, 202, 202]
    assert codes[3:] == [429, 429], f"client-id rotation was not stopped: {codes}"
    assert (
        "network"
        in client.post(
            "/api/engagements",
            json={"case_prompt": CASE},
            headers={"X-Client-Id": "yet-another-id-9"},
        ).json()["detail"]
    )


def test_byok_runs_are_never_ip_limited(client, monkeypatch):
    """A BYOK visitor spends their OWN provider quota, so rate-limiting them
    protects nothing and would punish the users we most want."""
    monkeypatch.setattr(config, "DAILY_IP_QUOTA", 1)
    assert (
        client.post(
            "/api/engagements", json={"case_prompt": CASE}, headers=CID_A
        ).status_code
        == 202
    )
    # free tier for this IP is now exhausted...
    assert (
        client.post(
            "/api/engagements", json={"case_prompt": CASE}, headers=CID_B
        ).status_code
        == 429
    )
    # ...but bringing your own key still works
    for i in range(3):
        assert (
            client.post(
                "/api/engagements",
                json={"case_prompt": CASE, "api_key": "sk-ant-user-supplied-key"},
                headers={"X-Client-Id": f"byok-visitor-{i:04d}"},
            ).status_code
            == 202
        )


def test_ip_is_hashed_never_stored_raw(client, monkeypatch):
    """An IP is PII and this product holds nothing about its users."""
    monkeypatch.setattr(config, "IP_HASH_SALT", "test-salt")
    client.post("/api/engagements", json={"case_prompt": CASE}, headers=CID_A)
    row = (
        db.connect()
        .execute("SELECT ip_hash FROM engagements ORDER BY created_at DESC LIMIT 1")
        .fetchone()
    )
    assert row["ip_hash"] and len(row["ip_hash"]) == 32
    raw = config.DB_PATH.read_bytes()
    assert b"testclient" not in raw  # starlette's test peer name
    assert b"127.0.0.1" not in raw


def test_forwarded_for_is_ignored_unless_a_proxy_is_declared(monkeypatch):
    """X-Forwarded-For is caller-supplied. Trusting it without a proxy in front
    hands the attacker the very bypass the IP quota closes — they'd just spoof a
    new XFF per request. And behind a real proxy, take the LAST hop: that is the
    one our own proxy observed and appended; earlier entries are client-claimed.
    """
    from app.routers.engagements import _source_ip

    class FakeRequest:
        def __init__(self, xff, peer):
            self.headers = {"x-forwarded-for": xff} if xff else {}
            self.client = type("C", (), {"host": peer})()

    spoofed = FakeRequest("1.2.3.4, 5.6.7.8", "10.0.0.9")

    monkeypatch.setattr(config, "TRUST_PROXY", False)
    assert _source_ip(spoofed) == "10.0.0.9", "XFF trusted with no proxy declared"

    monkeypatch.setattr(config, "TRUST_PROXY", True)
    assert _source_ip(spoofed) == "5.6.7.8", "must take the proxy-appended last hop"

    # no XFF present behind a proxy → fall back to the socket peer
    assert _source_ip(FakeRequest(None, "10.0.0.9")) == "10.0.0.9"


def test_config_survives_the_empty_env_vars_compose_exports():
    """docker-compose's `VAR: ${VAR:-}` — the standard way to declare an
    optional variable — exports an EMPTY STRING, not an absent one.

    This has now bitten twice: it silently blanked provider model ids, and it
    crashed the backend at import (`int("")` -> ValueError) the moment the
    deployment vars were added to compose. Every config read must treat empty
    as absent, so pin it for the whole module rather than one setting.
    """
    import importlib
    import os
    import subprocess
    import sys

    empty = {
        k: ""
        for k in (
            "STRATAGENT_DAILY_QUOTA",
            "STRATAGENT_DAILY_IP_QUOTA",
            "STRATAGENT_MAX_CONCURRENT",
            "STRATAGENT_MAX_TOKENS",
            "STRATAGENT_REPORT_MAX_TOKENS",
            "STRATAGENT_MAX_REWORK",
            "STRATAGENT_MAX_AUTO_RESUMES",
            "STRATAGENT_MIN_RESUME_DELAY",
            "STRATAGENT_MAX_RESUME_DELAY",
            "STRATAGENT_TELEMETRY_SAMPLE",
            "STRATAGENT_CORS_ORIGINS",
            "STRATAGENT_IP_SALT",
            "STRATAGENT_TRUST_PROXY",
            "STRATAGENT_DB",
            "STRATAGENT_ADMIN_TOKEN",
        )
    }
    # Fresh interpreter: config resolves at import time, so re-importing in this
    # process would not re-read the environment.
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app import config;"
            "assert config.CORS_ORIGINS, 'CORS blanked -> browser blocked';"
            "assert config.DAILY_IP_QUOTA > 0;"
            "assert config.MAX_CONCURRENT_ENGAGEMENTS > 0;"
            "assert len(config.IP_HASH_SALT) > 8;"
            "assert config.DB_PATH.name;"
            "print('ok')",
        ],
        env={**os.environ, **empty},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"config crashed on compose's empty env vars:\n{proc.stderr[-600:]}"
    )
    assert "ok" in proc.stdout
    importlib.import_module("app.config")  # keep the in-process module loaded


def test_migration_works_on_a_pre_existing_database(tmp_path, monkeypatch):
    """A new column's INDEX must live in _migrate(), never in _SCHEMA.

    _SCHEMA runs BEFORE the migration, and on an existing database
    `CREATE TABLE IF NOT EXISTS` is a no-op — so indexing a column added later
    raises "no such column" and the process dies at startup. Fresh databases
    hide this completely: only a real old-schema DB catches it (this exact bug
    took the backend down on deploy).
    """
    import sqlite3

    dbfile = tmp_path / "legacy.db"
    # A database as it existed BEFORE ip_hash — no column, no index.
    legacy = sqlite3.connect(dbfile)
    legacy.executescript("""
        CREATE TABLE engagements (
            id TEXT PRIMARY KEY, client_id TEXT NOT NULL, case_prompt TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued', report_md TEXT, error TEXT,
            review_verdict TEXT, challenge_verdict TEXT, review_ready INTEGER,
            created_at REAL NOT NULL, completed_at REAL
        );
        INSERT INTO engagements (id, client_id, case_prompt, status, created_at)
        VALUES ('eng_legacy', 'old-browser', 'an older engagement', 'completed', 1.0);
        """)
    legacy.commit()
    legacy.close()

    monkeypatch.setattr(config, "DB_PATH", dbfile)
    db.reset_for_tests()
    conn = db.connect()  # must not raise

    cols = {r[1] for r in conn.execute("PRAGMA table_info(engagements)")}
    assert {"ip_hash", "used_byok"} <= cols, "migration did not add the columns"
    idx = {r[1] for r in conn.execute("PRAGMA index_list(engagements)")}
    assert "idx_engagements_ip" in idx, "ip_hash index missing after migration"
    # and the pre-existing row survived
    assert (
        conn.execute(
            "SELECT case_prompt FROM engagements WHERE id='eng_legacy'"
        ).fetchone()["case_prompt"]
        == "an older engagement"
    )
    db.reset_for_tests()


def test_retention_purge_hard_deletes_old_engagements(tmp_path, monkeypatch):
    """Engagements past the window are HARD-deleted — row, events, feedback,
    and telemetry file — while newer ones are untouched. No signup means no
    other way to honour a deletion, so this must actually remove the data."""
    import time as _time

    from app import retention

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "ret.db")
    monkeypatch.setattr(config, "RETENTION_DAYS", 5.0)
    tel = tmp_path / "telemetry"
    tel.mkdir()
    monkeypatch.setattr(config, "TELEMETRY_DIR", str(tel))
    db.reset_for_tests()

    old = db.create_engagement("browser-old", "an OLD confidential brief")
    new = db.create_engagement("browser-new", "a RECENT brief")
    # backdate the old one past the window; leave events + telemetry behind
    conn = db.connect()
    conn.execute(
        "UPDATE engagements SET created_at = ? WHERE id = ?",
        (_time.time() - 6 * 86400, old),
    )
    conn.commit()
    db.append_event(old, "engagement_started", {})
    db.add_feedback(old, "browser-old", "sensitive comment")
    (tel / f"{old}.jsonl").write_text('{"event":"x"}\n')
    (tel / f"{new}.jsonl").write_text('{"event":"y"}\n')

    deleted = retention.purge_once()
    assert deleted == 1

    assert db.get_engagement(old) is None, "old engagement was not deleted"
    assert db.get_engagement(new) is not None, "recent engagement wrongly deleted"
    # cascaded to events, feedback, and the telemetry file
    assert db.list_events(old) == []
    assert db.list_feedback(old) == []
    assert not (tel / f"{old}.jsonl").exists(), "old telemetry file left behind"
    assert (tel / f"{new}.jsonl").exists(), "recent telemetry file wrongly deleted"
    db.reset_for_tests()


def test_retention_disabled_keeps_everything(tmp_path, monkeypatch):
    """RETENTION_DAYS=0 means a private instance keeps all history."""
    from app import retention

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "keep.db")
    monkeypatch.setattr(config, "RETENTION_DAYS", 0.0)
    db.reset_for_tests()
    import time as _time

    eid = db.create_engagement("browser-x", CASE)
    db.connect().execute(
        "UPDATE engagements SET created_at = ? WHERE id = ?",
        (_time.time() - 999 * 86400, eid),
    )
    db.connect().commit()
    assert retention.purge_once() == 0
    assert db.get_engagement(eid) is not None
    db.reset_for_tests()


def test_health_reports_the_real_retention_window(client, monkeypatch):
    """The landing-page privacy note reads this — it must be the true window,
    not a hardcoded number that can drift from the actual purge."""
    monkeypatch.setattr(config, "RETENTION_DAYS", 5.0)
    body = client.get("/api/health").json()
    assert body["retention_days"] == 5.0


def test_persistence_check_detects_ephemeral_storage(tmp_path, monkeypatch):
    """The worst silent failure this product has is a DB on ephemeral storage
    that vanishes on redeploy. The startup check must catch it.

    A tmp_path under the test runner's root filesystem shares / 's device, so it
    reads as NON-persistent — exactly the condition we must flag loudly.
    """
    from app import persistence_check

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "eph.db")
    ok, detail = persistence_check.check_persistence()
    # tmp_path is on the same device as / in CI, so this must report NOT durable
    assert ok is False, f"expected ephemeral, got {ok}: {detail}"
    assert "LOST on redeploy" in detail


def test_health_reports_persistence_state(client):
    body = client.get("/api/health").json()
    assert "persistent_storage" in body  # True / False / None, surfaced to ops
