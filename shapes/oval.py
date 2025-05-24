from typing import List, Dict, Optional, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from shapes.base_shape import Shape

class Oval(Shape):
    def __init__(self, sid, shape_type, coords, name, **kwargs): # shape_type is now passed from from_dict
        super().__init__(sid=sid, shape_type=shape_type, coords=coords, name=name, **kwargs)

    def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw]=None):
        if not self.coords or len(self.coords) < 4: return
        x1_outer, y1_outer, x2_outer, y2_outer = self.coords
        half_line_width = self.line_width / 2.0

        # Calculate coordinates for the inner ellipse bounding box
        # Inset from the outer boundary by half_line_width
        inset_x1 = min(x1_outer, x2_outer) + half_line_width
        inset_y1 = min(y1_outer, y2_outer) + half_line_width
        inset_x2 = max(x1_outer, x2_outer) - half_line_width
        inset_y2 = max(y1_outer, y2_outer) - half_line_width

        # Ensure inset coordinates are valid
        if inset_x1 > inset_x2: inset_x1, inset_x2 = inset_x2, inset_x1
        if inset_y1 > inset_y2: inset_y1, inset_y2 = inset_y2, inset_y1

        if canvas:
            # Tkinter oval uses bounding box corners
            canvas.create_oval(inset_x1, inset_y1, inset_x2, inset_y2,
                              outline=self.color, width=self.line_width, fill='')
        elif draw:
            # PIL ellipse uses bounding box [x0, y0, x1, y1] format
            draw.ellipse([inset_x1, inset_y1, inset_x2, inset_y2],
                         outline=self.color, width=self.line_width)

    def clip_image_to_geometry(self, pil_image: Image.Image) -> Image.Image:
        x1, y1, x2, y2 = self.get_bbox
        w, h = int(x2 - x1), int(y2 - y1)
        if w <= 0 or h <= 0: return Image.new('RGBA', (1,1))
        im = pil_image.convert('RGBA').resize((w, h), Image.Resampling.LANCZOS)
        mask = Image.new('L', (w, h), 0); mdraw = ImageDraw.Draw(mask); mdraw.ellipse([0, 0, w, h], fill=255); im.putalpha(mask)
        return im

    def contains_point(self, x: int, y: int) -> bool:
        # Check if point (x,y) is inside the ellipse using math
        x1, y1, x2, y2 = self.get_bbox
        center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
        radius_x, radius_y = abs(x2 - x1) / 2, abs(y2 - y1) / 2

        if radius_x == 0 or radius_y == 0: return False # Avoid division by zero

        # Equation of an ellipse: ((x - h)^2 / a^2) + ((y - k)^2 / b^2) <= 1
        # (h, k) is the center, (a, b) are the radii
        return ((x - center_x)**2 / radius_x**2) + ((y - center_y)**2 / radius_y**2) <= 1

