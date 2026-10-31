"""Obsidian-compatible vault: markdown notes with YAML frontmatter."""
import os, re, glob, difflib
from datetime import date
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
VAULT = Path(os.environ.get("INVOICE_VAULT", ROOT / "InvoiceVault"))

def read_note(path):
    t = Path(path).read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", t, re.S)
    return ((yaml.safe_load(m.group(1)) or {}), m.group(2)) if m else ({}, t)

def write_note(path, meta, body=""):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n" + body, encoding="utf-8")

def business():
    return read_note(VAULT / "Business.md")[0]

# ---- clients ----
def list_clients():
    out = []
    for f in sorted((VAULT / "Clients").glob("*.md")):
        meta, _ = read_note(f); meta.setdefault("name", f.stem); out.append(meta)
    return out

def find_client(name):
    n = (name or "").lower().strip()
    if not n: return None
    cl = list_clients()
    for c in cl:
        if c["name"].lower() == n: return c
    for c in cl:
        x = c["name"].lower()
        if n in x or x in n: return c
    close = difflib.get_close_matches(n, [c["name"].lower() for c in cl], 1, 0.75)
    return next((c for c in cl if c["name"].lower() == close[0]), None) if close else None

def similar_clients(name):
    names = [c["name"] for c in list_clients()]
    return difflib.get_close_matches(name or "", names, 3, 0.4)

def save_client(meta):
    safe = re.sub(r'[\\/:*?"<>|]', "", meta["name"]).strip()
    write_note(VAULT / "Clients" / f"{safe}.md", meta, f"# {meta['name']}\n")

# ---- invoices ----
def list_invoices():
    return [read_note(f)[0] for f in sorted((VAULT / "Invoices").glob("*.md"), reverse=True)]

def get_invoice(number):
    p = VAULT / "Invoices" / f"{number}.md"
    return read_note(p)[0] if p.exists() else None

def set_status(number, status):
    p = VAULT / "Invoices" / f"{number}.md"
    if not p.exists(): return False
    meta, body = read_note(p); meta["status"] = status; write_note(p, meta, body); return True

def effective_status(inv):
    if inv.get("status") != "Paid" and str(inv["due"]) < date.today().isoformat(): return "Overdue"
    return inv.get("status", "Draft")

def next_number():
    prefix = f"{business().get('invoice_prefix', 'INV')}-{date.today().year}-"
    nums = [int(m.group(1)) for f in glob.glob(str(VAULT / "Invoices" / f"{prefix}*.md"))
            if (m := re.search(r"-(\d+)\.md$", f))]
    return f"{prefix}{max(nums, default=0) + 1:04d}"
