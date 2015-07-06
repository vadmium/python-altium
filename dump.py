#! /usr/bin/env python3

import altium
from sys import stdin

def main():
    objects = altium.read(stdin.buffer)
    for o in objects:
        print(repr(o))

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, ConnectionError):
        raise SystemExit(1)
