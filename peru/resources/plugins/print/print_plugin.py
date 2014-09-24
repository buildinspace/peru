#! /usr/bin/env python3

# This plugin is for testing the fancy display. It prints some output without
# making any network requests. I needed it on an airplane :)

import random
import sys
import time

for i in range(1, 6):
    print(i)
    sys.stdout.flush()
    time.sleep(0.5 + random.random())
