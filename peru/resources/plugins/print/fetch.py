#! /usr/bin/env python3

import random
import sys
import time

for i in range(1, 6):
    print(i)
    sys.stdout.flush()
    time.sleep(0.5 + random.random())
