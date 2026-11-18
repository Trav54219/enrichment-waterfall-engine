import csv
from .providers import FIELDS


def write_csv(rows, path):
    cols = ["domain", "first_name", "last_name", "title_seniority", "title_function", "icp_fit"]
    for f in FIELDS:
        cols += [f, f"{f}_confidence", f"{f}_provider"]
    cols.append("row_cost")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            line = [r["domain"], r["first_name"], r["last_name"], r["title_seniority"], r["title_function"], r["icp_fit"]]
            for f in FIELDS:
                fr = r["fields"][f]
                line += [fr.value, fr.confidence if fr.value else "", fr.provider]
            line.append(r["row_cost"])
            w.writerow(line)


def summarize(name, rows, stats):
    n = len(rows)
    out = {"ordering": name, "rows": n, "total_cost": round(sum(r["row_cost"] for r in rows), 2),
           "cost_per_row": round(sum(r["row_cost"] for r in rows) / n, 4) if n else 0}
    filled_total = 0
    for f in FIELDS:
        filled = [r["fields"][f] for r in rows if r["fields"][f].status == "filled"]
        filled_total += len(filled)
        out[f"{f}_fill"] = round(len(filled) / n, 3) if n else 0
        out[f"{f}_cost_per_filled"] = round(sum(x.cost for x in filled) / len(filled), 4) if filled else None
        out[f"{f}_avg_conf"] = round(sum(x.confidence for x in filled) / len(filled), 3) if filled else None
    out["cost_per_filled_field"] = round(out["total_cost"] / filled_total, 4) if filled_total else None
    out["fields_filled"] = filled_total
    out["calls"], out["retries"], out["cache_hits"] = stats["calls"], stats["retries"], stats["cache_hits"]
    return out


def markdown(summaries):
    h = "| ordering | rows | total cost | cost/row | cost/filled field | fields filled | calls |\n|---|---|---|---|---|---|---|\n"
    t = "".join(f"| {s['ordering']} | {s['rows']} | {s['total_cost']} | {s['cost_per_row']} | "
                f"{s['cost_per_filled_field']} | {s['fields_filled']} | {s['calls']} |\n" for s in summaries)
    h2 = "\n\nFill rate by field\n\n| ordering | " + " | ".join(FIELDS) + " |\n|---|" + "---|" * len(FIELDS) + "\n"
    t2 = "".join(f"| {s['ordering']} | " + " | ".join(f"{s[f+'_fill']:.0%}" for f in FIELDS) + " |\n" for s in summaries)
    h3 = "\n\nAverage confidence of filled fields\n\n| ordering | " + " | ".join(FIELDS) + " |\n|---|" + "---|" * len(FIELDS) + "\n"
    t3 = "".join(f"| {s['ordering']} | " + " | ".join(str(s[f+'_avg_conf']) for f in FIELDS) + " |\n" for s in summaries)
    return h + t + h2 + t2 + h3 + t3
