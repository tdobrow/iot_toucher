#!/usr/bin/env python3

from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import time
import json
import os
import uuid
from functools import partial
from dotenv import load_dotenv
from datetime import datetime, timezone
import threading
import queue
import RPi.GPIO as GPIO

TOUCH_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(TOUCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # most TTP223 modules idle LOW, go HIGH on touch
GPIO.setwarnings(False)

def getenv(name, default=None):
    return os.getenv(name, default)


def build_metrics():
    current_time = datetime.now(timezone.utc).isoformat()
    return {
        "startup_timestamp": current_time,
        "total_time_alive": 0,
        "last_publish_timestamp": -1,
        "total_messages_sent": 0,
        "total_messages_received": 0,
        "client_reconnections": -1
    }


def print_metrics():
    parsed_time = datetime.fromisoformat(METRICS["startup_timestamp"])
    elapsed_seconds = int((datetime.now(timezone.utc) - parsed_time).total_seconds())
    METRICS["total_time_alive"] = elapsed_seconds
    print("System Metrics")
    print(json.dumps(METRICS, indent=2, sort_keys=True))
    print()


def on_message(current_client_id, topic, payload, dup, qos, retain, **kwargs):
    try:
        text = payload.decode("utf-8")
        msg = json.loads(text)
        if msg.get("client_id") == current_client_id:
            return
        INCOMING.put(msg)
        METRICS["total_messages_received"] += 1
        print("Message Received")
        print(json.dumps(msg, indent=2, sort_keys=True))
        print()

    except Exception as e:
        INCOMING.put({"_raw": repr(payload), "_error": str(e)})


def build_message(client_id, action="test", **extra):
    base = {
        "client_id": client_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action
    }
    if extra:
        base.update(extra)
    return base


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

# ---- touch listener ----

def touch_callback(channel, client, topic, current_client_id):
    try:
        # Many touch boards output a brief HIGH pulse; confirm current level is HIGH
        if GPIO.input(TOUCH_PIN):
            payload = json.dumps(build_message(current_client_id, action="touch"))
            client.publish(topic=topic, payload=payload, qos=mqtt.QoS.AT_LEAST_ONCE)
            METRICS["total_messages_sent"] += 1
            METRICS["last_publish_timestamp"] = datetime.now(timezone.utc).isoformat()
            print("[touch] published")
    except Exception as e:
        print(f"[touch_callback] error: {e}")
        RECONNECT_EVENT.set()

def setup_touch_listener(client, topic, current_client_id):
    try:
        GPIO.remove_event_detect(TOUCH_PIN)
    except Exception:
        pass  # safe if not set yet
    try:
        GPIO.cleanup(TOUCH_PIN)  # fully release pin from any prior run
    except Exception:
        pass

    # Reconfigure the pin each time before adding detection
    GPIO.setup(TOUCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    try:
        GPIO.add_event_detect(
            TOUCH_PIN,
            GPIO.RISING,  # many touch sensors go HIGH when touched
            callback=partial(touch_callback, client=client, topic=topic, current_client_id=current_client_id),
            bouncetime=200
        )
    except Exception as e:
        # Make the root cause obvious in logs
        raise RuntimeError(f"Failed to add edge detection on GPIO{TOUCH_PIN}: {e}")

# ---- worker loops ----

def listener_loop(client, topic, current_client_id):
    try:
        sub_future, _ = client.subscribe(
            topic=topic,
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=partial(on_message, current_client_id)
        )
        sub_future.result()

        while not STOP_EVENT.is_set() and not RECONNECT_EVENT.is_set():
            time.sleep(0.25)

    except Exception as e:
        print(f"[listener_loop] error: {e}")
        RECONNECT_EVENT.set()

def publisher_loop(client, topic, current_client_id):
    try:
        while not STOP_EVENT.is_set() and not RECONNECT_EVENT.is_set():
            payload = json.dumps(build_message(current_client_id))
            client.publish(topic=topic, payload=payload, qos=mqtt.QoS.AT_LEAST_ONCE)
            METRICS["total_messages_sent"] += 1
            METRICS["last_publish_timestamp"] = datetime.now(timezone.utc).isoformat()
            time.sleep(10)
    except Exception as e:
        print(f"[publisher_loop] error: {e}")
        RECONNECT_EVENT.set()

def metrics_loop():
    try:
        while not STOP_EVENT.is_set() and not RECONNECT_EVENT.is_set():
            print_metrics()
            time.sleep(30)
    except Exception as e:
        print(f"[metrics_loop] error: {e}")
        RECONNECT_EVENT.set()

def extra_loop():
    try:
        while not STOP_EVENT.is_set() and not RECONNECT_EVENT.is_set():
            time.sleep(1)
    except Exception as e:
        print(f"[extra_loop] error: {e}")
        RECONNECT_EVENT.set()

def start_workers(client, topic, client_id):
    STOP_EVENT.clear()
    RECONNECT_EVENT.clear()

    setup_touch_listener(client, topic, client_id)

    threads = [
        threading.Thread(target=listener_loop, args=(client, topic, client_id), daemon=True),
        threading.Thread(target=publisher_loop, args=(client, topic, client_id), daemon=True),
        threading.Thread(target=metrics_loop, daemon=True),
        threading.Thread(target=extra_loop, daemon=True),
    ]
    for th in threads:
        th.start()
    return threads

def stop_workers(threads, client):
    STOP_EVENT.set()
    for th in threads:
        th.join(timeout=2)
    try:
        GPIO.remove_event_detect(TOUCH_PIN)
    except Exception:
        pass
    try:
        if client is not None:
            client.disconnect().result(timeout=5)
    except Exception as e:
        print(f"[stop_workers] disconnect error (ignored): {e}")

def on_interrupted(connection, error, **kwargs):
    print(f"[connection_interrupted] {error}")
    RECONNECT_EVENT.set()

def on_resumed(connection, return_code, session_present, **kwargs):
    print(f"[connection_resumed] code={return_code} session_present={session_present}")

def main():
    load_dotenv()
    topic = getenv("TOPIC")

    while True:
        try:
            client_id, client = build_mqtt_client()

            client.connect().result(timeout=10)
            client.on_connection_interrupted = on_interrupted
            client.on_connection_resumed = on_resumed

            print(f"[connect] SUCCESS: client_id={client_id}")
            METRICS["client_reconnections"] += 1

            threads = start_workers(client, topic, client_id)

            while not RECONNECT_EVENT.is_set():
                time.sleep(0.5)

            print("[main] reconnect requested")
            stop_workers(threads, client)

        except KeyboardInterrupt:
            print("Stopping...")
            try:
                stop_workers(threads if 'threads' in locals() else [], client if 'client' in locals() else None)
            finally:
                GPIO.cleanup()
                break
        except Exception as e:
            raise RuntimeError(f"Failed to add edge detection on GPIO{TOUCH_PIN}: {e!r}")
        # except Exception as e:
        #     print(f"[main] setup error: {e}. Retrying soon...")
        #     time.sleep(3)

STOP_EVENT = threading.Event()
RECONNECT_EVENT = threading.Event()
INCOMING = queue.Queue()
METRICS = build_metrics()

if __name__ == "__main__":
  main()
