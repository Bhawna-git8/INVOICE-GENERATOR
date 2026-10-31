"""Streamlit UI:  streamlit run app_streamlit.py"""
from pathlib import Path
import streamlit as st
import agent, llm, tools, vault
from money import inr

st.set_page_config(page_title="InvoiceAgent", page_icon="🧾", layout="wide")
ss = st.session_state
ss.setdefault("ctx", tools.Ctx()); ss.setdefault("hist", []); ss.setdefault("shown", [])

with st.sidebar:
    st.header("🧾 InvoiceAgent")
    model = st.text_input("Ollama model", llm.MODEL)
    s = llm.status(model)
    if not s["running"]: st.error("Ollama is not running. Start the Ollama app or run `ollama serve`.")
    elif not s["model_ready"]: st.warning(f"Model not downloaded. Run: `ollama pull {model}`")
    else: st.success(f"Ollama ready · {model}")
    ss.ctx.auto_confirm = st.toggle("Save without asking (not recommended)", False)
    st.caption("On a laptop CPU each reply can take 20-60 seconds. Be patient on the first message (the model loads).")
    if st.button("New conversation"):
        ss.hist, ss.shown = [], []; ss.ctx.drafts.clear(); ss.ctx.last_pdf = None; st.rerun()

chat_tab, inv_tab, cli_tab = st.tabs(["💬 Chat", "📚 Invoices", "👥 Clients"])

with chat_tab:
    if not ss.shown:
        st.info('Try: "Invoice Sharma Traders for 10 hrs web design at 1500 and 2 banners at 800 each, 18% GST, due in 15 days"\n\n'
                'Or: "Which invoices are overdue?", "Mark INV-2026-0001 as paid", "Write a reminder for INV-2026-0001"')
    for m in ss.shown:
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if m.get("trace"):
                with st.expander(f"Agent steps ({len(m['trace'])})"):
                    for t in m["trace"]:
                        st.code(f"{t['tool']}({t['args']})\n-> {str(t['result'])[:600]}", language="text")
    if ss.ctx.last_pdf and Path(ss.ctx.last_pdf).exists():
        p = Path(ss.ctx.last_pdf)
        st.download_button(f"⬇ Download {p.name}", p.read_bytes(), p.name, "application/pdf")
    prompt = st.chat_input("Describe an invoice or ask about your invoices...")
    if prompt:
        ss.shown.append({"role": "user", "content": prompt})
        with st.spinner("Agent is working (can take up to a minute on CPU)..."):
            try:
                reply, ss.hist, trace = agent.run(prompt, ss.hist, ss.ctx, chat_fn=lambda m, t: llm.chat(m, t, model=model))
            except llm.LLMError as e:
                reply, trace = f"⚠️ {e}", []
        ss.shown.append({"role": "assistant", "content": reply, "trace": trace})
        st.rerun()

with inv_tab:
    invs = vault.list_invoices()
    st.dataframe([{"No": i["number"], "Client": i["client"], "Total": inr(i["total"]), "Due": str(i["due"]),
                   "Status": vault.effective_status(i)} for i in invs], use_container_width=True)
    if invs:
        a, b, c = st.columns([2, 2, 1])
        pick = a.selectbox("Invoice", [i["number"] for i in invs]); new = b.selectbox("Set status", ["Draft", "Sent", "Paid"])
        if c.button("Update"): vault.set_status(pick, new); st.rerun()
        pdf = vault.VAULT / "PDFs" / f"{pick}.pdf"
        if pdf.exists(): st.download_button(f"⬇ {pick}.pdf", pdf.read_bytes(), pdf.name, "application/pdf")

with cli_tab:
    st.dataframe(vault.list_clients(), use_container_width=True)
