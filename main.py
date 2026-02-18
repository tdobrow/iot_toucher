#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time

# Use pins that aren't GPIO 4
ROT_A_PIN = 17
ROT_B_PIN = 23

ROT_A_PIN_TWO = 10
ROT_B_PIN_TWO = 24

PUSH_PIN  = 14
PUSH_PIN_TWO = 15

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()  # clear any leftovers from previous runs

GPIO.setup(ROT_A_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ROT_B_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PUSH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.setup(ROT_A_PIN_TWO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ROT_B_PIN_TWO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PUSH_PIN_TWO, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# First spinner has value 1, second has value 2
def read_state(spinner_number):
    if spinner_number == 1:
        return GPIO.input(ROT_A_PIN), GPIO.input(ROT_B_PIN)
    if spinner_number == 2:
        return GPIO.input(ROT_A_PIN_TWO), GPIO.input(ROT_B_PIN_TWO)

def main():
    print("Polling first rotary on A={}, B={} (BCM). Ctrl+C to exit.".format(ROT_A_PIN, ROT_B_PIN))
    print("Polling second rotary on A={}, B={} (BCM). Ctrl+C to exit.".format(ROT_A_PIN_TWO, ROT_B_PIN_TWO))

    last_a_one, last_b_one = read_state(1)
    last_a_two, last_b_two = read_state(2)
    is_pushed_one = False
    is_pushed_two = False

    try:
        while True:
            a_one, b_one = read_state(1)
            a_two, b_two = read_state(2)

            if GPIO.input(PUSH_PIN) == GPIO.LOW:
                if not is_pushed_one:
                    print("ONE PUSHED")
                    is_pushed_one = True
            else:
                is_pushed_one = False

            if GPIO.input(PUSH_PIN_TWO) == GPIO.LOW:
                if not is_pushed_two:
                    print("TWO PUSHED")
                    is_pushed_two = True
            else:
                is_pushed_two = False

            # Only react when A changes (this is our "event")
            if a_one != last_a_one:
                # We usually look on the falling edge (a goes from 1 -> 0)
                if a_one == 0:
                    # Simple quadrature rule:
                    # If B != A on that edge → one direction, else → the other
                    if b_one == 1:
                        print("ONE RIGHT")
                    else:
                        print("ONE LEFT")

                last_a_one, last_b_one = a_one, b_one

            # Only react when A changes (this is our "event")
            if a_two != last_a_two:
                # We usually look on the falling edge (a goes from 1 -> 0)
                if a_two == 0:
                    # Simple quadrature rule:
                    # If B != A on that edge → one direction, else → the other
                    if b_two == 1:
                        print("TWO RIGHT")
                    else:
                        print("TWO LEFT")

                last_a_two, last_b_two = a_two, b_two

            time.sleep(0.01)  # small delay to avoid hammering CPU

    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
