# shapes/base_shape.py

import math
import textwrap
from typing import List, Dict, Optional, Any, Tuple
from PIL import Image, ImageDraw, ImageFont

# REMOVE THIS LINE: from app_service import AppService
# Assuming FontManager is in utils/font_manager.py
from utils.font_manager import FontManager # Still need FontManager type hint and class access

# Assuming utility functions like _update_coords_if_valid are in utils/geometry.py
from utils.geometry import _update_coords_if_valid # If used directly in Shape

# Assuming constants are in a central constants.py
from constants import CONTAINER_TYPES, SHAPE_TYPES # Example

# Import specific shape subclasses for the from_dict factory method
# from .rectangle import Rectangle # These imports go after the Shape class definition
# from .oval import Oval
# from .triangle import Triangle
# from .hexagon import Hexagon

class Shape:
    @classmethod
    def get_font_names(cls):
        # Assuming 'font_manager' is available globally or through another service
        return cls.font_manager.get_families()  # Dynamically get font families

    @classmethod
    def get_font_weights(cls, family):
        # Assuming 'font_manager' is available globally or through another service
        return cls.font_manager.get_weights_for_family(family)  # Get weights for a given family

    @property
    def property_spec(cls):
        """Dynamically populate property_spec with font names and weights"""
        return {
            "Name": {"type": "str"},
            "X": {"type": "float"},
            "Y": {"type": "float"},
            "Width": {"type": "float"},
            "Height": {"type": "float"},
            "Container Type": {"type": "enum", "values": ["Text", "Image"]},
            "Shape Type": {"type": "enum", "values": ["Rectangle", "Oval", "Triangle"]},
            "Font Name": {
                "type": "enum", 
                "values": cls.get_font_names()  # Dynamically populated font names
            },
            "Font Size": {"type": "int"},
            "Font Weight": {
                "type": "enum", 
                "values": lambda shape=None: (
                    cls.get_font_weights(shape.font_name) if shape else cls.get_font_weights(cls.get_font_names()[0])
                )
            },
            "Justification": {"type": "enum", "values": ["left", "right", "center"]}
        }

    def __init__(self, sid: Any, shape_type: str, coords: List[int], name: str, font_manager=None, **kwargs):
        # Store controller reference to access FontManager
        # self.app_service = AppService.get_instance()
        # self.font_manager = self.app_service.font_manager
        # self.controller = self.app_service.controller
        self.font_manager = font_manager
        # self.view = self.controller.view 
        # self.model = self.controller.model
        # Initialize existing properties
        self.sid = sid
        self.shape_type = shape_type

        self.coords = coords
        self.name = name
        self.line_width: int = kwargs.get('line_width', 1)
        self.init_coords(*coords)
        x0, y0, x1, y1, = self.get_bbox
        self.width = x1 - x0
        self.height = y1 - y0
        # Initialize other properties using kwargs.get() to override defaults
        # This ensures loaded values from JSON take precedence
        self.container_type: str = kwargs.get('container_type', 'Text')
        self.content: Optional[Any] = None # Content is regenerated, not loaded directly
        self.color: str = kwargs.get('color', 'black')
        self.clip_image: bool = kwargs.get('clip_image', True) # Assuming clip_image is a property
        self.path = kwargs.get('path', '')
        self.text = kwargs.get('text', '')

        # Font properties (already using kwargs.get(), keep as is)
        self.font_name = kwargs.get("font_name", "Arial Unicode")
        self.font_size = kwargs.get("font_size", 12)
        self.font_weight = kwargs.get("font_weight", "regular")
        self.justification = kwargs.get("justification", "left")
        self.vertical_justification = kwargs.get("vertical_justification", "top") # Add vertical justification

        # Transient display properties (not loaded/saved)
        self.display_x: float = 0.0
        self.display_y: float = 0.0
        self.display_w: float = 0.0
        self.display_h: float = 0.0


        # Regenerate content immediately after initialization if data is loaded
        # The checks here will now use the values loaded via kwargs.get()
        if self.container_type == 'Text' and self.text:
             print(f"Shape {self.sid}: Loading text content.") # Debugging
             self._draw_text_content()
        elif self.container_type == 'Image' and self.path:
             print(f"Shape {self.sid}: Loading image content from {self.path}.") # Debugging
             self._load_image_content()
        else:
             self.content = None # Ensure content is None if no text or image path
        
    @property
    def get_bbox(self):
        # The bounding box is simply the rectangle defined by the coordinates
        x1, y1, x2, y2 = self.coords
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

    def init_coords(self, x0, y0, x1, y1):
        # Initialize coords directly without adjusting for line_width
        self.coords = [x0, y0, x1, y1]
        print(f"Initializing coords: {self.coords}") # Keep print for debugging
        # Also initialize width, height, x, y based on the initial coords
        min_x, min_y, max_x, max_y = self.get_bbox
        self.width = max_x - min_x
        self.height = max_y - min_y
        self.x = min_x
        self.y = min_y


    def set_coords(self, x0, y0, x1, y1):
        # Set coords and update width/height/x/y based on the new coords
        self.coords = [x0, y0, x1, y1]
        min_x, min_y, max_x, max_y = self.get_bbox
        self.width = max_x - min_x
        self.height = max_y - min_y
        self.x = min_x
        self.y = min_y

    @classmethod
    def get_font_names(self):
        return self.font_manager.get_families()

    @classmethod
    def get_font_weights(cls, family):
        """Get font weights for a specific family"""
        return cls.controller.font_manager.get_weights_for_family(family)

    def set_font(self, font_name):
        self.font_name = font_name

    def set_line_width(self, line_width):
        self.line_width = line_width

    def set_x(self, new_x: float):
        """Sets the x-coordinate (left edge) of the shape's outer boundary."""
        x0, y0, x1, y1 = self.get_bbox
        width = x1 - x0 # Get current width
        # Set the new top-left x, keeping the width and top-left y
        self.set_coords(new_x, y0, new_x + width, y1)

    def set_y(self, new_y: float):
        """Sets the y-coordinate (top edge) of the shape's outer boundary."""
        x0, y0, x1, y1 = self.get_bbox
        height = y1 - y0 # Get current height
        # Set the new top-left y, keeping the height and top-left x
        self.set_coords(x0, new_y, x1, new_y + height)

    # You could also have a combined method
    def set_position(self, new_x: float, new_y: float):
        """Sets the top-left corner (x, y) of the shape's outer boundary."""
        x0, y0, x1, y1 = self.get_bbox
        width = x1 - x0
        height = y1 - y0
        self.set_coords(new_x, new_y, new_x + width, new_y + height)

    # And a set_height method
    def set_height(self, new_height: float):
        """Sets the height of the shape's outer boundary."""
        x0, y0, x1, y1 = self.get_bbox
        height = y1 - y0 # Get current height (for clarity, though not strictly needed)
        # Set the new bottom-right y, keeping the top-left x and y and the width
        self.set_coords(x0, y0, x1, y0 + new_height)

    def prop_get(self, controller, prop_name):
        handler = controller.PROPERTY_HANDLERS.get(prop_name)
        if handler and "get" in handler:
            return handler["get"](self)
        if prop_name == "X": return self.get_bbox[0]
        elif prop_name == "Y": return self.get_bbox[1]
        elif prop_name == "Width": return self.get_bbox[2] - self.get_bbox[0]
        elif prop_name == "Height": return self.get_bbox[3] - self.get_bbox[1]
        else:
            return getattr(self, prop_name.lower().replace(" ", "_"), None)

    def _get_font(self):
        """Helper to get the ImageFont object."""
        return self.font_manager.get_font(self.font_name, self.font_weight, self.font_size)


    def _draw_text_content(self):
            """Renders the text to an image and stores it in self.content, with word wrapping."""
            if not self.text:
                self.content = None
                return

            # Get container dimensions from shape coordinates
            min_x, min_y, max_x, max_y = self.get_bbox
            container_width = max(1, int(round(max_x - min_x)))
            container_height = max(1, int(round(max_y - min_y)))

            if container_width <= 0 or container_height <= 0:
                 self.content = None
                 return # Cannot draw text in a zero-sized container

            try:
                font = self.font_manager.get_font(self.font_name, self.font_weight, self.font_size)

                # --- Text Measurement ---
                # Use textlength for better width estimation if available
                if hasattr(font, 'textlength'):
                    # Estimate average character width based on a few common characters
                    test_string = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ "
                    avg_char_width = font.textlength(test_string) / len(test_string)
                else:
                    try:
                        # textsize returns (width, height) - use average of a few characters
                        avg_char_width, _ = font.textsize("nnn")
                        avg_char_width /= 3
                    except Exception:
                         avg_char_width = self.font_size * 0.6 # Final fallback estimation


                # Calculate max characters per line that fit within the container width
                max_chars_per_line = max(1, int(container_width // avg_char_width))

                # Wrap the text
                wrapped_text = textwrap.fill(self.text, width=max_chars_per_line)
                lines = wrapped_text.split('\n')

                # Calculate line height
                # We'll use textsize for height and add a small buffer
                try:
                    # textsize returns (width, height) for single line - height is a decent proxy for line height
                    # Using a common character that typically has ascenders/descenders to get full height
                    _, line_height = font.textsize("Ay")
                    line_height += 2 # Small padding between lines
                except Exception:
                     line_height = self.font_size + 2 # Fallback line height estimation


                # Determine how many lines can fit
                max_lines = max(1, int(container_height // line_height))
                lines_to_draw = lines[:max_lines] # Only draw lines that fit


                # Create the image to draw text onto (size of the container)
                # The background of this image should be transparent.
                # Change to BLACK transparent (0, 0, 0, 0)
                image = Image.new("RGBA", (container_width, container_height), (0, 0, 0, 0)) # BLACK transparent base
                draw = ImageDraw.Draw(image)


                # Calculate total height of the text block that will be drawn
                total_text_block_height = len(lines_to_draw) * line_height

                # Calculate the starting y position for the text block based on vertical centering
                # This part was simplified earlier, if you need vertical justification, the logic
                # from a previous turn should be used here instead of 'start_y_block = 0'
                # start_y_block = max(0, (container_height - total_text_block_height) // 2) # Example for centering

                start_y_block = 0 # Current simple top alignment


                # --- Ensure text fill color is opaque ---
                # Use the shape's color, but force alpha to 255 if it's an RGBA tuple
                text_fill_color = self.color
                if isinstance(text_fill_color, tuple) and len(text_fill_color) == 4:
                    # If it's an RGBA tuple, create an opaque version (set alpha to 255)
                    text_fill_color = (text_fill_color[0], text_fill_color[1], text_fill_color[2], 255)
                elif isinstance(text_fill_color, str):
                    # If it's a string (like color name or hex), assume it's opaque RGB
                    # Pillow handles these correctly as opaque by default
                    pass # No change needed
                # ----------------------------------------


                # Draw each line
                for i, line in enumerate(lines_to_draw):
                    # Calculate the x position for each line based on justification
                    # Need width of the actual line being drawn
                    if hasattr(font, 'textlength'):
                         line_width = font.textlength(line)
                    else:
                         try:
                              line_width, _ = font.textsize(line)
                         except Exception:
                               line_width = len(line) * avg_char_width # Fallback line width estimation


                    x = 0
                    if self.justification == "center":
                        # Center the line within the container width
                        x = (container_width - line_width) // 2
                    elif self.justification == "right":
                        # Align the right edge of the line with the right edge of the container
                        x = container_width - line_width

                    # Add a small padding from the left edge, and ensure x is not negative
                    x = max(2, x) # Add 2 pixels padding from left, ensure >= 0


                    # Calculate the y position for the current line
                    # This is the top-left y coordinate for the line
                    y = start_y_block + i * line_height

                    # Draw the text line using the opaque text_fill_color
                    # Temporarily change the fill color to a solid, obvious color like red
                    draw.text((x, y), line, font=font, fill=text_fill_color)
                    #draw.font_mode = "L" # Keep or remove this as needed for anti-aliasing


                # Just store the raw text image in self.content.
                # Clipping to shape geometry (if needed for text, less common than images)
                # and pasting onto the flattened card will handle composition.
                self.content = image


                print(f"Text content rendered for shape {self.sid}. Image size: {image.size}") # Debugging print

            except Exception as e:
                print(f"Font or Text Rendering Error for shape {self.sid}: {e}")
                # Print the full traceback for more detailed debugging
                import traceback
                traceback.print_exc()
                self.content = None # Clear content on error
                # Optionally draw error text or a placeholder

# Keep the rest of the Shape class and other classes below as they are.

    def _load_image_content(self):
        """Loads the image from self.path and stores it in self.content."""
        if self.container_type != 'Image' or not self.path:
            self.content = None # Clear content if not an image container or path is empty

        try:
            pil_image = Image.open(self.path)
            # We'll store the raw PIL image in content for now.
            # Clipping and resizing to the shape's bounds will happen during drawing.
            self.content = self.clip_image_to_geometry(pil_image.convert('RGBA')) # Convert to RGBA for consistent handling
            print(f"Shape {self.sid}: Successfully loaded image from {self.path}")
        except FileNotFoundError:
            print(f"Shape {self.sid}: Image file not found at {self.path}")
            self.content = None # Clear content if file not found
            # Optionally, load a placeholder "file not found" image
        except Exception as e:
            print(f"Shape {self.sid}: Error loading image from {self.path}: {e}")
            self.content = None # Clear content on other errors
            # Optionally, load a placeholder "error loading image"

    def set_container_type(self, container_type: str):
        """Sets the container type and reloads content if necessary."""
        if self.container_type != container_type:
            self.container_type = container_type
            self.content = None # Clear existing content

            if self.container_type == 'Text':
                 # If switching to text, trigger text rendering
                 self._draw_text_content()
            elif self.container_type == 'Image':
                 # If switching to image, trigger image loading
                 self._load_image_content()

            self._notify_view() # Notify view to redraw

    def set_path(self, path: str):
        """Sets the image path and reloads image content."""
        if self.path != path:
            self.path = path
            # Only attempt to load if it's an Image container
            if self.container_type == 'Image':
                 self._load_image_content()
                 self._notify_view() # Notify view to redraw

    # Ensure the prop_set method calls the new setter methods
    def prop_set(self, prop_name, value):
        handler = PROPERTY_HANDLERS.get(prop_name)
        if handler and "set" in handler:
            # Call the specific setter defined in PROPERTY_HANDLERS
            handler["set"](self, value)
        else:
            # Fallback to direct attribute setting if no specific handler
            try:
                # Use the specific setter methods if they exist
                setter_name = f"set_{prop_name.lower().replace(' ', '_')}"
                if hasattr(self, setter_name):
                     getattr(self, setter_name)(value)
                else:
                     setattr(self, prop_name.lower().replace(" ", "_"), value)
                print(f"Model: {self}.{prop_name} set to {value}")  # Debugging
            except AttributeError:
                print(f"Warning: Shape {self.sid} has no settable property '{prop_name}' or no handler.")
            except Exception as e:
                 print(f"Error setting property '{prop_name}' on shape {self.sid}: {e}")


    def set_name(self, name):
        self.name = name

    def set_font_name(self, font_name):
        if self.font_name != font_name:
            self.font_name = font_name
            self._draw_text_content()
            #  Notify the view to redraw (you'll need to implement this)
            # self._notify_view()

    def set_font_size(self, font_size):
        if self.font_size != font_size:
            self.font_size = font_size
            self._draw_text_content()
            # self._notify_view()

    def set_font_weight(self, font_weight):
        if self.font_weight != font_weight:
            self.font_weight = font_weight
            self._draw_text_content()
            # self._notify_view()

    def set_justification(self, justification):
        if self.justification != justification:
            self.justification = justification
            self._draw_text_content()
            # self._notify_view()

    def set_text(self, text):
        self.text = text
        self._draw_text_content()
        # self._notify_view()

    def _notify_view(self):
        """Placeholder:  Replace with your actual view update mechanism."""
        print(f"Shape {self.sid}: Needs redraw after font/text change")
        #  This is where you'd trigger a canvas redraw or update the UI
        #  For example, if you have a canvas object:
        #  self.canvas.itemconfig(self.canvas_item_id, image=self.rendered_text)
        # self.model.notify_observers()  

    # def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw] = None):
    #     # super().draw_shape(canvas, draw)  # Call the base class method

    #     # if self.container_type == 'Text' and self._rendered_text:
    #     #     x1, y1, x2, y2 = self.coords
    #     #     bbox = self.get_bbox
    #     #     text_x = bbox[0]
    #     #     text_y = bbox[1]

    #     #     if canvas:
    #     #         #  Render the PIL image onto the canvas
    #     #         self.tk_image = ImageTk.PhotoImage(self._rendered_text)  # Keep a reference!
    #     #         canvas.create_image(text_x, text_y, image=self.tk_image, anchor='nw')
    #     #     elif draw:
    #     #         draw.bitmap((text_x, text_y), self._rendered_text)
    #     pass


    def set_color(self, color: str):

        if self.color != color:
            print(f"Model: Setting shape {self.sid} color to {color}")  # Debugging
            self.color = color
            print(f"Model: Notified observers after setting shape {self.sid} color")  # Debugging

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

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the shape object to a dictionary."""
        shape_data = {
            'sid': self.sid,
            'shape_type': self.shape_type,
            'coords': self.coords,
            'name': self.name,
            'container_type': self.container_type,
            'color': self.color,
            'line_width': self.line_width,
            'path': self.path,         # Save image path
            'text': self.text,         # Save text content
            'font_name': self.font_name, # Save font properties
            'font_size': self.font_size,
            'font_weight': self.font_weight,
            'justification': self.justification,
            # Note: 'content' (PIL Image) is not saved, it's regenerated on load.
            # Note: 'clip_image' is related to rendering and can likely be inferred
            # based on container type or is a rendering flag, not core data to save.
            # Note: display_x/y/w/h are transient and not saved.
        }
        print(f"Shape.to_dict: Serialized shape ID {self.sid}") # Debugging
        return shape_data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], font_manager: FontManager): # Accept font_manager
        """
        Creates a Shape subclass instance from a dictionary.
        Acts as a factory based on 'shape_type'.
        """
        # ... (existing data retrieval and validation for sid, shape_type, coords, name) ...

        # Select the correct subclass based on shape_type
        # Make sure you have imported the subclass definitions *after* the base class definition
        # e.g., from .rectangle import Rectangle
        shape_class = None # Initialize shape_class to None
        shape_type = data.get('shape_type') # Get shape_type from data

        if shape_type == 'rectangle':
            shape_class = Rectangle # <-- Correct line: Assign the CLASS
        elif shape_type == 'oval':
            shape_class = Oval # <-- Assign the CLASS
        elif shape_type == 'triangle':
            shape_class = Triangle # <-- Assign the CLASS
        elif shape_type == 'hexagon':
            shape_class = Hexagon # <-- Assign the CLASS
        else:
            print(f"Shape.from_dict: Warning: Unknown shape type '{shape_type}'. Cannot create shape.")
            return None # Unknown shape type

        if shape_class is None: # Handle case where shape_type is valid but no class is assigned
             print(f"Shape.from_dict: Error: Could not determine shape class for type '{shape_type}'.")
             return None


        try:
            # Pass all relevant data from the dictionary during initialization
            # Pass the font_manager to the subclass constructor
            # Use the shape_class variable assigned above to create the INSTANCE
            shape_instance = shape_class(
                sid=data.get('sid'), # Get sid from data
                coords=data.get('coords', [0, 0, 10, 10]),
                name=data.get('name', 'Unnamed Shape'),
                font_manager=font_manager, # Pass the font_manager here
                container_type=data.get('container_type', 'Text'),
                color=data.get('color', 'black'),
                line_width=data.get('line_width', 1),
                path=data.get('path', ''),
                text=data.get('text', ''),
                font_name=data.get('font_name', 'Arial Unicode'),
                font_size=data.get('font_size', 12),
                font_weight=data.get('font_weight', 'regular'),
                justification=data.get('justification', 'left')
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


# Import specific shape subclasses for the from_dict factory method
# These imports MUST be *after* the Shape class definition
from .rectangle import Rectangle
from .oval import Oval
from .triangle import Triangle
from .hexagon import Hexagon # Make sure you have a Hexagon class and import it

