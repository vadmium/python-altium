#! /usr/bin/env python3

import altium
from sys import argv

def main(file):
    with open(file, "rb") as file:
        objects = altium.read(file)
    for [i, o] in enumerate(objects):
        if not i:
            i = "Header"
        else:
            i = format(i - 1)
        print("{}: {}".format(i, altium.dump_properties(o)))

if __name__ == "__main__":
    try:
        main(*argv[1:])
    except (KeyboardInterrupt, ConnectionError):
        raise SystemExit(1)
