"""Minimal Ollama client (stdlib only)."""
import os, json, urllib.request, urllib.error

URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600"))   # CPU-only laptops are slow

class LLMError(Exception): pass

def chat(messages, tools=None, model=None):
    model = model or MODEL
    body = {"model": model, "messages": messages, "stream": False, "keep_alive": "30m",
            "options": {"temperature": 0.1, "num_ctx": 4096}}
    if tools: body["tools"] = tools
    req = urllib.request.Request(URL + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())["message"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")
        if "does not support tools" in detail: raise LLMError(f"Model '{model}' can't use tools. Use qwen2.5:7b or llama3.1:8b.")
        if e.code == 404: raise LLMError(f"Model '{model}' is not downloaded. Run: ollama pull {model}")
        raise LLMError(f"Ollama error {e.code}: {detail[:200]}")
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise LLMError(f"Can't reach Ollama at {URL} ({e}). Start the Ollama app, or run 'ollama serve'.")

def status(model=None):
    model = model or MODEL
    try:
        with urllib.request.urlopen(URL + "/api/tags", timeout=3) as r:
            names = [m["name"] for m in json.loads(r.read()).get("models", [])]
        ready = any(n == model or n.split(":")[0] == model for n in names) or model in names
        return {"running": True, "models": names, "model_ready": ready}
    except Exception:
        return {"running": False, "models": [], "model_ready": False}
