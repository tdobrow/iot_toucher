#!/usr/bin/env python3

import json, time, uuid
from datetime import datetime, timezone
import RPi.GPIO as GPIO

GREEN_LED_PIN = 4            # GPIO 17 (physical pin 11)
YELLOW_LED_PIN = 27        # GPIO 27 (physical pin 13)
RED_LED_PIN = 24        # GPIO 26 (physical pin 37)

PIR_PIN = 17

ON_DURATION = 2.0

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(GREEN_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(YELLOW_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(RED_LED_PIN, GPIO.OUT, initial=GPIO.LOW)

GPIO.setup(PIR_PIN, GPIO.OUT, initial=GPIO.LOW)

def blink(pin):
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(ON_DURATION)
    GPIO.output(pin, GPIO.LOW)

def main():
    # Signal that things are up and running
    blink(GREEN_LED_PIN)
    blink(YELLOW_LED_PIN)
    blink(RED_LED_PIN)

    while True:
        if GPIO.input(17):
            blink(GREEN_LED_PIN)
            blink(YELLOW_LED_PIN)
            blink(RED_LED_PIN)
        else:
            print("No motion")
        


if __name__ == "__main__":
    main()
