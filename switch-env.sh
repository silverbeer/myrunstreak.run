#!/bin/bash
# Environment switcher for MyRunStreak local dev.
#
# Selects which env files are active by symlinking:
#   .env           -> .env.<env>            (backend; uvicorn runs from repo root)
#   frontend/.env  -> frontend/.env.<env>   (if present)
# The backend (pydantic, env_file=".env" resolved from the root CWD) and the
# frontend (vite) read the fixed .env, so switching is just repointing the
# symlink. State is in .mrs-config.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/.mrs-config"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

config_get() {
    local key="$1" default="$2"
    [ -f "$CONFIG_FILE" ] && grep "^${key}=" "$CONFIG_FILE" 2>/dev/null | head -1 | cut -d'=' -f2- | grep . && return
    echo "$default"
}
config_set() {
    local key="$1" value="$2"
    if [ -f "$CONFIG_FILE" ]; then
        grep -v "^${key}=" "$CONFIG_FILE" > "$CONFIG_FILE.tmp"; mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
    else
        echo "# MyRunStreak local env config" > "$CONFIG_FILE"
    fi
    echo "${key}=${value}" >> "$CONFIG_FILE"
}

current_env() { config_get env local; }

link_env() {
    local dir="$1" env="$2"
    local target="$dir/.env.$env"
    if [ -f "$target" ]; then
        ln -sf ".env.$env" "$dir/.env"
        echo -e "  ${GREEN}$dir/.env${NC} -> .env.$env"
    else
        echo -e "  ${YELLOW}$dir/.env.$env missing${NC} — skipped (copy from $dir/.env.example)"
    fi
}

switch() {
    local env="$1"
    if [ "$env" != "local" ] && [ "$env" != "prod" ]; then
        echo -e "${RED}Invalid env: $env${NC} (use local|prod)"; exit 1
    fi
    if [ ! -f "$SCRIPT_DIR/.env.$env" ]; then
        echo -e "${RED}.env.$env not found${NC} — create it from .env.example"
        exit 1
    fi
    echo -e "${BLUE}=== Switching to $env ===${NC}"
    link_env "$SCRIPT_DIR" "$env"
    link_env "$SCRIPT_DIR/frontend" "$env"
    config_set env "$env"
    echo -e "${GREEN}Active env: $env${NC}"
    if [ "$env" = "prod" ]; then
        echo -e "${YELLOW}Production — talking to the live DB. Be careful.${NC}"
    fi
    echo -e "${BLUE}Tip:${NC} ./myrunstreak.sh restart   # pick up the new env"
}

status() {
    local env; env="$(current_env)"
    echo -e "${BLUE}=== Env status ===${NC}"
    echo -e "  Active: ${GREEN}$env${NC}"
    echo ""
    echo "  Available env files:"
    for e in local prod; do
        if [ -f "$SCRIPT_DIR/.env.$e" ]; then
            [ "$e" = "$env" ] && echo -e "    ${GREEN}$e (ACTIVE)${NC}" || echo "    $e"
        else
            echo -e "    ${RED}$e (missing .env.$e)${NC}"
        fi
    done
    echo ""
    if [ "$env" = "local" ]; then
        if curl -s http://127.0.0.1:54321/rest/v1/ > /dev/null 2>&1; then
            echo -e "  ${GREEN}Local Supabase up${NC} (http://127.0.0.1:54321)"
        else
            echo -e "  ${YELLOW}Local Supabase down${NC} — ./myrunstreak.sh db up"
        fi
    fi
}

usage() {
    echo "MyRunStreak env switcher"
    echo ""
    echo "Usage: $0 {local|prod|status}"
    echo "  local    Use local Supabase (http://127.0.0.1:54321)"
    echo "  prod     Use cloud Supabase (api.myrunstreak.run)"
    echo "  status   Show active env + whether local Supabase is up"
}

case "${1:-status}" in
    local|prod) switch "$1" ;;
    status)     status ;;
    help|-h|--help) usage ;;
    *) echo -e "${RED}Unknown: $1${NC}"; echo ""; usage; exit 1 ;;
esac
