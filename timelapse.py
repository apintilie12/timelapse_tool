import os
import time
from picamera2 import Picamera2, Preview

from astral import LocationInfo
from astral.sun import sun
from datetime import datetime, timedelta, timezone
import json

TARGET_LONGITUDE = 23.6236

TARGET_LATITUDE = 46.7712

settings = {
    "fps": 60,
    "len_in_seconds": 30,
    "real_time_duration_in_days": 30,
}

state = {}
daily_progress = {}

GMT_OFFSET=3

def LOG(logfile, now_string, msg):
    logfile.write(f"[{now_string}] {msg}\n")

def now_tz():
    return datetime.now(tz=timezone(timedelta(hours=GMT_OFFSET)))

def capture_frame():
    picam = Picamera2()
    picam.start_preview(Preview.NULL)
    picam.start_and_capture_file(f"imgs/frame{state['current_frame']}.jpg")


def open_log():
    # Test if log exists already, else create it
    try:
        logfile = open("log.txt", 'a')
    except OSError:
        logfile = open("log.txt", 'w')
        logfile.close()
        logfile = open("log.txt", 'a')
    return logfile


def load_configs(verbose: bool):
    global settings
    global state

    logfile = open_log()

    now_string = now_tz().strftime("%d.%m.%Y--%H:%M:%S")

    # Load settings from file
    try:
        settings_file = open("settings.json", "r")
        settings = json.load(settings_file)
        settings_file.close()
        if verbose:
            LOG(logfile, now_string, "Loaded settings from file.")
    except OSError:  # Settings file should have been created -- critical error
        LOG(logfile, now_string, "Settings file was not created! Exiting...")
        exit(1)
    # Load state from file
    init_state(logfile, now_string, verbose)
    # Load daily progress from file
    init_daily_progress(logfile, now_string, verbose)
    logfile.close()


def init_state(logfile, now_string, verbose):
    global state
    global settings
    try:
        state_file = open("state.json", "r")
        state = json.load(state_file)
        state_file.close()
        if verbose:
            LOG(logfile, now_string, "Loaded state from file.")
    except OSError:  # State file doesn't exist ==> must be first run
        total_frames = settings['fps'] * settings['len_in_seconds']
        state['total_frames'] = total_frames
        state['current_frame'] = 0
        state['current_day'] = 0
        state['frames_per_day'] = total_frames / settings['real_time_duration_in_days']
        state['next_wakeup_time'] = 0
        state_file = open("state.json", "w")
        json.dump(state, state_file, indent=4)
        state_file.close()
        if verbose:
            LOG(logfile, now_string, "Initialized state file.")


def init_daily_progress(logfile, now_string, verbose):
    global daily_progress
    try:
        daily_progress_file = open("daily_progress.json", 'r')
        daily_progress = json.load(daily_progress_file)
        daily_progress_file.close()
        if verbose:
            LOG(logfile, now_string, "Loaded daily progress from file.")

    except OSError:  # Progress file doesn't exist ==> must be first run
        astral_data = get_astral_data(now_tz())
        daylight_in_s = astral_data['sunset'] - astral_data['sunrise']
        sleep_duration = daylight_in_s.seconds / state['frames_per_day']
        daily_progress['sleep_duration'] = sleep_duration
        daily_progress['current_frame'] = 0
        daily_progress_file = open("daily_progress.json", 'w')
        json.dump(daily_progress, daily_progress_file, indent=4)
        daily_progress_file.close()
        if verbose:
            LOG(logfile, now_string, f"Initialized daily progress. Sleep duration is {state['sleep_duration']} seconds.")


def get_astral_data(date):
    city = LocationInfo("Cluj-Napoca", "Romania")
    city.latitude = TARGET_LATITUDE
    city.longitude = TARGET_LONGITUDE
    s = sun(city.observer, date=date)
    return s


