#!/usr/bin/env python3

import os, json, time, uuid
from datetime import datetime, timezone
from functools import partial
from dotenv import load_dotenv
import RPi.GPIO as GPIO
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder

TOUCH_PIN = 17  # GPIO pin 17, which is pin 11 on the board
LED_PIN = 27    # GPIO pin 27, which is pin 13 on the board

TEST_INTERVAL_SEC = 10
TOUCH_DEBOUNCE_MS = 200

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(TOUCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)

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

def message_received(topic, payload, my_id=None, **kwargs):
    try:
        text = payload.decode("utf-8")
        msg = json.loads(text)
        # Ignore messages sent by *this* device
        if msg.get("client_id") == my_id:
            # Optional: uncomment to see skips
            # print(f"[msg] Skipping own message ({my_id})")
            return

        print(f"[msg] Received on {topic}: {json.dumps(msg, indent=2)}")

        action = msg.get("action")
        if action == "touch":
            GPIO.output(LED_PIN, GPIO.HIGH)
        else:  # any other message will reset it
            GPIO.output(LED_PIN, GPIO.LOW)

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

            # subscribe (pass our client_id so we can ignore our own messages)
            sub_future, _ = client.subscribe(
                topic=topic,
                qos=mqtt.QoS.AT_LEAST_ONCE,
                callback=partial(message_received, my_id=client_id)
            )
            sub_future.result()
            print(f"[subscribe] Listening on topic '{topic}'")

            next_test_at = time.monotonic() + TEST_INTERVAL_SEC
            last_state = GPIO.input(TOUCH_PIN)
            last_rise = 0.0

            while True:
                now = time.monotonic()

                # periodic test event
                if now >= next_test_at:
                    payload = json.dumps(build_message(client_id, action="test"))
                    client.publish(topic=topic, payload=payload, qos=mqtt.QoS.AT_LEAST_ONCE)
                    print("[publish] test")
                    next_test_at += TEST_INTERVAL_SEC

                # touch rising edge
                s = GPIO.input(TOUCH_PIN)
                if last_state == 0 and s == 1 and (now - last_rise) * 1000.0 > TOUCH_DEBOUNCE_MS:
                    payload = json.dumps(build_message(client_id, action="touch"))
                    client.publish(topic=topic, payload=payload, qos=mqtt.QoS.AT_LEAST_ONCE)
                    print("[publish] touch")
                    last_rise = now
                last_state = s

                time.sleep(0.01)

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
