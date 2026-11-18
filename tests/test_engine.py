import csv

from waterfall.engine import Cache, Engine, Step, icp_fit
from waterfall.normalize import classify_title, normalize_domain, normalize_name
from waterfall.plans import ORDERINGS
from waterfall.providers import MockProvider, TransientError, default_providers
from waterfall.report import summarize, write_csv
from waterfall.synth import make_leads

LEAD = {"first_name": "Alex", "last_name": "Alder", "domain": "acme.example", "title": ""}


def test_normalize_domain():
    assert normalize_domain("https://WWW.Acme.com/about?x=1") == "acme.com"
    assert normalize_domain("jane@Foo.io") == "foo.io"
    assert normalize_domain("not a domain") == ""


def test_normalize_name():
    assert normalize_name("SMITH, jane") == ("Jane", "Smith")
    assert normalize_name("  jane   o'neil-lee jr. ") == ("Jane", "O'Neil-Lee")


def test_title_classification():
    assert classify_title("Sr. VP of Sales")[1:] == ("vp", "sales")
    assert classify_title("Head of Growth")[1:] == ("director", "marketing")
    assert classify_title("RevOps Manager")[1:] == ("manager", "revops")
    assert classify_title("Founder & CEO")[1] == "c_level"
    assert classify_title("") == ("", "", "")


def test_providers_deterministic():
    a, b = default_providers(), default_providers()
    ent = {"domain": "x.example", "first": "A", "last": "B"}
    for f in ("email", "phone", "title"):
        for _ in range(2):
            ra = a["midfinder"].lookup(f, ent, attempt=1)
            rb = b["midfinder"].lookup(f, ent, attempt=1)
            assert (ra and ra.value) == (rb and rb.value)


def always(rate_conf):
    return MockProvider("p", {"email": (0.1, 1.0, rate_conf)}, flaky=0)


def test_early_stop_when_confident():
    provs = {"hi": MockProvider("hi", {"email": (0.5, 1.0, 0.95)}, 0),
             "lo": MockProvider("lo", {"email": (0.1, 1.0, 0.5)}, 0)}
    eng = Engine(provs, {"email": [Step("hi"), Step("lo")]}, threshold=0.8)
    r = eng.enrich_row(LEAD)
    assert r["fields"]["email"].provider == "hi"
    assert r["fields"]["email"].tried == ["hi:hit"]  # lo never called
    assert r["row_cost"] == 0.5


def test_falls_through_when_low_confidence_and_keeps_best():
    provs = {"a": MockProvider("a", {"email": (0.1, 1.0, 0.5)}, 0),
             "b": MockProvider("b", {"email": (0.2, 1.0, 0.7)}, 0)}
    r = Engine(provs, {"email": [Step("a"), Step("b")]}, threshold=0.9).enrich_row(LEAD)
    f = r["fields"]["email"]
    assert f.provider == "b" and len(f.tried) == 2 and abs(f.cost - 0.3) < 1e-9


def test_conditional_branch_only_if_prior_empty_and_icp():
    provs = {"a": MockProvider("a", {"email": (0.1, 0.0, 0.9)}, 0),  # always misses
             "b": MockProvider("b", {"email": (0.4, 1.0, 0.9)}, 0)}
    plan = {"email": [Step("a"), Step("b", lambda ctx: icp_fit(ctx))]}
    fit = Engine(provs, plan).enrich_row({**LEAD, "company_size": "201-1000", "title": "VP Sales"})
    assert fit["fields"]["email"].status == "filled"
    nofit = Engine(provs, plan).enrich_row({**LEAD, "company_size": "1-10", "title": "VP Sales"})
    assert nofit["fields"]["email"].status == "empty"
    assert "b:skipped(cond)" in nofit["fields"]["email"].tried
    assert nofit["row_cost"] == 0


