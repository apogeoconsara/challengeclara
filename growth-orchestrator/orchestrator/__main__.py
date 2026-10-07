"""Command line.

  python -m orchestrator demo [--flow D1] [--live]   run the demo flows through the engine and print each step
  python -m orchestrator stream                      replay the 561-delivery sample stream and summarise
  python -m orchestrator eval --recorded             validators vs 220 recorded model outputs (no model call)
  python -m orchestrator eval --live                 the 18 core cases against the real model (needs ANTHROPIC_API_KEY)
  python -m orchestrator serve [--port 8080]         local webhook receiver (POST /webhook), mock systems only
  python -m orchestrator export-web                  regenerate the data and prompts used by the Netlify page
  python -m orchestrator export-overview             summarise all 50k accounts for the page (needs data/generated)
  python -m orchestrator compare-scoring [V1 V2]      what changing the scoring does, measured by the real engine on the 50k world

Nothing here can send a real email: outreach goes to the mock ledger only.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import db, evals, scenario
from .ai.fixture import FixtureLLM
from .ai.llm import AnthropicLLM, LLMUnavailable
from .engine import Orchestrator
from .policy import SEED_DIR
from .timeutil import parse


def _live_llm():
    try:
        return AnthropicLLM()
    except LLMUnavailable as e:
        sys.exit(f"--live needs a model: {e}. Set ANTHROPIC_API_KEY in your shell (never in a file).")


def _print_result(e, r):
    print(f"  [{e.get('type')}] delivery={e.get('delivery_id')}  handling={r.handling}")
    if r.action:
        line = f"    decision: {r.action} {r.reason_codes}"
        if r.final_action and (r.final_action, r.final_reason_codes) != (r.action, r.reason_codes):
            line += f"  ->  after execution: {r.final_action} {r.final_reason_codes}"
        print(line)
    if r.ai:
        print(f"    ai: {json.dumps({k: v for k, v in r.ai.items() if v not in (None, [], '')})}")
    if r.route_to_ae_id:
        print(f"    route: {r.route_to_ae_id} ({r.route_reason})")
    if r.email:
        print(f"    email ({r.email['mode']}, {r.email.get('status')}, send_after={r.send_after}): {r.email['subject']}")
    for fx in r.effects:
        print(f"    effect: {fx}")


def cmd_demo(args):
    flows = json.loads((SEED_DIR / "demo_flows.json").read_text(encoding="utf-8"))["flows"]
    golden = {g["id"]: g for g in scenario.load_golden()}
    for f in flows:
        if args.flow and f["id"] != args.flow:
            continue
        print(f"\n=== {f['id']}: {f['title']} ===")
        for gid in f["golden"]:
            g = golden[gid]
            llm = _live_llm() if args.live else None
            print(f"\n-- {gid}: {g['title']}  (model: {'live ' + llm.model if llm else 'offline fixture'})")
            orch, results = scenario.run(g, llm=llm)
            for e, r in zip(g["events"], results):
                _print_result(e, r)
            led = orch.mocks.ledger
            print(f"  mock ledgers: emails={len(led['send'])} crm_writes={len(led['crm'])} meetings={len(led['calendar'])}"
                  f"  review_queue={orch.conn.execute('SELECT COUNT(*) FROM review_queue').fetchone()[0]}")


def cmd_stream(args):
    from collections import Counter
    conn = db.connect()
    db.load_world_dir(conn, SEED_DIR / "sample")
    events = [json.loads(l) for l in (SEED_DIR / "sample" / "events.jsonl").read_text(encoding="utf-8").splitlines() if l]
    orch = Orchestrator(conn, llm=_live_llm() if args.live else FixtureLLM(), as_of=parse("2026-10-01T16:00:00Z"))
    res = [orch.process(e) for e in events]
    print("handling:", dict(Counter(r.handling for r in res)))
    print("actions: ", dict(Counter(r.action for r in res)))
    print("mock emails:", len(orch.mocks.ledger["send"]), " review queue:",
          conn.execute("SELECT COUNT(*) FROM review_queue").fetchone()[0],
          " dead letters:", conn.execute("SELECT COUNT(*) FROM dead_letters").fetchone()[0])


def cmd_eval(args):
    if args.live:
        result = evals.run_live(_live_llm())
    else:
        result = evals.run_recorded()
    p = evals.save(result)
    print(json.dumps(result["summary"], indent=2))
    print(f"saved: {p.relative_to(evals.ROOT)}")


def cmd_serve(args):
    conn = db.connect(args.db)
    if not conn.execute("SELECT 1 FROM accounts LIMIT 1").fetchone():
        db.load_world_dir(conn, SEED_DIR / "sample")
    llm = _live_llm() if args.live else FixtureLLM()
    orch = Orchestrator(conn, llm=llm)
    secret = os.environ.get("ORCH_WEBHOOK_SECRET", "").encode()

    class H(BaseHTTPRequestHandler):
        def _send(self, code, body):
            data = json.dumps(body, default=str).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path != "/webhook":
                return self._send(404, {"error": "not_found"})
            n = int(self.headers.get("content-length", 0))
            if n > 64_000:
                return self._send(413, {"error": "too_large"})
            raw = self.rfile.read(n)
            if secret:                                  # HMAC-signed webhooks when a secret is configured
                sig = hmac.new(secret, raw, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(self.headers.get("x-signature", ""), "sha256=" + sig):
                    return self._send(401, {"error": "bad_signature"})
            try:
                env = json.loads(raw)
            except ValueError:
                env = {"_unparseable": raw[:2000].decode(errors="replace")}
            self._send(200, orch.process(env).to_dict())

        def do_GET(self):
            parts = self.path.strip("/").split("/")
            if len(parts) == 2 and parts[0] == "accounts":
                return self._send(200, {"account": db.one(conn, "SELECT * FROM accounts WHERE account_id=?", (parts[1],)),
                                        "decisions": db.rows(conn, "SELECT * FROM decisions WHERE account_id=?", (parts[1],)),
                                        "audit": orch.audit.trail(parts[1])})
            self._send(404, {"error": "not_found"})

    print(f"listening on http://127.0.0.1:{args.port}/webhook  (mock systems only; model: {getattr(llm, 'mode', '?')})")
    ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()


def cmd_export_web(args):
    from . import webexport
    for p in webexport.export_all():
        print("wrote", p)


def cmd_export_overview(args):
    from . import webexport
    for p in webexport.export_overview():
        print("wrote", p)


def cmd_compare_scoring(args):
    from . import showcase
    world = Path(args.world) if args.world else showcase.GENERATED
    p = showcase.scoring_compare_payload(world, [args.a, args.b] if args.a and args.b else None)
    print(showcase.scoring_compare_markdown(p))
    if args.write_web:
        from . import webexport
        out = webexport.WEB / "scoring_compare.json"
        out.write_text(json.dumps(p, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print("wrote", out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m orchestrator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo"); d.add_argument("--flow"); d.add_argument("--live", action="store_true")
    s = sub.add_parser("stream"); s.add_argument("--live", action="store_true")
    e = sub.add_parser("eval"); g = e.add_mutually_exclusive_group(required=True)
    g.add_argument("--live", action="store_true"); g.add_argument("--recorded", action="store_true")
    v = sub.add_parser("serve"); v.add_argument("--port", type=int, default=8080); v.add_argument("--db", default=":memory:")
    v.add_argument("--live", action="store_true")
    sub.add_parser("export-web")
    sub.add_parser("export-overview")
    c = sub.add_parser("compare-scoring"); c.add_argument("a", nargs="?"); c.add_argument("b", nargs="?"); c.add_argument("--world"); c.add_argument("--write-web", action="store_true")
    a = ap.parse_args(argv)
    {"demo": cmd_demo, "stream": cmd_stream, "eval": cmd_eval, "serve": cmd_serve, "export-web": cmd_export_web,
     "export-overview": cmd_export_overview, "compare-scoring": cmd_compare_scoring}[a.cmd](a)


if __name__ == "__main__":
    main()
