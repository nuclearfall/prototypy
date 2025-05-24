from typing import List, Dict, Optional, Any, Tuple
import math
from PIL import Image, ImageDraw, ImageFont
from shapes.base_shape import Shape

class Triangle(Shape):
    def __init__(self, sid, shape_type, coords, name, **kwargs): # shape_type is now passed from from_dict
        super().__init__(sid=sid, shape_type=shape_type, coords=coords, name=name, **kwargs)

    def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw]=None):
            if not self.coords or len(self.coords) < 4: return
            x1_outer, y1_outer, x2_outer, y2_outer = self.coords
            half_line_width = self.line_width / 2.0

            # Calculate outer vertices based on the bounding box
            base_y_outer = max(y1_outer, y2_outer)
            apex_y_outer = min(y1_outer, y2_outer)
            left_x_outer = min(x1_outer, x2_outer)
            right_x_outer = max(x1_outer, x2_outer)
            center_x_outer = (left_x_outer + right_x_outer) / 2

            outer_pts = [(left_x_outer, base_y_outer), (center_x_outer, apex_y_outer), (right_x_outer, base_y_outer)]

            # Calculate center of the outer bounding box for scaling towards center
            bbox_center_x = (left_x_outer + right_x_outer) / 2
            bbox_center_y = (apex_y_outer + base_y_outer) / 2

            inner_pts_flat = [] # Use a flat list for Tkinter
            inner_pts_pil = [] # Use a list of tuples for PIL

            # Calculate inner vertices by moving outer vertices towards the center
            for ox, oy in outer_pts:
                # Vector from center to outer vertex
                vx, vy = ox - bbox_center_x, oy - bbox_center_y
                dist = math.sqrt(vx**2 + vy**2)

                if dist > 0:
                    # Normalize the vector and move inwards by half_line_width
                    nx, ny = vx / dist, vy / dist
                    ix = ox - nx * half_line_width
                    iy = oy - ny * half_line_width
                else: # Handle the case where the vertex is at the center (shouldn't happen for a triangle)
                     ix, iy = ox, oy

                inner_pts_flat.extend([ix, iy])
                inner_pts_pil.append((ix, iy))

            if canvas:
                canvas.create_polygon(inner_pts_flat, outline=self.color, width=self.line_width, fill='')
            elif draw:
                draw.polygon(inner_pts_pil, outline=self.color, width=self.line_width)

    def clip_image_to_geometry(self, pil_image: Image.Image) -> Image.Image:
        x1, y1, x2, y2 = self.get_bbox
        w, h = int(x2 - x1), int(y2 - y1)
        if w <= 0 or h <= 0: return Image.new('RGBA', (1,1))
        im = pil_image.convert('RGBA').resize((w, h), Image.Resampling.LANCZOS)
        mask = Image.new('L', (w, h), 0); mdraw = ImageDraw.Draw(mask)
        mask_pts = [(0, h), (w/2, 0), (w, h)]; mdraw.polygon(mask_pts, fill=255); im.putalpha(mask)
        return im

    def contains_point(self, x: int, y: int) -> bool:
        # Get actual triangle vertices from coords
        x1, y1, x2, y2 = self.coords
        base_y = max(y1, y2)
        apex_y = min(y1, y2)
        left_x = min(x1, x2)
        right_x = max(x1, x2)
        center_x = (left_x + right_x) / 2  # Precise center

        # Check if point is within bounding box
        if not (left_x <= x <= right_x and apex_y <= y <= base_y):
            return False

        # Determine which edge to check based on X position
        if x <= center_x:
            # Check against left edge (left_x, base_y) to (center_x, apex_y)
            if center_x == left_x:
                return True  # Vertical line
            slope = (apex_y - base_y) / (center_x - left_x)
            edge_y = slope * (x - left_x) + base_y
        else:
            # Check against right edge (center_x, apex_y) to (right_x, base_y)
            if right_x == center_x:
                return True  # Vertical line
            slope = (base_y - apex_y) / (right_x - center_x)
            edge_y = slope * (x - center_x) + apex_y

        # Point is valid if below the edge line (triangle interior)
        return y >= edge_y