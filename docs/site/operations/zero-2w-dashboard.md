# Zero 2 W Dashboard

The production dashboard link is USB Ethernet only:

| Device | Interface | Address |
|---|---|---|
| Raspberry Pi 5 | `usb0` | `192.168.10.1/24` |
| Raspberry Pi Zero 2 W | USB gadget `usb0` | `192.168.10.2/24` |

The Zero receives UDP telemetry on port `8765` and drives the 64×32 HUB75 panel. Wi-Fi can remain available for SSH, but the controller does not send dashboard packets to a Wi-Fi hostname.

## Install Permanent Recovery

Run the role matching each machine from `code/test_files`:

```bash
# Pi 5
sudo ./install_usb_dashboard_link.sh rpi
./install_usb_dashboard_link.sh verify-rpi
```

```bash
# Zero 2 W
sudo ./install_usb_dashboard_link.sh z2w
./install_usb_dashboard_link.sh verify-z2w
```

The installer creates static addressing and `sidewalkpilot-usb0-keeper.service`. The keeper restores addresses, flushes failed neighbor entries, cycles the interface after repeated failures, and reloads `dwc2/g_ether` on the Zero when its gadget interface disappears.

## Start and Verify

```bash
# Zero 2 W
sudo systemctl restart sidewalkpilot-z2w-dashboard.service
sudo systemctl status sidewalkpilot-z2w-dashboard.service -l --no-pager
ss -lunp | grep 8765
```

```bash
# Pi 5
ping -c 3 192.168.10.2
sudo systemctl restart sidewalkpilot-rpi-car.service
journalctl -u sidewalkpilot-rpi-car.service -n 80 -l --no-pager
```

Pass criteria are carrier on both `usb0` interfaces, successful peer ping, UDP port `8765` bound on the Zero, and live page updates without `NO LINK` or `STALE`.

## Inspect the Link

Run on each device with the appropriate peer address:

```bash
ip -br addr show usb0
cat /sys/class/net/usb0/carrier
ip neigh show dev usb0
sudo systemctl status sidewalkpilot-usb0-keeper.service -l --no-pager
```

`carrier=1` with an `INCOMPLETE` neighbor means USB electrical enumeration succeeded but Ethernet frames are not completing. Inspect both devices; restarting only the sender cannot repair the Zero's gadget state.

## Linked Shutdown

When the controller exits normally, it sends several shutdown datagrams. The receiver logs `Dashboard receiver shutdown requested by controller.` and exits. Restart both services before a new run if the service units do not automatically restart after clean exit.

## Physical Failure Boundary

Repeated USB descriptor errors (`-110`, `-62`, or `unable to enumerate`) occur below the application layer. Move to a known-good Pi 5 USB port/cable and verify `lsusb` before changing Python. A cable carrying power does not prove its data path is healthy.
