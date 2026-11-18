"""Waterfall engine: ordered provider steps per field, with early stop,
conditional branching, budgets, retries, caching and idempotency."""
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from .normalize import classify_title, lead_key, normalize_domain, normalize_name
from .providers import COMPANY_FIELDS, FIELDS, TransientError


@dataclass
class Step:
    provider: str
    when: Optional[Callable[[dict], bool]] = None  # row context -> run this step?


@dataclass
class FieldResult:
    value: str = ""
    confidence: float = 0.0
    provider: str = ""
    cost: float = 0.0
    status: str = "empty"  # filled | empty | budget_skipped
    tried: list = field(default_factory=list)


def idem_key(provider, fld, domain, first="", last=""):
    ent = domain if fld in COMPANY_FIELDS else f"{domain}|{first.lower()}|{last.lower()}"
    return hashlib.sha256(f"{provider}|{fld}|{ent}".encode()).hexdigest()[:20]


class Cache:
    """Idempotency/result cache. Misses are cached too, so a repeat run (or a
    duplicate entity) is never charged twice. Optional JSON persistence."""

    def __init__(self, path=None):
        self.path, self.data, self.hits = path, {}, 0
        if path and os.path.exists(path):
            self.data = json.load(open(path))

    def get(self, k):
        if k in self.data:
            self.hits += 1
            return True, self.data[k]
        return False, None

    def put(self, k, v):
        self.data[k] = v

    def save(self):
        if self.path:
            json.dump(self.data, open(self.path, "w"))


def icp_fit(ctx, sizes=("51-200", "201-1000", "1001-5000"), functions=("sales", "marketing", "revops")):
    """ICP: mid/large company and a GTM-function title. Unknown size passes."""
    size_ok = ctx.get("company_size") in sizes if ctx.get("company_size") else True
    fn_ok = ctx.get("function") in functions if ctx.get("function") else True
    return size_ok and fn_ok


class Engine:
    def __init__(self, providers, plan, threshold=0.8, max_retries=2,
                 row_budget=None, total_budget=None, cache=None):
        self.providers, self.plan, self.threshold = providers, plan, threshold
        self.max_retries, self.row_budget, self.total_budget = max_retries, row_budget, total_budget
        self.cache = cache or Cache()
        self.spent = 0.0
        self.stats = {"calls": 0, "retries": 0, "cache_hits": 0, "budget_skips": 0, "gave_up": 0}

    # ---- single provider call with retry + cache ----
    def _call(self, prov, fld, ent):
        k = idem_key(prov.name, fld, ent["domain"], ent["first"], ent["last"])
        found, val = self.cache.get(k)
        if found:
            self.stats["cache_hits"] += 1
            return val, 0.0
        res, attempt = None, 0
        while True:
            try:
                self.stats["calls"] += 1
                res = prov.lookup(fld, ent, attempt)
                break
            except TransientError:
                if attempt >= self.max_retries:
                    self.stats["gave_up"] += 1
                    return None, 0.0  # not cached: a later run may succeed
                attempt += 1
                self.stats["retries"] += 1
        out = None if res is None else {"value": res.value, "confidence": res.confidence}
        self.cache.put(k, out)
        return out, (prov.price(fld) if out else 0.0)

    # ---- one row ----
    def enrich_row(self, lead):
        dom = normalize_domain(lead.get("domain") or lead.get("website"))
        first, last = normalize_name(f'{lead.get("first_name","")} {lead.get("last_name","")}')
        ent = {"domain": dom, "first": first, "last": last}
        title, sen, fn = classify_title(lead.get("title"))
        ctx = {"industry": lead.get("industry", ""), "company_size": lead.get("company_size", ""),
               "title": title, "seniority": sen, "function": fn, "email": "", "phone": ""}
        results, row_cost = {}, 0.0
        for fld in FIELDS:
            fr = FieldResult()
            if ctx.get(fld) and fld in ("company_size", "title"):  # already supplied
                fr.value, fr.confidence, fr.provider, fr.status = ctx[fld], 1.0, "input", "filled"
                results[fld] = fr
                continue
            for step in self.plan.get(fld, []):
                prov = self.providers[step.provider]
                if not prov.supports(fld):
                    continue
                if step.when and not step.when(ctx):
                    fr.tried.append(f"{step.provider}:skipped(cond)")
                    continue
                p = prov.price(fld)
                if (self.row_budget is not None and row_cost + p > self.row_budget + 1e-9) or \
                   (self.total_budget is not None and self.spent + p > self.total_budget + 1e-9):
                    fr.tried.append(f"{step.provider}:skipped(budget)")
                    fr.status = "budget_skipped"
                    self.stats["budget_skips"] += 1
                    continue
                out, cost = self._call(prov, fld, ent)
                row_cost += cost
                self.spent += cost
                fr.cost += cost
                fr.tried.append(f"{step.provider}:{'hit' if out else 'miss'}")
                if out and out["confidence"] > fr.confidence:
                    fr.value, fr.confidence, fr.provider = out["value"], out["confidence"], step.provider
                    fr.status = "filled"
                if fr.status == "filled" and fr.confidence >= self.threshold:
                    break  # early stop
            if fr.status == "budget_skipped" and fr.value:
                fr.status = "filled"
            results[fld] = fr
            if fr.status == "filled":
                ctx[fld] = fr.value
                if fld == "title":
                    _, ctx["seniority"], ctx["function"] = classify_title(fr.value)
        return {"domain": dom, "first_name": first, "last_name": last, "title_seniority": ctx["seniority"],
                "title_function": ctx["function"], "icp_fit": icp_fit(ctx), "fields": results,
                "row_cost": round(row_cost, 4)}

    # ---- whole list ----
    def run(self, leads):
        seen, rows, dupes = {}, [], 0
        for lead in leads:
            dom = normalize_domain(lead.get("domain") or lead.get("website"))
            f, l = normalize_name(f'{lead.get("first_name","")} {lead.get("last_name","")}')
            if not dom or not f:
                continue
            k = lead_key(dom, f, l)
            if k in seen:
                dupes += 1
                continue
            seen[k] = True
            rows.append(self.enrich_row(lead))
        self.cache.save()
        return rows, {"input": len(leads), "duplicates_removed": dupes, **self.stats,
                      "total_cost": round(self.spent, 4)}
