"""Tools the agent can call. RULE: the model never calculates. Every number comes from here."""
import json, re, inspect
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal as D
import vault, pdfgen
from money import q2, num, inr

@dataclass
class Ctx:
    drafts: dict = field(default_factory=dict)
    auto_confirm: bool = False       # UI toggle: allow saving without an explicit "yes"
    user_confirmed: bool = False     # set by the agent from the user's latest message
    last_pdf: str | None = None
    counter: int = 0

# ---------- pure helpers ----------
def _items(raw):
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except Exception: raise ValueError("items must be a list of {desc, qty, rate}")
    if isinstance(raw, dict): raw = [raw]
    out = []
    for r in raw or []:
        out.append({"desc": str(r.get("desc") or r.get("description") or r.get("name") or "").strip(),
                    "qty": num(r.get("qty", r.get("quantity", 1)), 0),
                    "rate": num(r.get("rate", r.get("price")), 0),
                    "unit": str(r.get("unit") or "").strip()})
    return out

def compute(items, gst, client_state, biz_state):
    rows, sub = [], D(0)
    for i in items:
        amt = q2(D(str(i["qty"])) * D(str(i["rate"]))); rows.append({**i, "amount": float(amt)}); sub += amt
    sub = q2(sub); tax = q2(sub * D(str(gst)) / 100)
    cs, bs = (client_state or "").strip().lower(), (biz_state or "").strip().lower()
    same = (cs == bs) if cs and bs else True
    half = q2(tax / 2)
    return rows, same, {"subtotal": float(sub), "tax": float(tax), "cgst": float(half) if same else 0.0,
                        "sgst": float(tax - half) if same else 0.0, "igst": 0.0 if same else float(tax), "total": float(sub + tax)}

def _problems(items, gst):
    p = []
    if not items: p.append("No line items.")
    for i in items:
        if not i["desc"]: p.append("An item has no description.")
        if i["qty"] <= 0: p.append(f"Item '{i['desc']}' needs a quantity above zero.")
        if i["rate"] <= 0: p.append(f"Item '{i['desc']}' needs a rate above zero.")
    if not 0 <= gst <= 28: p.append("GST percent must be between 0 and 28.")
    return p

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$")

# ---------- tools ----------
def find_client(ctx, name=""):
    """Look up a saved client, or list all clients when name is empty."""
    if not name: return {"clients": [{"name": c["name"], "state": c.get("state", "")} for c in vault.list_clients()]}
    c = vault.find_client(name)
    if c: return {"found": True, "client": c}
    return {"found": False, "similar": vault.similar_clients(name), "hint": "Ask the user for the client's state (GSTIN, email, address optional), then call add_client."}

def add_client(ctx, name, state, gstin="", email="", address=""):
    """Save a new client."""
    if not str(name).strip() or not str(state).strip(): return {"error": "name and state are required"}
    meta = {"name": str(name).strip(), "state": str(state).strip(), "gstin": str(gstin or "").strip().upper(),
            "email": str(email or "").strip(), "address": str(address or "").strip()}
    vault.save_client(meta)
    w = ["GSTIN format looks invalid."] if meta["gstin"] and not GSTIN_RE.match(meta["gstin"]) else []
    return {"saved": True, "client": meta, "warnings": w}

def draft_invoice(ctx, client_name, items, gst_percent=None, due_days=None):
    """Create a DRAFT (not saved). Returns computed totals to show the user."""
    biz = vault.business(); client = vault.find_client(client_name)
    if not client:
        return {"error": "client_not_found", "similar": vault.similar_clients(client_name),
                "hint": "Ask the user for the client's state, then call add_client, then draft_invoice again."}
    items = _items(items)
    gst = num(gst_percent, None); gst = float(biz.get("default_gst", 18)) if gst is None else gst
    days = int(num(due_days, None) if num(due_days, None) is not None else biz.get("default_due_days", 15))
    probs = _problems(items, gst)
    if probs: return {"error": "invalid_input", "problems": probs, "hint": "Ask the user to correct these."}
    rows, same, totals = compute(items, gst, client.get("state"), biz.get("state"))
    ctx.counter += 1; did = f"D{ctx.counter}"; today = date.today()
    ctx.drafts[did] = {"client": client, "items": rows, "gst_percent": gst, "same_state": same, "totals": totals,
                       "date": today.isoformat(), "due": (today + timedelta(days=days)).isoformat()}
    warn = [] if client.get("state") else ["Client state missing: assumed same state (CGST+SGST)."]
    return {"draft_id": did, "client": client["name"], "items": [{"desc": r["desc"], "qty": r["qty"], "unit": r["unit"], "rate": r["rate"], "amount": r["amount"]} for r in rows],
            "gst_percent": gst, "tax_type": "CGST+SGST" if same else "IGST", **totals, "due_date": ctx.drafts[did]["due"], "warnings": warn,
            "next_step": "Show this summary to the user and ask if they want to save it. Do NOT call create_invoice yet."}

