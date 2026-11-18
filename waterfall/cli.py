"""python -m waterfall.cli [--n 300] [--seed 7] [--out out]"""
import argparse
import os

from .engine import Engine
from .plans import ORDERINGS
from .providers import default_providers
from .report import markdown, summarize, write_csv
from .synth import make_leads


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="out")
    ap.add_argument("--row-budget", type=float, default=None)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    leads = make_leads(a.n, a.seed)
    sums = []
    for name, mk in ORDERINGS.items():
        eng = Engine(default_providers(), mk(), row_budget=a.row_budget)  # fresh cache per ordering
        rows, stats = eng.run(leads)
        write_csv(rows, os.path.join(a.out, f"enriched_{name}.csv"))
        sums.append(summarize(name, rows, stats))
        print(f"{name}: {stats['input']} in, {stats['duplicates_removed']} dupes removed")
    md = f"# Waterfall ordering comparison (synthetic leads, mock providers, n={a.n}, seed={a.seed})\n\n" + markdown(sums)
    open(os.path.join(a.out, "report.md"), "w").write(md)
    print("\n" + md)


if __name__ == "__main__":
    main()
