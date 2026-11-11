#!/usr/bin/env bash
# tor-node-manager.sh
# Local Tor SOCKS5 exit-node manager for country-based outbounds.
# It does NOT touch x-ui / 3x-ui / Xray configs. It only creates local SOCKS5 ports.

set -Eeuo pipefail

APP_NAME="tor-node-manager"
BASE_DIR="/etc/tor-multi"
NODE_DIR="${BASE_DIR}/nodes"
TORRC_DIR="/etc/tor"
DATA_BASE="/var/lib/tor-multi"
LOG_BASE="/var/log/tor-multi"
DEFAULT_ATTEMPTS=8
DEFAULT_WAIT=70

# Countries shown in the menu: code|name|default_port
COUNTRIES=(
  "tr|Turkey|9053"
  "de|Germany|9054"
  "nl|Netherlands|9055"
  "fr|France|9056"
)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

msg()  { echo -e "${BLUE}==>${NC} $*"; }
ok()   { echo -e "${GREEN}OK:${NC} $*"; }
warn() { echo -e "${YELLOW}WARN:${NC} $*"; }
err()  { echo -e "${RED}ERROR:${NC} $*" >&2; }

# ====================== UI BANNER ==========================
show_banner() {
  clear
  echo -e "${CYAN}${BOLD}"
  cat << "EOF"
 ▄▄                              ▄▄▄   ▄▄▄        ▄▄▄▄▄▄▄
   ▄█▀▀█▄         █▄                █▀▀██ ██▀        █▀▀██▀▀▀▀                         █▄
   ██  ██         ██          ▄        ▀█▄█▀            ██         ▄    ▀▀    ▄▄      ▄██▄
   ██▀▀██   ██ ██ ████▄ ▄▀▀█▄ ████▄     ███             ██   ▄███▄ ████▄██ ▄████ ▄▀▀█▄ ██ ▄███▄
 ▄ ██  ██   ██▄██ ██ ██ ▄█▀██ ██ ██   ▄█▀██▄   ▀▀▀▀     ██   ██ ██ ██   ██ ██ ██ ▄█▀██ ██ ██ ██
 ▀██▀  ▀█▄█▄▄▀██▀▄██ ██▄▀█▄██▄██ ▀█ ▀██▀  ▀██▄          ▀██▄▄▀███▀▄█▀  ▄██▄▀████▄▀█▄██▄██▄▀███▀
              ██                                                              ██
            ▀▀▀                                                             ▀▀▀
EOF
  echo -e "${NC}"
  echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════╗"
  echo -e "${CYAN}║${YELLOW}     🌐 Tor Node Manager v2.0 – Multi‑Country SOCKS5 Proxy${CYAN}     ║"
  echo -e "${CYAN}║${GREEN}     🔒 Local • Lightweight • No x‑ui touch${CYAN}                  ║"
  echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
  echo ""
}

# ====================== UI HELPERS ==========================
print_header() {
  echo -e "\n${BLUE}${BOLD}═══ $* ${NC}"
}

