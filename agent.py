"""The agent loop: the model chooses tools, tools do the work, loop until it answers."""
import re, json
from datetime import date
import llm, tools

SYSTEM = """You are InvoiceAgent, an assistant for a small business that creates GST invoices. Today is {today}.
You work ONLY through tools. Rules:
1. NEVER calculate totals, tax, dates or invoice numbers yourself. Quote numbers only from tool results.
2. To invoice someone: call draft_invoice directly. If it says client_not_found, ask the user for the client's state (GSTIN, email, address are optional), call add_client, then call draft_invoice again.
3. After draft_invoice, show a short summary (client, items, subtotal, tax type, total, due date) and ask "Save this invoice? (yes/no)".
4. Call create_invoice ONLY when the user's latest message says yes.
5. If a client, item, quantity or rate is missing, ask ONE short question.
6. Use list_invoices, mark_status and draft_reminder for tracking and payment follow-ups.
Keep replies brief. Use the Rs. or ₹ sign for amounts."""

YES = re.compile(r"\b(yes|y|yeah|yep|ok|okay|confirm(ed)?|save( it)?|go ahead|do it|proceed|sure|haan|ha|kar do|theek hai)\b", re.I)
NO = re.compile(r"\b(no|nope|don'?t|do not|cancel|stop|wait|nahi|nahin)\b", re.I)

def user_confirms(text):
    return bool(YES.search(text)) and not NO.search(text)

def _text_calls(msg):
    """Small models sometimes print the tool call as JSON text instead of using tool_calls."""
    m = re.search(r"\{.*\}", msg.get("content") or "", re.S)
    if not m: return []
    try: d = json.loads(m.group(0))
    except Exception: return []
    name = d.get("name") or d.get("tool")
    if name in tools.TOOL_FUNCS:
        return [{"function": {"name": name, "arguments": d.get("arguments") or d.get("parameters") or {}}}]
    return []

def _trim(msgs, keep=24):
    msgs = msgs[-keep:]
    while msgs and msgs[0]["role"] != "user": msgs = msgs[1:]
    return msgs

def run(user_text, history, ctx, chat_fn=None, max_steps=6):
    """Returns (reply, new_history, trace). history excludes the system prompt."""
    chat_fn = chat_fn or llm.chat
    ctx.user_confirmed = user_confirms(user_text)
    msgs = [{"role": "system", "content": SYSTEM.format(today=date.today().strftime("%d %b %Y"))}] + list(history) + [{"role": "user", "content": user_text}]
    trace = []
    for _ in range(max_steps):
        msg = chat_fn(msgs, tools.TOOLS)
        calls = msg.get("tool_calls") or _text_calls(msg)
        if not calls:
            reply = (msg.get("content") or "").strip() or "Done."
            msgs.append({"role": "assistant", "content": reply})
            return reply, _trim(msgs[1:]), trace
        msgs.append({"role": "assistant", "content": "", "tool_calls": calls})
        for c in calls:
            fn = c["function"]; name, args = fn["name"], fn.get("arguments") or {}
            result = tools.dispatch(ctx, name, args)
            trace.append({"tool": name, "args": args, "result": result})
            msgs.append({"role": "tool", "tool_name": name, "content": json.dumps(result, ensure_ascii=False)})
    reply = "I couldn't finish that in a few steps. Could you rephrase or break it into smaller requests?"
    msgs.append({"role": "assistant", "content": reply})
    return reply, _trim(msgs[1:]), trace
