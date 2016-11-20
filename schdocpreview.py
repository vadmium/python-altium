from tkinter import Tk, PhotoImage, Label
from configparser import ConfigParser
from binascii import unhexlify
import zlib
from sys import stdin
from io import BytesIO

image = ConfigParser(interpolation=None)
image.read_file(stdin)
width = image.getint("Preview", "LargeImageWidth", raw=True)
height = image.getint("Preview", "LargeImageHeight", raw=True)
ppm = BytesIO()
ppm.write(
    "P6\n"
    f"{width} {height}\n"
    "255\n".encode("ascii")
)

image = image.get("Preview", "LargeImage", raw=True)
image = zlib.decompress(unhexlify(image))
for row in range(height):
    for col in range(width):
        pixel = ( (height - row) * width + col ) * 4
        pixel = int.from_bytes(image[pixel:pixel + 4], "little")
        ppm.write(pixel.to_bytes(3, "big"))

tk = Tk()
image = PhotoImage(data=ppm.getvalue())
label = Label(tk, image=image)
label.pack()
tk.mainloop()
