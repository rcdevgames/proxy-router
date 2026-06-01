#!/bin/bash

# ============================================
# Service Setup Script untuk Proxy Router
# ============================================

set -e

APP_NAME="proxy-router"
APP_USER="$USER"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="python3"
MAIN_SCRIPT="main.py"

# Warna output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo -e "${YELLOW}Usage:${NC} $0 {install|uninstall|status|start|stop|restart}"
    echo ""
    echo "  install   - Install service ke systemd"
    echo "  uninstall - Hapus service dari systemd"
    echo "  status    - Cek status service"
    echo "  start     - Start service"
    echo "  stop      - Stop service"
    echo "  restart   - Restart service"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Error: Jalankan sebagai root (sudo)${NC}"
        exit 1
    fi
}

get_python_path() {
    $PYTHON_BIN -c "import sys; print(sys.executable)" 2>/dev/null || echo "/usr/bin/python3"
}

create_service_file() {
    PYTHON_PATH=$(get_python_path)

    cat > /etc/systemd/system/${APP_NAME}.service << EOF
[Unit]
Description=Proxy Router Service
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${PYTHON_PATH} ${APP_DIR}/${MAIN_SCRIPT}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    echo -e "${GREEN}Service file created: /etc/systemd/system/${APP_NAME}.service${NC}"
}

install_service() {
    check_root

    if [ ! -f "${APP_DIR}/${MAIN_SCRIPT}" ]; then
        echo -e "${RED}Error: ${MAIN_SCRIPT} tidak ditemukan di ${APP_DIR}${NC}"
        exit 1
    fi

    create_service_file

    systemctl daemon-reload
    systemctl enable ${APP_NAME}.service

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Service berhasil diinstall!${NC}"
    echo -e "Nama service: ${APP_NAME}"
    echo -e "File: ${APP_DIR}/${MAIN_SCRIPT}"
    echo ""
    echo "Commands:"
    echo "  sudo systemctl start ${APP_NAME}   # Start service"
    echo "  sudo systemctl stop ${APP_NAME}    # Stop service"
    echo "  sudo systemctl status ${APP_NAME}  # Cek status"
    echo "  sudo journalctl -u ${APP_NAME}     # Lihat logs"
    echo -e "${GREEN}========================================${NC}"
}

uninstall_service() {
    check_root

    echo -e "${YELLOW}Menghapus service ${APP_NAME}...${NC}"

    systemctl stop ${APP_NAME} 2>/dev/null || true
    systemctl disable ${APP_NAME} 2>/dev/null || true

    if [ -f /etc/systemd/system/${APP_NAME}.service ]; then
        rm /etc/systemd/system/${APP_NAME}.service
        systemctl daemon-reload
        echo -e "${GREEN}Service file dihapus${NC}"
    else
        echo -e "${YELLOW}Service file tidak ditemukan${NC}"
    fi

    echo -e "${GREEN}Uninstall selesai!${NC}"
}

show_status() {
    systemctl status ${APP_NAME}.service --no-pager || true
}

start_service() {
    check_root
    systemctl start ${APP_NAME}.service
    echo -e "${GREEN}Service started${NC}"
}

stop_service() {
    check_root
    systemctl stop ${APP_NAME}.service
    echo -e "${GREEN}Service stopped${NC}"
}

restart_service() {
    check_root
    systemctl restart ${APP_NAME}.service
    echo -e "${GREEN}Service restarted${NC}"
}

# Main
case "${1:-}" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    status)
        show_status
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    *)
        usage
        exit 1
        ;;
esac