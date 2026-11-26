#!/usr/bin/env python3
"""x402 paid data feed - CELO PORT, LOCAL TEST BUILD (no settlement, no hosting).

Serves the custodian-watch signal feed behind an x402 payment gate.
Test mode validates the X-PAYMENT payload structure only; nothing settles.
Real mode calls the Celo facilitator /verify then /settle (API key from a
one-time wallet signature, no gas). Settlement gas is sponsored but metered:
gas at cost + 0.3% of payment value, debited from a prepaid facilitator
balance (free starting credits cover one settlement each). Topping up that
balance or any burner funding needs Leon's typed Approve with amount + quote.
"""
import json, base64, datetime, urllib.request, re
from http.server import BaseHTTPRequestHandler, HTTPServer

PAY_TO = "0x5e0Fca933f0bFB1ae507F37C6122a4fDDb2cbcDD"  # Leon's burner, receive-only
PRICE_USDC = "1000"        # $0.001 per call (USDC 6dp) - test price
# Celo port: facilitator api.x402.celo.org (mainnet eip155:42220) /
# api.x402.sepolia.celo.org (testnet eip155:11142220). Asset table per
# https://x402.celo.org/skill.md fetched 26 Nov 2026 08:24 UK.
# Develop on Sepolia (USDC is the only testnet asset); flip to mainnet at hosting.
NETWORK = "eip155:11142220"  # Celo Sepolia for dev; mainnet = eip155:42220
USDC = {
    "eip155:11142220": "0x01C5C0122039549AD1493B8220cABEdD739BC44E",  # Sepolia USDC
    "eip155:42220":    "0xcebA9300f2b948710d2653dD7B07f33A8B32118C",  # mainnet USDC (eip3009)
}
FACILITATOR = {
    "eip155:11142220": "https://api.x402.sepolia.celo.org",
    "eip155:42220":    "https://api.x402.celo.org",
}
USDC_BASE = USDC[NETWORK]
TEST_MODE = True           # False only after facilitator approval + hosting

REPOS = ["BitGo/BitGoJS"]
PATTERN = re.compile(r"(add(ing)?\s(support\sfor\s)?[a-z0-9:_-]{2,}|client[- ]requested|new coin|ofc token|token config)", re.I)
TOKENISH = re.compile(r"\b(hoodeth|arb|sol|eth|base|poly|trx|xrp|sui|apt|near|doge|avax|ton|bsc)[:.-]([a-z0-9_-]{2,})\b", re.I)

def gh(path):
    req = urllib.request.Request("https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "x402-feed/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def custodian_signals(hours=40):
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).isoformat()
    leads = []
    for repo in REPOS:
        for pr in gh(f"/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=50"):
            merged = pr.get("merged_at")
            if not merged or merged < since:
                continue
            text = f"{pr.get('title','')} {pr.get('body') or ''}"
            tokens = TOKENISH.findall(text)
            if not PATTERN.search(text) or (not tokens and "add" not in pr["title"].lower()):
                continue
            leads.append({"repo": repo, "pr": pr["number"], "merged_at": merged,
                          "title": pr["title"], "url": pr["html_url"],
                          "token_refs": [f"{c}:{t}" for c, t in tokens][:5]})
    return {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "window_hours": hours, "leads": leads,
            "disclaimer": "Public PR data only. A research signal, not financial advice."}

def payment_requirements(resource):
    return {"x402Version": 1,
            "accepts": [{"scheme": "exact", "network": NETWORK,
                         "maxAmountRequired": PRICE_USDC, "asset": USDC_BASE,
                         "payTo": PAY_TO, "resource": resource,
                         "description": "Custodian token-onboarding signal feed",
                         "mimeType": "application/json", "maxTimeoutSeconds": 60,
                         "extra": {"name": "USDC", "version": "2",
                                   "assetTransferMethod": "eip3009"}}],
            "error": "X-PAYMENT header required"}

def check_payment(header):
    """TEST MODE: structure check only. Real mode posts to facilitator /verify."""
    try:
        payload = json.loads(base64.b64decode(header))
    except Exception:
        return False, "undecodable X-PAYMENT"
    ok = (payload.get("x402Version") == 1 and payload.get("scheme") == "exact"
          and payload.get("network") == NETWORK
          and isinstance(payload.get("payload"), dict))
    return ok, ("structure ok (TEST MODE, no settlement)" if ok else "payload shape invalid")

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, code, obj, extra=None):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == "/health":
            return self._json(200, {"ok": True, "mode": "TEST" if TEST_MODE else "LIVE"})
        if self.path.startswith("/signals/custodian"):
            pay = self.headers.get("X-PAYMENT")
            if not pay:
                return self._json(402, payment_requirements(self.path))
            ok, why = check_payment(pay)
            if not ok:
                return self._json(402, payment_requirements(self.path), {"X-PAYMENT-RESPONSE": why})
            hours = 40
            if "hours=" in self.path:
                try: hours = min(168, int(self.path.split("hours=")[1].split("&")[0]))
                except ValueError: pass
            return self._json(200, custodian_signals(hours),
                              {"X-PAYMENT-RESPONSE": base64.b64encode(
                                  json.dumps({"success": True, "note": why}).encode()).decode()})
        return self._json(404, {"error": "not found", "endpoints": ["/signals/custodian", "/health"]})

if __name__ == "__main__":
    print("x402 feed TEST build on http://127.0.0.1:8402 (no settlement)")
    HTTPServer(("127.0.0.1", 8402), H).serve_forever()
