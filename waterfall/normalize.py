"""Normalization and dedupe helpers: domains, names, titles."""
import re
from urllib.parse import urlparse

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "mba", "cpa"}


def normalize_domain(raw):
    """'https://WWW.Acme.com/about' -> 'acme.com'; emails accepted; '' if unusable."""
    if not raw:
        return ""
    s = str(raw).strip().lower()
    if "@" in s and "/" not in s:
        s = s.split("@", 1)[1]
    if "://" not in s:
        s = "//" + s
    host = (urlparse(s).hostname or "").strip(".")
    if host.startswith("www."):
        host = host[4:]
    if "." not in host or " " in host:
        return ""
    return host


def normalize_name(raw):
    """'  SMITH, jane  ' / 'jane smith jr.' -> ('Jane', 'Smith')."""
    if not raw:
        return ("", "")
    s = re.sub(r"\s+", " ", str(raw).strip())
    if "," in s:
        last, _, first = s.partition(",")
        s = f"{first.strip()} {last.strip()}"
    parts = [p for p in s.replace(".", " ").split() if p.lower() not in _SUFFIXES]
    if not parts:
        return ("", "")
    cap = lambda w: "-".join("'".join(y.capitalize() for y in x.split("'")) for x in w.split("-"))
    first, last = parts[0], " ".join(parts[1:])
    return (cap(first), " ".join(cap(p) for p in last.split()))


# Ordered: first match wins. (regex, seniority)
_SENIORITY = [
    (r"\b(founder|co-?founder|owner|president|ceo|cto|cfo|coo|cmo|cro|chief)\b", "c_level"),
    (r"\b(svp|evp|vp|vice president)\b", "vp"),
    (r"\b(head of|director)\b", "director"),
    (r"\b(manager|lead|supervisor)\b", "manager"),
    (r"\b(intern|trainee)\b", "entry"),
]
_FUNCTION = [
    (r"\b(revenue operations|revops|sales operations|sales ops|marketing operations)\b", "revops"),
    (r"\b(sales|business development|bdr|sdr|account executive|revenue|cro)\b", "sales"),
    (r"\b(marketing|growth|demand gen|brand|cmo|content)\b", "marketing"),
    (r"\b(engineer|engineering|developer|cto|software|data|devops)\b", "engineering"),
    (r"\b(finance|cfo|accounting|controller)\b", "finance"),
    (r"\b(operations|coo|supply chain|logistics)\b", "operations"),
    (r"\b(people|hr|human resources|talent|recruit)\b", "hr"),
]


def classify_title(raw):
    """Return (clean_title, seniority, function). Unknowns -> 'ic' / 'other'."""
    if not raw or not str(raw).strip():
        return ("", "", "")
    t = re.sub(r"\s+", " ", str(raw).strip())
    low = t.lower().replace("&", "and")
    low = re.sub(r"\bsr\.?\b", "senior", low)
    low = re.sub(r"\bvp\.?\b", "vp", low)
    sen = "ic"
    for pat, label in _SENIORITY:
        if re.search(pat, low):
            sen = label
            break
    fn = "other"
    for pat, label in _FUNCTION:
        if re.search(pat, low):
            fn = label
            break
    return (t, sen, fn)


def lead_key(domain, first, last):
    """Dedupe key for a person; company-level key is just the domain."""
    return f"{domain}|{first.lower()}|{last.lower()}"
