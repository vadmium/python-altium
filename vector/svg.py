from xml.sax.saxutils import XMLGenerator
from contextlib import contextmanager
from . import base

class Renderer(base.Renderer):
    def __init__(self, size, line=0.4, colour="black"):
        self.svg = XMLGenerator(encoding="UTF-8", short_empty_elements=True)
        self.svg.startElement("svg", {
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "xmlns": "http://www.w3.org/2000/svg",
            "width": "{}mm".format(size[0]),
            "height": "{}mm".format(size[1]),
            "viewBox": "{},{} {},{}".format(0, 0, size[0], size[1]),
        })
        
        style = """
            /*.outline, path,*/ line/*, polyline*/ {{
                stroke: {colour};
                fill: none;
                stroke-width: {line};
            }}
            
            .solid {{
                fill: {colour};
                stroke: none;
            }}
        """
        style = style.format(line=line, colour=colour)
        tree(self.svg, (("style", dict(type="text/css"), (style,)),))
    
    def set_objects(self, objects):
        with element(self.svg, "defs", dict()):
            for d in objects:
                with element(self.svg, "g", dict(id=type(d).__name__)):
                    d.draw(self)
    
    def draw(self, object, offset):
        attrs = {"xlink:href": "#{}".format(type(object).__name__)}
        if offset:
            attrs.update(zip("xy", map(format, offset)))
        emptyElement(self.svg, "use", attrs)
    
    def line(self, *points):
        attrs = dict()
        for (n, p) in enumerate(points, 1):
            for (x, s) in zip(p, "xy"):
                attrs[s + format(n)] = format(x)
        emptyElement(self.svg, "line", attrs)
    
    def circle(self, r, point=None):
        attrs = {"r": format(r), "class": "solid"}
        if point:
            attrs.update(zip(("cx", "cy"), map(format, point)))
        emptyElement(self.svg, "circle", attrs)
    
    def polygon(self, points):
        points = " ".join(",".join(map(format, point)) for point in points)
        attrs = {"class": "solid", "points": points}
        emptyElement(self.svg, "polygon", attrs)
    
    def rectangle(self, dim, start=None):
        attrs = {"class": "solid"}
        attrs.update(zip(("width", "height"), map(format, dim)))
        if start:
            attrs.update(zip("xy", map(format, start)))
        emptyElement(self.svg, "rect", attrs)
    
    def finish(self):
        self.svg.endElement("svg")

@contextmanager
def element(xml, name, *pos, **kw):
    xml.startElement(name, *pos, **kw)
    yield
    xml.endElement(name)

def emptyElement(*pos, **kw):
    with element(*pos, **kw):
        pass

def tree(xml, elements):
    for e in elements:
        if isinstance(e, str):
            xml.characters(e)
        else:
            (name, attrs, children) = e
            with element(xml, name, attrs):
                tree(xml, children)
