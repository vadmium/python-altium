from tkinter import Tk
import tkinter
from . import base
from tkinter.font import Font

class Renderer(base.Renderer):
    def __init__(self, size, units, unitmult=1, *, margin=0,
    down=+1,  # -1 if y axis points upwards, not implemented
    line=1, textsize=None, textbottom=False):
        self.colour = "black"
        
        root = Tk()
        self.scaling = root.call("tk", "scaling") * 72  # pixels/in
        self.scaling *= unitmult / {"mm": 25.4, "in": 1}[units]
        self.linewidth = line * self.scaling
        self.canvas = tkinter.Canvas(root,
            relief=tkinter.SUNKEN, borderwidth=1,
            background="white",
            height=size[1] * self.scaling, width=size[0] * self.scaling,
        )
        self.canvas.pack(fill=tkinter.BOTH, expand=True)
        self.fonts = dict()
    
    def addfont(self, id, size, family, italic=None, bold=None):
        kw = dict()
        if italic:
            kw.update(slant="italic")
        if bold:
            kw.update(weight="bold")
        self.fonts[id] = Font(name=id, family=family, size=-size, **kw)
    
    def line(self, a=(0, 0), b=(0, 0), *pos, **kw):
        self.polyline(a, b, *pos, **kw)
    
    def polyline(self, points, *, colour=None, width=None):
        points = (x * self.scaling for point in points for x in point)
        width = width or self.linewidth
        colour = self._colour(colour)
        self.canvas.create_line(*points, fill=colour, width=width)
    
    def box(self, dim, start=(0, 0), *, width=None):
        coords = tuple((x, o + x) for (x, o) in zip(start, dim))
        points = (x[i] * self.scaling for i in range(2) for x in coords)
        self.canvas.create_rectangle(*points, outline=self.colour)
    
    def circle(self, r, centre=(0, 0), *, colour=None):
        coords = tuple((o - r, o + r) for o in centre)
        points = (x[i] * self.scaling for i in range(2) for x in coords)
        self.canvas.create_oval(*points, fill=self._colour(colour), width=0)
    
    def polygon(self, points, *, colour=None):
        points = tuple(x * self.scaling for point in points for x in point)
        self.canvas.create_polygon(points, fill=self._colour(colour))
    
    def rectangle(self, dim, start=(0, 0)):
        coords = tuple((x, o + x) for (x, o) in zip(start, dim))
        points = (x[i] * self.scaling for i in range(2) for x in coords)
        self.canvas.create_rectangle(*points, fill=self.colour, width=0)
    
    def _colour(self, colour=None):
        if colour:
            colour = (min(int(x * 0x1000), 0xFFF) for x in colour)
            return "#" + "".join(map("{:03X}".format, colour))
        else:
            return self.colour
    
    def finish(self):
        tkinter.mainloop()
