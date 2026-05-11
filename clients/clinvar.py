"""Client for ClinVar through NCBI E-utilities."""

from __future__ import annotations

from typing import Any

import requests


class ClinVarClient:
    """Small requests-based client for ClinVar ESearch and ESummary."""

    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    DEFAULT_LIMIT = 5
    MAX_LIMIT = 25
    TIMEOUT_SECONDS = 10

    def search(self, query: str, limit: int = DEFAULT_LIMIT) -> dict:
        source_url = self._build_search_url(query, limit)
        if not query or not query.strip():
            return self._error("query is required", source_url)

        search_params = {
            "db": "clinvar",
            "term": query.strip(),
            "retmax": self._normalize_limit(limit),
            "retmode": "json",
        }
        source_url = self._prepare_url(self.ESEARCH_URL, search_params)

        try:
            search_response = requests.get(
                self.ESEARCH_URL,
                params=search_params,
                timeout=self.TIMEOUT_SECONDS,
            )
            search_response.raise_for_status()
            search_payload = search_response.json()
            ids = search_payload.get("esearchresult", {}).get("idlist", [])
            if not ids:
                return {"status": "ok", "records": [], "source_url": source_url, "error": None}

            summary_payload = self._fetch_summaries(ids)
        except requests.Timeout:
            return self._error(f"request timed out after {self.TIMEOUT_SECONDS} seconds", source_url)
        except requests.RequestException as exc:
            return self._error(str(exc), source_url)
        except ValueError as exc:
            return self._error(f"invalid JSON response: {exc}", source_url)

        result = summary_payload.get("result", {})
        records = [
            self._normalize_record(result[item_id])
            for item_id in result.get("uids", [])
            if isinstance(result.get(item_id), dict)
        ]
        return {"status": "ok", "records": records, "source_url": source_url, "error": None}

    def _fetch_summaries(self, ids: list[str]) -> dict[str, Any]:
        params = {
            "db": "clinvar",
            "id": ",".join(ids),
            "retmode": "json",
        }
        response = requests.get(self.ESUMMARY_URL, params=params, timeout=self.TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()

    def _normalize_record(self, item: dict[str, Any]) -> dict[str, Any]:
        uid = item.get("uid")
        accession = item.get("accession")
        germline = item.get("germline_classification") or {}
        somatic = item.get("somatic_clinical_impact") or {}

        return {
            "id": uid,
            "accession": accession,
            "title": item.get("title"),
            "gene": item.get("gene_sort"),
            "variant_type": item.get("variant_type"),
            "clinical_significance": self._classification(germline, somatic),
            "review_status": self._review_status(germline, somatic),
            "conditions": self._traits(item.get("trait_set")),
            "source_url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/" if uid else None,
        }

    def _classification(self, germline: Any, somatic: Any) -> str | None:
        for candidate in (germline, somatic):
            if isinstance(candidate, dict) and candidate.get("description"):
                return candidate["description"]
        return None

    def _review_status(self, germline: Any, somatic: Any) -> str | None:
        for candidate in (germline, somatic):
            if isinstance(candidate, dict) and candidate.get("review_status"):
                return candidate["review_status"]
        return None

    def _traits(self, trait_set: Any) -> list[str]:
        if not isinstance(trait_set, list):
            return []

        traits = []
        for trait in trait_set:
            if isinstance(trait, dict) and trait.get("trait_name"):
                traits.append(trait["trait_name"])
        return traits

    def _build_search_url(self, query: str, limit: int) -> str:
        return self._prepare_url(
            self.ESEARCH_URL,
            {
                "db": "clinvar",
                "term": (query or "").strip(),
                "retmax": self._normalize_limit(limit),
                "retmode": "json",
            },
        )

    def _prepare_url(self, url: str, params: dict[str, Any]) -> str:
        request = requests.Request("GET", url, params=params).prepare()
        return request.url or url

    def _normalize_limit(self, limit: int) -> int:
        try:
            value = int(limit)
        except (TypeError, ValueError):
            value = self.DEFAULT_LIMIT
        return max(1, min(value, self.MAX_LIMIT))

    def _error(self, message: str, source_url: str) -> dict:
        return {"status": "error", "records": [], "source_url": source_url, "error": message}
