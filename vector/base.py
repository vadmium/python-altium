import operator
from contextlib import contextmanager

class Renderer:
    def hline(self, a=None, b=None, y=None, *pos, **kw):
        for (name, x) in zip("ab", (a, b)):
            if x is not None or y is not None:
                kw[name] = (x or 0, y or 0)
        self.line(*pos, **kw)
    
    def vline(self, a=None, b=None, x=None, *pos, **kw):
        for (name, y) in zip("ab", (a, b)):
            if x is not None or y is not None:
                kw[name] = (x or 0, y or 0)
        self.line(*pos, **kw)
    
    def addobjects(self, objects):
        pass
    
    def draw(self, object, offset=None):
        with self.offset(offset) as offset:
            object.draw(offset)
    
    @contextmanager
    def offset(self, offset):
        yield OffsetRenderer(self, offset)
    
    CENTRE = 0

class OffsetRenderer:
    def __init__(self, renderer, offset):
        self._renderer = renderer
        self._offset = offset
    
    def line(self, a=None, b=None, *pos, **kw):
        self._renderer.line(self._map(a), self._map(b), *pos, **kw)
    
    def hline(self, a=None, b=None, y=None, *pos, **kw):
        if self._offset:
            a = (a or 0) + offset[0]
            b = (b or 0) + offset[0]
            y = (y or 0) + offset[1]
        self._renderer.hline(a, b, y, *pos, **kw)
    
    def vline(self, a=None, b=None, x=None, *pos, **kw):
        if self._offset:
            a = (a or 0) + offset[1]
            b = (b or 0) + offset[1]
            x = (x or 0) + offset[0]
        self._renderer.vline(a, b, x, *pos, **kw)
    
    def polygon(self, points, *pos, **kw):
        self._renderer.polygon(map(self._map, points), *pos, **kw)
    def polyline(self, points, *pos, **kw):
        self._renderer.polyline(map(self._map, points), *pos, **kw)
    def box(self, dim, start=None, *pos, **kw):
        self._renderer.box(dim, self._map(start), *pos, **kw)
    def circle(self, r, centre=None, *pos, **kw):
        self._renderer.circle(r, self._map(centre), *pos, **kw)
    def rectangle(self, dim, start=None, *pos, **kw):
        self._renderer.rectangle(dim, self._map(start), *pos, **kw)
    
    def _map(self, point):
        if not self._offset:
            return point
        if not point:
            return self._offset
        return map(operator.add, point, self._offset)
