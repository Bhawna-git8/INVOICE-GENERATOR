# InvoiceAgent v2 (local AI agent)

A tool-using agent: the local model (Ollama) decides which tool to call, and the tools do all the
math, GST split, numbering, PDFs and saving. The model never calculates.

## Windows quick start
1. Install Python 3.10+ (python.org, tick "Add to PATH") and Ollama (ollama.com/download).
2. Double-click `setup_and_run.bat`. First run installs packages and downloads `qwen2.5:7b` (~4.7 GB).
3. Choose 1 (Streamlit) or 2 (Gradio).

Manual: `pip install -r requirements.txt`, `ollama pull qwen2.5:7b`, then
`streamlit run app_streamlit.py` or `python app_gradio.py`.

## Try it
- "Invoice Sharma Traders for 10 hrs web design at 1500 and 2 banners at 800 each, 18% GST, due in 15 days"
- reply "yes" to save -> PDF in InvoiceVault/PDFs, note in InvoiceVault/Invoices
- "Which invoices are overdue?" / "Mark INV-2026-0001 as paid" / "Write a reminder for INV-2026-0001"
- "Invoice Patel Steel for 1 gate at 40000" -> it asks for the state, saves the client, drafts the invoice

## CPU-only laptop notes
Expect 20-60 s per reply with qwen2.5:7b. Faster, less reliable: `set OLLAMA_MODEL=qwen2.5:3b`.
Open `InvoiceVault/` as an Obsidian vault; edit `Business.md` with your real details.

## Tests (no Ollama needed): `python tests/run_tests.py`
