"""Synthetic lead list. Fake names and invented company domains (.example)."""
import random

FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Riley", "Casey", "Jamie", "Avery", "Quinn",
         "Drew", "Reese", "Skyler", "Parker", "Rowan", "Blake", "Harper", "Emerson"]
LAST = ["Alder", "Birch", "Cedar", "Dunn", "Ellis", "Foster", "Grove", "Hale", "Ivers", "Jarvis",
        "Keene", "Lowe", "Marsh", "Nash", "Orr", "Pike", "Reyes", "Stone"]
TITLES = ["VP Sales", "Sr. Director of Marketing", "Head of Growth", "RevOps Manager", "CEO & Founder",
          "Software Engineer", "Account Executive", "Chief Financial Officer", "", "", "", "",
          "Operations Manager", "Sales Development Rep"]
WORDS = ["north", "bright", "vertex", "lumen", "orbit", "cobalt", "ember", "fable", "gamut", "helix"]
INDUSTRIES = ["software", "logistics", "fintech", "healthcare", "retail"]


def make_leads(n=300, seed=7, dup_rate=0.08):
    rng = random.Random(seed)
    companies = [f"{rng.choice(WORDS)}{rng.choice(WORDS)}{i}.example" for i in range(max(10, n // 4))]
    leads = []
    for _ in range(n):
        dom = rng.choice(companies)
        first, last = rng.choice(FIRST), rng.choice(LAST)
        messy = rng.choice([dom, "https://www." + dom.upper() + "/", "www." + dom + "/about", dom])
        name = rng.choice([(first, last), (first.upper(), last.lower()), (f" {first} ", last)])
        leads.append({"first_name": name[0], "last_name": name[1], "domain": messy,
                      "title": rng.choice(TITLES), "industry": rng.choice(INDUSTRIES)})
    for _ in range(int(n * dup_rate)):  # exact-entity dupes with messy formatting
        d = dict(rng.choice(leads))
        d["domain"] = "https://" + d["domain"].replace("https://", "").lower()
        leads.append(d)
    rng.shuffle(leads)
    return leads
