# Container image for the stk CLI — used by the k3s splits-backfill CronJob
# (SB-184). Build context is stk/ (this project is self-contained).
FROM python:3.12-slim

WORKDIR /app
COPY . /app

# pip builds the wheel via the uv_build backend declared in pyproject.toml.
RUN pip install --no-cache-dir . && rm -rf /root/.cache

# Session lives at $HOME/.config/stk/session.json — the CronJob mounts a PVC
# there so the rotated refresh token survives across ticks.
ENV HOME=/root \
    STK_API_URL=https://api.myrunstreak.run

ENTRYPOINT ["stk"]
