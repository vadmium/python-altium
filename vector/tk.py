from tkinter import Tk
import tkinter
from . import base

class Renderer(base.Renderer):
    def __init__(self, size, line=0.4, colour="black"):
        self.colour = colour
        
        root = Tk()
        self.scaling = root.call("tk", "scaling") * 72 / 25.4  # pixels/mm
        self.linewidth = line * self.scaling
        self.canvas = tkinter.Canvas(root,
            relief=tkinter.SUNKEN, borderwidth=1,
            background="white",
            height=size[1] * self.scaling, width=size[0] * self.scaling,
        )
        self.canvas.pack(fill=tkinter.BOTH, expand=True)
    
    def line(self, a=(0, 0), b=(0, 0), *pos, **kw):
        self.polyline(a, b, *pos, **kw)
    
    def polyline(self, points, *, width=None):
        points = (x * self.scaling for point in points for x in point)
        width = width or self.linewidth
        self.canvas.create_line(*points, fill=self.colour, width=width)
    
    def box(self, dim, start=(0, 0), *, width=None):
        coords = tuple((x, o + x) for (x, o) in zip(start, dim))
        points = (x[i] * self.scaling for i in range(2) for x in coords)
        self.canvas.create_rectangle(*points, outline=self.colour)
    
    def circle(self, r, centre=(0, 0)):
        coords = tuple((o - r, o + r) for o in centre)
        points = (x[i] * self.scaling for i in range(2) for x in coords)
        self.canvas.create_oval(*points, fill=self.colour, width=0)
    
    def polygon(self, points):
        points = tuple(x * self.scaling for point in points for x in point)
        self.canvas.create_polygon(points)
    
    def rectangle(self, dim, start=(0, 0)):
        coords = tuple((x, o + x) for (x, o) in zip(start, dim))
        points = (x[i] * self.scaling for i in range(2) for x in coords)
        self.canvas.create_rectangle(*points, fill=self.colour, width=0)
    
    def finish(self):
        tkinter.mainloop()
