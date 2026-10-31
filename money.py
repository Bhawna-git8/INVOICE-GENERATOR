import re
from decimal import Decimal as D, ROUND_HALF_UP

def q2(x):
    return D(str(x)).quantize(D("0.01"), ROUND_HALF_UP)

def num(x, default=None):
    """Coerce '₹1,500', 'Rs. 800', 12 -> float. Returns default if not a number."""
    if isinstance(x, bool): return default
    if isinstance(x, (int, float)): return float(x)
    s = re.sub(r"[₹,\s]|rs\.?|inr", "", str(x), flags=re.I)
    try: return float(s)
    except ValueError: return default

def inr(x):
    """Indian digit grouping: 1234567.5 -> 12,34,567.50"""
    s = f"{q2(x):.2f}"
    neg = s.startswith("-"); s = s.lstrip("-")
    whole, dec = s.split(".")
    if len(whole) > 3:
        head, tail, parts = whole[:-3], whole[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head: parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return ("-" if neg else "") + whole + "." + dec