print_box() {
  local title="$1"
  local len=$(( ${#title} + 4 ))
  printf "${CYAN}┌%${len}s┐${NC}\n" | tr ' ' '─'
  printf "${CYAN}│ ${YELLOW}%s${CYAN} │${NC}\n" "$title"
  printf "${CYAN}└%${len}s┘${NC}\n" | tr ' ' '─'
}

# ====================== CORE FUNCTIONS (unchanged) ==========================
need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    err "Run as root. Example: sudo bash $0"
    exit 1
  fi
}

usage() {
  cat <<USAGE
${APP_NAME}

Usage:
  $0 menu
  $0 install <country_code> [socks_port]
  $0 test <country_code>
  $0 delete <country_code>
  $0 restart <country_code>
  $0 list
  $0 json <country_code>
  $0 logs <country_code>

Examples:
  $0 install tr 9053
  $0 test tr
  $0 json tr

Notes:
  - Creates local SOCKS5 only: 127.0.0.1:<port>
  - Does not edit x-ui / 3x-ui / Xray.
  - Country codes are ISO-3166 alpha-2, lowercase or uppercase accepted, e.g. tr, de, nl, fr.
USAGE
}

normalize_cc() {
  local cc="${1:-}"
  cc="$(echo "$cc" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z')"
  if [[ ! "$cc" =~ ^[a-z]{2}$ ]]; then
    err "Invalid country code: ${1:-empty}. Use two letters, e.g. tr, de, nl, fr."
    exit 1
  fi
  echo "$cc"
}

upper_cc() {
  echo "$1" | tr '[:lower:]' '[:upper:]'
}

validate_port() {
  local port="${1:-}"
  if [[ ! "$port" =~ ^[0-9]+$ ]] || (( port < 1024 || port > 65535 )); then
    err "Invalid port: ${port}. Use 1024-65535."
    exit 1
  fi
  echo "$port"
}

service_name() {
  local cc
  cc="$(normalize_cc "$1")"
  echo "tor-exit-${cc}"
}

meta_file() {
  local cc
  cc="$(normalize_cc "$1")"
  echo "${NODE_DIR}/${cc}.env"
}

torrc_file() {
  local cc
  cc="$(normalize_cc "$1")"
  echo "${TORRC_DIR}/tor-exit-${cc}.torrc"
}

load_meta() {
  local cc mf
  cc="$(normalize_cc "$1")"
  mf="$(meta_file "$cc")"
  if [[ ! -f "$mf" ]]; then
    err "Node '${cc}' not found. Install it first."
    exit 1
  fi
  # shellcheck disable=SC1090
  source "$mf"
  : "${COUNTRY_CODE:?missing COUNTRY_CODE}"
  : "${SOCKS_PORT:?missing SOCKS_PORT}"
}

install_deps() {
  msg "Installing dependencies"
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y tor curl jq ca-certificates iproute2 netcat-openbsd
  else
    err "This script currently supports Debian/Ubuntu apt-based systems."
    exit 1
  fi
}

tor_user() {
  if id debian-tor >/dev/null 2>&1; then
    echo "debian-tor"
  elif id tor >/dev/null 2>&1; then
    echo "tor"
  else
    echo "root"
  fi
}

port_in_use_by_other() {
  local port="$1" service="$2"
  local pids cmd bad=0

  if ! ss -ltnp 2>/dev/null | awk -v p=":${port}" '$4 ~ p"$" {print}' | grep -q .; then
    return 1
  fi

  pids="$(ss -ltnp 2>/dev/null | awk -v p=":${port}" '$4 ~ p"$" {print $NF}' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi

  for pid in $pids; do
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    if [[ "$cmd" != *"$(torrc_file "${service#tor-exit-}")"* ]]; then
      bad=1
    fi
  done

  (( bad == 1 ))
}

prepare_dirs() {
  local user="$1"
  mkdir -p "$BASE_DIR" "$NODE_DIR" "$DATA_BASE" "$LOG_BASE"
  chown -R "$user":"$user" "$DATA_BASE" "$LOG_BASE" 2>/dev/null || true
  chmod 755 "$BASE_DIR" "$NODE_DIR"
}

write_node_files() {
  local cc="$1" port="$2"
  local svc torrc data_dir log_file user unit meta
  svc="$(service_name "$cc")"
  torrc="$(torrc_file "$cc")"
  data_dir="${DATA_BASE}/${svc}"
  log_file="${LOG_BASE}/${svc}.log"
  user="$(tor_user)"
  unit="/etc/systemd/system/${svc}.service"
  meta="$(meta_file "$cc")"

  prepare_dirs "$user"
  mkdir -p "$data_dir"
  touch "$log_file"
  chown -R "$user":"$user" "$data_dir" "$log_file" 2>/dev/null || true
  chmod 700 "$data_dir"

  cat > "$torrc" <<TORRC
# Managed by ${APP_NAME}. Do not edit manually unless you know what you are doing.
SocksPort 127.0.0.1:${port}
DataDirectory ${data_dir}
Log notice file ${log_file}

ClientOnly 1
ExitNodes {${cc}}
StrictNodes 1
AvoidDiskWrites 1
SafeSocks 1
TORRC

  cat > "$unit" <<UNIT
[Unit]
Description=Tor SOCKS5 exit ${cc} on 127.0.0.1:${port}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/tor -f ${torrc} --RunAsDaemon 0
Restart=always
RestartSec=5
User=${user}
Group=${user}
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
UNIT

  cat > "$meta" <<META
COUNTRY_CODE="${cc}"
COUNTRY_CODE_UPPER="$(upper_cc "$cc")"
SOCKS_PORT="${port}"
SERVICE_NAME="${svc}"
TORRC_FILE="${torrc}"
DATA_DIR="${data_dir}"
LOG_FILE="${log_file}"
CREATED_AT="$(date -Is)"
META
}

curl_socks() {
  local port="$1" url="$2" timeout="${3:-20}"
  curl --socks5-hostname "127.0.0.1:${port}" \
    --silent --show-error --location --max-time "$timeout" \
    --connect-timeout 10 \
    -A "${APP_NAME}/1.0" \
    "$url"
}

wait_for_socks() {
  local port="$1" max_wait="${2:-$DEFAULT_WAIT}" i
  for ((i=1; i<=max_wait; i++)); do
    if nc -z -w 1 127.0.0.1 "$port" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

get_tor_status() {
  local port="$1" json is_tor ip
  json="$(curl_socks "$port" "https://check.torproject.org/api/ip" 25 2>/dev/null || true)"
  is_tor="$(echo "$json" | jq -r '.IsTor // empty' 2>/dev/null || true)"
  ip="$(echo "$json" | jq -r '.IP // empty' 2>/dev/null || true)"
  echo "${is_tor}|${ip}"
}

get_geo_votes() {
  local port="$1" c1 c2 c3 c4
  c1="$(curl_socks "$port" "https://ipinfo.io/country" 15 2>/dev/null | tr -d '\r\n \"' | tr '[:lower:]' '[:upper:]' || true)"
  c2="$(curl_socks "$port" "https://ifconfig.co/country-iso" 15 2>/dev/null | tr -d '\r\n \"' | tr '[:lower:]' '[:upper:]' || true)"
  c3="$(curl_socks "$port" "https://ipapi.co/country/" 15 2>/dev/null | tr -d '\r\n \"' | tr '[:lower:]' '[:upper:]' || true)"
  c4="$(curl_socks "$port" "https://api.country.is/" 15 2>/dev/null | jq -r '.country // empty' 2>/dev/null | tr -d '\r\n \"' | tr '[:lower:]' '[:upper:]' || true)"
  echo "${c1}|${c2}|${c3}|${c4}"
}

print_check_result() {
  local expected="$1" port="$2" is_tor="$3" ip="$4" votes="$5"
  echo "Country expected: ${expected}"
  echo "SOCKS5: 127.0.0.1:${port}"
  echo "Tor check: ${is_tor:-unknown}"
  echo "Exit IP: ${ip:-unknown}"
  echo "Geo votes: ${votes}"
}

health_check() {
  local cc="$1" port="$2" attempts="${3:-$DEFAULT_ATTEMPTS}" wait_secs="${4:-$DEFAULT_WAIT}"
  local expected svc attempt status is_tor ip votes match_count vote
  expected="$(upper_cc "$cc")"
  svc="$(service_name "$cc")"

  for ((attempt=1; attempt<=attempts; attempt++)); do
    msg "Health check ${svc}, attempt ${attempt}/${attempts}"

    if ! systemctl is-active --quiet "$svc"; then
      systemctl restart "$svc" || true
    fi

    if ! wait_for_socks "$port" "$wait_secs"; then
      warn "SOCKS port 127.0.0.1:${port} did not become ready. Restarting..."
      systemctl restart "$svc" || true
      sleep 5
      continue
    fi

    status="$(get_tor_status "$port")"
    is_tor="${status%%|*}"
    ip="${status#*|}"
    votes="$(get_geo_votes "$port")"

    match_count=0
    IFS='|' read -r -a arr <<< "$votes"
    for vote in "${arr[@]}"; do
      if [[ "$vote" == "$expected" ]]; then
        ((match_count++)) || true
      fi
    done

    print_check_result "$expected" "$port" "$is_tor" "$ip" "$votes"

    if [[ "$is_tor" == "true" && "$match_count" -ge 1 ]]; then
      ok "Node is healthy. Confirmed Tor exit country: ${expected}"
      return 0
    fi

    warn "Not confirmed yet. Restarting Tor instance to try another circuit/exit."
    systemctl restart "$svc" || true
    sleep 8
  done

  err "Node could not be confirmed as ${expected} after ${attempts} attempts."
  return 1
}

install_node() {
  local cc port svc
  cc="$(normalize_cc "$1")"
  port="$(validate_port "${2:-$(default_port_for "$cc")}")"
  svc="$(service_name "$cc")"

  install_deps

  msg "Installing node: country=${cc}, socks_port=${port}"
  systemctl stop "$svc" 2>/dev/null || true

  if port_in_use_by_other "$port" "$svc"; then
    err "Port ${port} is already in use by another process. Choose another port."
    ss -ltnp | grep -E ":${port}\b" || true
    exit 1
  fi

  write_node_files "$cc" "$port"

  systemctl daemon-reload
  systemctl enable "$svc"
  systemctl restart "$svc"

  sleep 5
  systemctl status "$svc" --no-pager -l || true

  if health_check "$cc" "$port" "$DEFAULT_ATTEMPTS" "$DEFAULT_WAIT"; then
    echo
    print_outbound_json "$cc"
  else
    warn "Service was created but health check failed. Use '$0 logs ${cc}' and '$0 test ${cc}'."
    exit 2
  fi
}

default_port_for() {
  local cc="$1" row rcc name port
  for row in "${COUNTRIES[@]}"; do
    IFS='|' read -r rcc name port <<< "$row"
    if [[ "$rcc" == "$cc" ]]; then
      echo "$port"
      return 0
    fi
  done
  echo "9059"
}

test_node() {
  local cc port
  cc="$(normalize_cc "$1")"
  load_meta "$cc"
  port="$SOCKS_PORT"
  health_check "$cc" "$port" "$DEFAULT_ATTEMPTS" "$DEFAULT_WAIT"
}

restart_node() {
  local cc svc
  cc="$(normalize_cc "$1")"
  load_meta "$cc"
  svc="$SERVICE_NAME"
  systemctl restart "$svc"
  sleep 5
  test_node "$cc"
}

delete_node() {
  local cc svc torrc mf data log unit
  cc="$(normalize_cc "$1")"
  mf="$(meta_file "$cc")"

  if [[ -f "$mf" ]]; then
    # shellcheck disable=SC1090
    source "$mf"
    svc="${SERVICE_NAME:-$(service_name "$cc")}" 
    torrc="${TORRC_FILE:-$(torrc_file "$cc")}" 
    data="${DATA_DIR:-${DATA_BASE}/$(service_name "$cc")}" 
    log="${LOG_FILE:-${LOG_BASE}/$(service_name "$cc").log}" 
  else
    svc="$(service_name "$cc")"
    torrc="$(torrc_file "$cc")"
    data="${DATA_BASE}/${svc}"
    log="${LOG_BASE}/${svc}.log"
  fi

  unit="/etc/systemd/system/${svc}.service"

  msg "Deleting node ${cc}"
  systemctl stop "$svc" 2>/dev/null || true
  systemctl disable "$svc" 2>/dev/null || true
  rm -f "$unit" "$torrc" "$mf"
  rm -rf "$data"
  rm -f "$log"
  systemctl daemon-reload
  systemctl reset-failed
  ok "Deleted ${cc}"
}

list_nodes() {
  mkdir -p "$NODE_DIR"
  if ! compgen -G "${NODE_DIR}/*.env" >/dev/null; then
    warn "No nodes installed."
    return 0
  fi

  printf "${CYAN}%-8s %-8s %-28s %-10s %-18s${NC}\n" "COUNTRY" "PORT" "SERVICE" "ACTIVE" "SOCKS"
  for mf in "${NODE_DIR}"/*.env; do
    # shellcheck disable=SC1090
    source "$mf"
    local active="inactive"
    if systemctl is-active --quiet "$SERVICE_NAME"; then active="active"; fi
    if [[ "$active" == "active" ]]; then
      printf "${GREEN}%-8s %-8s %-28s %-10s %-18s${NC}\n" "${COUNTRY_CODE_UPPER}" "${SOCKS_PORT}" "${SERVICE_NAME}" "${active}" "127.0.0.1:${SOCKS_PORT}"
    else
      printf "${RED}%-8s %-8s %-28s %-10s %-18s${NC}\n" "${COUNTRY_CODE_UPPER}" "${SOCKS_PORT}" "${SERVICE_NAME}" "${active}" "127.0.0.1:${SOCKS_PORT}"
    fi
  done
}

print_outbound_json() {
  local cc port tag
  cc="$(normalize_cc "$1")"
  load_meta "$cc"
  port="$SOCKS_PORT"
  tag="tor-${cc}"
  cat <<JSON

SOCKS5 local:
127.0.0.1:${port}

Xray outbound sample:
{
  "tag": "${tag}",
  "protocol": "socks",
  "settings": {
    "servers": [
      {
        "address": "127.0.0.1",
        "port": ${port}
      }
    ]
  },
  "targetStrategy": "AsIs"
}
JSON
}

show_logs() {
  local cc svc log
  cc="$(normalize_cc "$1")"
  load_meta "$cc"
  svc="$SERVICE_NAME"
  log="$LOG_FILE"
  echo "===== systemd logs: ${svc} ====="
  journalctl -u "$svc" --no-pager -n 120 || true
  echo
  echo "===== tor log file: ${log} ====="
  tail -n 120 "$log" 2>/dev/null || true
}

# ====================== UI MENU FUNCTIONS ==========================
select_country_menu() {
  local row i choice cc name port custom_cc custom_port
  echo -e "\n${CYAN}${BOLD}Select country:${NC}"
  i=1
  for row in "${COUNTRIES[@]}"; do
    IFS='|' read -r cc name port <<< "$row"
    echo -e "  ${GREEN}${i})${NC} ${name} (${cc^^}) ${BLUE}default port ${port}${NC}"
    ((i++))
  done
  echo -e "  ${GREEN}${i})${NC} ${YELLOW}Custom country code${NC}"
  read -r -p "$(echo -e "${GREEN}[?] Choice: ${NC}")" choice

  if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice < i )); then
    row="${COUNTRIES[$((choice-1))]}"
    IFS='|' read -r cc name port <<< "$row"
    read -r -p "$(echo -e "${GREEN}[?] SOCKS port [${port}]: ${NC}")" custom_port
    custom_port="${custom_port:-$port}"
    install_node "$cc" "$custom_port"
  elif [[ "$choice" == "$i" ]]; then
    read -r -p "$(echo -e "${GREEN}[?] Country code, e.g. es: ${NC}")" custom_cc
    custom_cc="$(normalize_cc "$custom_cc")"
    read -r -p "$(echo -e "${GREEN}[?] SOCKS port [9059]: ${NC}")" custom_port
    custom_port="${custom_port:-9059}"
    install_node "$custom_cc" "$custom_port"
  else
    err "Invalid choice"
    exit 1
  fi
}

show_status() {
  echo -e "\n${CYAN}${BOLD}═══ Current Node Status ═══${NC}"
  list_nodes
  echo ""
  local total active
  total="$(find "${NODE_DIR}" -name '*.env' 2>/dev/null | wc -l)"
  active=0
  for mf in "${NODE_DIR}"/*.env 2>/dev/null; do
    # shellcheck disable=SC1090
    source "$mf" 2>/dev/null || continue
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
      ((active++))
    fi
  done
  echo -e "${BLUE}Total nodes: ${total}  |  Active: ${GREEN}${active}${NC}  |  Inactive: ${RED}$((total - active))${NC}"
}

show_help() {
  usage
}

main_menu() {
  while true; do
    show_banner
    echo -e "${CYAN}${BOLD}┌─────────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}${BOLD}│ ${GREEN}1${CYAN}. Install new node                                          │${NC}"
    echo -e "${CYAN}${BOLD}│ ${GREEN}2${CYAN}. Test an existing node                                    │${NC}"
    echo -e "${CYAN}${BOLD}│ ${GREEN}3${CYAN}. Restart / change IP of a node                            │${NC}"
    echo -e "${CYAN}${BOLD}│ ${GREEN}4${CYAN}. Delete a node                                           │${NC}"
    echo -e "${CYAN}${BOLD}│ ${GREEN}5${CYAN}. List installed nodes                                    │${NC}"
    echo -e "${CYAN}${BOLD}│ ${GREEN}6${CYAN}. Show Xray outbound JSON for a node                      │${NC}"
    echo -e "${CYAN}${BOLD}│ ${GREEN}7${CYAN}. View logs of a node                                     │${NC}"
    echo -e "${CYAN}${BOLD}│ ${GREEN}8${CYAN}. Show overall status                                     │${NC}"
    echo -e "${CYAN}${BOLD}│ ${GREEN}0${CYAN}. Exit                                                    │${NC}"
    echo -e "${CYAN}${BOLD}└─────────────────────────────────────────────────────────────────────┘${NC}"
    read -r -p "$(echo -e "${GREEN}[?] Select option (0-8): ${NC}")" ans
    case "$ans" in
      1) select_country_menu ;;
      2) read -r -p "$(echo -e "${GREEN}[?] Country code: ${NC}")" cc; test_node "$cc" ;;
      3) read -r -p "$(echo -e "${GREEN}[?] Country code: ${NC}")" cc; restart_node "$cc" ;;
      4) read -r -p "$(echo -e "${GREEN}[?] Country code: ${NC}")" cc; delete_node "$cc" ;;
      5) list_nodes; read -r -p "$(echo -e "${YELLOW}[i] Press Enter to continue...${NC}")" ;;
      6) read -r -p "$(echo -e "${GREEN}[?] Country code: ${NC}")" cc; print_outbound_json "$cc"; read -r -p "$(echo -e "${YELLOW}[i] Press Enter to continue...${NC}")" ;;
      7) read -r -p "$(echo -e "${GREEN}[?] Country code: ${NC}")" cc; show_logs "$cc"; read -r -p "$(echo -e "${YELLOW}[i] Press Enter to continue...${NC}")" ;;
      8) show_status; read -r -p "$(echo -e "${YELLOW}[i] Press Enter to continue...${NC}")" ;;
      0) echo -e "${GREEN}Goodbye!${NC}"; exit 0 ;;
      *) warn "Invalid choice" ;;
    esac
  done
}

# ====================== MAIN ENTRY ==========================
main() {
  need_root
  local cmd="${1:-menu}"
  case "$cmd" in
    menu) main_menu ;;
    install) [[ $# -ge 2 ]] || { usage; exit 1; }; install_node "$2" "${3:-}" ;;
    test) [[ $# -eq 2 ]] || { usage; exit 1; }; test_node "$2" ;;
    delete|remove) [[ $# -eq 2 ]] || { usage; exit 1; }; delete_node "$2" ;;
    restart) [[ $# -eq 2 ]] || { usage; exit 1; }; restart_node "$2" ;;
    list) list_nodes ;;
    json) [[ $# -eq 2 ]] || { usage; exit 1; }; print_outbound_json "$2" ;;
    logs) [[ $# -eq 2 ]] || { usage; exit 1; }; show_logs "$2" ;;
    help|-h|--help) usage ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
