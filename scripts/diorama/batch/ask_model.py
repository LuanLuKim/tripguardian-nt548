"""ask_model.py: call a vision model as a FUNCTION (prompt + images -> text/JSON). No agent, no shell, no sandbox: the
caller's script runs build/shot/checks and sends the results back. Works while Codex's bwrap sandbox is unusable.
Models (owner 11-04: prefer the free Gemma lanes, sol costs quota): lan = LAN vLLM gemma-4-26b, uit = UIT Gemma
(both free); gemma = lan, falling back to uit; sol = cx/gpt-6.1-sol via 9router /v1/responses (paid, last resort).
CLI: python3 batch/ask_model.py <sol|gemma> "<prompt>|@prompt.md" [image ...] [--effort low|medium|high]
Python: from ask_model import ask; obj, usage = ask(prompt, [paths], model="sol", want_json=True)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA, REPO

import base64
import io
import json
import re
import ssl
import time
import urllib.request

from PIL import Image


ENV = {}
for line in (REPO / ".env").read_text().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1)
        ENV[k.strip()] = v.strip().strip("\"'")


def _image_url(path, side=1400):
    im = Image.open(DATA / path).convert("RGB")
    im.thumbnail((side, side))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


_CA = next(iter(sorted((REPO / ".venv/lib").glob("python3*/site-packages/certifi/cacert.pem"))), None)
SSL = ssl.create_default_context(cafile=str(_CA)) if _CA else None  # system CA store lacks the UIT issuer


def _post(url, body, key, timeout=600):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", "Authorization": "Bearer " + key,
                                                                  "User-Agent": "curl/8.5.0"})
    return json.load(urllib.request.urlopen(req, timeout=timeout, context=SSL if url.startswith("https") else None))


def _json(text):
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
    return json.loads(m.group(0)) if m else None


LANES = {"lan": ("EXTRACTOR_BASE_URL", "LLM_API_KEY", "EXTRACTOR_MODEL"), "uit": ("UIT_API_BASE_URL", "UIT_API_KEY", "UIT_API_MODEL")}


def ask(prompt, images=(), model="sol", effort="low", want_json=True, side=1400, retries=2):
    if model == "gemma":  # free lanes first: LAN, then UIT
        for lane in ("lan", "uit"):
            try:
                return ask(prompt, images, lane, effort, want_json, side, retries=0)
            except Exception:
                continue
        raise RuntimeError("both Gemma lanes failed")
    for attempt in range(retries + 1):
        try:
            t = time.time()
            if model == "sol":
                content = [{"type": "input_text", "text": prompt}] + [{"type": "input_image", "image_url": _image_url(p, side)} for p in images]
                d = _post(ENV["9ROUTER_API_URL"] + "/responses", {"model": "cx/gpt-6.1-sol", "reasoning": {"effort": effort},
                          "service_tier": "priority", "input": [{"role": "user", "content": content}]}, ENV["9ROUTER_API_KEY"])
                text = "".join(c.get("text", "") for o in d.get("output", []) for c in (o.get("content") or []) if isinstance(c, dict))
            else:
                base, key, name = (ENV[x] for x in LANES[model])
                content = [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": _image_url(p, side)}} for p in images]
                d = _post(base.rstrip("/") + "/chat/completions", {"model": name, "max_tokens": 4000, "temperature": 0.2,
                          "messages": [{"role": "user", "content": content}]}, key)
                text = d["choices"][0]["message"]["content"]
            usage = dict(d.get("usage") or {}, seconds=round(time.time() - t, 1), model=model)
            return (_json(text) if want_json else text), usage
        except Exception as e:  # network / router hiccup: retry, then raise
            if attempt == retries:
                raise
            time.sleep(5 * (attempt + 1))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    effort = args.pop(args.index("--effort") + 1) if "--effort" in args else "low"
    if "--effort" in args:
        args.remove("--effort")
    model, prompt, imgs = args[0], args[1], args[2:]
    if prompt.startswith("@"):
        prompt = (DATA / prompt[1:]).read_text()
    out, usage = ask(prompt, imgs, model=model, effort=effort, want_json=False)
    print(out)
    print(json.dumps(usage), file=sys.stderr)
