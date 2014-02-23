import operator

class Renderer:
    def addobjects(self, objects):
        pass
    
    def draw(self, object, offset=None):
        object.draw(OffsetRenderer(self, offset))

class OffsetRenderer:
    def __init__(self, renderer, offset):
        self._renderer = renderer
        self._offset = offset
    
    def line(self, a=None, b=None, *pos, **kw):
        self._renderer.line(self._map(a), self._map(b), *pos, **kw)
    def circle(self, r, centre=None, *pos, **kw):
        self._renderer.circle(r, self._map(centre), *pos, **kw)
    def polygon(self, points, *pos, **kw):
        self._renderer.polygon(map(self._map, points), *pos, **kw)
    def rectangle(self, dim, start=None, *pos, **kw):
        self._renderer.rectangle(dim, self._map(start), *pos, **kw)
    
    def _map(self, point):
        if not self._offset:
            return point
        if not point:
            return self._offset
        return map(operator.add, point, self._offset)
