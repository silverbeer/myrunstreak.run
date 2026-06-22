#!/bin/bash
# MyRunStreak local service manager: backend (uvicorn), frontend (vite), and
# the local Supabase stack. Mirrors missing-table.sh, trimmed to this stack
# (no k3s redis — local dev runs with CACHE_ENABLED=false).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

BACKEND_PORT=8000
FRONTEND_PORT=5174
SUPABASE_API=http://127.0.0.1:54321

LOG_DIR="$SCRIPT_DIR/.run-logs"
mkdir -p "$LOG_DIR"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

current_env() {
    [ -f "$SCRIPT_DIR/.mrs-config" ] && grep "^env=" "$SCRIPT_DIR/.mrs-config" | head -1 | cut -d= -f2- | grep . && return
    echo "local"
}
port_up() { lsof -i :"$1" > /dev/null 2>&1; }
pid_on_port() { lsof -ti :"$1" 2>/dev/null; }

kill_port() {
    local port="$1" name="$2"
    local pid; pid="$(pid_on_port "$port")"
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}Stopping $name (:$port, PID $pid)…${NC}"
        kill $pid 2>/dev/null
        local n=0; while port_up "$port" && [ $n -lt 8 ]; do sleep 1; n=$((n+1)); done
        port_up "$port" && { echo -e "${RED}Force killing $name${NC}"; kill -9 $pid 2>/dev/null; }
    fi
}

supabase_up() { curl -s "$SUPABASE_API/rest/v1/" > /dev/null 2>&1; }
docker_up()   { docker info > /dev/null 2>&1; }

require_docker() {
    if ! docker_up; then
        echo -e "${RED}Docker isn't running.${NC} The local Supabase stack needs it."
        echo -e "${BLUE}Fix:${NC} start Docker Desktop, then retry."
        return 1
    fi
}

# ---- db ----
db() {
    case "${1:-status}" in
        up)     require_docker && supabase start ;;
        down)   supabase stop ;;
        reset)  require_docker && supabase db reset ;;
        status) supabase status ;;
        studio) supabase status 2>/dev/null | grep -i studio ;;
        *) echo "Usage: $0 db {up|down|reset|status|studio}"; exit 1 ;;
    esac
}

# ---- start ----
start_backend() {
    local watch="$1"
    if port_up "$BACKEND_PORT"; then
        echo -e "${YELLOW}Backend already on :$BACKEND_PORT${NC}"; return 0
    fi
    local reload=""; [ "$watch" = "true" ] && reload="--reload"
    echo -e "${YELLOW}Starting backend (uvicorn :$BACKEND_PORT${reload:+ --reload})…${NC}"
    nohup uv run uvicorn backend.app:app --host 0.0.0.0 --port "$BACKEND_PORT" $reload \
        > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
    local n=0; while [ $n -lt 12 ]; do port_up "$BACKEND_PORT" && { echo -e "${GREEN}Backend up${NC} → http://localhost:$BACKEND_PORT"; return 0; }; sleep 1; n=$((n+1)); done
    echo -e "${RED}Backend failed to start — see $LOG_DIR/backend.log${NC}"; return 1
}

start_frontend() {
    if port_up "$FRONTEND_PORT"; then
        echo -e "${YELLOW}Frontend already on :$FRONTEND_PORT${NC}"; return 0
    fi
    [ -d frontend/node_modules ] || { echo "Installing frontend deps…"; (cd frontend && npm install); }
    echo -e "${YELLOW}Starting frontend (vite :$FRONTEND_PORT)…${NC}"
    (cd frontend && nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 & echo $! > "$FRONTEND_PID_FILE")
    local n=0; while [ $n -lt 15 ]; do port_up "$FRONTEND_PORT" && { echo -e "${GREEN}Frontend up${NC} → http://localhost:$FRONTEND_PORT"; return 0; }; sleep 1; n=$((n+1)); done
    echo -e "${RED}Frontend failed to start — see $LOG_DIR/frontend.log${NC}"; return 1
}

start() {
    local watch="false"; [ "$1" = "--watch" ] && watch="true"
    local env; env="$(current_env)"
    echo -e "${GREEN}Starting MyRunStreak (env: $env${watch:+, watch})…${NC}\n"
    if [ "$env" = "local" ]; then
        require_docker || return 1
        if supabase_up; then echo -e "${GREEN}Local Supabase up${NC}"; else
            echo -e "${YELLOW}Local Supabase down — starting…${NC}"; supabase start || return 1
        fi
    fi
    start_backend "$watch" && start_frontend
    echo ""
    echo -e "Use '$0 status' / '$0 tail' / '$0 stop'"
}

stop() {
    echo -e "${YELLOW}Stopping MyRunStreak services…${NC}"
    kill_port "$BACKEND_PORT" backend
    kill_port "$FRONTEND_PORT" frontend
    rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
    echo -e "${GREEN}Stopped.${NC} (Supabase left running — '$0 db down' to stop it)"
}

status() {
    echo -e "${BLUE}=== MyRunStreak status ===${NC}"
    echo -e "  Env: ${GREEN}$(current_env)${NC}"
    port_up "$BACKEND_PORT"  && echo -e "  ${GREEN}● backend${NC}  :$BACKEND_PORT"  || echo -e "  ${RED}○ backend${NC}  :$BACKEND_PORT"
    port_up "$FRONTEND_PORT" && echo -e "  ${GREEN}● frontend${NC} :$FRONTEND_PORT" || echo -e "  ${RED}○ frontend${NC} :$FRONTEND_PORT"
    supabase_up              && echo -e "  ${GREEN}● supabase${NC} $SUPABASE_API"   || echo -e "  ${RED}○ supabase${NC} $SUPABASE_API"
}

logs()  { for f in backend frontend; do echo -e "${BLUE}── $f ──${NC}"; tail -n 20 "$LOG_DIR/$f.log" 2>/dev/null; done; }
tail_logs() { tail -f "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log"; }

usage() {
    echo -e "${BLUE}MyRunStreak Service Manager${NC}"
    echo ""
    echo "Usage: $0 {start|stop|restart|status|logs|tail|db}"
    echo "  start [--watch]   backend + frontend (+ local Supabase); --watch = uvicorn reload"
    echo "  stop              stop backend + frontend (Supabase stays up)"
    echo "  restart [--watch] stop then start"
    echo "  status            what's up (backend/frontend/supabase) + active env"
    echo "  logs              recent backend + frontend logs"
    echo "  tail              follow logs live"
    echo "  db {up|down|reset|status|studio}   wrap 'supabase start|stop|db reset|status'"
    echo ""
    echo "Env: switch with ./switch-env.sh {local|prod}"
}

case "${1:-status}" in
    start)   start "$2" ;;
    stop)    stop ;;
    restart) stop; echo ""; start "$2" ;;
    status)  status ;;
    logs)    logs ;;
    tail)    tail_logs ;;
    db)      shift; db "$@" ;;
    help|-h|--help) usage ;;
    *) echo -e "${RED}Unknown: $1${NC}"; echo ""; usage; exit 1 ;;
esac
