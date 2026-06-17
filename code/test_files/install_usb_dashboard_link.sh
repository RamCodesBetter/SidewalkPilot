#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  sudo ./install_usb_dashboard_link.sh rpi
  sudo ./install_usb_dashboard_link.sh z2w
  ./install_usb_dashboard_link.sh verify-rpi
  ./install_usb_dashboard_link.sh verify-z2w

Permanent USB dashboard link:
  rpi usb0  -> 192.168.10.1/24
  z2w usb0  -> 192.168.10.2/24
EOF
}

ROLE="${1:-}"
RPI_IP="192.168.10.1/24"
Z2W_IP="192.168.10.2/24"
RPI_PEER="192.168.10.1"
Z2W_PEER="192.168.10.2"

if [[ -z "$ROLE" ]]; then
  usage
  exit 1
fi

if [[ "$ROLE" == "rpi" || "$ROLE" == "z2w" ]] && [[ "${EUID}" -ne 0 ]]; then
  echo "Run install roles with sudo."
  usage
  exit 1
fi

run() {
  echo "+ $*"
  "$@"
}

find_boot_file() {
  local name="$1"
  if [[ -f "/boot/firmware/${name}" ]]; then
    printf "/boot/firmware/%s\n" "$name"
    return 0
  fi
  if [[ -f "/boot/${name}" ]]; then
    printf "/boot/%s\n" "$name"
    return 0
  fi
  return 1
}

configure_usb0_nmcli() {
  local role="$1"
  local address="$2"
  local connection_name="sidewalkpilot-usb0-${role}"

  if ! command -v nmcli >/dev/null 2>&1; then
    return 1
  fi

  run nmcli device set usb0 managed yes || true

  if nmcli -t -f NAME connection show | grep -Fxq "$connection_name"; then
    run nmcli connection modify "$connection_name" \
      connection.interface-name usb0 \
      connection.autoconnect yes \
      connection.autoconnect-priority 100 \
      ipv4.method manual \
      ipv4.addresses "$address" \
      ipv4.never-default yes \
      ipv6.method disabled
  else
    run nmcli connection add type ethernet ifname usb0 con-name "$connection_name" \
      connection.autoconnect yes \
      connection.autoconnect-priority 100 \
      ipv4.method manual \
      ipv4.addresses "$address" \
      ipv4.never-default yes \
      ipv6.method disabled
  fi

  run nmcli connection up "$connection_name" || true
}

configure_usb0_networkd() {
  local address="$1"

  cat >/etc/systemd/network/10-sidewalkpilot-usb0.network <<EOF
[Match]
Name=usb0

[Network]
Address=${address}
LinkLocalAddressing=no
IPv6AcceptRA=no
EOF

  run systemctl enable systemd-networkd
  run systemctl restart systemd-networkd || true
}

configure_usb0_static_ip() {
  local role="$1"
  local address="$2"

  if ! configure_usb0_nmcli "$role" "$address"; then
    configure_usb0_networkd "$address"
  fi

  run ip link set usb0 up || true
  run ip addr replace "$address" dev usb0 || true
}

configure_z2w_gadget() {
  local config_txt
  local cmdline_txt

  config_txt="$(find_boot_file config.txt)"
  cmdline_txt="$(find_boot_file cmdline.txt)"

  cp -n "$config_txt" "${config_txt}.sidewalkpilot.bak" || true
  cp -n "$cmdline_txt" "${cmdline_txt}.sidewalkpilot.bak" || true

  if grep -Eq '^[[:space:]]*dtoverlay=dwc2' "$config_txt"; then
    sed -i 's/^[[:space:]]*dtoverlay=dwc2.*/dtoverlay=dwc2,dr_mode=peripheral/' "$config_txt"
  else
    printf '\n# SidewalkPilot Zero 2 W USB Ethernet gadget\ndtoverlay=dwc2,dr_mode=peripheral\n' >>"$config_txt"
  fi

  python3 - "$cmdline_txt" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8").strip()
parts = text.split()
module_token = "modules-load=dwc2,g_ether"
updated = []
found = False

for part in parts:
    if part.startswith("modules-load="):
        found = True
        modules = [m for m in part.split("=", 1)[1].split(",") if m]
        for module in ("dwc2", "g_ether"):
            if module not in modules:
                modules.append(module)
        updated.append("modules-load=" + ",".join(modules))
    else:
        updated.append(part)

if not found:
    updated.append(module_token)

path.write_text(" ".join(updated) + "\n", encoding="utf-8")
PY

  cat >/etc/modprobe.d/sidewalkpilot-g_ether.conf <<'EOF'
# Stable MACs keep the Pi 5 and Zero 2 W from treating the USB link as a new
# network every boot.
options g_ether host_addr=02:5a:10:00:00:01 dev_addr=02:5a:10:00:00:02
EOF

  run modprobe dwc2 || true
  run modprobe g_ether || true
}

verify_link() {
  local expected="$1"
  local peer="$2"
  echo "usb0 address:"
  ip -br addr show usb0 || true
  echo
  echo "usb0 carrier:"
  cat /sys/class/net/usb0/carrier 2>/dev/null || true
  echo
  echo "route to peer:"
  ip route get "$peer" || true
  echo
  echo "ping peer:"
  ping -c 3 "$peer"
  echo
  echo "Expected local address: $expected"
}

case "$ROLE" in
  rpi)
    configure_usb0_static_ip rpi "$RPI_IP"
    echo "RPi side installed. Reboot recommended."
    ;;
  z2w)
    configure_z2w_gadget
    configure_usb0_static_ip z2w "$Z2W_IP"
    echo "Z2W side installed. Reboot required for gadget boot config."
    ;;
  verify-rpi)
    verify_link "$RPI_IP" "$Z2W_PEER"
    ;;
  verify-z2w)
    verify_link "$Z2W_IP" "$RPI_PEER"
    ;;
  *)
    usage
    exit 1
    ;;
esac
