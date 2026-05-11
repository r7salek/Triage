"""Shared data structures for the triage assistant."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CaseData:
    raw_text: str
    focus: str = "General"
    detected_terms: List[str] = field(default_factory=list)
    symptoms: List[str] = field(default_factory=list)
    vitals: Dict[str, str] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    labs: List[str] = field(default_factory=list)
    condition_terms: List[str] = field(default_factory=list)
    genes_or_variants: List[str] = field(default_factory=list)
    phi_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResult:
    agent_name: str
    status: str
    summary: str
    findings: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def result_from_error(agent_name: str, message: str, source_url: str = "") -> AgentResult:
    sources = [{"label": "source", "url": source_url}] if source_url else []
    return AgentResult(
        agent_name=agent_name,
        status="error",
        summary="This agent could not complete its lookup, but the rest of the briefing is still available.",
        findings=[],
        sources=sources,
        caveats=["Public API lookup failed or timed out. Re-run later or inspect the source manually."],
        error=message,
    )
