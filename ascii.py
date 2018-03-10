#! /usr/bin/env python3

import altium
from sys import argv, stdout
from warnings import warn

def main(file):
    with open(file, "rb") as file:
        file = altium.OleFileIO(file)
        for stream in ("FileHeader", "Storage", "Additional"):
            if not file.exists(stream):
                continue
            stream = file.openstream(stream)
            for [type, length] in altium.iter_records(stream):
                if type != 0:
                    warn("Cannot handle record type " + format(type))
                    continue
                record = stream.read(length - 1)
                if b"\n" in record:
                    warn("Embedded newline in record")
                stdout.buffer.write(record)
                stdout.buffer.write(b"\n")
                if stream.read(1) != b"\x00":
                    warn("Properties record not null-terminated")

if __name__ == "__main__":
    try:
        main(*argv[1:])
    except (KeyboardInterrupt, ConnectionError):
        raise SystemExit(1)
