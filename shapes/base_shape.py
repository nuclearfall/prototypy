# shapes/base_shape.py

import math
import textwrap
from typing import List, Dict, Optional, Any, Tuple
from PIL import Image, ImageDraw, ImageFont # Ensure ImageFont is here
import tkinter as tk # Needed for tk.Canvas type hint
import tkinter.font as tkFont # Needed for tkFont.Font type hint

from utils.font_manager import FontManager # Still need FontManager type hint and class access
from utils.geometry import _update_coords_if_valid # If used directly in Shape
from constants import CONTAINER_TYPES, SHAPE_TYPES # Example

class Shape:
    # Make these instance methods so they can access self.font_manager
    def get_font_names(self) -> List[str]:
        if self.font_manager:
            return self.font_manager.get_families()
        return []

    def get_font_weights(self, family: str) -> List[str]:
        if self.font_manager:
            return self.font_manager.get_weights_for_family(family)
        return []

    @property
    def property_spec(self) -> Dict[str, Any]: # 'self' is the instance here, not 'cls'
        """Dynamically populate property_spec with font names and weights"""
        # Ensure font_name is accessible for Font Weight lambda
        # Use a fallback if font_name isn't set yet (e.g., during initialization)
        current_font_name = getattr(self, 'font_name', None)
        if not current_font_name and self.get_font_names():
            current_font_name = self.get_font_names()[0]

        return {
            "ID": {"type": "str", "editable": False}, # Not directly editable by user, but good to list
            "Shape Type": {"type": "str", "editable": False}, # Not directly editable via prop panel
            "Name": {"type": "str"},
            "X": {"type": "float"},
            "Y": {"type": "float"},
            "Width": {"type": "float"},
            "Height": {"type": "float"},
            "Container Type": {"type": "enum", "values": ["Text", "Image", "None"]}, # Added "None" option
            "Text": {"type": "str", "editable": True}, # Property for text content
            "Path": {"type": "str", "editable": True}, # Property for image path
            "Color": {"type": "str"},
            "Line Width": {"type": "int"},
            "Clip Image": {"type": "bool"},

            "Font Name": {
                "type": "enum", 
                "values": self.get_font_names()  # Call instance method
            },
            "Font Size": {"type": "int"},
            "Font Weight": {
                "type": "enum", 
                "values": (
                    self.get_font_weights(current_font_name) if current_font_name else []
                )
            },
            "Justification": {"type": "enum", "values": ["left", "right", "center"]},
            "Vertical Justification": {"type": "enum", "values": ["top", "center", "bottom"]}
        }

    def __init__(self, sid: Any, shape_type: str, coords: List[int], name: str, font_manager=None, **kwargs):
        self.font_manager = font_manager
        
        self.sid = sid
        self.shape_type = shape_type
        self.coords = coords
        self.name = name

        # Initialize properties that can be derived from coords or explicitly passed
        self.init_coords(*coords) # This sets self.x, self.y, self.width, self.height

        self.line_width: int = kwargs.get('line_width', 1)
        self.container_type: str = kwargs.get('container_type', 'Text')
        self.content: Optional[Any] = None # Rendered content (PIL Image for images/text)
        self.color: str = kwargs.get('color', 'black')
        self.clip_image: bool = kwargs.get('clip_image', True)
        self.path = kwargs.get('path', '') # For image shapes
        self.text = kwargs.get('text', '') # For text shapes

        # Font properties
        self.font_name = kwargs.get("font_name", "Arial Unicode")
        self.font_size = kwargs.get("font_size", 12)
        self.font_weight = kwargs.get("font_weight", "normal")
        self.font_slant = kwargs.get("font_slant", "roman") # Ensure font_slant is initialized
        self.justification = kwargs.get("justification", "left")
        self.vertical_justification = kwargs.get("vertical_justification", "top") # Add vertical justification

        # Load content if it's an image or text container and data is present
        if self.container_type == 'Text' and self.text:
            # When initializing, we want to create the PIL content first for later use (e.g., clipping)
            # Use a default DPI (e.g., 300) for initial PIL text rendering
            self._draw_text_content(draw_pil=True, render_dpi=300) 
        elif self.container_type == 'Image' and self.path:
            self._load_image_content()

    @property
    def x(self) -> float:
        """Returns the x-coordinate (left edge) of the shape's outer boundary."""
        return self.coords[0]

    @property
    def y(self) -> float:
        """Returns the y-coordinate (top edge) of the shape's outer boundary."""
        return self.coords[1]

    @property
    def width(self) -> float:
        """Returns the width of the shape's outer boundary."""
        return self.coords[2] - self.coords[0]

    @property
    def height(self) -> float:
        """Returns the height of the shape's outer boundary."""
        return self.coords[3] - self.coords[1]

    def set_name(self, new_name: str):
        self.name = new_name.strip()
        print(f"Shape {self.sid}: Name changed to {self.name}")

    def set_x(self, new_x: float):
        """Sets the x-coordinate (left edge) of the shape's outer boundary."""
        x0, y0, x1, y1 = self.get_bbox
        width = x1 - x0
        new_x = max(0, new_x) # Ensure x is not negative
        self.set_coords(new_x, y0, new_x + width, y1)

    def set_y(self, new_y: float):
        """Sets the y-coordinate (top edge) of the shape's outer boundary."""
        x0, y0, x1, y1 = self.get_bbox
        height = y1 - y0
        new_y = max(0, new_y) # Ensure y is not negative
        self.set_coords(x0, new_y, x1, new_y + height)

    def set_width(self, new_width: float):
        """Sets the width of the shape, adjusting x1."""
        x0, y0, x1, y1 = self.get_bbox
        new_width = max(1, new_width) # Ensure width is at least 1
        self.set_coords(x0, y0, x0 + new_width, y1)

    def set_height(self, new_height: float):
        """Sets the height of the shape, adjusting y1."""
        x0, y0, x1, y1 = self.get_bbox
        new_height = max(1, new_height) # Ensure height is at least 1
        self.set_coords(x0, y0, x1, y0 + new_height)

    def set_color(self, new_color: str):
        self.color = new_color
        # self.model.notify_observers() # Model should notify

    def set_line_width(self, new_line_width: int):
        self.line_width = max(0, new_line_width)
        # self.model.notify_observers() # Model should notify

    def set_container_type(self, container_type: str):
        if container_type in ["Text", "Image", "None"]:
            self.container_type = container_type
            if container_type == "Text":
                self.path = "" # Clear path if changing to text
                self._draw_text_content(draw_pil=True, render_dpi=300) # Re-render text content as PIL
            elif container_type == "Image":
                self.text = "" # Clear text if changing to image
                self._load_image_content() # Attempt to load image content
            else: # "None" or other
                self.content = None # Clear content
        else:
            print(f"Invalid container type: {container_type}")
        # self.model.notify_observers() # Model should notify

    def set_text(self, new_text: str):
        self.text = new_text
        if self.container_type == 'Text':
            self._draw_text_content(draw_pil=True, render_dpi=300) # Regenerate content as PIL
        # self.model.notify_observers() # Model should notify

    def set_path(self, new_path: str):
        self.path = new_path
        if self.container_type == 'Image':
            self._load_image_content() # Attempt to load new image
        # self.model.notify_observers() # Model should notify

    def set_font_name(self, new_font_name: str):
        if self.font_manager and new_font_name in self.font_manager.get_families():
            self.font_name = new_font_name
            if self.container_type == 'Text':
                self._draw_text_content(draw_pil=True, render_dpi=300) # Regenerate text content
        # self.model.notify_observers() # Model should notify

    def set_font_size(self, new_font_size: int):
        new_font_size = max(1, new_font_size) # Ensure font size is at least 1
        self.font_size = new_font_size
        if self.container_type == 'Text':
            self._draw_text_content(draw_pil=True, render_dpi=300) # Regenerate text content
        # self.model.notify_observers() # Model should notify

    def set_font_weight(self, new_font_weight: str):
        if self.font_manager and new_font_weight in self.font_manager.get_weights_for_family(self.font_name):
            self.font_weight = new_font_weight
            if self.container_type == 'Text':
                self._draw_text_content(draw_pil=True, render_dpi=300) # Regenerate text content
        # self.model.notify_observers() # Model should notify


    def set_justification(self, new_justification: str):
        if new_justification in ["left", "right", "center"]:
            self.justification = new_justification
            if self.container_type == 'Text':
                self._draw_text_content(draw_pil=True, render_dpi=300) # Regenerate text content
        # self.model.notify_observers() # Model should notify

    def set_vertical_justification(self, new_vertical_justification: str):
        if new_vertical_justification in ["top", "center", "bottom"]:
            self.vertical_justification = new_vertical_justification
            if self.container_type == 'Text':
                self._draw_text_content(draw_pil=True, render_dpi=300) # Regenerate text content
        # self.model.notify_observers() # Model should notify

    def init_coords(self, x0, y0, x1, y1):
        self.coords = [x0, y0, x1, y1]

    def set_coords(self, x0, y0, x1, y1):
        """Sets the shape's coordinates."""
        self.coords = [x0, y0, x1, y1]

    @property
    def get_bbox(self) -> Tuple[int, int, int, int]:
        """Returns the bounding box (x0, y0, x1, y1) in integer coordinates."""
        x0, y0, x1, y1 = self.coords
        # Ensure x0,y0 are top-left, x1,y1 are bottom-right
        min_x = min(x0, x1)
        max_x = max(x0, x1)
        min_y = min(y0, y1)
        max_y = max(y0, y1)
        return int(min_x), int(min_y), int(max_x), int(max_y)

    def move(self, dx: int, dy: int):
        """Moves the shape by dx, dy."""
        x0, y0, x1, y1 = self.coords
        self.set_coords(x0 + dx, y0 + dy, x1 + dx, y1 + dy)

    def resize(self, handle: str, dx: int, dy: int):
        """Resizes the shape based on the drag handle and delta."""
        x0, y0, x1, y1 = self.coords

        # Store original coordinates for calculations
        original_x0, original_y0, original_x1, original_y1 = x0, y0, x1, y1

        # Calculate new coordinates based on handle
        if 'n' in handle: y0 += dy
        if 's' in handle: y1 += dy
        if 'w' in handle: x0 += dx
        if 'e' in handle: x1 += dx

        # Ensure minimum size (e.g., 10x10 pixels)
        min_size = 10
        if abs(x1 - x0) < min_size:
            if 'w' in handle: x0 = original_x0 # Prevent resizing past minimum
            else: x1 = original_x1
        if abs(y1 - y0) < min_size:
            if 'n' in handle: y0 = original_y0
            else: y1 = original_y1

        self.set_coords(x0, y0, x1, y1)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Shape instance to a dictionary."""
        return {
            'sid': self.sid,
            'shape_type': self.shape_type,
            'coords': self.coords,
            'name': self.name,
            'line_width': self.line_width,
            'container_type': self.container_type,
            'color': self.color,
            'clip_image': self.clip_image,
            'path': self.path,
            'text': self.text,
            'font_name': self.font_name,
            'font_size': self.font_size,
            'font_weight': self.font_weight,
            'justification': self.justification,
            'vertical_justification': self.vertical_justification,
            # content is not serialized, as it's a runtime PIL Image object
        }

    @staticmethod
    def from_dict(data: Dict[str, Any], font_manager: FontManager):
        """Factory method to create a Shape instance from a dictionary."""
        sid = data.get('sid')
        shape_type = data.get('shape_type')
        coords = data.get('coords')
        name = data.get('name')

        if sid is None or shape_type is None or coords is None or name is None:
            print(f"Shape.from_dict: Missing essential data for shape creation: {data}")
            return None

        # Select the correct subclass based on shape_type
        # Make sure you have imported the subclass definitions *after* the Shape class definition
        shape_class = {
            'rectangle': Rectangle,
            'oval': Oval,
            'triangle': Triangle,
            'hexagon': Hexagon,
        }.get(shape_type.lower()) # Ensure case-insensitivity

        if not shape_class:
            print(f"Shape.from_dict: Unknown shape type: {shape_type}")
            return None

        try:
            # Pass all relevant data to the constructor of the specific shape class
            # The specific shape class will then call Shape.__init__ with kwargs
            shape_instance = shape_class(
                sid=sid,
                shape_type=shape_type,
                coords=coords,
                name=name,
                font_manager=font_manager, # Pass font_manager
                line_width=data.get('line_width', 1),
                container_type=data.get('container_type', 'Text'),
                color=data.get('color', 'black'),
                clip_image=data.get('clip_image', True),
                path=data.get('path', ''),
                text=data.get('text', ''),
                font_name=data.get('font_name', 'Arial Unicode'),
                font_size=data.get('font_size', 12),
                font_weight=data.get('font_weight', 'regular'),
                justification=data.get('justification', 'left'),
                vertical_justification=data.get('vertical_justification', 'top')
            )

            # After creation, regenerate content using the loaded properties and the font_manager
            # Always generate PIL content when loading from dict for consistency with clipping
            if shape_instance.container_type == 'Text' and shape_instance.text:
                 # Use a default DPI (e.g., 300) for initial PIL text rendering
                 shape_instance._draw_text_content(draw_pil=True, render_dpi=300)
            elif shape_instance.container_type == 'Image' and shape_instance.path:
                 shape_instance._load_image_content()

            print(f"Shape.from_dict: Created shape ID {shape_instance.sid} of type '{shape_type}'")
            return shape_instance

        except Exception as e:
            print(f"Shape.from_dict: Error creating shape instance from data {data}: {e}")
            import traceback
            traceback.print_exc()
            return None # Handle errors during instance creation


    def _draw_text_content(self, canvas: Optional[tk.Canvas] = None, draw_pil: bool = False, render_dpi: int = 72):
        """
        Renders the text content either directly to a Tkinter Canvas (if `canvas` is provided
        and `draw_pil` is False) or into a PIL Image (otherwise).
        The text is word-wrapped and justified within the shape's bounding box.

        Args:
            canvas (tkinter.Canvas, optional): If provided and `draw_pil` is False,
                                              text will be drawn directly onto this Tkinter Canvas.
            draw_pil (bool): If True, forces PIL rendering to `self.content`.
                             If False and `canvas` is a Tkinter.Canvas, draws to the Tkinter canvas.
            render_dpi (int): The DPI to use when rendering text to a PIL image. Higher values
                              result in sharper text, especially for PDF export.
        """
        if not self.font_manager or not self.text:
            self.content = None # Clear PIL content
            if isinstance(canvas, tk.Canvas):
                # Clear any text items previously drawn by this shape instance on the canvas
                canvas.delete(f"text_shape_{self.sid}")
            return

        x0, y0, x1, y1 = self.get_bbox
        # Calculate container width and height in pixels based on the shape's bounding box.
        # These are the dimensions of the area the text should occupy *on the final output*.
        container_width_pixels = max(1, x1 - x0)
        container_height_pixels = max(1, y1 - y0)

        # Determine if we are drawing to a Tkinter Canvas directly
        is_tk_canvas_draw = isinstance(canvas, tk.Canvas) and not draw_pil

        if is_tk_canvas_draw:
            # --- Tkinter Drawing Path ---
            try:
                # Use get_tk_font for Tkinter canvas drawing
                tk_font = self.font_manager.get_tk_font(
                    self.font_name, self.font_size, self.font_weight, self.font_slant
                )
                if not tk_font:
                    print(f"Shape {self.sid}: Could not load Tkinter font {self.font_name} {self.font_weight} {self.font_size}")
                    canvas.delete(f"text_shape_{self.sid}")
                    return

                # Remove previous text drawn by this shape instance
                canvas.delete(f"text_shape_{self.sid}")

                # Tkinter's create_text with 'width' handles word wrapping automatically.
                # We need to estimate the total height for vertical justification.
                # A simple approximation for height calculation:
                # Get the approximate max chars per line that Tkinter's width would cause
                # Based on average char width
                approx_char_width_tk = tk_font.measure("M")
                max_chars_per_line_approx = max(1, int(container_width_pixels / approx_char_width_tk))
                
                wrapped_lines_for_height_calc = textwrap.fill(self.text, width=max_chars_per_line_approx).split('\n')
                total_text_height_tk = len(wrapped_lines_for_height_calc) * tk_font.metrics("linespace")

                # Determine starting Y for vertical justification
                start_y_text_tk = y0 # Default to top of the shape's bbox
                if self.vertical_justification == "center":
                    start_y_text_tk = y0 + (container_height_pixels - total_text_height_tk) / 2
                elif self.vertical_justification == "bottom":
                    start_y_text_tk = y0 + container_height_pixels - total_text_height_tk
                
                # Ensure the starting Y is not above the shape's top boundary and within bounds
                start_y_text_tk = max(y0, start_y_text_tk)
                # Cap the start_y_text_tk so text doesn't flow past bottom if it's too tall
                start_y_text_tk = min(y1, start_y_text_tk)


                # Determine Tkinter anchor and justify for create_text
                tk_anchor = "nw" # Default: top-left of text block at (x, y)
                tk_justify = self.justification # 'left', 'center', 'right'

                # Calculate x-coordinate based on horizontal justification
                text_x_tk = x0 # Default for left justification (anchor 'nw')
                if self.justification == "center":
                    text_x_tk = x0 + container_width_pixels / 2 # Center of the shape's width
                    tk_anchor = "n" # Anchor text block's top-center at (text_x_tk, start_y_text_tk)
                elif self.justification == "right":
                    text_x_tk = x0 + container_width_pixels # Right edge of the shape's width
                    tk_anchor = "ne" # Anchor text block's top-right at (text_x_tk, start_y_text_tk)

                canvas.create_text(
                    text_x_tk,
                    start_y_text_tk,
                    text=self.text,
                    font=tk_font,
                    fill=self.color,
                    width=container_width_pixels, # This is crucial for Tkinter's internal word wrapping
                    anchor=tk_anchor,      # Anchor point for the overall text block
                    justify=tk_justify,    # Justification *within* the wrapped text block
                    tags=f"text_shape_{self.sid}" # Unique tag for this shape's text
                )
                self.content = None # No PIL content needed when drawing directly to Tkinter

            except Exception as e:
                print(f"Shape {self.sid}: Error drawing text to Tkinter canvas: {e}")
                self.content = None # Clear PIL content on error
                canvas.delete(f"text_shape_{self.sid}") # Clear any partial text

        else:
            # --- PIL Drawing Path ---
            # This path is used if `canvas` is not a Tkinter.Canvas or `draw_pil` is True.
            # This is also the path that will generate the PIL Image for clipping.
            try:
                # Calculate PIL font size in pixels based on desired point size and render_dpi
                # 1 point = 1/72 inch. So, size_in_pixels = (size_in_points / 72) * render_dpi
                pil_font_size_pixels = int(round((self.font_size / 72.0) * render_dpi))
                pil_font_size_pixels = max(1, pil_font_size_pixels) # Ensure minimum font size

                # Use get_pil_font for PIL rendering with the calculated pixel size
                font = self.font_manager.get_pil_font(
                    self.font_name, pil_font_size_pixels, self.font_weight, self.font_slant
                )
                if not font:
                    print(f"Shape {self.sid}: Could not load PIL font {self.font_name} {self.font_weight} {pil_font_size_pixels}px.")
                    self.content = None
                    return

                # Calculate container dimensions in high-resolution pixels
                # This is the target size for the text image *before* final scaling to the PDF.
                # It's based on the shape's actual dimensions, scaled up by the render_dpi.
                high_res_container_width = max(1, int(round((container_width_pixels / 72.0) * render_dpi)))
                high_res_container_height = max(1, int(round((container_height_pixels / 72.0) * render_dpi)))
                
                # Create a dummy image and draw context to measure text at high resolution
                # Use a larger dummy image to avoid issues with textbbox for large fonts
                dummy_img = Image.new('RGBA', (high_res_container_width + 100, high_res_container_height + 100), (0, 0, 0, 0))
                dummy_draw = ImageDraw.Draw(dummy_img)

                # Estimate average character width for initial wrapping based on high-res font
                # Use textbbox to get more accurate character width
                try:
                    avg_char_width_bbox = dummy_draw.textbbox((0, 0), "M", font=font)
                    avg_char_width = avg_char_width_bbox[2] - avg_char_width_bbox[0]
                except Exception:
                    # Fallback if textbbox fails for some reason
                    avg_char_width = pil_font_size_pixels * 0.6 # A rough estimate

                max_chars_per_line = max(1, int(high_res_container_width // avg_char_width))
                if max_chars_per_line == 0: 
                     max_chars_per_line = 1

                wrapped_text = textwrap.fill(self.text, width=max_chars_per_line)
                lines = wrapped_text.split('\n')

                total_text_height = 0
                line_heights = []
                max_line_width = 0
                for line in lines:
                    bbox = dummy_draw.textbbox((0, 0), line, font=font)
                    line_height = bbox[3] - bbox[1] 
                    line_width = bbox[2] - bbox[0]
                    line_heights.append(line_height)
                    total_text_height += line_height
                    max_line_width = max(max_line_width, line_width)

                # Determine starting y for vertical justification within the PIL image
                start_y_text_pil = 0
                if self.vertical_justification == "center":
                    start_y_text_pil = (high_res_container_height - total_text_height) / 2
                elif self.vertical_justification == "bottom":
                    start_y_text_pil = high_res_container_height - total_text_height
                start_y_text_pil = max(0, start_y_text_pil) 

                # Create the final PIL image for the text content
                # The image needs to be large enough to contain the wrapped text and justification padding.
                # It should be at least the high-res container dimensions.
                final_img_width = max(high_res_container_width, int(max_line_width) + 2) # Add a small buffer
                final_img_height = max(high_res_container_height, int(total_text_height) + 2) # Add a small buffer
                
                text_img = Image.new('RGBA', (final_img_width, final_img_height), (0, 0, 0, 0)) # Fully transparent background
                pil_draw_context = ImageDraw.Draw(text_img)

                y_offset = start_y_text_pil
                for i, line in enumerate(lines):
                    line_bbox = pil_draw_context.textbbox((0, 0), line, font=font)
                    line_width = line_bbox[2] - line_bbox[0]

                    x_pil = 0
                    if self.justification == "center":
                        x_pil = (final_img_width - line_width) / 2
                    elif self.justification == "right":
                        x_pil = final_img_width - line_width
                    x_pil = max(0, x_pil) 

                    # PIL's text method draws from the top-left of the text's bounding box relative to the text_img origin.
                    # Adjust 'x_pil' and 'y_offset' by the line_bbox[0] and line_bbox[1] to get the correct draw position.
                    pil_draw_context.text((x_pil - line_bbox[0], y_offset - line_bbox[1]), line, font=font, fill=self.color)
                    y_offset += line_heights[i] 

                self.content = self.clip_image_to_geometry(text_img) # Store the PIL image

            except Exception as e:
                print(f"Shape {self.sid}: Error drawing text content (PIL): {e}")
                import traceback
                traceback.print_exc() # Print full traceback for debugging
                self.content = None


    def _load_image_content(self, path=None):
        """Loads an image from self.path or path into self.content."""
        full_path = path or self.path # Assume path is relative or absolute
        if full_path:
            # Check if it's a relative path to the current working directory
            if not os.path.isabs(full_path) and not full_path.startswith('./') and not full_path.startswith('.\\'):
                # Prepend './' for paths that are just filenames or relative without explicit dot
                full_path = os.path.join('./', full_path)
            
            if not os.path.exists(full_path):
                print(f"Shape {self.sid}: Image file not found at {full_path}")
                self.content = None
                return

            try:
                img = Image.open(full_path)
                img = img.convert("RGBA") # Ensure RGBA for transparency
            except Exception as e:
                print(f"Shape {self.sid}: Error opening image {full_path}: {e}")
                self.content = None
                return
        elif self.content:
            img = self.content.convert("RGBA")
        else:
            return

        self.content = self.clip_image_to_geometry(img)

    def draw_content(self, path=None, text=None, draw=True):
        # Step 1: Use PIL to create the content image
        # This method is now primarily for generating the PIL content
        # Use a default DPI (e.g., 300) for PIL text rendering here
        if self.container_type.lower() == 'text':
            self._draw_text_content(draw_pil=True, render_dpi=300) # Always generate PIL content here
        elif self.container_type.lower() == 'image':
            self._load_image_content()
        else:
            self.content = None
            return None

        # Step 2: If draw=False, convert the PIL image to a Tk-compatible PhotoImage
        # This typically means a PhotoImage is requested for display
        if not draw:
            from PIL import ImageTk # Import ImageTk locally for this method to avoid circular dependency
            if ImageTk is None: # This check might be redundant if import is direct
                raise RuntimeError("Tkinter not available")
            if self.content:
                self.tk_image = ImageTk.PhotoImage(self.content)
                return self.tk_image
            return None # Return None if no content to convert

        return self.content # Return PIL Image content if draw=True (default)
    
    def handle_contains(self, x, y):
        if not self.coords or len(self.coords) < 4: return False
        x1, y1, x2, y2 = self.coords
        effective_x2 = max(x1, x2)
        effective_y2 = max(y1, y2)
        handle_size = 8
        return (effective_x2 - handle_size <= x <= effective_x2 + handle_size and
                effective_y2 - handle_size <= y <= effective_y2 + handle_size)

    def contains_point(self, x: int, y: int) -> bool:
        return False  # Override in subclasses

    def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw]=None):
        pass  # Override in subclasses

    def clip_image_to_geometry(self, pil_image: Image.Image) -> Image.Image:
        return pil_image  # Override in subclasses

    def draw(self):
        pass


# Import specific shape subclasses for the from_dict factory method
# These imports MUST be *after* the Shape class definition
import os # Ensure os is imported for _load_image_content
from .rectangle import Rectangle
from .oval import Oval
from .triangle import Triangle
from .hexagon import Hexagon # Make sure you have a Hexagon class and import it
