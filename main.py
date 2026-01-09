#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time

ROT_A_PIN = 22
ROT_B_PIN = 17

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()  # clear any previous edge detection

GPIO.setup(ROT_A_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ROT_B_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def rotary_callback():
    a = GPIO.input(ROT_A_PIN)
    b = GPIO.input(ROT_B_PIN)

    # Simple direction guess:
    if a == b:
        print("RIGHT")
    else:
        print("LEFT")

GPIO.add_event_detect(ROT_A_PIN, GPIO.BOTH,
                      callback=rotary_callback, bouncetime=2)

print("Listening for rotation on A/B (23/24). Ctrl+C to exit.")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
