"""Waterfall orderings to compare. Each maps field -> ordered Steps."""
from .engine import Step, icp_fit
from .providers import FIELDS


def _by(order, extra=None):
    plan = {}
    for f in FIELDS:
        steps = [Step(p) for p in order]
        plan[f] = steps
    plan.update(extra or {})
    return plan


CHEAP_FIRST = ["scrapely", "techscan", "budgetdata", "midfinder", "premiumgraph"]
PREMIUM_FIRST = ["premiumgraph", "midfinder", "budgetdata", "techscan", "scrapely"]


def cheap_first():
    return _by(CHEAP_FIRST)


def premium_first():
    return _by(PREMIUM_FIRST)


def conditional():
    """Cheap tiers for everything; premium/mid only when the row is ICP-fit.
    Phone (expensive) runs only if an email was found and the row fits ICP."""
    fit = lambda ctx: icp_fit(ctx)
    plan = _by(CHEAP_FIRST)
    for f in ("email", "title"):
        plan[f] = [Step("scrapely"), Step("budgetdata"), Step("midfinder", fit), Step("premiumgraph", fit)]
    plan["phone"] = [Step("budgetdata", fit), Step("midfinder", lambda c: fit(c) and bool(c.get("email"))),
                     Step("premiumgraph", lambda c: fit(c) and bool(c.get("email")))]
    return plan


ORDERINGS = {"cheap_first": cheap_first, "premium_first": premium_first, "conditional_icp": conditional}