def test_row_and_total_budget_caps():
    provs = {"a": MockProvider("a", {"email": (0.4, 1.0, 0.9), "phone": (0.4, 1.0, 0.9)}, 0)}
    plan = {"email": [Step("a")], "phone": [Step("a")]}
    r = Engine(provs, plan, row_budget=0.5).enrich_row(LEAD)
    assert r["row_cost"] == 0.4 and r["fields"]["phone"].status == "budget_skipped"
    eng = Engine(provs, {"email": [Step("a")]}, total_budget=0.8)
    rows, _ = eng.run([{**LEAD, "first_name": n} for n in ("Ann", "Bob", "Cy")])
    assert eng.spent <= 0.8 + 1e-9 and sum(r["fields"]["email"].status == "filled" for r in rows) == 2


class Flaky(MockProvider):
    def __init__(self, fails):
        super().__init__("f", {"email": (0.1, 1.0, 0.9)}, 0)
        self.fails, self.n = fails, 0

    def lookup(self, field, entity, attempt=0):
        self.n += 1
        if self.n <= self.fails:
            raise TransientError("503")
        return super().lookup(field, entity, attempt=1)


def test_retries_then_success_and_giveup():
    p = Flaky(2)
    eng = Engine({"f": p}, {"email": [Step("f")]}, max_retries=2)
    assert eng.enrich_row(LEAD)["fields"]["email"].status == "filled" and eng.stats["retries"] == 2
    q = Flaky(10)
    eng2 = Engine({"f": q}, {"email": [Step("f")]}, max_retries=2)
    assert eng2.enrich_row(LEAD)["fields"]["email"].status == "empty" and eng2.stats["gave_up"] == 1
    assert eng2.spent == 0  # failures never charged


def test_cache_and_idempotency_no_double_charge(tmp_path):
    leads = make_leads(60, seed=1)
    path = str(tmp_path / "cache.json")
    e1 = Engine(default_providers(), ORDERINGS["cheap_first"](), cache=Cache(path))
    r1, _ = e1.run(leads)
    assert e1.spent > 0
    e2 = Engine(default_providers(), ORDERINGS["cheap_first"](), cache=Cache(path))  # rerun, same ledger
    r2, s2 = e2.run(leads)
    assert e2.spent == 0 and s2["calls"] == 0
    assert [r["fields"]["email"].value for r in r1] == [r["fields"]["email"].value for r in r2]


def test_company_level_fields_shared_across_people():
    provs = {"c": MockProvider("c", {"company_size": (0.1, 1.0, 0.9)}, 0)}
    eng = Engine(provs, {"company_size": [Step("c")]})
    eng.run([{**LEAD, "first_name": n} for n in ("Ann", "Bob", "Cy")])
    assert eng.stats["calls"] == 1 and eng.stats["cache_hits"] == 2


def test_dedupe_messy_duplicates():
    rows, stats = Engine(default_providers(), ORDERINGS["cheap_first"]()).run([
        {"first_name": "Jane", "last_name": "Doe", "domain": "https://www.Foo.example/"},
        {"first_name": " JANE ", "last_name": "doe", "domain": "foo.example"},
        {"first_name": "No", "last_name": "Domain", "domain": ""}])
    assert len(rows) == 1 and stats["duplicates_removed"] == 1


def test_comparison_and_csv(tmp_path):
    leads = make_leads(120, seed=3)
    sums = {}
    for name, mk in ORDERINGS.items():
        eng = Engine(default_providers(), mk())
        rows, stats = eng.run(leads)
        sums[name] = summarize(name, rows, stats)
        assert all(r["row_cost"] >= 0 for r in rows)
    # conditional skips premium spend on non-ICP rows; premium-first costs the most
    assert sums["conditional_icp"]["total_cost"] < sums["cheap_first"]["total_cost"] < sums["premium_first"]["total_cost"]
    p = tmp_path / "o.csv"
    write_csv(rows, str(p))
    got = list(csv.DictReader(open(p)))
    assert len(got) == len(rows) and "email_confidence" in got[0]
