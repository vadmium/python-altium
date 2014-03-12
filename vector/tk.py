from tkinter import Tk
import tkinter
from . import base
from tkinter.font import Font
from collections import Iterable

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
    
    def circle(self, r, offset=(0, 0), *,
    outline=None, fill=None, width=None):
        coords = tuple((o - r, o + r) for o in offset)
        points = (x[i] * self.scaling for i in range(2) for x in coords)
        kw = self._closed(outline, fill, width)
        self.canvas.create_oval(*points, **kw)
    
    def polygon(self, points, *, outline=None, fill=None, width=None):
        points = tuple(x * self.scaling for point in points for x in point)
        kw = self._closed(outline, fill, width)
        self.canvas.create_polygon(points, **kw)
    
    def rectangle(self, a, b=None, *, offset=(0, 0),
    outline=None, fill=None, width=None):
        if not b:
            b = a
            a = (0, 0)
        
        (ox, oy) = offset
        (ax, ay) = a
        (bx, by) = b
        coords = ((ox + ax, oy + ay), (ox + bx, oy + by))
        points = (x * self.scaling for p in coords for x in p)
        kw = self._closed(outline, fill, width)
        self.canvas.create_rectangle(*points, **kw)
    
    def _closed(self, outline=None, fill=None, width=None):
        kw = dict()
        if fill:
            if isinstance(fill, Iterable):
                kw.update(fill=self._colour(fill))
            else:
                kw.update(fill=self.colour)
            if outline:
                kw.update(width=width or self.linewidth)
            else:
                kw.update(width=0)
        if isinstance(outline, Iterable):
            kw.update(outline=self._colour(outline))
        return kw
    
    def text(self, text, offset=(0, 0),
    horiz=base.Renderer.LEFT, vert=base.Renderer.BOTTOM, *,
    angle=None, font=None, colour=None):
        kw = dict()
        if angle is not None:
            kw.update(angle=angle)
        anchors = {
            (self.TOP, self.LEFT): tkinter.NW,
            (self.TOP, self.CENTRE): tkinter.N,
            (self.TOP, self.RIGHT): tkinter.NE,
            (self.CENTRE, self.LEFT): tkinter.W,
            (self.CENTRE, self.CENTRE): tkinter.CENTER,
            (self.CENTRE, self.RIGHT): tkinter.E,
            (self.BOTTOM, self.LEFT): tkinter.SW,
            (self.BOTTOM, self.CENTRE): tkinter.S,
            (self.BOTTOM, self.RIGHT): tkinter.SE,
        }
        kw.update(anchor=anchors[(vert, horiz)])
        if font is not None:
            kw.update(font=self.fonts[font])
        colour = self._colour(colour)
        kw.update(fill=colour)
        offset = (x * self.scaling for x in offset)
        self.canvas.create_text(*offset, text=text, **kw)
    
    def _colour(self, colour=None):
        if colour:
            colour = (min(int(x * 0x1000), 0xFFF) for x in colour)
            return "#" + "".join(map("{:03X}".format, colour))
        else:
            return self.colour
    
    def finish(self):
        tkinter.mainloop()
