from typing import List, Dict, Optional, Any, Tuple
import math
from PIL import Image, ImageDraw, ImageFont
from shapes.base_shape import Shape

class Hexagon(Shape):
    def __init__(self, sid, shape_type, coords, name, **kwargs): # shape_type is now passed from from_dict
        super().__init__(sid=sid, shape_type=shape_type, coords=coords, name=name, **kwargs)

    def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw]=None):
            if not self.coords or len(self.coords) < 4:
                print(f"Hexagon ID {self.sid}: Invalid coords: {self.coords}")
                return

            x1_outer, y1_outer, x2_outer, y2_outer = self.coords
            half_line_width = self.line_width / 2.0

            # Calculate outer bounding box center for scaling towards center
            bbox_center_x = (x1_outer + x2_outer) / 2
            bbox_center_y = (y1_outer + y2_outer) / 2
            width_outer = abs(x2_outer - x1_outer)
            height_outer = abs(y2_outer - y1_outer)


            outer_pts = []
            # Calculate outer vertices
            for i in range(6):
                angle_deg = 60 * i - 30
                angle_rad = math.radians(angle_deg)
                ox = bbox_center_x + (width_outer/2) * math.cos(angle_rad)
                oy = bbox_center_y + (height_outer/2) * math.sin(angle_rad)
                outer_pts.append((ox, oy))


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
                else: # Handle the case where the vertex is at the center (shouldn't happen for a hexagon)
                     ix, iy = ox, oy

                inner_pts_flat.extend([ix, iy])
                inner_pts_pil.append((ix, iy))


            tags = ('shape', f'id{self.sid}')

            if canvas:
                canvas.create_polygon(inner_pts_flat, outline=self.color,
                                    width=self.line_width, fill='', tags=tags)

            elif draw:
                draw.polygon(inner_pts_pil, outline=self.color, width=self.line_width)

    def clip_image_to_geometry(self, pil_image: Image.Image) -> Image.Image:
        x1, y1, x2, y2 = self.get_bbox
        w, h = int(x2 - x1), int(y2 - y1)
        if w <= 0 or h <= 0: return Image.new('RGBA', (1,1))
        
        # Create hexagonal mask
        mask = Image.new('L', (w, h), 0)
        mdraw = ImageDraw.Draw(mask)
        
        center_x, center_y = w/2, h/2
        points = []
        for i in range(6):
            angle_deg = 60 * i - 30
            angle_rad = math.pi / 180 * angle_deg
            x = center_x + w/2 * math.cos(angle_rad)
            y = center_y + h/2 * math.sin(angle_rad)
            points.append((x, y))
            
        mdraw.polygon(points, fill=255)
        
        im = pil_image.convert('RGBA').resize((w, h), Image.Resampling.LANCZOS)
        im.putalpha(mask)
        return im

    def contains_point(self, x: int, y: int) -> bool:
        x1, y1, x2, y2 = self.get_bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        
        # Transform point to hexagon coordinate space
        dx = (x - center_x) / (width/2) if width != 0 else 0
        dy = (y - center_y) / (height/2) if height != 0 else 0
        
        # Check if point is inside hexagon using cross product
        for i in range(6):
            angle1 = math.radians(60 * i - 30)
            angle2 = math.radians(60 * (i + 1) - 30)
            
            x1_hex = math.cos(angle1)
            y1_hex = math.sin(angle1)
            x2_hex = math.cos(angle2)
            y2_hex = math.sin(angle2)
            
            # Calculate edge equation using AP × AB instead of AB × AP
            edge = (dx - x1_hex) * (y2_hex - y1_hex) - (dy - y1_hex) * (x2_hex - x1_hex)
            if edge > 0:
                return False
                
        return True