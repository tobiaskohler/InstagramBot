import time
import random
import sys

def powernap():
    kurz = random.randint(6, 8)
    for i in range(kurz, 0, -1):
        sys.stdout.write(str(i) + ' ')
        sys.stdout.flush()
        time.sleep(1)

def kurzschlafen():
    kurz = 5 + random.randint(3, 10)
    for i in range(kurz, 0, -1):
        sys.stdout.write(str(i) + ' ')
        sys.stdout.flush()
        time.sleep(1)

def langschlafen():
    lang = 15 + random.randint(5, 15)
    for i in range(lang, 0, -1):
        sys.stdout.write(str(i) + ' ')
        sys.stdout.flush()
        time.sleep(1)

def scrollpause():
    kurz = 2
    for i in range(kurz, 0, -1):
        sys.stdout.write(str(i))
        sys.stdout.flush()
        time.sleep(1)