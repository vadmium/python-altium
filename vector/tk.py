from tkinter import Tk
import tkinter
from . import base
from tkinter.font import Font
from collections import Iterable
from math import sin, cos, radians
import tkinter.font

class Renderer(base.Renderer):
    def __init__(self, size, units, unitmult=1, *, margin=0,
    down=+1,  # -1 if y axis points upwards, not implemented
    line=1, textsize=10, textbottom=False):
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
        size = -round(size * self.scaling)
        self.fonts[id] = Font(name=id, family=family, size=size, **kw)
    
    def line(self, a, b=None, *, offset=(0, 0), **kw):
        (ox, oy) = offset
        if b is None:
            b = a
            a = (ox, oy)
        else:
            (ax, ay) = a
            a = (ox + ax, oy + ay)
        (bx, by) = b
        self.polyline((a, (ox + bx, oy + by)), **kw)
    
    def polyline(self, points, *,
    colour=None, width=None, startarrow=None, endarrow=None):
        tkpoints = list()
        for (x, y) in points:
            tkpoints.extend((x * self.scaling, y * self.scaling))
        width = width or self.linewidth
        colour = self._colour(colour)
        
        kw = dict()
        if startarrow:
            kw["arrow"] = tkinter.FIRST
            kw["arrowshape"] = (
                startarrow["base"] * self.scaling,
                startarrow["shoulder"] * self.scaling,
                (startarrow["radius"] - width / 2) * self.scaling,
            )
        if endarrow:
            kw["arrow"] = tkinter.LAST
            kw["arrowshape"] = (
                endarrow["base"] * self.scaling,
                endarrow["shoulder"] * self.scaling,
                (endarrow["radius"] - width / 2) * self.scaling,
            )
        if startarrow and endarrow:
            kw["arrow"] = tkinter.BOTH
        
        self.canvas.create_line(*tkpoints, fill=colour, width=width, **kw)
    
    def cubicbezier(self, a, b, c, d, *,
    offset=(0, 0), colour=None, width=None):
        (ox, oy) = offset
        points = list()
        for (x, y) in (a, b, c, d):
            points.extend(((ox + x) * self.scaling, (oy + y) * self.scaling))
        width = width or self.linewidth
        colour = self._colour(colour)
        self.canvas.create_line(*points, smooth="bezier",
            fill=colour, width=width)
    
    def circle(self, r, offset=(0, 0), *,
    outline=None, fill=None, width=None):
        coords = tuple((o - r, o + r) for o in offset)
        points = (x[i] * self.scaling for i in range(2) for x in coords)
        kw = self._closed(outline, fill, width)
        self.canvas.create_oval(*points, **kw)
    
    def polygon(self, points, *,
    offset=None, rotate=None, outline=None, fill=None, width=None):
        if rotate:
            (costh, sinth) = _rotation(rotate)
            points = ((x * costh - y * sinth, x * sinth + y * costh) for
                (x, y) in points)
        if offset:
            (ox, oy) = offset
            points = ((ox + x, oy + y) for (x, y) in points)
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
    angle=None, font=None, colour=None, width=None):
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
        
        kw = dict()
        if angle is not None:
            kw.update(angle=angle)
        if font is not None:
            kw.update(font=self.fonts[font])
        colour = self._colour(colour)
        kw.update(fill=colour)
        
        if isinstance(text, str):
            kw.update(anchor=anchors[(vert, horiz)])
            offset = (x * self.scaling for x in offset)
            if width is not None:
                kw.update(width=width * self.scaling)
            self.canvas.create_text(*offset, text=text, **kw)
            return
        
        font = kw.get("font") or tkinter.font.nametofont("TkDefaultFont")
        length = sum(font.measure(seg["text"]) for seg in text)
        anchor = anchors[(vert, self.LEFT)]
        anchors = {self.LEFT: 0, self.CENTRE: 0.5, self.RIGHT: 1}
        pos = -length * anchors[horiz]
        (ox, oy) = offset
        ox *= self.scaling
        oy *= self.scaling
        (cos, sin) = _rotation(angle or 0)
        for seg in text:
            x = ox + pos * cos
            y = oy + pos * sin
            text = seg["text"]
            self.canvas.create_text(x, y, text=text, anchor=anchor, **kw)
            newpos = pos + font.measure(text)
            
            if seg.get("overline"):
                linespace = font.metrics("linespace")
                anchors = {self.TOP: 0, self.CENTRE: 0.5, self.RIGHT: 1}
                linespace *= anchors[vert]
                dx = +linespace * sin
                dy = -linespace * cos
                nx = ox + dx + newpos * cos
                ny = oy + dy + newpos * sin
                self.canvas.create_line(x + dx, y + dy, nx, ny, fill=colour)
            
            pos = newpos
    
    def _colour(self, colour=None):
        if colour:
            colour = (min(int(x * 0x1000), 0xFFF) for x in colour)
            return "#" + "".join(map("{:03X}".format, colour))
        else:
            return self.colour
    
    def finish(self):
        tkinter.mainloop()

def _rotation(rotate):
    th = radians(rotate)
    return (cos(th), sin(th))
