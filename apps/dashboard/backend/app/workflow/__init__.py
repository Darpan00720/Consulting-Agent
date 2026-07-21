"""Workflow Router (ADR-013) — classify a unit of work's task-type and SELECT
the agent/toolchain that should own it.

W1 scope: a pure classifier + selector. It never dispatches and never calls a
target's ``invoke`` — dispatch is the host's job (ADR-013 §2a, Option A). See
``router.route`` for the entry point and ``targets`` for the Target interface.
"""
