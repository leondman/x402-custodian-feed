# x402-custodian-feed

A dependency-free Python HTTP server that serves a custodian token-onboarding
signal feed behind an x402 payment gate on Celo.

The feed: recently merged pull requests in custodian repositories (default
BitGo/BitGoJS) are scanned for token-onboarding patterns, and structured
leads (chain, token, PR, merge time, URL) are returned as JSON. A
token-onboarding PR is a research signal, not a buy recommendation.

The gate: `GET /signals/custodian` returns HTTP 402 with an x402 payment
requirement (exact scheme, USDC on Celo, eip3009). Verification and
settlement go through the Celo x402 facilitator
(`https://api.x402.celo.org`, Sepolia testnet for development).

Current state: local test build. `TEST_MODE = True` validates the X-PAYMENT
payload structure only; nothing settles. Live mode, hosting and any funding
are separate, explicit steps.

## Run

```sh
python3 server.py   # serves on 127.0.0.1:8402
curl localhost:8402/health
curl -i localhost:8402/signals/custodian   # 402 + payment requirements
```

## Endpoints

- `GET /health` - service status and mode
- `GET /signals/custodian?hours=40` - the feed (x402-gated, max 168h window)

## Licence

MIT
