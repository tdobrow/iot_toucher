#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth

ROT_A_PIN     = 17
ROT_B_PIN     = 23
ROT_A_PIN_TWO = 10
ROT_B_PIN_TWO = 24
PUSH_PIN      = 14
PUSH_PIN_TWO  = 15

VOLUME_STEP = 5  # percent per detent

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()
GPIO.setup(ROT_A_PIN,     GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ROT_B_PIN,     GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PUSH_PIN,      GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ROT_A_PIN_TWO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ROT_B_PIN_TWO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PUSH_PIN_TWO,  GPIO.IN, pull_up_down=GPIO.PUD_UP)


def read_state(spinner_number):
    if spinner_number == 1:
        return GPIO.input(ROT_A_PIN), GPIO.input(ROT_B_PIN)
    if spinner_number == 2:
        return GPIO.input(ROT_A_PIN_TWO), GPIO.input(ROT_B_PIN_TWO)


def change_volume(sp, delta):
    try:
        playback = sp.current_playback()
        if playback and playback.get("device"):
            current_vol = playback["device"]["volume_percent"]
            new_vol = max(0, min(100, current_vol + delta))
            sp.volume(new_vol)
            print(f"Volume: {new_vol}%")
        else:
            print("No active device found")
    except Exception as e:
        print(f"Volume error: {e}")


def main():
    print("Polling knob 1 on A={}, B={} (BCM). Ctrl+C to exit.".format(ROT_A_PIN, ROT_B_PIN))
    print("Polling knob 2 on A={}, B={} (BCM). Ctrl+C to exit.".format(ROT_A_PIN_TWO, ROT_B_PIN_TWO))

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id="b1b1446daf184504a6553cbd9cced3e9",
        client_secret="5fab21f6b7da48d9bfe4eb75fcb1e856",
        redirect_uri="http://127.0.0.1:8888/callback",
        scope="user-modify-playback-state user-read-playback-state"
    ))

    last_a_one, last_b_one = read_state(1)
    last_a_two, last_b_two = read_state(2)
    is_pushed_one = False
    is_pushed_two = False

    try:
        while True:
            a_one, b_one = read_state(1)
            a_two, b_two = read_state(2)

            # Knob 1 push → pause
            if GPIO.input(PUSH_PIN) == GPIO.LOW:
                if not is_pushed_one:
                    print("KNOB 1 PUSHED - Pause")
                    try:
                        sp.pause_playback()
                    except Exception as e:
                        print(f"Pause error: {e}")
                    is_pushed_one = True
            else:
                is_pushed_one = False

            # Knob 2 push (unassigned)
            if GPIO.input(PUSH_PIN_TWO) == GPIO.LOW:
                if not is_pushed_two:
                    print("KNOB 2 PUSHED")
                    is_pushed_two = True
            else:
                is_pushed_two = False

            # Knob 1 rotation: right → next, left → previous
            if a_one != last_a_one:
                if a_one == 0:
                    if b_one == 1:
                        print("KNOB 1 RIGHT - Next Track")
                        try:
                            sp.next_track()
                        except Exception as e:
                            print(f"Next track error: {e}")
                    else:
                        print("KNOB 1 LEFT - Previous Track")
                        try:
                            sp.previous_track()
                        except Exception as e:
                            print(f"Previous track error: {e}")
                last_a_one, last_b_one = a_one, b_one

            # Knob 2 rotation: right → volume up, left → volume down
            if a_two != last_a_two:
                if a_two == 0:
                    if b_two == 1:
                        print("KNOB 2 RIGHT - Volume Up")
                        change_volume(sp, +VOLUME_STEP)
                    else:
                        print("KNOB 2 LEFT - Volume Down")
                        change_volume(sp, -VOLUME_STEP)
                last_a_two, last_b_two = a_two, b_two

            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
