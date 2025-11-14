#!/usr/bin/env python3

import os, json, time, uuid
from datetime import datetime, timezone
from functools import partial
from dotenv import load_dotenv
import RPi.GPIO as GPIO
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder

TOUCH_PIN = 17           # GPIO 17 (physical pin 11)
WHITE_LED_PIN = 27       # GPIO 27 (physical pin 13)
GREEN_LED_PIN = 26       # GPIO 26 (physical pin 37)

STATUS_INTERVAL_SEC = 60
TOUCH_DEBOUNCE_MS = 200
LED_ON_SECONDS = 10
GREEN_BLINK_DURATION = 0.3

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(TOUCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(WHITE_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(GREEN_LED_PIN, GPIO.OUT, initial=GPIO.LOW)

def getenv(name, default=None):
    return os.getenv(name, default)

def build_message(client_id, action, **extra):
    msg = {
        "client_id": client_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action
    }
    msg.update(extra)
    return msg

def build_mqtt_client():
    endpoint = getenv("IOT_ENDPOINT")
    client_id = str(uuid.uuid4())

    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

    client = mqtt_connection_builder.mtls_from_path(
        endpoint=endpoint,
        cert_filepath="certificates/certificate.pem.crt",
        pri_key_filepath="certificates/private.pem.key",
        client_bootstrap=client_bootstrap,
        client_id=client_id,
        clean_session=False,
        keep_alive_secs=6
    )
    return client_id, client

# --- simple synchronous blink (keep duration tiny to avoid blocking) ---
def blink(pin):
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(GREEN_BLINK_DURATION)
    GPIO.output(pin, GPIO.LOW)

def message_received(topic, payload, my_id=None, state=None, **kwargs):
    """Extend WHITE timer for remote touches. Optionally blink green on own echo."""
    try:
        text = payload.decode("utf-8")
        msg = json.loads(text)

        # Our own message echoed back: quick green blink (non-blocking enough if <= ~150ms)
        if msg.get("client_id") == my_id:
            blink(GREEN_LED_PIN)
            return

        # Remote message → extend white LED window
        if msg.get("action") == "touch":
            state["led_end_at"] = time.monotonic() + LED_ON_SECONDS
            print(f"[msg] remote touch → white until {state['led_end_at']:.3f}")

    except Exception as e:
        print(f"[msg] decode error: {e}")

def main():
    load_dotenv()
    topic = getenv("TOPIC")

    while True:
        try:
            client_id, client = build_mqtt_client()
            client.connect().result(timeout=10)
            print(f"[connect] OK client_id={client_id}")

            # WHITE timer state only
            state = {"led_end_at": 0.0}

            sub_future, _ = client.subscribe(
                topic=topic,
                qos=mqtt.QoS.AT_LEAST_ONCE,
                callback=partial(message_received, my_id=client_id, state=state)
            )
            sub_future.result()
            print(f"[subscribe] Listening on topic '{topic}'")

            next_status_message_at = time.monotonic() + STATUS_INTERVAL_SEC
            last_state = GPIO.input(TOUCH_PIN)
            last_rise = 0.0

            while True:
                now = time.monotonic()

                # periodic status
                if now >= next_status_message_at:
                    payload = json.dumps(build_message(client_id, action="status"))
                    client.publish(topic=topic, payload=payload, qos=mqtt.QoS.AT_LEAST_ONCE)
                    print("[publish] status message")
                    next_status_message_at += STATUS_INTERVAL_SEC

                # local touch rising edge → publish + synchronous green blink
                s = GPIO.input(TOUCH_PIN)
                if last_state == 0 and s == 1 and (now - last_rise) * 1000.0 > TOUCH_DEBOUNCE_MS:
                    payload = json.dumps(build_message(client_id, action="touch"))
                    client.publish(topic=topic, payload=payload, qos=mqtt.QoS.AT_LEAST_ONCE)
                    print("[publish] touch")
                    last_rise = now

                last_state = s

                # WHITE LED: on while remote-touch window active
                GPIO.output(WHITE_LED_PIN, GPIO.HIGH if now < state["led_end_at"] else GPIO.LOW)

                time.sleep(0.05)

        except Exception as e:
            print(f"[main] error: {e}. Restarting soon...")
            try:
                client.disconnect().result(timeout=3)
            except Exception:
                pass
            time.sleep(2)
            continue

if __name__ == "__main__":
    main()
