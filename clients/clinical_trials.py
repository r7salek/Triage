"""Client for the ClinicalTrials.gov API v2."""

from __future__ import annotations

from typing import Any

import requests


class ClinicalTrialsClient:
    """Small requests-based client for ClinicalTrials.gov condition search."""

    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
    DEFAULT_LIMIT = 5
    MAX_LIMIT = 25
    TIMEOUT_SECONDS = 10

    def search(self, condition: str, limit: int = DEFAULT_LIMIT) -> dict:
        source_url = self._build_source_url(condition, limit)
        if not condition or not condition.strip():
            return self._error("condition is required", source_url)

        params = {
            "query.cond": condition.strip(),
            "pageSize": self._normalize_limit(limit),
            "format": "json",
        }
        source_url = self._prepare_url(params)

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=self.TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout:
            return self._error(f"request timed out after {self.TIMEOUT_SECONDS} seconds", source_url)
        except requests.RequestException as exc:
            return self._error(str(exc), source_url)
        except ValueError as exc:
            return self._error(f"invalid JSON response: {exc}", source_url)

        studies = payload.get("studies", [])
        records = [self._normalize_record(study) for study in studies if isinstance(study, dict)]
        return {"status": "ok", "records": records, "source_url": source_url, "error": None}

    def _normalize_record(self, study: dict[str, Any]) -> dict[str, Any]:
        protocol = study.get("protocolSection") or {}
        identification = protocol.get("identificationModule") or {}
        status = protocol.get("statusModule") or {}
        conditions = protocol.get("conditionsModule") or {}
        design = protocol.get("designModule") or {}
        sponsor = protocol.get("sponsorCollaboratorsModule") or {}
        arms = protocol.get("armsInterventionsModule") or {}

        nct_id = identification.get("nctId")
        lead_sponsor = sponsor.get("leadSponsor") or {}
        interventions = arms.get("interventions") or []

        return {
            "id": nct_id,
            "title": identification.get("briefTitle") or identification.get("officialTitle"),
            "official_title": identification.get("officialTitle"),
            "status": status.get("overallStatus"),
            "conditions": conditions.get("conditions") or [],
            "interventions": self._intervention_names(interventions),
            "study_type": design.get("studyType"),
            "phases": design.get("phases") or [],
            "sponsor": lead_sponsor.get("name"),
            "start_date": self._date_value(status.get("startDateStruct")),
            "completion_date": self._date_value(status.get("completionDateStruct")),
            "source_url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None,
        }

    def _intervention_names(self, interventions: list[Any]) -> list[str]:
        names = []
        for item in interventions:
            if isinstance(item, dict) and item.get("name"):
                names.append(item["name"])
        return names

    def _date_value(self, date_struct: Any) -> str | None:
        if isinstance(date_struct, dict):
            return date_struct.get("date")
        return None

    def _build_source_url(self, condition: str, limit: int) -> str:
        return self._prepare_url(
            {
                "query.cond": (condition or "").strip(),
                "pageSize": self._normalize_limit(limit),
                "format": "json",
            }
        )

    def _prepare_url(self, params: dict[str, Any]) -> str:
        request = requests.Request("GET", self.BASE_URL, params=params).prepare()
        return request.url or self.BASE_URL

    def _normalize_limit(self, limit: int) -> int:
        try:
            value = int(limit)
        except (TypeError, ValueError):
            value = self.DEFAULT_LIMIT
        return max(1, min(value, self.MAX_LIMIT))

    def _error(self, message: str, source_url: str) -> dict:
        return {"status": "error", "records": [], "source_url": source_url, "error": message}
