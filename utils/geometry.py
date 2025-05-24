# geometry.py

import math
import re  # Import regex for parsing dimensions
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from base_shape import Shape
    from model import DrawingModel

# geometry.py
import re

def parse_dimension(value: str, ppi: float) -> int:
    """Parses a dimension string (e.g., '5px', '2.5in') into pixels using the given PPI."""
    import re
    value = value.strip().lower()
    match = re.match(r"([0-9.]+)\s*(px|in|mm|cm|pt)?", value)
    if not match:
        raise ValueError(f"Invalid dimension format: '{value}'")
    
    num_str, unit = match.groups()
    num = float(num_str)
    unit = unit or "px"

    conversions = {
        "px": 1,
        "in": ppi,
        "cm": ppi / 2.54,
        "mm": ppi / 25.4,
        "pt": ppi / 72,
    }

    if unit not in conversions:
        raise ValueError(f"Unsupported unit: '{unit}'")
    
    return int(round(num * conversions[unit]))

def format_pixel_output(pixel_value: float,
                        ppi: float,
                        target_unit: str = 'px') -> str:
    """
    Converts a pixel value into a formatted string in a specified unit.
    Supports: 'px', 'in', 'cm', 'mm', 'pt'.
    """
    if not isinstance(pixel_value, (int, float)):
        return str(pixel_value)  # fallback

    unit = (target_unit or 'px').lower()

    conversions = {
        "px": 1,
        "in": ppi,
        "cm": ppi / 2.54,
        "mm": ppi / 25.4,
        "pt": ppi / 72,
    }

    if unit not in conversions:
        raise ValueError(f"Unsupported unit: '{unit}'")

    factor = conversions[unit]
    value = pixel_value if unit == 'px' else pixel_value / factor

    # Format cleanly: show integer if exact, otherwise 2 decimal places
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value))} {unit}"
    else:
        return f"{value:.2f} {unit}"

# Keep existing geometry utility functions below

def move_coords_x(shape: "Shape", new_x):
    coords = shape.get_bbox.copy()
    min_x, max_x = min(coords[0], coords[2]), max(coords[0], coords[2])
    dx = new_x - min_x
    new_coords = [coords[0] + dx, coords[1], coords[2] + dx, coords[3]]
    return _update_coords_if_valid(shape, new_coords) # Pass shape here

def move_coords_y(shape: "Shape", new_y): # Add shape type hint
    coords = shape.get_bbox.copy()
    min_y, max_y = min(coords[1], coords[3]), max(coords[1], coords[3])
    dy = new_y - min_y
    new_coords = [coords[0], coords[1] + dy, coords[2], coords[3] + dy]
    return _update_coords_if_valid(shape, new_coords) # Pass shape here

def resize_width(shape: "Shape", new_width): # Add shape type hint
    coords = shape.get_bbox.copy()
    min_x, max_x = min(coords[0], coords[2]), max(coords[0], coords[2])
    # Anchor the left side (min_x) and adjust the right side
    new_coords = [min_x, coords[1], min_x + max(0, new_width), coords[3]]
    return _update_coords_if_valid(shape, new_coords) # Pass shape here

def resize_height(shape: "Shape", new_height): # Add shape type hint
    coords = shape.get_bbox.copy()
    min_y, max_y = min(coords[1], coords[3]), max(coords[1], coords[3])
    # Anchor the top side (min_y) and adjust the bottom side
    new_coords = [coords[0], min_y, coords[2], min_y + max(0, new_height)]
    return _update_coords_if_valid(shape, new_coords) # Pass shape here



def _update_coords_if_valid(shape: "Shape", new_bbox: List[float]) -> bool:
    """
    Updates the shape's internal coordinates if the new bounding box is valid and different.
    Expects new_bbox as [min_x, min_y, max_x, max_y].
    Returns True if coordinates were updated, False otherwise.
    """
    # Basic validation: ensure it's a list/tuple of 4 numbers
    if not isinstance(new_bbox, (list, tuple)) or len(new_bbox) != 4:
        print(f"Geometry._update_coords_if_valid: Invalid new_bbox format: {new_bbox}")
        return False

    # Ensure coordinates are ordered correctly (min_x, min_y, max_x, max_y)
    x1, y1, x2, y2 = new_bbox
    ordered_x1, ordered_y1, ordered_x2, ordered_y2 = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    ordered_bbox = [ordered_x1, ordered_y1, ordered_x2, ordered_y2]

    # Calculate new width and height for validation (must be non-negative or meet minimum)
    new_width = ordered_x2 - ordered_x1
    new_height = ordered_y2 - ordered_y1

    # Add a check for minimum dimensions here if not already done in the caller (Controller)
    min_size_px = 1 # pixels
    if new_width < min_size_px or new_height < min_size_px:
         print(f"Geometry._update_coords_if_valid: New dimensions ({new_width}x{new_height}) are less than minimum {min_size_px}. Rejecting update.")
         # The controller should handle user feedback.
         return False # Do not update if dimensions are too small


    # Compare with current coordinates to avoid unnecessary updates and notifications
    # Use a tolerance for floating point comparisons
    current_bbox = list(shape.get_bbox) # Get current ordered bbox [min_x, min_y, max_x, max_y]
    tolerance = 0.01 # pixels (reduced tolerance slightly)

    coords_changed = False
    # Compare each coordinate
    for i in range(4):
        if abs(ordered_bbox[i] - current_bbox[i]) > tolerance:
            coords_changed = True
            break

    if coords_changed:
        # Update the shape's internal coordinates using its setter method
        # This is the fix from Potential Issue 1
        print(f"Geometry._update_coords_if_valid: Coordinates changed. Updating shape {shape.sid} coords using set_coords.")
        # Pass the ordered bounding box corners to the set_coords method
        shape.set_coords(ordered_bbox[0], ordered_bbox[1], ordered_bbox[2], ordered_bbox[3])
        return True # Indicate that coordinates were updated
    else:
        # print(f"Geometry._update_coords_if_valid: Coordinates did not change significantly.")
        return False # Indicate no significant change


def calculate_snap(model, x, y):
    inc = model.grid_minor_px
    return (round(x / inc) * inc, round(y / inc) * inc)