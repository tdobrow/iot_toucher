import asyncio
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from datetime import datetime, timedelta, timezone

# A small table of common company IDs — extend as you like
COMPANY_IDS = {
    0x004c: "Apple",
    0x0006: "Microsoft",
    0x000f: "Broadcom",
    0x0075: "Samsung",
    0x00e0: "Google",
    0x0157: "Garmin",
    0x09C8: "XUNTONG (Flock Safety)",
}

# Apple's CoreBluetooth epoch starts Jan 1 2001
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)

def parse_platform_data(platform_data) -> dict:
    if not platform_data or len(platform_data) < 2:
        return {}
    _, adv_dict, *_ = platform_data
    result = {}
    ts = adv_dict.get("kCBAdvDataTimestamp")
    if ts:
        dt = APPLE_EPOCH + timedelta(seconds=float(ts))
        result["timestamp"] = dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    if adv_dict.get("kCBAdvDataIsConnectable"):
        result["connectable"] = True
    phy = adv_dict.get("kCBAdvDataRxPrimaryPHY")
    if phy:
        result["phy"] = {1: "LE 1M", 2: "LE 2M", 3: "LE Coded", 129: "LE 1M (legacy)"}.get(phy, phy)
    return result

def format_manufacturer_data(raw: dict) -> dict:
    out = {}
    for company_id_hex, payload_hex in raw.items():
        company_id = int(company_id_hex, 16)
        company_name = COMPANY_IDS.get(company_id, f"Unknown ({company_id_hex})")
        out[company_name] = decode_apple_payload(company_id, payload_hex)
    return out

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

def decode_apple_payload(company_id: int, payload_hex: str) -> str:
    if company_id != 0x004c or len(payload_hex) < 2:
        return payload_hex
    type_byte = int(payload_hex[:2], 16)
    label = APPLE_PAYLOAD_TYPES.get(type_byte, f"type=0x{type_byte:02x}")
    return f"{label}  [{payload_hex}]"

def extract_info(device: BLEDevice, adv: AdvertisementData) -> dict:
    return {
        "name": device.name or adv.local_name,
        "rssi": adv.rssi,
        "tx_power": adv.tx_power,
        "manufacturer": format_manufacturer_data(
            {hex(k): v.hex() for k, v in adv.manufacturer_data.items()}
        ),
        "service_uuids": adv.service_uuids,
        "service_data": {k: v.hex() for k, v in adv.service_data.items()},
        **parse_platform_data(adv.platform_data),
    }

def format_device(address: str, info: dict) -> str:
    lines = [f"\n{'='*55}", f"  Address : {address}"]
    for key, value in info.items():
        if value not in (None, {}, [], ""):
            lines.append(f"  {key:<22}: {value}")
    lines.append(f"{'='*55}")
    return "\n".join(lines)

seen_devices: dict[str, dict] = {}
TRACKED_KEYS = {"name", "tx_power", "manufacturer", "service_uuids", "service_data"}

def callback(device: BLEDevice, adv: AdvertisementData):
    address = device.address
    info = extract_info(device, adv)
    now = datetime.now().strftime("%H:%M:%S")

    if address not in seen_devices:
        seen_devices[address] = info
        print(f"\n[{now}] NEW DEVICE")
        print(format_device(address, info))
    else:
        prev = seen_devices[address]
        changes = {
            k: (prev.get(k), info[k])
            for k in TRACKED_KEYS
            if info.get(k) not in (None, {}, [], "") and info.get(k) != prev.get(k)
        }
        if changes:
            seen_devices[address].update(info)
            print(f"\n[{now}] UPDATE — {address} ({info['name'] or 'unnamed'})")
            for key, (old, new) in changes.items():
                print(f"  {key:<22}: {old!r}")
                print(f"  {'':22}→ {new!r}")

async def main():
    print("Scanning for BLE devices... (Ctrl+C to stop)\n")
    async with BleakScanner(callback):
        await asyncio.sleep(float("inf"))

if __name__ == "__main__":
    asyncio.run(main())
