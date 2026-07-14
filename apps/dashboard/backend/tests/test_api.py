"""Dashboard API tests — run entirely in mock mode (no Groq API calls).

No accounts: identity is the anonymous X-Client-Id header.
Server holds the Groq key; users need no key to run cases.
"""

from __future__ import annotations

import asyncio
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
    inline = {"engagement-manager"}
    for _, agent in PHASES:
        if agent.endswith("(parallel)") or agent in inline:
            continue
        assert len(prompts.agent_system_prompt(agent)) > 100
    for agent in ANALYSTS:
        assert len(prompts.agent_system_prompt(agent)) > 100
    assert "profit" in prompts.vault_framework_index()


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


def test_engine_direct_with_fake_agent(tmp_path, monkeypatch):
    """The engine accepts an injectable call — verify context threading."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "engine.db")
    db.reset_for_tests()
    seen: list[str] = []

    async def fake_call(agent, system, user, **kw):
        seen.append(agent)
        assert len(system) > 100  # real prompt loaded
        return f"output-of-{agent}"

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
            return "Verdict: approved — all five checks pass against the canonical ledger"
        if agent == "challenger":
            return "Verdict: stands_with_caveats"
        return f"output-of-{agent}"

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
        return f"output-of-{agent}"

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
                "LESSON: For acquisition cases, include a commercial go-to-market branch.\n"
                "LESSON: Assign globally-unique assumption IDs across all analysts.\n"
                "NONE"
            )
        return f"output-of-{agent}"

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


def test_reflection_dedupes_lessons(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "dedupe.db")
    db.reset_for_tests()
    assert db.add_lesson("Assign unique assumption IDs.") is True
    assert db.add_lesson("Assign unique assumption IDs.") is False  # duplicate
    assert len(db.list_lessons()) == 1
    db.reset_for_tests()


def test_reflection_skipped_when_review_ready(tmp_path, monkeypatch):
    """A clean (approved) engagement learns nothing — reflection is blocked-only."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "clean.db")
    db.reset_for_tests()

    async def fake_call(agent, system, user, **kw):
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands"
        if agent == "reflector":
            raise AssertionError("reflection must not run on an approved engagement")
        return f"output-of-{agent}"

    eid = db.create_engagement("browser-x", CASE)
    asyncio.run(run_engagement(eid, CASE, call=fake_call))
    assert db.list_lessons() == []
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

    assert _reviewer_verdict("Final verdict: needs_rework, 2 checks fail") == "needs_rework"
    assert _reviewer_verdict("VERDICT: APPROVED") == "approved"
    assert _reviewer_verdict("no token here") == "approved"  # safe default
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


def test_ownership_isolation(client):
    engagement_id = client.post(
        "/api/engagements", json={"case_prompt": CASE}, headers=CID_A
    ).json()["id"]
    assert (
        client.get(f"/api/engagements/{engagement_id}", headers=CID_B).status_code == 404
    )
    assert (
        client.get(f"/api/engagements/{engagement_id}", headers=CID_A).status_code == 200
    )


def test_mock_mode_returns_canned_output():
    """In mock mode (no GROQ_API_KEY set), call_agent returns demo text."""
    from app.pipeline import claude as claude_mod

    output = asyncio.run(
        claude_mod.call_agent("financial-analyst", "s" * 200, "case")
    )
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


def test_case_crud_and_isolation(client):
    created = client.post(
        "/api/cases",
        json={"title": "GlobaPharm", "prompt": CASE, "rubric": RUBRIC},
        headers=CID_A,
    )
    assert created.status_code == 201
    case_id = created.json()["id"]

    listed = client.get("/api/cases", headers=CID_A).json()
    assert [c["id"] for c in listed] == [case_id]
    assert listed[0]["eval_count"] == 0 and listed[0]["latest_score"] is None

    # another browser can't see, fetch, or delete it
    assert client.get("/api/cases", headers=CID_B).json() == []
    assert client.get(f"/api/cases/{case_id}", headers=CID_B).status_code == 404
    assert client.delete(f"/api/cases/{case_id}", headers=CID_B).status_code == 404

    assert client.delete(f"/api/cases/{case_id}", headers=CID_A).status_code == 204
    assert client.get("/api/cases", headers=CID_A).json() == []


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
            return "LESSON: Always evaluate strategic alternatives, not only the proposed move."
        return f"output-of-{agent}"

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


def test_run_eval_endpoint_mock(client):
    """The API path works end to end in mock mode (no key needed)."""
    case_id = client.post(
        "/api/cases",
        json={"title": "Mock case", "prompt": CASE, "rubric": RUBRIC},
        headers=CID_A,
    ).json()["id"]

    run = client.post(f"/api/cases/{case_id}/run", json={}, headers=CID_A)
    assert run.status_code == 202
    body = run.json()
    assert body["eval_id"] and body["engagement_id"]

    for _ in range(200):
        evals = client.get(f"/api/cases/{case_id}/evals", headers=CID_A).json()
        if evals and evals[0]["status"] != "running":
            break
    # the mock grader returns a parseable demo grade so the loop is visible
    assert evals[0]["status"] == "completed"
    assert evals[0]["score"] == 62


def test_parse_grade():
    from app.pipeline.grading import _parse_grade

    score, missed = _parse_grade(
        "SCORE: 85\nGOT: covered synergies\nMISSED: no KOL analysis\nMISSED: \nmissed: alternatives"
    )
    assert score == 85
    assert missed == ["no KOL analysis", "alternatives"]
    assert _parse_grade("no structure at all") == (None, [])
    assert _parse_grade("SCORE: 400")[0] == 100  # clamped
