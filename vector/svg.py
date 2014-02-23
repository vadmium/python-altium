from xml.sax.saxutils import XMLGenerator
from contextlib import contextmanager
from . import base

class Renderer(base.Renderer):
    def __init__(self, size, units, unitmult=1, *, margin=0,
    down=+1,  # -1 if y axis points upwards
    line=None):
        width = size[0] + 2 * margin
        height = size[1] + 2 * margin
        if down < 0:
            top = -size[1]
            self.flip = (+1, -1)
        else:
            top = 0
            self.flip = (+1, +1)
        viewbox = "{},{} {},{}".format(-margin, top - margin, width, height)
        
        self.xml = XMLGenerator(encoding="UTF-8", short_empty_elements=True)
        self.xml.startElement("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "width": "{}{}".format(width * unitmult, units),
            "height": "{}{}".format(height * unitmult, units),
            "viewBox": viewbox,
        })
        
        outline = ["stroke: currentColor", "fill: none"]
        if line is not None:
            outline.append("stroke-width: {}".format(line))
        
        rulesets = (
            (".outline, path, line, polyline", outline),
            (".solid", ("fill: currentColor", "stroke: none")),
        )
        
        css = list()
        for (selector, rules) in rulesets:
            rules = "".join(map("  {};\n".format, rules))
            css.append("{} {{\n{}}}\n".format(selector, rules))
        self.tree(("style", dict(type="text/css"), css))
    
    def set_objects(self, objects):
        with self.element("defs", dict()):
            for d in objects:
                with self.element("g", dict(id=type(d).__name__)):
                    d.draw(self)
    
    def draw(self, object, offset):
        attrs = {"xlink:href": "#{}".format(type(object).__name__)}
        if offset:
            attrs.update(zip("xy", map(format, offset)))
        self.emptyelement("use", attrs)
    
    def line(self, a=None, b=None):
        attrs = dict()
        for (n, p) in enumerate((a, b), 1):
            if p:
                (x, y) = p
                attrs["x{}".format(n)] = format(x)
                attrs["y{}".format(n)] = format(y * self.flip[1])
        self.emptyelement("line", attrs)
    
    def circle(self, r, point=None):
        attrs = {"r": format(r), "class": "solid"}
        if point:
            (x, y) = point
            attrs["cx"] = format(x)
            attrs["cy"] = format(y * self.flip[1])
        self.emptyelement("circle", attrs)
    
    def polygon(self, points):
        s = list()
        for (x, y) in points:
            s.append("{},{}".format(x, y * self.flip[1]))
        attrs = {"class": "solid", "points": " ".join(s)}
        self.emptyelement("polygon", attrs)
    
    def rectangle(self, dim, start=None):
        attrs = {"class": "solid"}
        attrs.update(zip(("width", "height"), map(format, dim)))
        if start:
            attrs.update(zip("xy", map(format, start)))
        self.emptyelement("rect", attrs)
    
    def finish(self):
        self.xml.endElement("svg")
    
    @contextmanager
    def element(self, name, *pos, **kw):
        self.xml.startElement(name, *pos, **kw)
        yield
        self.xml.endElement(name)
    
    def emptyelement(self, *pos, **kw):
        with self.element(*pos, **kw):
            pass
    
    def tree(self, *elements):
        for e in elements:
            if isinstance(e, str):
                self.xml.characters(e)
            else:
                (name, attrs, children) = e
                with self.element(name, attrs):
                    self.tree(*children)