def create_invoice(ctx, draft_id):
    """Save a confirmed draft: assigns number, writes PDF and vault note."""
    if not (ctx.user_confirmed or ctx.auto_confirm):
        return {"error": "not_confirmed", "hint": "The user has not confirmed. Ask 'Save this invoice? (yes/no)' and wait."}
    d = ctx.drafts.get(draft_id)
    if not d: return {"error": "unknown_draft_id", "known": list(ctx.drafts)}
    number = vault.next_number(); inv = {**d, "number": number, "status": "Draft"}
    pdf = vault.VAULT / "PDFs" / f"{number}.pdf"; pdf.parent.mkdir(parents=True, exist_ok=True)
    pdfgen.render_invoice_pdf(pdf, vault.business(), inv)
    t = d["totals"]
    meta = {"number": number, "client": d["client"]["name"], "date": d["date"], "due": d["due"], "status": "Draft",
            "subtotal": t["subtotal"], "tax": t["tax"], "total": t["total"], "gst_percent": d["gst_percent"],
            "same_state": d["same_state"], "items": d["items"], "pdf": f"PDFs/{number}.pdf"}
    rows = "\n".join(f"| {i['desc']} | {i['qty']:g} | {inr(i['rate'])} | {inr(i['amount'])} |" for i in d["items"])
    vault.write_note(vault.VAULT / "Invoices" / f"{number}.md", meta,
                     f"# {number}\n\nClient: [[Clients/{d['client']['name']}|{d['client']['name']}]]  \nDue: {d['due']}  \nTotal: **{inr(t['total'])}**\n\n| Item | Qty | Rate | Amount |\n|---|---|---|---|\n{rows}\n")
    del ctx.drafts[draft_id]; ctx.last_pdf = str(pdf)
    return {"saved": True, "number": number, "total": t["total"], "pdf": str(pdf)}

def list_invoices(ctx, status=None):
    """List invoices (max 20, newest first). status: Draft, Sent, Paid or Overdue."""
    rows = [{"number": i["number"], "client": i["client"], "total": i["total"], "due": str(i["due"]), "status": vault.effective_status(i)} for i in vault.list_invoices()]
    if status: rows = [r for r in rows if r["status"].lower() == str(status).lower()]
    return {"count": len(rows), "total_amount": float(q2(sum(D(str(r["total"])) for r in rows))), "invoices": rows[:20]}

def mark_status(ctx, number, status):
    """Set an invoice status to Draft, Sent or Paid."""
    s = str(status).capitalize()
    if s not in ("Draft", "Sent", "Paid"): return {"error": "status must be Draft, Sent or Paid"}
    return {"updated": True, "number": number, "status": s} if vault.set_status(str(number).upper(), s) else {"error": f"invoice {number} not found"}

def draft_reminder(ctx, number):
    """Write a polite payment reminder for an unpaid invoice."""
    inv = vault.get_invoice(str(number).upper())
    if not inv: return {"error": f"invoice {number} not found"}
    if inv.get("status") == "Paid": return {"error": "invoice is already paid"}
    biz = vault.business(); due = date.fromisoformat(str(inv["due"])); late = (date.today() - due).days
    when = f"was due on {due.strftime('%d %b %Y')} ({late} days ago)" if late > 0 else f"is due on {due.strftime('%d %b %Y')}"
    pay = f" You can pay via UPI: {biz['upi']}." if biz.get("upi") else ""
    return {"subject": f"Reminder: invoice {inv['number']}",
            "body": f"Hi {inv['client']},\n\nA gentle reminder that invoice {inv['number']} for Rs. {inr(inv['total'])} {when}.{pay}\nPlease ignore this if you have already paid.\n\nThank you,\n{biz.get('name','')}"}

TOOL_FUNCS = {f.__name__: f for f in (find_client, add_client, draft_invoice, create_invoice, list_invoices, mark_status, draft_reminder)}

def _fn(name, desc, props, req=()):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": list(req)}}}
_s, _n = {"type": "string"}, {"type": "number"}
TOOLS = [
    _fn("draft_invoice", "Create a draft invoice for a saved client. Totals and GST are computed by the tool. Does not save.",
        {"client_name": _s, "items": {"type": "array", "description": "line items", "items": {"type": "object", "properties": {"desc": _s, "qty": _n, "rate": {"type": "number", "description": "price of ONE unit"}, "unit": _s}, "required": ["desc", "qty", "rate"]}},
         "gst_percent": _n, "due_days": _n}, ("client_name", "items")),
    _fn("create_invoice", "Save a draft as a final invoice with PDF. Only after the user said yes.", {"draft_id": _s}, ("draft_id",)),
    _fn("find_client", "Look up a saved client by name, or list all clients if name is empty.", {"name": _s}),
    _fn("add_client", "Save a new client. State is required.", {"name": _s, "state": _s, "gstin": _s, "email": _s, "address": _s}, ("name", "state")),
    _fn("list_invoices", "List invoices, optionally filtered by status (Draft, Sent, Paid, Overdue).", {"status": _s}),
    _fn("mark_status", "Set an invoice status to Draft, Sent or Paid.", {"number": _s, "status": _s}, ("number", "status")),
    _fn("draft_reminder", "Write a payment reminder message for an unpaid invoice number.", {"number": _s}, ("number",)),
]

def dispatch(ctx, name, args):
    fn = TOOL_FUNCS.get(name)
    if not fn: return {"error": f"unknown tool '{name}'", "available": list(TOOL_FUNCS)}
    if isinstance(args, str):
        try: args = json.loads(args)
        except Exception: args = {}
    ok = inspect.signature(fn).parameters
    try: return fn(ctx, **{k: v for k, v in (args or {}).items() if k in ok})
    except TypeError as e: return {"error": f"bad arguments: {e}"}
    except Exception as e: return {"error": f"{type(e).__name__}: {e}"}
