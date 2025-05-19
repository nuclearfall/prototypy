# shapes/base_shape.py

import math
import textwrap
from typing import List, Dict, Optional, Any, Tuple
from PIL import Image, ImageDraw, ImageFont

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
        self.font_weight = kwargs.get("font_weight", "regular")
        self.justification = kwargs.get("justification", "left")
        self.vertical_justification = kwargs.get("vertical_justification", "top") # Add vertical justification

        # Load content if it's an image or text container and data is present
        if self.container_type == 'Text' and self.text:
            self._draw_text_content()
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
                self._draw_text_content() # Re-render text content
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
            self._draw_text_content() # Regenerate content
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
                self._draw_text_content() # Regenerate text content
        # self.model.notify_observers() # Model should notify

    def set_font_size(self, new_font_size: int):
        new_font_size = max(1, new_font_size) # Ensure font size is at least 1
        self.font_size = new_font_size
        if self.container_type == 'Text':
            self._draw_text_content() # Regenerate text content
        # self.model.notify_observers() # Model should notify

    def set_font_weight(self, new_font_weight: str):
        if self.font_manager and new_font_weight in self.font_manager.get_weights_for_family(self.font_name):
            self.font_weight = new_font_weight
            if self.container_type == 'Text':
                self._draw_text_content() # Regenerate text content
        # self.model.notify_observers() # Model should notify

    def set_justification(self, new_justification: str):
        if new_justification in ["left", "right", "center"]:
            self.justification = new_justification
            if self.container_type == 'Text':
                self._draw_text_content() # Regenerate text content
        # self.model.notify_observers() # Model should notify

    def set_vertical_justification(self, new_vertical_justification: str):
        if new_vertical_justification in ["top", "center", "bottom"]:
            self.vertical_justification = new_vertical_justification
            if self.container_type == 'Text':
                self._draw_text_content()
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
            'id': self.sid,
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
        sid = data.get('id')
        shape_type = data.get('shape_type')
        coords = data.get('coords')
        name = data.get('name')

        if not all([sid, shape_type, coords, name is not None]):
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
            if shape_instance.container_type == 'Text' and shape_instance.text:
                 shape_instance._draw_text_content()
            elif shape_instance.container_type == 'Image' and shape_instance.path:
                 shape_instance._load_image_content()

            print(f"Shape.from_dict: Created shape ID {shape_instance.sid} of type '{shape_type}'")
            return shape_instance

        except Exception as e:
            print(f"Shape.from_dict: Error creating shape instance from data {data}: {e}")
            import traceback
            traceback.print_exc()
            return None # Handle errors during instance creation

    def _draw_text_content(self):
        """Renders the text content into a PIL Image."""
        if not self.font_manager or not self.text:
            self.content = None
            return

        try:
            font = self.font_manager.get_font(self.font_name, self.font_size, self.font_weight)
            if not font:
                print(f"Shape {self.sid}: Could not load font {self.font_name} {self.font_weight} {self.font_size}")
                self.content = None
                return

            # Get bounding box of the shape for text rendering
            x0, y0, x1, y1 = self.get_bbox
            container_width = max(1, x1 - x0)
            container_height = max(1, y1 - y0)

            # Create a dummy image and draw context to measure text
            dummy_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
            dummy_draw = ImageDraw.Draw(dummy_img)

            # Estimate average character width for initial wrapping
            # A more robust solution might involve a fixed-width font or iterating character by character
            avg_char_width = font.getbbox("A")[2] - font.getbbox("A")[0] # Get width of 'A'

            # Calculate max characters per line that fit within the container width
            max_chars_per_line = max(1, int(container_width // avg_char_width))
            if max_chars_per_line == 0: # Avoid division by zero if container_width is very small
                 max_chars_per_line = 1

            # Wrap the text
            wrapped_text = textwrap.fill(self.text, width=max_chars_per_line)
            lines = wrapped_text.split('\n')

            # Calculate total text height
            total_text_height = 0
            line_heights = []
            for line in lines:
                # Use gettextbbox for accurate measurement
                bbox = dummy_draw.textbbox((0, 0), line, font=font)
                line_height = bbox[3] - bbox[1] # height is ymax - ymin
                line_heights.append(line_height)
                total_text_height += line_height

            # Determine starting y for vertical justification
            start_y_text = 0
            if self.vertical_justification == "center":
                start_y_text = (container_height - total_text_height) / 2
            elif self.vertical_justification == "bottom":
                start_y_text = container_height - total_text_height
            start_y_text = max(0, start_y_text) # Ensure not negative

            # Create the final image for the text content
            text_img = Image.new('RGBA', (int(container_width), int(container_height)), (0, 0, 0, 0))
            draw = ImageDraw.Draw(text_img)

            y_offset = start_y_text
            for i, line in enumerate(lines):
                # Calculate line width for justification
                line_bbox = draw.textbbox((0, 0), line, font=font)
                line_width = line_bbox[2] - line_bbox[0]

                x = 0
                if self.justification == "center":
                    x = (container_width - line_width) / 2
                elif self.justification == "right":
                    x = container_width - line_width
                x = max(0, x) # Ensure not negative

                draw.text((x, y_offset), line, font=font, fill=self.color)
                y_offset += line_heights[i] # Move to the next line

            self.content = text_img

        except Exception as e:
            print(f"Shape {self.sid}: Error drawing text content: {e}")
            self.content = None

    def _load_image_content(self):
        """Loads an image from self.path into self.content."""
        if not self.path:
            self.content = None
            return

        try:
            full_path = self.path # Assume path is relative or absolute
            
            # Check if it's a relative path to the current working directory
            if not os.path.isabs(full_path) and not full_path.startswith('./') and not full_path.startswith('.\\'):
                # Prepend './' for paths that are just filenames or relative without explicit dot
                full_path = os.path.join('./', full_path)
            
            if not os.path.exists(full_path):
                print(f"Shape {self.sid}: Image file not found at {full_path}")
                self.content = None
                return

            img = Image.open(full_path)
            img = img.convert("RGBA") # Ensure RGBA for transparency
            
            # Resize image to fit bounding box while maintaining aspect ratio, then crop if clip_image is True
            x0, y0, x1, y1 = self.get_bbox
            container_width = max(1, x1 - x0)
            container_height = max(1, y1 - y0)

            if self.clip_image:
                # Fill the container, cropping excess
                img_aspect = img.width / img.height
                container_aspect = container_width / container_height

                if img_aspect > container_aspect:
                    # Image is wider than container, scale to height and crop width
                    new_height = container_height
                    new_width = int(new_height * img_aspect)
                else:
                    # Image is taller or same aspect as container, scale to width and crop height
                    new_width = container_width
                    new_height = int(new_width / img_aspect)

                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Calculate crop box
                left = (new_width - container_width) / 2
                top = (new_height - container_height) / 2
                right = (new_width + container_width) / 2
                bottom = (new_height + container_height) / 2
                img = img.crop((int(left), int(top), int(right), int(bottom)))
            else:
                # Fit within container, maintaining aspect ratio, without cropping
                img.thumbnail((container_width, container_height), Image.Resampling.LANCZOS)
                # Create a new blank image of the container size and paste the scaled image
                # This centers the image if it's smaller than the container after thumbnailing
                final_img = Image.new('RGBA', (int(container_width), int(container_height)), (0, 0, 0, 0))
                paste_x = (container_width - img.width) // 2
                paste_y = (container_height - img.height) // 2
                final_img.paste(img, (int(paste_x), int(paste_y)))
                img = final_img # Use the new image with padding

            self.content = img

        except FileNotFoundError:
            print(f"Shape {self.sid}: Image file not found at {self.path}")
            self.content = None
        except Exception as e:
            print(f"Shape {self.sid}: Error loading image from {self.path}: {e}")
            self.content = None

    
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



# Import specific shape subclasses for the from_dict factory method
# These imports MUST be *after* the Shape class definition
import os # Ensure os is imported for _load_image_content
from .rectangle import Rectangle
from .oval import Oval
from .triangle import Triangle
from .hexagon import Hexagon # Make sure you have a Hexagon class and import it