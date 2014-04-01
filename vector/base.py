import operator
from contextlib import contextmanager
from collections import Iterable

class Renderer:
    def start(self):
        pass
    
    def hline(self, a, b=None, **kw):
        if b is not None:
            kw.update(b=(b, 0))
        self.line((a, 0), **kw)
    
    def vline(self, a, b=None, **kw):
        if b is not None:
            kw.update(b=(0, b))
        self.line((0, a), **kw)
    
    def roundrect(self, r, a, b=None, *, offset=None,
    fill=None, outline=None, **kw):
        if not all(r):
            return self.rectangle(a, b,
                offset=offset, fill=fill, outline=outline, **kw)
        
        if b:
            (ax, ay) = a
            (bx, by) = b
        else:
            (ax, ay) = (0, 0)
            (bx, by) = a
        
        # Only positive dimensions are considered
        (rx, ry) = r
        cax = ax + rx
        cay = ay + ry
        cbx = bx - rx
        cby = by - ry
        
        with self.view(offset=offset):
            # TODO: circles not good enough if fill=None; need arcs
            c0 = (cax, cay)
            self.circle(r, c0, fill=fill, outline=outline, **kw)
            c = (cbx, cay)
            if c != c0:
                self.circle(r, c, fill=fill, outline=outline, **kw)
            c = (cax, cby)
            if c != c0:
                self.circle(r, c, fill=fill, outline=outline, **kw)
            c = (cbx, cby)
            if c != c0:
                self.circle(r, c, fill=fill, outline=outline, **kw)
            
            if cby != cay:
                if fill:
                    self.rectangle((ax, cay), (bx, cby), fill=fill)
                if outline or not fill:
                    self.vline(cay, cby, offset=(ax, 0), colour=outline)
                    self.vline(cay, cby, offset=(bx, 0), colour=outline)
            if cbx != cax:
                if fill:
                    self.rectangle((cax, ay), (cbx, by), fill=fill)
                if outline or not fill:
                    self.hline(cax, cbx, offset=(0, ay), colour=outline)
                    self.hline(cax, cbx, offset=(0, by), colour=outline)
    
    def addobjects(self, objects=(), arrows=()):
        pass
    
    def draw(self, object, offset=None):
        with self.view(offset=offset) as view:
            object.draw(view)
    
    @contextmanager
    def view(self, **kw):
        yield View(self, **kw)
    
    # Values such that:
    # * Text aligned at point (align_x, align_y) is
    #     inside a double unit square square, aligned to adjacent edges,
    #     and is centred between pairs of distant edges
    # * Negating an alignment value
    #     mirrors between left and right, and top and bottom
    # * An alignment is considered false precisely if it is centred
    CENTRE = 0
    LEFT = -1
    RIGHT = +1
    TOP = -1
    BOTTOM = +1
    
    START = 1 << 0
    END = 1 << 1

class View:
    def __init__(self, renderer, *, offset=None, rotate=None, colour=None):
        self._renderer = renderer
        self._offset = offset
        self._rotatearg = rotate
        self._colour = colour
        self._rotation = self._rotatearg or 0
    
    def line(self, *pos, offset=None, colour=None, **kw):
        pos = map(self._rotate, pos)
        offset = self._map(offset)
        colour = colour or self._colour
        return self._renderer.line(*pos, offset=offset, colour=colour, **kw)
    
    def hline(self, *pos, offset=None, colour=None, **kw):
        offset = self._map(offset)
        colour = colour or self._colour
        if self._rotation & 2:
            pos = map(operator.neg, pos)  # Rotate by 180 degrees
        if self._rotation & 1:
            method = self._renderer.vline  # Rotate by 90 degrees
        else:
            method = self._renderer.hline
        return method(*pos, offset=offset, colour=colour, **kw)
    
    def vline(self, *pos, offset=None, colour=None, **kw):
        offset = self._map(offset)
        colour = colour or self._colour
        if self._rotation + 1 & 2:
            pos = map(operator.neg, pos)  # Rotate by 180 degrees
        if self._rotation + 1 & 1:
            method = self._renderer.vline
        else:
            method = self._renderer.hline  # Rotate by -90 degrees
        return method(*pos, offset=self._map(offset), colour=colour, **kw)
    
    def polygon(self, *pos, offset=None, rotate=None, **kw):
        self._closed(kw)
        if rotate is None:
            rotate = self._rotatearg
        else:
            rotate += self._rotation
        return self._renderer.polygon(*pos,
            offset=self._map(offset),
            rotate=rotate,
        **kw)
    
    def polyline(self, points, *pos, colour=None, **kw):
        points = map(self._map, points)
        colour = colour or self._colour
        return self._renderer.polyline(points, *pos, colour=colour, **kw)
    def circle(self, r, offset=None, *pos, **kw):
        self._closed(kw)
        return self._renderer.circle(r, self._map(offset), *pos, **kw)
    def rectangle(self, *pos, offset=None, **kw):
        pos = map(self._rotate, pos)
        self._closed(kw)
        return self._renderer.rectangle(*pos, offset=self._map(offset), **kw)
    
    def _map(self, point):
        if not point:
            return self._offset
        point = self._rotate(point)
        if not self._offset:
            return point
        return map(operator.add, point, self._offset)
    
    def _rotate(self, point):
        if self._rotation & 2:
            point = map(operator.neg, point)  # Rotate by 180 degrees
        if self._rotation & 1:
            (x, y) = point
            point = (-y, +x)  # Rotate by 90 degrees
        return point
    
    def _closed(self, kw):
        if self._colour:
            for param in ("fill", "outline"):
                if kw.get(param) and not isinstance(kw[param], Iterable):
                    kw[param] = self._colour
