"""Deterministic MOCK providers. No network, no keys, no vendor connection.

Each provider has, per field, a (price, hit_rate, base_confidence). Whether a
lookup hits is decided by hashing (provider, field, entity key), so results are
reproducible. Providers are charged only on a hit. A small share of first
attempts raise TransientError so retry logic is exercised.
"""
import hashlib
from dataclasses import dataclass

FIELDS = ["company_size", "tech_stack", "title", "email", "phone"]
COMPANY_FIELDS = {"company_size", "tech_stack"}  # keyed by domain only


class TransientError(Exception):
    pass


def _h(*parts):
    d = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(d[:8], "big") / 2**64  # uniform [0,1)


@dataclass
class Lookup:
    value: str
    confidence: float


_TECH = ["salesforce", "hubspot", "snowflake", "aws", "segment", "stripe", "zendesk", "shopify"]
_TITLES = ["VP of Sales", "Director of Marketing", "Head of Growth", "Revenue Operations Manager",
           "Chief Financial Officer", "Software Engineer", "Account Executive", "Founder & CEO",
           "Senior Data Engineer", "Operations Manager"]
_BANDS = [("1-10", 6), ("11-50", 30), ("51-200", 120), ("201-1000", 500), ("1001-5000", 2500)]


class MockProvider:
    def __init__(self, name, table, flaky=0.04):
        self.name, self.table, self.flaky = name, table, flaky

    def supports(self, field):
        return field in self.table

    def price(self, field):
        return self.table[field][0]

    def lookup(self, field, entity, attempt=0):
        """entity: dict(domain, first, last). Returns Lookup or None (miss)."""
        price, rate, base = self.table[field]
        key = entity["domain"] if field in COMPANY_FIELDS else f'{entity["domain"]}|{entity["first"]}|{entity["last"]}'
        if attempt == 0 and _h(self.name, field, key, "flaky") < self.flaky:
            raise TransientError(f"{self.name} 503")
        if _h(self.name, field, key, "hit") >= rate:
            return None
        conf = round(min(0.99, max(0.2, base + (_h(self.name, field, key, "conf") - 0.5) * 0.1)), 3)
        return Lookup(self._value(field, entity, key), conf)

    @staticmethod
    def _value(field, e, key):
        # Values depend only on the entity, so providers agree on what they find.
        r = _h("truth", field, key)
        if field == "email":
            return f'{e["first"].lower()}.{e["last"].lower().replace(" ", "")}@{e["domain"]}'
        if field == "phone":
            n = int(r * 1e7)
            return f"+1-555-{n // 10000:03d}-{n % 10000:04d}"
        if field == "title":
            return _TITLES[int(r * len(_TITLES))]
        if field == "company_size":
            return _BANDS[int(r * len(_BANDS))][0]
        k = 1 + int(_h("n", key) * 3)
        return ";".join(sorted({_TECH[int(_h("t", key, i) * len(_TECH))] for i in range(k)}))


def default_providers():
    # field: (price per hit in credits, hit rate, base confidence)
    return {p.name: p for p in [
        MockProvider("scrapely", {  # cheap, thin
            "company_size": (0.01, 0.40, 0.60), "tech_stack": (0.01, 0.50, 0.65),
            "title": (0.02, 0.30, 0.55), "email": (0.02, 0.25, 0.55)}),
        MockProvider("budgetdata", {
            "company_size": (0.03, 0.60, 0.75), "title": (0.05, 0.50, 0.75),
            "email": (0.05, 0.50, 0.72), "phone": (0.10, 0.20, 0.70)}),
        MockProvider("midfinder", {
            "company_size": (0.08, 0.75, 0.85), "title": (0.12, 0.70, 0.85),
            "email": (0.15, 0.70, 0.86), "phone": (0.30, 0.40, 0.82)}),
        MockProvider("premiumgraph", {
            "company_size": (0.20, 0.92, 0.95), "tech_stack": (0.15, 0.55, 0.9),
            "title": (0.30, 0.88, 0.95), "email": (0.40, 0.85, 0.95), "phone": (0.90, 0.60, 0.93)}),
        MockProvider("techscan", {"tech_stack": (0.03, 0.70, 0.85)}),
    ]}
