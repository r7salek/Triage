"""Client for the Europe PMC RESTful search API."""

from __future__ import annotations

from typing import Any

import requests


class EuropePMCClient:
    """Small requests-based client for Europe PMC literature search."""

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    DEFAULT_LIMIT = 5
    MAX_LIMIT = 25
    TIMEOUT_SECONDS = 10

    def search(self, query: str, limit: int = DEFAULT_LIMIT) -> dict:
        source_url = self._build_source_url(query, limit)
        if not query or not query.strip():
            return self._error("query is required", source_url)

        params = {
            "query": query.strip(),
            "format": "json",
            "pageSize": self._normalize_limit(limit),
            "resultType": "lite",
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

        results = payload.get("resultList", {}).get("result", [])
        records = [self._normalize_record(item) for item in results if isinstance(item, dict)]
        return {"status": "ok", "records": records, "source_url": source_url, "error": None}

    def _normalize_record(self, item: dict[str, Any]) -> dict[str, Any]:
        source = item.get("source")
        record_id = item.get("id")
        pmid = item.get("pmid")
        pmcid = item.get("pmcid")
        doi = item.get("doi")

        return {
            "id": pmid or pmcid or record_id,
            "title": item.get("title"),
            "authors": item.get("authorString"),
            "journal": item.get("journalTitle"),
            "publication_date": item.get("firstPublicationDate") or item.get("pubYear"),
            "doi": doi,
            "pmid": pmid,
            "pmcid": pmcid,
            "source": source,
            "source_url": self._record_url(source, record_id, pmid, pmcid),
        }

    def _record_url(
        self,
        source: str | None,
        record_id: str | None,
        pmid: str | None,
        pmcid: str | None,
    ) -> str | None:
        if source and record_id:
            return f"https://europepmc.org/article/{source}/{record_id}"
        if pmid:
            return f"https://europepmc.org/article/MED/{pmid}"
        if pmcid:
            return f"https://europepmc.org/article/PMC/{pmcid.replace('PMC', '')}"
        return None

    def _build_source_url(self, query: str, limit: int) -> str:
        return self._prepare_url(
            {
                "query": (query or "").strip(),
                "format": "json",
                "pageSize": self._normalize_limit(limit),
                "resultType": "lite",
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
