#!/usr/bin/env python3

import time
import RPi.GPIO as GPIO

GREEN_LED_PIN = 4     # BCM 4
YELLOW_LED_PIN = 27   # BCM 27
RED_LED_PIN = 24      # BCM 24

PIR_PIN = 17          # BCM 17

ON_DURATION = 2.0

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(GREEN_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(YELLOW_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(RED_LED_PIN, GPIO.OUT, initial=GPIO.LOW)

GPIO.setup(PIR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def blink(pin):
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(ON_DURATION)
    GPIO.output(pin, GPIO.LOW)

def main():
    blink(GREEN_LED_PIN)
    blink(YELLOW_LED_PIN)
    blink(RED_LED_PIN)

    print("Warming up PIR (they often need ~30–60s)...")
    time.sleep(30)

    print("Ready. Move in front of the sensor.")
    try:
        while True:
            if GPIO.input(PIR_PIN):
                print("Motion!")
                blink(GREEN_LED_PIN)
                blink(YELLOW_LED_PIN)
                blink(RED_LED_PIN)
            else:
                print("No motion")
                time.sleep(0.5)
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
