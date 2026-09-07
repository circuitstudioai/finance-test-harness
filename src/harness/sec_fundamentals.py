"""Small SEC Company Facts adapter that emits the shared evidence contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from .evidence import EvidenceItem, EvidenceKind, EvidencePacket, MissingStatus, Source, utc_now


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

FACTS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "USD"),
    "net_income": ("NetIncomeLoss", "USD"),
    "assets": ("Assets", "USD"),
    "cash": ("CashAndCashEquivalentsAtCarryingValue", "USD"),
    "debt_current": ("ShortTermBorrowings", "USD"),
    "shares_outstanding": ("EntityCommonStockSharesOutstanding", "shares"),
    "eps_diluted": ("EarningsPerShareDiluted", "USD/share"),
}


@dataclass
class SecClient:
    user_agent: str
    session: Any = requests
    timeout: int = 20

    def _get_json(self, url: str) -> dict[str, Any]:
        response = self.session.get(
            url,
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def cik_for_ticker(self, ticker: str) -> str:
        rows = self._get_json(SEC_TICKERS_URL).values()
        match = next((row for row in rows if row["ticker"].upper() == ticker.upper()), None)
        if match is None:
            raise ValueError(f"SEC CIK not found for ticker {ticker}")
        return str(match["cik_str"]).zfill(10)

    def evidence_packet(self, ticker: str, *, retrieved_at: str | None = None) -> EvidencePacket:
        retrieved_at = retrieved_at or utc_now()
        cik = self.cik_for_ticker(ticker)
        url = SEC_FACTS_URL.format(cik=cik)
        payload = self._get_json(url)
        us_gaap = payload.get("facts", {}).get("us-gaap", {})
        items = tuple(
            self._latest_item(ticker.upper(), metric, concept, unit, us_gaap, url, retrieved_at)
            for metric, (concept, unit) in FACTS.items()
        )
        return EvidencePacket(ticker.upper(), retrieved_at, items, "sec_fundamentals", metadata={"cik": cik})

    @staticmethod
    def _latest_item(
        ticker: str, metric: str, concept: str, unit: str, facts: dict[str, Any], url: str, retrieved_at: str
    ) -> EvidenceItem:
        concept_data = facts.get(concept, {})
        observations = concept_data.get("units", {}).get(unit, [])
        filed = [row for row in observations if row.get("filed") and row.get("val") is not None]
        if not filed:
            return EvidenceItem(
                f"sec-{metric}-missing", EvidenceKind.FACT, metric, None, unit, ticker, "latest", 0, None,
                missing_status=MissingStatus.UNAVAILABLE,
                notes=f"SEC concept {concept} was unavailable",
            )
        row = max(filed, key=lambda value: (value.get("filed", ""), value.get("end", "")))
        filed_at = f"{row['filed']}T00:00:00Z"
        retrieved = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        observed = datetime.fromisoformat(filed_at.replace("Z", "+00:00"))
        freshness = max(0, int((retrieved - observed).total_seconds()))
        period = row.get("fy") and f"FY{row['fy']}" or row.get("end", "latest")
        return EvidenceItem(
            id=f"sec-{metric}-{row.get('accn', row['filed'])}",
            kind=EvidenceKind.FACT,
            metric=metric,
            value=row["val"],
            unit=unit,
            ticker=ticker,
            period=str(period),
            confidence=0.98,
            freshness_seconds=freshness,
            source=Source("sec_companyfacts", url, retrieved_at, filed_at, row.get("end")),
            notes=f"SEC concept {concept}; form {row.get('form', 'unknown')}",
        )
