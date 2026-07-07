"""One-command laptop checkup: verify the environment, find a model server,
run the unit tests, run the eval harness, and write a paste-able report.

    cd coding_agent
    python3 checkup.py                         # local servers only
    python3 checkup.py --host <server-ip>      # also probe a LAN server
    python3 checkup.py --host <server-ip> --save-profile
                                               # ...and persist it as the
                                               # default profile (stored in
                                               # .anvil/config.json, which is
                                               # gitignored — IPs never reach git)
    python3 checkup.py --no-evals              # skip the (slower) eval run
    python3 checkup.py --model X               # override auto-picked model

Output: checkup-report.md next to this script (gitignored). Paste it back
into the chat.
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "checkup-report.md")

# (kind, port, api-base template, probe path)
PROBES = [
    ("ollama",  11434, "http://{h}:11434",     "/api/tags"),
    ("openai",   1234, "http://{h}:1234/v1",   "/models"),   # LM Studio
    ("openai",   8080, "http://{h}:8080/v1",   "/models"),   # llama.cpp
    ("openai",   8000, "http://{h}:8000/v1",   "/models"),   # vLLM / mlx
]


def _get(url, timeout=4):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def detect_servers(hosts):
    """-> list of (kind, host, base_url, [model names])"""
    found = []
    for h in hosts:
        for kind, _port, base_tpl, path in PROBES:
            base = base_tpl.format(h=h)
            data = _get(base + path)
            if data is None:
                continue
            if kind == "ollama":
                models = [m.get("name", "?") for m in data.get("models", [])]
            else:
                models = [m.get("id", "?") for m in data.get("data", [])]
            found.append((kind, h, base, models))
    return found


def pick_model(models, prefer=None):
    """Prefer an explicit hint, then coder models, then qwen, then instruct."""
    wants = ([prefer.lower()] if prefer else []) + \
        ["coder", "code", "devstral", "codestral", "qwen", "instruct"]
    for want in wants:
        for m in models:
            if want in m.lower():
                return m
    return models[0] if models else None


def save_profile(kind, base, model):
    """Persist the detected endpoint as the default profile. Lives in
    .anvil/config.json which is gitignored — endpoints/IPs never reach git."""
    path = os.path.join(HERE, ".anvil", "config.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cfg = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError):
            cfg = {}
    cfg.setdefault("profiles", {})["server"] = {
        "backend": kind,
        "model": model,
        "url": base if kind == "openai" else base.rsplit("/v1", 1)[0],
    }
    cfg["default_profile"] = "server"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    return path


def run(cmd, cwd=HERE, timeout=1800):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd,
                           capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out.strip(), time.time() - t0
    except subprocess.TimeoutExpired:
        return -1, f"timed out after {timeout}s", time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-evals", action="store_true")
    ap.add_argument("--model", default=None,
                    help="model name or substring to prefer")
    ap.add_argument("--backend", default=None, choices=["ollama", "openai"])
    ap.add_argument("--url", default=None)
    ap.add_argument("--host", default="localhost",
                    help="comma-separated hosts to probe (e.g. localhost,<server-ip>)")
    ap.add_argument("--save-profile", action="store_true",
                    help="persist the detected server as the default "
                         "profile in .anvil/config.json (gitignored)")
    args = ap.parse_args()
    hosts = [h.strip() for h in args.host.split(",") if h.strip()]
    if "localhost" not in hosts:
        hosts.append("localhost")

    lines = ["# Anvil laptop checkup", ""]
    say = lambda s="": (print(s), lines.append(s))

    # ---- 1. environment ----------------------------------------------------
    say("## Environment")
    say(f"- platform: {platform.platform()}")
    say(f"- python: {sys.version.split()[0]} ({sys.executable})")
    on_mac = sys.platform == "darwin"
    if on_mac:
        rc, out, _ = run(["sw_vers"])
        say("- macOS: " + " ".join(out.split()))
    for tool in ("git", "node", "rg", "mdfind", "brew"):
        say(f"- {tool}: {'✓ ' + (shutil.which(tool) or '') if shutil.which(tool) else '✗ not found'}")
    say()

    # ---- 2. model servers ---------------------------------------------------
    say("## Model servers")
    servers = detect_servers(hosts)
    if not servers:
        say(f"- none reachable on {', '.join(hosts)} "
            "(ports 11434/1234/8080/8000)")
        say("- if the server sleeps, wake it first (e.g. your `server-wake` "
            "alias), then re-run")
    for kind, h, base, models in servers:
        say(f"- **{kind}** on {h} ({base}) — {len(models)} model(s): "
            + (", ".join(models[:8]) or "(none)"))
    say()

    # ---- 3. unit tests --------------------------------------------------------
    say("## Unit tests")
    rc, out, secs = run([sys.executable, "-m", "unittest", "discover",
                         "-s", "tests"])
    tail = "\n".join(out.splitlines()[-3:])
    say(f"```\n{tail}\n```")
    say(f"- result: {'✅ PASS' if rc == 0 else '❌ FAIL'} ({secs:.1f}s)")
    say()

    # ---- 4. evals -------------------------------------------------------------
    say("## Evals")
    backend = args.backend
    url = args.url
    model = args.model
    if not backend and servers:
        # prefer a remote/LAN hit over localhost (bigger model likely)
        servers.sort(key=lambda s: s[1] in ("localhost", "127.0.0.1"))
        kind, h, base, models = servers[0]
        backend = kind
        url = base   # bare base for ollama, .../v1 for openai — both correct
        model = pick_model(models, prefer=args.model) or args.model
        if args.save_profile and model:
            p = save_profile(kind, base, model)
            say(f"- profile 'server' saved to {p} (gitignored); "
                f"use: `python3 -m anvil.cli --profile server`")
    if args.no_evals:
        say("- skipped (--no-evals)")
    elif not backend or not model:
        say("- skipped: no model server/model detected")
    else:
        say(f"- running against {backend}:{model}"
            + (f" ({url})" if url else "") + " — this can take several "
            "minutes on a 7B model...")
        cmd = [sys.executable, "-m", "evals.harness",
               "--backend", backend, "--model", model]
        if url:
            cmd += ["--url", url]
        rc, out, secs = run(cmd, timeout=3600)
        say(f"```\n{out[-2500:]}\n```")
        say(f"- eval run finished in {secs/60:.1f} min "
            f"(exit={'0 ✅' if rc == 0 else rc})")
    say()

    say("## Next")
    say("Paste this whole report back into the chat so the failures can be "
        "turned into fixes (and `anvil improve` lessons).")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nreport written to {REPORT}")


if __name__ == "__main__":
    main()
