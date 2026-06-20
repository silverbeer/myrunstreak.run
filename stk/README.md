# stk — myrunstreak.run terminal client

A thin, terminal-native client for [myrunstreak.run](https://myrunstreak.run).
Talks to `api.myrunstreak.run` over HTTPS — no database or shared-code
dependency, so it installs and runs standalone.

## Install

```bash
uv tool install ./stk          # from a checkout
# or, without installing:
uvx --from ./stk stk --version
```

## Use

```bash
stk auth login                 # Supabase email/password
stk                            # current streak
stk plan show                  # today's adaptive plan
stk splits <run>               # per-mile splits
stk workout show <id>          # an athlete workout card
```

## Develop

```bash
uv sync --project stk --all-extras
uv run --project stk ruff check stk/
```

Packaging note (SB-169): the installable package is `cli` (matching
`from cli import ...`); `[tool.uv.build-backend] module-name = "cli"` points the
build backend at `stk/src/cli`. The root project stays `package = false` so
`uv run pytest` keeps working.
