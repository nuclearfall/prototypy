from typing import List, Dict, Optional, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from shapes.base_shape import Shape

class Rectangle(Shape):
    def __init__(self, sid: Any, coords: List[int], name: str, **kwargs):
        super().__init__(sid=sid, shape_type='rectangle', coords=coords, name=name, **kwargs)

    def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw]=None):
        if not self.coords or len(self.coords) < 4: return
        x1_outer, y1_outer, x2_outer, y2_outer = self.coords
        half_line_width = self.line_width / 2.0

        # Calculate coordinates for the inner rectangle where the line should be drawn
        # Inset from the outer boundary by half_line_width
        inset_x1 = min(x1_outer, x2_outer) + half_line_width
        inset_y1 = min(y1_outer, y2_outer) + half_line_width
        inset_x2 = max(x1_outer, x2_outer) - half_line_width
        inset_y2 = max(y1_outer, y2_outer) - half_line_width

        # Ensure inset coordinates are valid for very thin shapes
        if inset_x1 > inset_x2: inset_x1, inset_x2 = inset_x2, inset_x1
        if inset_y1 > inset_y2: inset_y1, inset_y2 = inset_y2, inset_y1

        if canvas:
            # Tkinter rectangle uses top-left and bottom-right corners
            canvas.create_rectangle(inset_x1, inset_y1, inset_x2, inset_y2,
                                    outline=self.color, width=self.line_width, fill='')

        elif draw:
            # PIL rectangle uses [x0, y0, x1, y1] format
            draw.rectangle([inset_x1, inset_y1, inset_x2, inset_y2],
                           outline=self.color, width=self.line_width)

    def clip_image_to_geometry(self, pil_image: Image.Image) -> Image.Image:
        x1, y1, x2, y2 = self.get_bbox
        w, h = int(x2 - x1), int(y2 - y1)
        if w <= 0 or h <= 0: return Image.new('RGBA', (1,1))
        im = pil_image.convert('RGBA').resize((w, h), Image.Resampling.LANCZOS)
        mask = Image.new('L', (w, h), 0); mdraw = ImageDraw.Draw(mask); mdraw.rectangle([0,0,w,h], fill=255); im.putalpha(mask)
        return im

    def contains_point(self, x: int, y: int) -> bool:
        x1, y1, x2, y2 = self.get_bbox
        return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)
