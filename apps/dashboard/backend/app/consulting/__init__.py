"""Consulting Workflow Engine — sits ON TOP of the platform (Workflow
Router, Dispatcher, Agent Runtime, Memory Platform, Tool Platform).

Owns consulting METHODOLOGY: the 10-stage engagement lifecycle, quality
gates, hypothesis/assumption/evidence discipline, and consulting artifacts —
never infrastructure. See ``engine.py`` for the two integration points this
package uses (never reimplements): the Workflow Router + Dispatcher for
analysis execution, and the Memory Platform for checkpointing.
"""
