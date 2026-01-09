#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time

# Use pins that aren't GPIO 4
ROT_A_PIN = 17
ROT_B_PIN = 23

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()  # clear any leftovers from previous runs

GPIO.setup(ROT_A_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ROT_B_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def read_state():
    state = GPIO.input(ROT_A_PIN), GPIO.input(ROT_B_PIN)
    print("Rotary State: ${}".format(state))
    return state

def main():
    print("Polling rotary on A={}, B={} (BCM). Ctrl+C to exit.".format(ROT_A_PIN, ROT_B_PIN))

    last_a, last_b = read_state()

    try:
        while True:
            a, b = read_state()

            # Only react when A changes (this is our "event")
            if a != last_a:
                # We usually look on the falling edge (a goes from 1 -> 0)
                if a == 0:
                    # Simple quadrature rule:
                    # If B != A on that edge → one direction, else → the other
                    if b == 1:
                        print("RIGHT")
                    else:
                        print("LEFT")

                last_a, last_b = a, b

            time.sleep(0.001)  # small delay to avoid hammering CPU

    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
