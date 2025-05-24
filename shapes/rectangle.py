from typing import List, Dict, Optional, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from shapes.base_shape import Shape

class Rectangle(Shape):
    def __init__(self, sid, shape_type, coords, name, **kwargs): # shape_type is now passed from from_dict
        super().__init__(sid=sid, shape_type=shape_type, coords=coords, name=name, **kwargs)

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
            # Corrected: draw is the drawing context, use draw.rectangle()
            draw.rectangle([inset_x1, inset_y1, inset_x2, inset_y2],
                           outline=self.color, width=self.line_width)

    def clip_image_to_geometry(self, pil_image: Image.Image) -> Image.Image:
        # Always ensure the input image is RGBA
        im_rgba = pil_image.convert('RGBA')

        # If it's a text container, or if clipping is not desired for image containers,
        # return the image as is, preserving its original alpha channel.
        if self.container_type == 'Text' or (self.container_type == 'Image' and not self.clip_image):
            return im_rgba

        # For image containers where clipping is enabled:
        x1, y1, x2, y2 = self.get_bbox
        w, h = int(x2 - x1), int(y2 - y1)
        if w <= 0 or h <= 0:
            # Return a tiny transparent image if dimensions are invalid
            return Image.new('RGBA', (1,1), (0,0,0,0)) 

        # Resize the image to the shape's bounding box
        im_resized = im_rgba.resize((w, h), Image.Resampling.LANCZOS)

        # Create a mask for the rectangular shape.
        # The mask should be white (255) where the image content should be visible,
        # and black (0) where it should be transparent.
        mask = Image.new('L', (w, h), 0) # Initialize with black (transparent)
        mdraw = ImageDraw.Draw(mask)
        mdraw.rectangle([0,0,w,h], fill=255) # Draw an opaque rectangle over the entire mask area

        # Apply the mask. This will make areas *outside* the rectangle transparent,
        # but since the mask itself is a solid rectangle, it effectively makes the
        # entire `im_resized` opaque within the rectangle. This is the intended
        # behavior for clipping an image to a solid rectangular shape.
        im_resized.putalpha(mask)
        return im_resized

    def contains_point(self, x: int, y: int) -> bool:
        x1, y1, x2, y2 = self.get_bbox
        return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)

