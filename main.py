import time
import RPi.GPIO as GPIO

# BCM pin numbers
ROT_A_PIN = 4   # encoder A
ROT_B_PIN = 17   # encoder B

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Use internal pull-ups so pins sit at 3.3V when switches open
GPIO.setup(ROT_A_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ROT_B_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

last_encoded = 0  # last A/B state

def rotary_callback(channel):
    global last_encoded

    # Read current A/B states
    msb = GPIO.input(ROT_A_PIN)  # most significant bit
    lsb = GPIO.input(ROT_B_PIN)  # least significant bit
    encoded = (msb << 1) | lsb

    combined = (last_encoded << 2) | encoded

    # These patterns mean one direction…
    if combined in (0b1101, 0b0100, 0b0010, 0b1011):
        print("RIGHT")
    # …and these mean the other
    elif combined in (0b1110, 0b0111, 0b0001, 0b1000):
        print("LEFT")

    last_encoded = encoded

# Fire callback when either channel changes
GPIO.add_event_detect(ROT_A_PIN, GPIO.BOTH, callback=rotary_callback)
GPIO.add_event_detect(ROT_B_PIN, GPIO.BOTH, callback=rotary_callback)

try:
    print("Listening for encoder turns… Ctrl+C to exit.")
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
