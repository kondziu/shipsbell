#!/usr/bin/env python

# Standard libraries
import pygame, datetime, time, sys
from sched import scheduler
from os import path

# Local libraries
from daemon3x import daemon

# List and range of watches. Watches start *after* the first specified hour and
# end at the second hour. Dog watch is split into two shorter watches as per
# spec.
WATCHES = {
    (0,  4):  "middle watch", 
    (4,  8):  "morning watch", 
    (8,  12): "forenoon watch", 
    (12, 16): "afternoon watch", 
    (16, 18): "1st dog watch", 
    (18, 20): "last dog watch", 
    (20, 24):  "first watch",
}

# Delay between bell chimes when composing sequences.
bell_delay = .1

# Bell sound functions, keys are the number of bells chiming.
bells = {}

# Type of bell composition: 
#  * "composite" - compose each sequence out of double and single bell sounds
#  * "individual" - use individual read-made sequences
bell_composition = "individual" # or "composite"

# The template for the names of the bells. There should always be a number
# (%d)representing the number of bell chimes used.
sound_name = "%dbells.ogg" # or "shipsbell%d.ogg"

# The directory where all the sounds are kept.
sound_dir = "sounds"

# Whether to run the clock as a deamon or as is.
daemonize = False

# Operation to perform on the daemon.
operation = "start" # or "stop" or "restart"

# If running as daemon this is where the PID will be stored.
pid_file = "/tmp/shipsbell.pid"

# If the exception is in place, eight bells are not sounded during dog watch.
nore_mutiny_exception = False

def init_composite_bells():
    global bells, sound_dir, sound_name, bell_delay

    # Required for sounds to play.
    pygame.init()

    # Bell sounds.
    single_bell_snd = pygame.mixer.Sound(path.join(sound_dir, sound_name  % 1))
    double_bell_snd = pygame.mixer.Sound(path.join(sound_dir, sound_name  % 2))

    # Bell sound lengths.
    single_bell_len = single_bell_sound.get_length() + bell_delay
    double_bell_len = double_bell_sound.get_length() + bell_delay

    # Functions responsible for playing bell sounds.
    single_bell = lambda: (double_bell_snd.play(), time.sleep(double_bell_len))
    double_bell = lambda: (single_bell_snd.play(), time.sleep(single_bell_len))

    # Prepare functions responsible for playing bell sounds.
    def make_lambda(sequence):
        return lambda: [snd() for snd in sequence]

    # Prepare sequences for each number of bells.
    for i in range(1, 8 + 1):
        chimes = i
        double_chimes = int(chimes / 2)
        single_chime = chimes % 2
        bell_sequence = []

        # Double chimes for every ful hour.
        while double_chimes:
            bell_sequence.append(double_bell)
            double_chimes -= 1
    
        # Plus one chime if it's half past.
        if single_chime:
            bell_sequence.append(single_bell)

        # Prepare a ready-to-run function/lambda.
        bells[i] = make_lambda(sequence)

def init_individual_bells():
    global bells, sound_dir, sound_name

    # Required for sounds to play.
    pygame.init()

    # Create functions responsible for playing bell sounds.
    def make_lambda(snd, len):
        return lambda: (snd.play(), time.sleep(len))

    # Bell sounds and their lengths along with functions to play them.
    for i in range(1, 8 + 1):
        sound = pygame.mixer.Sound(path.join(sound_dir, sound_name % i))
        length = sound.get_length() 
        bells[i] = make_lambda(sound, length)

def chime_time(hour, minutes):
    chimes = 2 * (hour % 4) + (1 if minutes >= 30 else 0)
    chimes = 8 if not chimes else chimes

    bells[chimes]()

    return chimes

def current_watch(t):
    hour = time.localtime(t).tm_hour
    # hour = 24 if hour == 0 else hour
    for r in WATCHES:
        if hour >= r[0] and hour < r[1]:
            return WATCHES[r]
    raise ValueError("No valid watch for time " + time.localtime(t) + ".")

def register_new_event(s, time, delay, priority, f):
    """ Delay is in minutes."""
    t = time + delay * 60
    return s.enterabs(t, priority, f, (s, t, priority))

def watch_event(s, t, priority):
    print(current_watch(t))

def clock_event(s, t, priority):
    tm = time.localtime(t)
    if nore_mutiny_exception:
        if tm.tm_hour == 20 and tm.tm_min == 0:
            return 0
    chimes = chime_time(tm.tm_hour, tm.tm_min)

def handle_event(s, t, p, f):
    current = time.time()

    # only if not 30 minutes overdue
    if current <= t + 30 * 60:
        f(s, t, p)
    else:
        print('cancel, overdue')

    nexttime = t + 30 * 60
    return s.enterabs(t, p, handle_event, (s, nexttime, p, f))

def clock(clock_f = clock_event, watch_f = watch_event):
    tt = time.time() + 10 # Extra couple of seconds for all this stuff below.
    tm = time.localtime(tt)
    
    # Even the time out to the nearest half-hour mark.
    secs = 0
    mins = 30 if tm.tm_min < 30 else 0
    hrs = (tm.tm_hour + 1) % 24 if mins == 0 else tm.tm_hour

    # Could be we ended up with a new date as well.
    if hrs == 0:
        tm = time.localtime(tt + 60 * 60 * 24)

    # Estimate epoch time with delay included.
    t = time.mktime((tm.tm_year, tm.tm_mon, tm.tm_mday, hrs, mins, secs,
        tm.tm_wday, tm.tm_wday, tm.tm_isdst))

    # Run the scheduler (and hang).
    s = scheduler(time.time, time.sleep)
    s.enterabs(t, 1, handle_event, (s, t, 1, clock_f))
    s.enterabs(t, 2, handle_event, (s, t, 2, watch_f))
    s.run()

class ShipsBellDaemon(daemon):
    def run(self):
        clock()

if __name__ == '__main__':
    args = sys.argv[1:]

    # Prepare bell sounds.
    if bell_composition == "individual":
        init_individual_bells()
    elif bell_composition == "composite":
        init_composite_bells()

    if daemonize:
        if args:
            operation = args[0]

        daemon = ShipsBellDaemon(pid_file)

        # Do something with the daemon.
        if operation == "start":
            daemon.start()
        elif operation == "stop":
            daemon.stop()
        elif operation == "restart":
            daemon.restart()

    else:
        clock()

