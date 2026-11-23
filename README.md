# GoatCash

<p align="center">
  <img src="assets/goatcash-logo.png" alt="GoatCash logo" width="280" />
</p>

[Polska wersja: README.pl.md](README.pl.md)

An open crypto market intelligence platform: analytical agents, forecasts settled in a
Forecast Ledger, calibration and self-learning within hard limits, and, in later stages, a
trading bot with gradually increasing autonomy.

> **Status:** stage **E1** (repository, standards, CI, secrets). Features arrive according
> to the E0–E18 roadmap; every stage ends with a quality gate that is checked automatically.

## Layout

```
apps/web/              Next.js (frontend)
services/platform/     Python package `goatcash` (api, worker, ingest, scheduler)
services/executor/     trading bot executor (separate image, separate secrets)
packages/contracts/    OpenAPI, event JSON Schemas, TS client (from E2)
ml/                    training and notebooks (no data)
prompts/               versioned LLM prompts
infra/terraform/       Oracle, Cloudflare (from E3)
infra/ansible/         server configuration (from E3)
infra/compose/         Docker Compose for dev, staging, prod (from E3)
infra/secrets/         *.enc.yaml files encrypted with SOPS + age
docs/adr/              architecture decision records
docs/gates/            quality gate reports
tests/e2e/             Playwright (from E12)
.github/workflows/     CI/CD
```

## Getting started (macOS)

`make doctor` checks the required tools (gate G0). Then:

```bash
make install     # uv sync + pnpm install + pre-commit hooks
make lint        # ruff + Biome
make typecheck   # pyright (strict) + tsc
make imports     # module boundaries (import-linter)
make test        # pytest with coverage + vitest
make gate G=1    # automated checks of gate G1, report in reports/gates/
```

## Security

The repository only contains what could be printed on the front page of a newspaper.
Secrets are either encrypted with SOPS or kept outside the repo; `SECURITY.md` describes
the five layers of protection and how to report a vulnerability privately.

## License

[GNU AGPL-3.0](LICENSE): anyone who offers a modified version as a network service must
publish its source code.

Project documentation (roadmap, decisions, quality gates) is written in Polish.
