"""Gradio UI:  python app_gradio.py   (opens http://127.0.0.1:7860)"""
from pathlib import Path
import gradio as gr
import agent, llm, tools, vault
from money import inr

def status_md():
    s = llm.status()
    if not s["running"]: return "🔴 **Ollama is not running.** Start the Ollama app or run `ollama serve`."
    if not s["model_ready"]: return f"🟡 Model not downloaded. Run `ollama pull {llm.MODEL}`"
    return f"🟢 Ollama ready · `{llm.MODEL}` · CPU replies can take 20-60 s"

def invoice_rows():
    return [[i["number"], i["client"], inr(i["total"]), str(i["due"]), vault.effective_status(i)] for i in vault.list_invoices()]

def steps_md(trace):
    return "\n\n".join(f"**{t['tool']}** `{t['args']}`\n→ `{str(t['result'])[:400]}`" for t in trace) or "No tools used."

def respond(text, chat, hist, ctx, auto):
    if not text.strip(): return chat, hist, ctx, "", None, "", invoice_rows()
    ctx.auto_confirm = bool(auto)
    try: reply, hist, trace = agent.run(text, hist, ctx, chat_fn=llm.chat)
    except llm.LLMError as e: reply, trace = f"⚠️ {e}", []
    chat = (chat or []) + [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
    pdf = ctx.last_pdf if ctx.last_pdf and Path(ctx.last_pdf).exists() else None
    return chat, hist, ctx, "", pdf, steps_md(trace), invoice_rows()

def set_status(number, status):
    if number: vault.set_status(number.strip().upper(), status)
    return invoice_rows()

with gr.Blocks(title="InvoiceAgent") as demo:
    gr.Markdown("# 🧾 InvoiceAgent")
    banner = gr.Markdown()
    ctx, hist = gr.State(tools.Ctx()), gr.State([])
    with gr.Tab("Chat"):
        try: bot = gr.Chatbot(type="messages", height=420)
        except TypeError: bot = gr.Chatbot(height=420)   # newer Gradio: messages format is the default
        box = gr.Textbox(placeholder="Invoice Sharma Traders for 10 hrs web design at 1500, 18% GST, due in 15 days", label="Message", lines=2)
        with gr.Row():
            send = gr.Button("Send", variant="primary"); auto = gr.Checkbox(label="Save without asking (not recommended)")
        pdf = gr.File(label="Latest invoice PDF")
        steps = gr.Markdown(label="Agent steps")
    with gr.Tab("Invoices"):
        table = gr.Dataframe(headers=["No", "Client", "Total", "Due", "Status"], value=invoice_rows, interactive=False)
        with gr.Row():
            num = gr.Textbox(label="Invoice number (e.g. INV-2026-0001)")
            st_ = gr.Dropdown(["Draft", "Sent", "Paid"], value="Paid", label="Set status")
            upd = gr.Button("Update")
    with gr.Tab("Clients"):
        gr.Dataframe(value=lambda: [[c["name"], c.get("state", ""), c.get("gstin", ""), c.get("email", "")] for c in vault.list_clients()],
                     headers=["Name", "State", "GSTIN", "Email"], interactive=False)
    outs = [bot, hist, ctx, box, pdf, steps, table]
    send.click(respond, [box, bot, hist, ctx, auto], outs); box.submit(respond, [box, bot, hist, ctx, auto], outs)
    upd.click(set_status, [num, st_], table)
    demo.load(status_md, None, banner)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1")