def save_states():
    with open("settings.json", 'w') as settings_file:
        json.dump(settings, settings_file, indent=4)
    with open("state.json", 'w') as state_file:
        json.dump(state, state_file, indent=4)
    with open("daily_progress.json", 'w') as daily_progress_file:
        json.dump(daily_progress, daily_progress_file, indent=4)


def sleep_until_sunrise(logfile):
    tommorow = now_tz() + timedelta(days=1)
    adt = get_astral_data(tommorow)
    next_sunrise = adt['sunrise']
    state['next_wakeup_time'] = next_sunrise.timestamp()
    sleep_interval = (next_sunrise - now_tz()).seconds
    now_string = now_tz().strftime("%d.%m.%Y--%H.%M.%S")
    next_wakeup_string = next_sunrise.strftime("%d.%m.%Y--%H:%M:%S")
    LOG(logfile, now_string, f"Finished for the day going to sleep until: {next_wakeup_string}")
    save_states()
    os.remove("daily_progress.json")
    logfile.close()
    time.sleep(sleep_interval)


def main():
    now_string = now_tz().strftime("%d.%m.%Y--%H:%M:%S")
    logfile = open_log()
    LOG(logfile, now_string, "Process started")
    logfile.close()
    load_configs(True)
    logfile = open_log()
    next_wakeup_string =datetime.fromtimestamp(state['next_wakeup_time'], tz=timezone(timedelta(hours=GMT_OFFSET))).strftime("%d.%m.%Y--%H:%M:%S")
    LOG(logfile, now_string, f"Next wakeup at: {next_wakeup_string}")
    logfile.close()
    while True:
        load_configs(False)
        now = now_tz().timestamp()
        logfile = open_log()
        if now >= state['next_wakeup_time']:  # Waken up correctly -- take picture and update
            if now >= get_astral_data(now_tz())['sunset'].timestamp(): #somehow woken up after sunset and next wakeup time is incorrectly configured
                sleep_until_sunrise(logfile)
            if state['current_frame'] == 0 and state['current_day'] == 0:  # First run, adapt sleep interval to remaining daylight
                adt = get_astral_data(now_tz())
                next_sunset = adt['sunset']
                daily_progress['sleep_duration'] = (next_sunset - now_tz()).seconds / state['frames_per_day']
                LOG(logfile, now_string, f"Timelapse started after sunrise. Setting sleep duration to {state['frames_per_day']} seconds.")
            now_string = now_tz().strftime("%d.%m.%Y--%H:%M:%S")
            state['current_frame'] = state['current_frame'] + 1
            daily_progress['current_frame'] = daily_progress['current_frame'] + 1
            capture_frame()
            LOG(logfile, now_string,
                f"Captured frame {daily_progress['current_frame']}/{state['frames_per_day']} frames today and"
                f" {state['current_frame']}/{state['total_frames']} frames total.")
            if daily_progress['current_frame'] == state['frames_per_day']:  # Finished for the day
                state['current_day'] = state['current_day'] + 1
                if state['current_day'] == settings[
                    'real_time_duration_in_days']:  # Finished timelapse -- cleanup and exit
                    LOG(logfile, now_string, "Finished completely -- cleanup and exit")
                    os.remove("state.json")
                    os.remove("daily_progress.json")
                    logfile.close()
                    break
                else:  # Go to sleep until the next sunrise
                    sleep_until_sunrise(logfile)
            else:  # Still have frames to capture today
                next_wakeup_time = now_tz() + timedelta(seconds=daily_progress['sleep_duration'])
                state['next_wakeup_time'] = next_wakeup_time.timestamp()
                save_states()
                next_wakeup_string = next_wakeup_time.strftime("%d.%m.%Y--%H:%M:%S")
                LOG(logfile, now_string, f"Next wakeup is at: {next_wakeup_string}")
                logfile.close()
                time.sleep(daily_progress['sleep_duration'])

        else:  # Woken up erroneously -- go back to sleep
            time.sleep(state['next_wakeup_time'] - now)


if __name__ == "__main__":
    main()
