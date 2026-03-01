import asyncio
import csv
import os
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from datetime import datetime, timedelta, timezone

CSV_FILE = "data.csv"
CSV_FIELDS = [
    "address", "name", "rssi", "tx_power", "manufacturer",
    "service_uuids", "service_data", "connectable", "phy",
    "adv_timestamp", "first_seen", "last_updated",
]

COMPANY_IDS = {
    0x004c: "Apple",
    0x0006: "Microsoft",
    0x000f: "Broadcom",
    0x0075: "Samsung",
    0x00e0: "Google",
    0x0157: "Garmin",
    0x09C8: "XUNTONG (Flock Safety)",
}

APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)

APPLE_PAYLOAD_TYPES = {
    0x02: "iBeacon",
    0x05: "AirDrop",
    0x07: "AirPods",
    0x08: "Hey Siri",
    0x09: "AirPlay target",
    0x0a: "AirPlay source",
    0x0b: "MagicSwitch",
    0x0c: "Nearby/Handoff",
    0x0d: "Tethering target",
    0x0e: "Tethering source",
    0x0f: "Nearby Action",
    0x10: "Find My",
    0x12: "FindMy accessory",
}


def parse_platform_data(platform_data) -> dict:
    if not platform_data or len(platform_data) < 2:
        return {}
    _, adv_dict, *_ = platform_data
    result = {}
    ts = adv_dict.get("kCBAdvDataTimestamp")
    if ts:
        dt = APPLE_EPOCH + timedelta(seconds=float(ts))
        result["adv_timestamp"] = dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    if adv_dict.get("kCBAdvDataIsConnectable"):
        result["connectable"] = True
    phy = adv_dict.get("kCBAdvDataRxPrimaryPHY")
    if phy:
        result["phy"] = {1: "LE 1M", 2: "LE 2M", 3: "LE Coded", 129: "LE 1M (legacy)"}.get(phy, phy)
    return result


def get_manufacturer_type_labels(raw: dict) -> set[str]:
    """Returns stable type labels like {'Apple: Find My', 'Apple: type=0x01'} — ignores rotating payload bytes."""
    labels = set()
    for company_id_hex, payload_hex in raw.items():
        company_id = int(company_id_hex, 16)
        company_name = COMPANY_IDS.get(company_id, f"Unknown ({company_id_hex})")
        if company_id == 0x004c and len(payload_hex) >= 2:
            type_byte = int(payload_hex[:2], 16)
            type_label = APPLE_PAYLOAD_TYPES.get(type_byte, f"type=0x{type_byte:02x}")
            labels.add(f"{company_name}: {type_label}")
        else:
            labels.add(company_name)
    return labels


def extract_info(device: BLEDevice, adv: AdvertisementData) -> dict:
    manufacturer_raw = {hex(k): v.hex() for k, v in adv.manufacturer_data.items()}
    info = {
        "name": device.name or adv.local_name or "",
        "rssi": adv.rssi,
        "tx_power": adv.tx_power or "",
        "_manufacturer_labels": get_manufacturer_type_labels(manufacturer_raw),
        "service_uuids": "; ".join(adv.service_uuids),
        "service_data": "; ".join(f"{k}={v.hex()}" for k, v in adv.service_data.items()),
        "connectable": "",
        "phy": "",
        "adv_timestamp": "",
    }
    info.update(parse_platform_data(adv.platform_data))
    return info


def load_csv() -> dict[str, dict]:
    devices = {}
    if not os.path.exists(CSV_FILE):
        return devices
    with open(CSV_FILE, newline="") as f:
        for row in csv.DictReader(f):
            # Reconstruct the in-memory label set from the pipe-delimited CSV field
            row["_manufacturer_labels"] = set(row.get("manufacturer", "").split(" | ")) - {""}
            devices[row["address"]] = row
    return devices


def write_csv(devices: dict[str, dict]):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        # Exclude in-memory-only fields (prefixed with _) when writing
        writer.writerows(
            {k: v for k, v in row.items() if not k.startswith("_")}
            for row in devices.values()
        )


def print_summary(devices: dict[str, dict]):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*60}")
    print(f"  SUMMARY [{now}] — {len(devices)} devices tracked")
    print(f"{'='*60}")
    for address, row in devices.items():
        name = row.get("name") or "unnamed"
        rssi = row.get("rssi", "")
        manufacturer = row.get("manufacturer", "")
        last = row.get("last_updated", "")
        print(f"  {address}  {name:<30}  rssi={rssi:<5}  {manufacturer[:40]:<40}  last={last}")
    print(f"{'='*60}\n")


seen_devices: dict[str, dict] = {}
TRACKED_KEYS = {"name", "tx_power", "service_uuids", "service_data", "connectable", "phy"}


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def callback(device: BLEDevice, adv: AdvertisementData):
    address = device.address
    info = extract_info(device, adv)
    timestamp = now_str()

    if address not in seen_devices:
        manufacturer_labels = info["_manufacturer_labels"]
        row = {
            "address": address,
            "first_seen": timestamp,
            "last_updated": timestamp,
            "manufacturer": " | ".join(sorted(manufacturer_labels)),
            **{k: v for k, v in info.items() if not k.startswith("_")},
            "_manufacturer_labels": manufacturer_labels,
        }
        seen_devices[address] = row
        write_csv(seen_devices)
        print(f"\n[{timestamp}] NEW  {address}  {info['name'] or 'unnamed'}  rssi={info['rssi']}  {row['manufacturer']}")
    else:
        prev = seen_devices[address]
        changes = {
            k: (prev.get(k), info[k])
            for k in TRACKED_KEYS
            if info.get(k) not in (None, "", {}, []) and info.get(k) != prev.get(k)
        }

        # Check for genuinely new manufacturer type labels
        prev_labels = prev.get("_manufacturer_labels", set())
        new_labels = info["_manufacturer_labels"] - prev_labels
        if new_labels:
            merged_labels = prev_labels | new_labels
            changes["manufacturer"] = (prev.get("manufacturer"), " | ".join(sorted(merged_labels)))
            prev["_manufacturer_labels"] = merged_labels
            prev["manufacturer"] = " | ".join(sorted(merged_labels))

        if changes:
            seen_devices[address].update({
                **{k: v for k, v in info.items() if not k.startswith("_")},
                "last_updated": timestamp,
                "manufacturer": prev["manufacturer"],
            })
            write_csv(seen_devices)
            print(f"\n[{timestamp}] UPD  {address}  {info['name'] or 'unnamed'}")
            for key, (old, new) in changes.items():
                print(f"  {key:<22}: {old!r} → {new!r}")


async def periodic_summary():
    while True:
        await asyncio.sleep(60)
        print_summary(seen_devices)


async def main():
    global seen_devices
    seen_devices = load_csv()
    print(f"Loaded {len(seen_devices)} devices from {CSV_FILE}")
    print("Scanning for BLE devices... (Ctrl+C to stop)\n")

    async with BleakScanner(callback):
        await periodic_summary()


if __name__ == "__main__":
    asyncio.run(main())
