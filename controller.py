# controller.py

import os           # For file path manipulation (e.g., os.path.basename)
import json         # For saving and loading project files (JSON)
import pandas as pd # For handling CSV data
import io           # Potentially for in-memory data handling (e.g., image buffers, though might move with PDF)
import traceback    # For printing detailed error info (especially in export)
import math
from typing import Optional, Any, Tuple, List, Dict, TYPE_CHECKING

# Tkinter and its modules for UI interaction and dialogs
import tkinter as tk
from tkinter import ttk, simpledialog, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw # Add ImageDraw here

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Need access to the base Shape class for type hinting and potentially the factory method
from shapes.base_shape import Shape
# Need to import specific shape subclasses for creating new shapes in _create_final_shape_object
from shapes.rectangle import Rectangle
from shapes.oval import Oval
from shapes.triangle import Triangle
from shapes.hexagon import Hexagon

# Assuming utility functions like calculate_snap are in utils/geometry.py
from utils.geometry import calculate_snap, parse_dimension, format_pixel_output, _update_coords_if_valid # Or other geometry utils used
# Assuming FontManager is accessed via AppService, but might need import if used directly
# from utils.font_manager import FontManager # Import if you use FontManager directly
from model import DrawingModel, Layer # Import DrawingModel and Layer
from view import DrawingView # Import DrawingView
# Assuming constants are in a central constants.py at the root level
from constants import SHAPE_BUTTONS, CONTAINER_TYPES, SHAPE_TYPES# Import all necessary constants

if TYPE_CHECKING:
    from view import DrawingView # DrawingApp uses DrawingView type hint
    from model import DrawingModel # DrawingApp uses DrawingModel type hint
    from utils.font_manager import FontManager # DrawingApp uses FontManager type hint


class DrawingApp:
    def __init__(self, root: tk.Tk, model: 'DrawingModel', font_manager: 'FontManager'):
        print("DrawingApp.__init__: Starting initialization.") # Added print
        self.root = root
        self.font_manager = font_manager

        print("DrawingApp.__init__: Creating DrawingModel.") # Added print
        # THIS LINE IS CRUCIAL for the 'model' attribute to exist
        self.model = model
        print("DrawingApp.__init__: DrawingModel created and assigned.") # Added print

        print("DrawingApp.__init__: Creating DrawingView.") # Added print
        # The View needs access to the controller (self)
        self.view = DrawingView(root, self)
        print("DrawingApp.__init__: DrawingView created and assigned.") # Added print

        # Register the View as an observer of the Model
        # This line requires self.model to exist
        print("DrawingApp.__init__: Adding model observer.") # Added print
        self.model.add_observer(lambda: self.view.refresh_all(self.model))
        print("DrawingApp.__init__: Model observer added.") # Added print

        # Controller state for drawing/interaction
        self.current_tool: Optional[str] = None
        self.start_x: int = 0
        self.start_y: int = 0
        self.drag_start = (0, 0)
        self.is_resizing = False
        self.is_moving = False
        self.resize_start = (0, 0)

        # Controller state for drawing a new shape (from previous fixes)
        self.is_drawing_new_shape: bool = False
        self.raw_drag_offset: Optional[Tuple[float, float]] = None

        # Controller state for file management and data
        self.current_file_path: Optional[str] = None
        self.csv_data_df: Optional[pd.DataFrame] = None
        self.csv_file_path: Optional[str] = None
        self._refocus_info: Optional[tuple] = None


        # Build Menubar (Controller responsibility)
        print("DrawingApp.__init__: Building menubar.") # Added print
        self._build_menubar()
        print("DrawingApp.__init__: Menubar built.") # Added print

        # Initial state sync - Controller updates View's variables from Model
        # These lines require self.model and self.view to exist
        print("DrawingApp.__init__: Syncing view variables from model.") # Added print
        if hasattr(self, 'view') and hasattr(self.view, 'grid_var'):
             self.view.grid_var.set(self.model.grid_visible)
             print("DrawingApp.__init__: grid_var synced.") # Added print
        if hasattr(self, 'view') and hasattr(self.view, 'snap_var'):
             self.view.snap_var.set(self.model.snap_to_grid)
             print("DrawingApp.__init__: snap_var synced.") # Added print


        # Build property handlers and spec (Controller responsibility)
        # These may require self.model or self.font_manager
        print("DrawingApp.__init__: Building property handlers and spec.") # Added print
        self._build_property_handlers()
        self._build_property_spec()
        print("DrawingApp.__init__: Property handlers and spec built.") # Added print

        print("DrawingApp.__init__: Initialization finished.") # Added print

    def _build_property_spec(self):
        # The Shape.property_spec drives your data-validation schema
        Shape.property_spec = {
            "Name":           {"type": "str"},
            "X":              {"type": "float"},
            "Y":              {"type": "float"},
            "Width":          {"type": "float"},
            "Height":         {"type": "float"},
            "Container Type": {"type": "enum",  "values": CONTAINER_TYPES},
            "Shape Type":     {"type": "enum",  "values": SHAPE_TYPES},
            "Font Name":      {"type": "enum",  "values": self.font_manager.get_families()},
            "Font Size":      {"type": "int"},
            "Font Weight":    {"type": "enum",  "values": []},  # filled in dynamically below
            "Justification":  {"type": "enum",  "values": ['left','center','right']},
            "Text":           {"type": "str"},
        }

        Shape.property_spec["Font Weight"]["values"] = lambda shape=None: (
        self.font_manager.get_weights_for_family(shape.font_name) if shape else self.font_manager.get_weights_for_family("Arial Unicode"))

    def _build_property_handlers(self):
            self.PROPERTY_HANDLERS = {
                "Name": {
                    "type": str,
                    "get": lambda s: s.name,
                    "set": lambda s, v: s.set_name(v),  # Use set_name
                    "validate": lambda v: isinstance(v, str) and v.strip() != "",
                },
                "Shape Type": {
                    "type": str,
                    "get": lambda s: s.shape_type,
                    "set": lambda s, v: s.set_shape_type(v),  # Use set_shape_type
                    "validate": lambda v: v in SHAPE_TYPES,
                    "options": SHAPE_TYPES,
                },
                "X": {
                    "type": float,
                    "get": lambda s: format_pixel_output(s.x, self.model.ppi, self.model.measure),
                    "set": lambda s, v: self._set_shape_coord(s, 'x', v),
                    "validate": lambda v: _is_valid_dimension(v, self.model.ppi),
                },
                "Y": {
                    "type": float,
                    "get": lambda s: format_pixel_output(s.y, self.model.ppi, self.model.measure),
                    "set": lambda s, v: self._set_shape_coord(s, 'y', v),
                    "validate": lambda v: _is_valid_dimension(v, self.model.ppi),
                },
                "Width": {
                    "type": float,
                    "get": lambda s: format_pixel_output(s.width, self.model.ppi, self.model.measure),
                    "set": lambda s, v: self._set_shape_dim(s, 'width', v),
                    "validate": lambda v: _is_valid_dimension(v, self.model.ppi),
                },
                "Height": {
                    "type": float,
                    "get": lambda s: format_pixel_output(s.height, self.model.ppi, self.model.measure),
                    "set": lambda s, v: self._set_shape_dim(s, 'height', v),
                    "validate": lambda v: _is_valid_dimension(v, self.model.ppi),
                },
                "Color": {
                    "type": str,
                    "get": lambda s: s.color,
                    "set": lambda s, v: s.set_color(v),  # Use set_color
                    "validate": lambda v: isinstance(v, str) and v.strip() != "",
                },
                "Line Width": {
                    "type": int,
                    "get": lambda s: s.line_width,
                    "set": lambda s, v: s.set_line_width(v),  # Use set_line_width
                    "validate": lambda v: int(v) >= 0,
                },
                "Container Type": {
                    "type": str,
                    "get": lambda s: s.container_type,
                    "set": lambda s, v: s.set_container_type(v),  # Use set_container_type
                    "validate": lambda v: v in CONTAINER_TYPES,
                    "options": CONTAINER_TYPES,
                },
                "Text": {
                    "type": str,
                    "get": lambda s: s.text,
                    "set": lambda s, v: s.set_text(v),  # Model's set_text (as you have it)
                    "validate": lambda v: True,
                },
                "Path": {
                    "type": str,
                    "get": lambda s: s.path,
                    "set": lambda s, v: s.set_path(v),  # Use set_path
                },
                "Font Name": {
                    "type": str,
                    "get": lambda s: s.font_name,
                    "set": lambda s, v: s.set_font_name(v),  # Use set_font_name
                    "options": lambda _: self.model.font_manager.get_families(),
                },
                "Font Size": {
                    "type": int,
                    "get": lambda s: s.font_size,
                    "set": lambda s, v: s.set_font_size(v),
                    "validate": lambda v: v.isdigit() and int(v) > 0, # Corrected validation
                },
                "Font Weight": {
                    "type": str,
                    "get": lambda s: s.font_weight,
                    "set": lambda s, v: s.set_font_weight(v),  # Use set_font_weight
                    "options": lambda s: self.model.font_manager.get_weights_for_family(s.font_name),
                },
                "Justification": {
                    "type": str,
                    "get": lambda s: s.justification,
                    "set": lambda s, v: s.set_justification(v),  # Use set_justification
                    "options": ["left", "center", "right"],
                },
            }

    def _build_menubar(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_drawing, accelerator="Ctrl+N")
        filemenu.add_command(label="Open...", command=self.open_drawing, accelerator="Ctrl+O")
        filemenu.add_command(label="Save", command=self.save_drawing, accelerator="Ctrl+S")
        filemenu.add_command(label="Save As...", command=self.save_drawing_as, accelerator="Ctrl+Shift+S")
        filemenu.add_separator()
        filemenu.add_command(label="Import CSV file...", command=self.import_csv)
        filemenu.add_command(label="Export PDF...", command=self._on_export_pdf)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        editm  = tk.Menu(menubar, tearoff=0)
        editm.add_command(label="Remove Selected", accelerator="Del", command=self.remove_selected)
        menubar.add_cascade(label="Edit", menu=editm)
        self.root.config(menu=menubar)


    # --- Controller - Canvas Event Handlers ---

    def on_canvas_press(self, e):
        """Handles mouse button press on the canvas."""
        print(f"\nController.on_canvas_press: Raw: ({e.x}, {e.y}) - Tool: {self.current_tool}, Selected: {self.model.selected_shape}")

        # Reset all interaction states at the start of a new press
        self.is_resizing = False
        self.is_moving = False
        self.is_drawing_new_shape = False
        self.raw_drag_offset = None # Clear raw drag offset

        # Get raw and snapped click coordinates
        raw_click_x, raw_click_y = self.view.get_canvas_coords(e)
        snapped_x, snapped_y = (calculate_snap(self.model, raw_click_x, raw_click_y)
                               if self.model.snap_to_grid else (raw_click_x, raw_click_y))

        # Store the snapped start position (used for new shape drawing)
        self.start_x, self.start_y = snapped_x, snapped_y
        print(f"Controller.on_canvas_press: Snapped start: ({self.start_x}, {self.start_y})")

        # --- Check if a drawing tool is active ---
        # If a tool is active, any click on the canvas starts drawing a new shape.
        # This check is prioritized BEFORE checking for interaction with existing shapes.
        if self.current_tool:
             print(f"Controller.on_canvas_press: Tool '{self.current_tool}' active. Starting new shape drawing.")
             self.is_drawing_new_shape = True # Set state for new shape drawing
             print(f"Controller.on_canvas_press: Setting is_drawing_new_shape = {self.is_drawing_new_shape}")

             # Create the temporary preview shape on the canvas at the snapped start position
             self.view.create_preview_shape(self.current_tool, self.start_x, self.start_y)

             # When starting a new drawing, we do NOT check for existing shapes or deselect.
             return # Exit the method, as drawing is starting

        # --- If no drawing tool is active, proceed to handle interaction with existing shapes ---

        # 1. Check for interaction with the resize handle
        # This should be checked first when interacting with existing shapes
        if self.model.selected_shape is not None:
             selected_shape_instance = self.model.get_shape(self.model.selected_shape)
             if selected_shape_instance and selected_shape_instance.handle_contains(raw_click_x, raw_click_y):
                 print(f"Controller.on_canvas_press: Resize handle clicked for shape ID {self.model.selected_shape}. Setting is_resizing = True.")
                 self.is_resizing = True
                 # No need to store raw offset for resize, logic uses fixed corner and snapped drag
                 self.view.canvas.focus_set() # Ensure canvas has focus for drag events
                 return # Exit the method, as a resize is starting

        # 2. Find if an existing shape was clicked in the current layer
        found_shape_id: Optional[Any] = None
        current_layer_shapes = self.model.current_layer.shapes
        # Iterate through shape IDs in descending order to find the topmost visually
        current_layer_shape_ids_sorted_desc = sorted(current_layer_shapes.keys(), reverse=True)
        print(f"Controller.on_canvas_press: No tool active. Checking {len(current_layer_shapes)} shapes in current layer for click.")

        for shape_id in current_layer_shape_ids_sorted_desc:
            shape = current_layer_shapes.get(shape_id) # Use .get() for safe access
            # Ensure the shape object is valid and the click is within its bounds
            # Also ensure we are on the shape's layer for interaction
            # The check for the shape being on the current layer is implicitly done by getting shapes from model.current_layer
            if shape and shape.contains_point(raw_click_x, raw_click_y):
                 # If a shape contains the point, we found the topmost one in the current layer
                 found_shape_id = shape_id
                 print(f"Controller.on_canvas_press: Raw click ({raw_click_x}, {raw_click_y}) is inside topmost shape ID {found_shape_id} in current layer.")
                 break # Found the topmost interactive shape


        # 3. Handle the click based on which shape was found (or not found)
        if found_shape_id is not None:
             # An existing shape was clicked
             if self.model.selected_shape != found_shape_id:
                  # Clicked a *different* shape: Select the new shape
                  print(f"Controller.on_canvas_press: Selecting new shape ID {found_shape_id}. Calling select_shape().")
                  # select_shape updates the model, which triggers refresh_all to show selection
                  # It also handles potential UI updates via root.after()
                  self.select_shape(found_shape_id)
             else:
                 # Clicked the *already* selected shape: Prepare for moving it
                 print(f"Controller.on_canvas_press: Selected shape ID {found_shape_id} clicked again. Preparing for move.")
                 self.is_moving = True # Set the moving state
                 selected_shape_instance = self.model.get_shape(found_shape_id)
                 if selected_shape_instance:
                      self.view.canvas.focus_set() # Ensure canvas has focus for drag events
                      shape_bbox = selected_shape_instance.get_bbox # Call the method
                      shape_tl_x, shape_tl_y = shape_bbox[0], shape_bbox[1]

                      # Calculate and store the offset from the shape's top-left to the RAW click position
                      self.raw_drag_offset = (raw_click_x - shape_tl_x, raw_click_y - shape_tl_y)
                      print(f"Controller.on_canvas_press: Stored raw_drag_offset: {self.raw_drag_offset}")


                 else:
                      # Defensive: Should not happen if found_shape_id was valid, but handle
                      print(f"Controller.on_canvas_press: Error: Clicked selected shape ID {found_shape_id} but shape not found in model.")
                      self.select_shape(None) # Deselect if the shape is unexpectedly missing

             # In either case (selecting new or preparing to move existing), we're done with this press event
             return # Exit the method

        # 4. If no handle and no existing shape was clicked, and no tool was active
        else:
             # No interactive element clicked and no tool is active: Deselect any shape
             print("Controller.on_canvas_press: No interactive item clicked and no tool active. Deselecting shape.")
             # Deselect the current shape (if any). This will trigger refresh_all to remove selection visuals.
             self.select_shape(None)
             # No preview shape needed, no new shape drawing state needed.


    def on_canvas_drag(self, e):
        """Handles mouse drag on the canvas."""
        print(f"Controller.on_canvas_drag: Raw: ({e.x}, {e.y}) - State: is_drawing_new_shape={self.is_drawing_new_shape}, is_moving={self.is_moving}, is_resizing={self.is_resizing}")

        # Get raw and snapped current drag coordinates
        raw_current_x, raw_current_y = self.view.get_canvas_coords(e)
        snapped_current_x, snapped_current_y = (calculate_snap(self.model, raw_current_x, raw_current_y)
               if self.model.snap_to_grid else (raw_current_x, raw_current_y))
        print(f"Controller.on_canvas_drag: Snapped current: ({snapped_current_x}, {snapped_current_y})")


        # --- Update preview shape if drawing a new shape ---
        # Use the dedicated state variable to ensure we are in the correct mode
        if self.is_drawing_new_shape and self.current_tool:
             print("Controller.on_canvas_drag: Updating preview shape.")
             # Update preview shape using the snapped coordinates
             self.view.update_preview_shape(self.current_tool, self.start_x, self.start_y, snapped_current_x, snapped_current_y)

        # --- Handle moving or resizing the selected shape ---
        # Use the dedicated state variables
        elif self.model.selected_shape is not None:
             selected_shape_instance = self.model.get_shape(self.model.selected_shape)

             # Ensure necessary state is present
             if not selected_shape_instance:
                   print(f"Controller.on_canvas_drag: Error: Selected shape {self.model.selected_shape} not found during drag.")
                   # Reset states and deselect if the shape is missing
                   self.is_moving = False # Reset state if something is wrong
                   self.is_resizing = False
                   self.select_shape(None)
                   return

             if self.is_moving:
                  print(f"Controller.on_canvas_drag: Handling move for shape {self.model.selected_shape}.")
                  # Ensure raw_drag_offset is available for moving
                  if self.raw_drag_offset is None:
                       print(f"Controller.on_canvas_drag: Error: raw_drag_offset is None during move drag.")
                       self.is_moving = False # Cannot move without offset
                       # Optionally deselect
                       # self.select_shape(None)
                       return

                  # Calculate the desired raw top-left position based on the CURRENT RAW drag position
                  # and the RAW offset stored on press. Then SNAP this calculated position.
                  # This ensures the shape snaps correctly relative to the cursor.
                  desired_raw_tl_x = raw_current_x - self.raw_drag_offset[0]
                  desired_raw_tl_y = raw_current_y - self.raw_drag_offset[1]

                  # Apply snapping to the desired raw top-left position
                  if self.model.snap_to_grid:
                       # Snap the desired raw top-left coordinates
                       new_tl_x, new_tl_y = calculate_snap(self.model, desired_raw_tl_x, desired_raw_tl_y)
                  else:
                       # No snapping, use the raw desired top-left position
                       new_tl_x, new_tl_y = desired_raw_tl_x, desired_raw_tl_y


                  print(f"Controller.on_canvas_drag: Calculated new_tl: ({new_tl_x}, {new_tl_y}) after snapping.")


                  # Get the current dimensions from the shape's bounding box
                  current_bbox = selected_shape_instance.get_bbox # Call the method
                  width = current_bbox[2] - current_bbox[0]
                  height = current_bbox[3] - current_bbox[1]

                  # Calculate the new coordinates for the shape's bounding box
                  # Ensure coordinates are ordered min_x, min_y, max_x, max_y
                  new_coords = [new_tl_x, new_tl_y, new_tl_x + width, new_tl_y + height]
                  print(f"Controller.on_canvas_drag: Updating shape coords to: {new_coords}")

                  # Update shape coords in Model. Model.update_shape_coords notifies observers if coords change.
                  # This notification will trigger refresh_all.
                  self.model.update_shape_coords(selected_shape_instance.sid, new_coords)
                  # The View's refresh_all (triggered by model) will redraw the shape and update panels


             elif self.is_resizing:
                  print(f"Controller.on_canvas_drag: Handling resize.")
                  # Keep resize logic as is. It uses the initial fixed corner (fx, fy)
                  # from get_bbox and the current snapped drag position (snapped_x, snapped_y)
                  # which should align the dragged corner to the grid.
                  min_size = 5
                  # Get the fixed corner (top-left of the original bbox)
                  x1_bbox, y1_bbox, x2_bbox, y2_bbox = selected_shape_instance.get_bbox # Call the method
                  fx, fy = min(x1_bbox, x2_bbox), min(y1_bbox, y2_bbox) # Fixed top-left

                  # Use the current snapped drag position for the new bottom-right
                  new_x2 = snapped_current_x # Use the snapped x from the drag event
                  new_y2 = snapped_current_y # Use the snapped y from the drag event

                  # Ensure minimum size during resize
                  if abs(new_x2 - fx) < min_size: new_x2 = fx + (min_size if new_x2 > fx else -min_size)
                  if abs(new_y2 - fy) < min_size: new_y2 = fy + (min_size if new_y2 > fy else -min_size)

                  # Update shape coords in Model
                  # Pass the coordinates in the correct order for set_coords/update_shape_coords
                  # Ensure the coordinates are ordered min_x, min_y, max_x, max_y
                  ordered_coords = [min(fx, new_x2), min(fy, new_y2), max(fx, new_x2), max(fy, new_y2)]
                  print(f"Controller.on_canvas_drag: Updating shape coords to: {ordered_coords}")
                  self.model.update_shape_coords(selected_shape_instance.sid, ordered_coords)
                  # The View's refresh_all (triggered by model) will redraw the shape and update panels


        # If not in any recognized drag state, do nothing or handle as needed
        # This helps prevent unexpected behavior if state flags get out of sync
        # elif self.model.selected_shape is None and not self.is_drawing_new_shape:
        #      pass # Do nothing


    def on_canvas_release(self, e):
        """Handles mouse button release on the canvas."""
        print(f"Controller.on_canvas_release: Raw: ({e.x}, {e.y}) - State: is_drawing_new_shape={self.is_drawing_new_shape}, is_moving={self.is_moving}, is_resizing={self.is_resizing}")

        # Get final raw and snapped release coordinates
        raw_release_x, raw_release_y = self.view.get_canvas_coords(e)
        final_x, final_y = (calculate_snap(self.model, raw_release_x, raw_release_y)
               if self.model.snap_to_grid else (raw_release_x, raw_release_y))
        print(f"Controller.on_canvas_release: Final snapped: ({final_x}, {final_y})")

        # --- Handle finishing a new shape creation ---
        # Use the dedicated state variable to ensure we are in the correct mode
        if self.is_drawing_new_shape and self.current_tool:
            print("Controller.on_canvas_release: Entering new shape creation block.")
            min_dim_px = parse_dimension("5px", self.model.ppi)

            # Ensure that the start and end points are not too close to form a tiny shape
            effective_width = abs(final_x - self.start_x)
            effective_height = abs(final_y - self.start_y)

            # Adjust final_x and final_y if the dimensions are too small
            adjusted_final_x = final_x
            adjusted_final_y = final_y

            # If width is less than min_dim_px, adjust final_x
            if effective_width < min_dim_px:
                print(f"Controller.on_canvas_release: Width {effective_width} is less than min_dim {min_dim_px}. Adjusting final_x.")
                # Adjust final_x to be min_dim_px away from start_x in the direction of drag
                # If final_x is greater than start_x, add min_dim_px; otherwise subtract min_dim_px.
                # Handle the case where they are the same (click without drag)
                adjusted_final_x = self.start_x + (min_dim_px if final_x >= self.start_x else -min_dim_px)


            # If height is less than min_dim_px, adjust final_y
            if effective_height < min_dim_px:
                 print(f"Controller.on_canvas_release: Height {effective_height} is less than min_dim {min_dim_px}. Adjusting final_y.")
                 # Adjust final_y to be min_dim_px away from start_y in the direction of drag
                 # If final_y is greater than start_y, add min_dim_px; otherwise subtract min_dim_px.
                 # Handle the case where they are the same (click without drag)
                 adjusted_final_y = self.start_y + (min_dim_px if final_y >= self.start_y else -min_dim_px)

            # Special case: If both dimensions were zero (a simple click, no drag)
            # Create a small square shape at the start position
            if effective_width == 0 and effective_height == 0:
                 print(f"Controller.on_canvas_release: Both dimensions were zero (click). Creating min_dim_px square.")
                 adjusted_final_x = self.start_x + min_dim_px
                 adjusted_final_y = self.start_y + min_dim_px


            print(f"Controller.on_canvas_release: Adjusted final coordinates for shape creation: ({adjusted_final_x}, {adjusted_final_y}). Start coordinates: ({self.start_x}, {self.start_y})")


            # Create the final shape object and add it to the Model
            # _create_final_shape_object calls model.add_shape, which calls notify_observers()
            # This notification will trigger refresh_all, drawing the new shape permanently.
            print("Controller.on_canvas_release: Calling _create_final_shape_object.")
            new_shape_id = self._create_final_shape_object(adjusted_final_x, adjusted_final_y)
            print(f"Controller.on_canvas_release: _create_final_shape_object returned new shape ID: {new_shape_id}.")

            # Clear the temporary preview shape from the View
            print("Controller.on_canvas_release: Calling view.clear_preview_shape().")
            self.view.clear_preview_shape()

            # Reset drawing state variables
            print("Controller.on_canvas_release: Resetting current_tool and is_drawing_new_shape.")
            self.current_tool = None # Reset the active tool
            self.is_drawing_new_shape = False # Reset the new shape drawing state
            print(f"Controller.on_canvas_release: State after reset: is_drawing_new_shape={self.is_drawing_new_shape}, current_tool={self.current_tool}")


            # Select the newly created shape
            if new_shape_id is not None:
                print(f"Controller.on_canvas_release: New shape ID {new_shape_id} is not None. Calling select_shape().")
                # select_shape will update the model's selected shape and trigger another refresh_all.
                # This might be slightly redundant as add_shape already triggered one, but it ensures
                # the selection visuals and properties panel are updated for the new shape.
                self.select_shape(new_shape_id)
            else:
                print("Controller.on_canvas_release: New shape ID is None. Skipping shape selection.")


        # --- Handle finishing a shape move or resize ---
        # Use the dedicated state variables
        elif self.model.selected_shape is not None and (self.is_moving or self.is_resizing):
            print(f"Controller.on_canvas_release: Finishing move/resize for shape ID {self.model.selected_shape}.")
            # If moving, clean up the raw drag offset
            if self.is_moving and hasattr(self, 'raw_drag_offset') and self.raw_drag_offset is not None:
                 del self.raw_drag_offset
                 print("Controller.on_canvas_release: Cleaned up raw_drag_offset.")


            # The shape's coordinates in the model were updated during the drag
            # (via model.update_shape_coords, which notified observers).
            # The view has been refreshing during the drag.
            # At release, just ensure states are reset.
            pass # No additional model update or view refresh needed here

        # --- Ensure all drawing/interaction states are off at the end of the release ---
        print("Controller.on_canvas_release: Resetting all interaction states.")
        self.is_resizing = False
        self.is_moving = False
        # is_drawing_new_shape is reset in the new shape creation block, but ensure it's off
        # in case release happens in an unexpected state.
        if hasattr(self, 'is_drawing_new_shape') and self.is_drawing_new_shape:
             print("Controller.on_canvas_release: Resetting is_drawing_new_shape state.")
             self.is_drawing_new_shape = False

        # Also ensure raw_drag_offset is None at the end in case release happens in an unexpected state.
        if hasattr(self, 'raw_drag_offset') and self.raw_drag_offset is not None:
             print("Controller.on_canvas_release: Cleaning up raw_drag_offset state.")
             del self.raw_drag_offset


    # --- Helper method to create final shape object ---
    def _set_shape_coord(self, shape: Shape, coord_name: str, value_str: str):
        """Parses input string for X or Y, converts to pixels, and updates shape coordinates via model."""
        # Use the imported utility function
        pixel_value = parse_dimension(value_str, self.model.ppi) #

        # Check if parsing was successful
        if pixel_value is None:
            # Error message shown by messagebox in commit method
            return False # Indicate failure

        # Get current coordinates to create the new_coords list
        x1, y1, x2, y2 = shape.get_bbox # Use current bbox from shape
        width = x2 - x1
        height = y2 - y1

        # Calculate new coordinates based on the converted pixel value
        # Start with current bbox coords.
        # This will ensure min_x, min_y, max_x, max_y order is maintained by _update_coords_if_valid.
        new_coords = list(shape.get_bbox)


        if coord_name == 'x':
            new_min_x = pixel_value
            # New bbox: [new_min_x, min_y, new_min_x + width, max_y]
            new_coords = [new_min_x, y1, new_min_x + width, y2]
        elif coord_name == 'y':
            new_min_y = pixel_value
            # New bbox: [min_x, new_min_y, max_x, new_min_y + height]
            new_coords = [x1, new_min_y, x2, new_min_y + height]
        else:
             print(f"Controller._set_shape_coord: Invalid coord_name: {coord_name}")
             return False # Indicate failure

        # Call the geometry utility function to update shape coordinates with validation
        if _update_coords_if_valid(shape, new_coords): #
            return True # Indicate successful update
        else:
             print(f"Controller._set_shape_coord: Coordinates for {coord_name} did not change or were invalid for shape {shape.sid}.")
             return False # Indicate no change or invalid update

    def _set_shape_dim(self, shape: Shape, dim_name: str, value_str: str):
        """Parses input string for Width or Height, converts to pixels, and updates shape dimensions via model."""
        # Use the imported utility function
        pixel_value = parse_dimension(value_str, self.model.ppi) #

        # Check if parsing was successful
        if pixel_value is None:
            # Error message shown by messagebox in commit method
            return False # Indicate failure

        # Ensure minimum size after conversion to pixels
        min_size_px = parse_dimension("1px", self.model.ppi) # Define a minimum size in pixels (adjust as needed)
        if pixel_value < min_size_px:
             print(f"Controller._set_shape_dim: Dimension {dim_name} ({pixel_value}px) is less than minimum {min_size_px}px for shape {shape.sid}.")
             # Show a warning to the user via messagebox
             messagebox.showwarning("Size Warning", f"{dim_name} must be at least {format_pixel_output(min_size_px, self.model.ppi, self.model.measure)}.") #
             return False # Indicate failure


        # Get current coordinates to calculate the new bounding box
        x1, y1, x2, y2 = shape.get_bbox # Use current bbox from shape
        # We need the actual top-left corner as the anchor for resizing
        current_x1 = min(x1, x2) # Ensure we use the left edge as the fixed point
        current_y1 = min(y1, y2) # Ensure we use the top edge as the fixed point


        # Calculate new coordinates in pixels based on the converted pixel value
        new_coords = list(shape.get_bbox) # Start with current bbox coords

        if dim_name == 'width':
            new_width = pixel_value # Use the converted pixel value
            new_x2 = current_x1 + new_width
            new_coords = [current_x1, current_y1, new_x2, max(y1, y2)]

        elif dim_name == 'height':
            new_height = pixel_value # Use the converted pixel value
            new_y2 = current_y1 + new_height
            new_coords = [current_x1, current_y1, max(x1, x2), new_y2]

        else:
             print(f"Controller._set_shape_dim: Invalid dim_name: {dim_name}")
             return False # Indicate failure

        # Call the geometry utility function to update shape coordinates with validation
        if _update_coords_if_valid(shape, new_coords): #
            return True # Indicate successful update
        else:
             print(f"Controller._set_shape_dim: Dimensions for {dim_name} did not change or were invalid for shape {shape.sid}.")
             return False # Indicate no change or invalid update

    def _is_valid_dimension(value_str: str, ppi: float) -> bool:
        try:
            parse_dimension(value_str, self.model.ppi)
            return True
        except (ValueError, TypeError):
            return False
    def _create_final_shape_object(self, x, y) -> Optional[Any]:
        """Creates the shape object and adds it to the Model (Controller logic)."""
        print(f"Controller._create_final_shape_object: Called with final_x={x}, final_y={y}")

        # Generate a new unique shape ID
        all_shape_ids = set(self.model._shape_map.keys())
        iid = 0
        while iid in all_shape_ids:
            iid += 1
        print(f"Controller._create_final_shape_object: Generated new shape ID: {iid}")

        # Calculate the ordered coordinates for the shape's bounding box
        # These coordinates define the outer boundary of the shape
        ordered_coords = [min(self.start_x, x), min(self.start_y, y), max(self.start_x, x), max(self.start_y, y)]
        print(f"Controller._create_final_shape_object: Ordered coordinates for new shape: {ordered_coords}. Start coords: ({self.start_x}, {self.start_y})")

        new_shape = None
        # Create a new shape instance based on the current tool type
        # Pass the generated ID, calculated coordinates, and font_manager
        if self.current_tool == 'rectangle':
            new_shape = Rectangle(sid=iid, coords=ordered_coords, name=f"Rectangle {iid}", font_manager=self.font_manager)
        elif self.current_tool == 'oval':
            new_shape = Oval(sid=iid, coords=ordered_coords, name=f"Oval {iid}", font_manager=self.font_manager)
        elif self.current_tool == 'triangle':
             # Triangle needs base and apex, calculate based on bounding box
             # The Triangle class __init__ should handle converting bbox to its internal representation if needed.
             # Here we pass the bounding box coords.
            new_shape = Triangle(sid=iid, coords=ordered_coords, name=f"Triangle {iid}", font_manager=self.font_manager)
        elif self.current_tool == 'hexagon':
             # Hexagon also takes a bounding box
            new_shape = Hexagon(sid=iid, coords=ordered_coords, name=f"Hexagon {iid}", font_manager=self.font_manager)
        else:
            print(f"Controller._create_final_shape_object: Unknown tool type: {self.current_tool}. Returning None.")
            return None # If current_tool is not a valid shape type, return None

        # If a shape instance was successfully created
        if new_shape:
             print(f"Controller._create_final_shape_object: Shape instance created: {new_shape}. Adding to model.")
             # Add the new shape to the model. This method calls model.add_shape.
             # model.add_shape adds the shape to the current layer and the global map,
             # and critically, calls model.notify_observers().
             self.model.add_shape(new_shape)
             print(f"Controller._create_final_shape_object: Shape added to model. Returning shape ID: {new_shape.sid}")
             return new_shape.sid # Return the new shape's ID so it can be selected

        else:
             print("Controller._create_final_shape_object: Shape instance is None. Returning None.")
             return None # Return None if shape creation failed

    # ... (select_shape and other methods) ...

    # Ensure on_canvas_configure also checks is_moving and is_resizing
    def on_canvas_configure(self, event):
        """Handles canvas resize (Controller logic triggering View update)."""
        # Add this print statement at the start of the configure handler
        print(f"Controller.on_canvas_configure: Received configure event. Canvas size: {event.width}x{event.height}. State: is_drawing_new_shape={self.is_drawing_new_shape}, is_moving={self.is_moving}, is_resizing={self.is_resizing}")

        # Prevent refresh during any interactive drag (new shape, move, or resize)
        if self.is_drawing_new_shape or self.is_moving or self.is_resizing:
            print("Controller.on_canvas_configure: Ignoring configure event during interactive drag.")
            return

        # If not in an interactive drag, a configure event means a genuine resize.
        # Trigger a full refresh to redraw grid and shapes scaled to the new canvas size.
        print("Controller.on_canvas_configure: Triggering refresh_all due to genuine configure event.")
        self.view.refresh_all(self.model) # View refreshes based on Model state


    def select_shape(self, sid: Optional[Any]):
        if self.model.selected_shape == sid:
            self.root.after(1, lambda: self._post_selection_ui_update(sid))
            return
        self.model.selected_shape = sid
        self.view.refresh_all(self.model)  # Force immediate refresh
        self.root.after(1, lambda: self._post_selection_ui_update(sid))

    def _post_selection_ui_update(self, sid):
        """
        Called via `after(…)` once a new shape is selected.
        Ensures the layers tree, properties panel, and any other UI elements
        are updated for the newly selected shape.
        """
        # 1) Update the layers/shapes tree selection (you probably have code for that)
        #    e.g. self.view.select_tree_item_for_shape(sid)

        # 2) Fetch the real Shape object
        selected_shape = self.model.get_shape(sid)
        if selected_shape is None:
            # Nothing selected (or shape deleted), clear the properties panel
            self.view._update_properties_panel(None, self.get_refocus_info())
            return

        # 3) Now update the properties panel with the actual Shape
        self.view._update_properties_panel(
            selected_shape,
            self.get_refocus_info()
        )



    # --- Controller - Treeviews Event Handlers ---

    def on_treeview_select(self, e):
        """Handles selection changes in the Layers/Shapes treeview."""
        # Ignore during property edit (using the view's state)
        if self.view._is_editing_property:
            return

        selected_info = self.view.get_selected_treeview_item_info()

        # Deselect everything if nothing is selected in the treeview
        if selected_info is None:
            print("\nController.on_treeview_select: Nothing selected in treeview. Deselecting shape.")
            self.select_shape(None) # Deselect shape
            # Do not deselect layer automatically, keep the last selected layer active
            return

        item_type, model_id = selected_info

        if item_type == "layer":
            model_layer_idx = model_id
            print(f"\nController.on_treeview_select: Layer selected (model index {model_layer_idx}).")
            # Select the layer in the model
            if self.model.selected_layer_idx != model_layer_idx:
                 self.model.select_layer(model_layer_idx) # Model update + notify

            # When a layer is selected, deselect any shape
            self.select_shape(None)


        elif item_type == "shape":
            shape_id_to_select = model_id
            print(f"\nController.on_treeview_select: Shape selected (ID {shape_id_to_select}).")
            # Select the shape in the model
            if self.model.selected_shape != shape_id_to_select:
                 self.select_shape(shape_id_to_select) # Controller method selects shape and notifies

    # --- Controller - Property Editing ---

    def _on_treeview_double_click(self, event):
        """Handles double-click on the properties treeview to start editing (Controller logic)."""
        if self.view._is_editing_property: return
        cell_info = self.view.get_property_treeview_cell_info(event)
        if cell_info:
            row_id, col_name = cell_info
            self.view.start_editing_treeview_cell(event) # View starts editing widget

    def handle_property_edit_commit(self, shape_id: Any, property_name: str, new_value_str: str):
        """Handles the logic when a property value is committed (Controller logic)."""
        print(f"\nController.handle_property_edit_commit: shape_id={shape_id}, property='{property_name}', new value='{new_value_str}'")

        shape = self.model.get_shape(shape_id)
        if shape is None:
            print(f"Controller.handle_property_edit_commit: Shape ID {shape_id} not found. Refreshing all.")
            self.view.refresh_all(self.model)
            return

        handler = self.PROPERTY_HANDLERS.get(property_name)
        if not handler:
            print(f"Controller.handle_property_edit_commit: No handler defined for property '{property_name}'.")
            self.update_properties_panel()  # Refresh panel
            return

        stripped_value = new_value_str.strip()

        # --- UNIT CONVERSION FOR DIMENSIONS ---
        if property_name in ['X', 'Y', 'Width', 'Height']:
            try:
                parsed_px_value = parse_dimension(new_value_str, self.model.ppi)
                # pass only parsed_px_value (int) to your handler:
                raw_for_handler = str(parsed_px_value)
            except ValueError as e:
                # [error handling…]
                return
        else:
            raw_for_handler = new_value_str.strip()


        # --- VALIDATION ---
        if "validate" in handler:
            if property_name in ['X', 'Y', 'Width', 'Height']:
                # Validation is handled in the set method for dimensions
                pass
            elif not handler["validate"](stripped_value):
                print(f"Controller.handle_property_edit_commit: Validation failed for non-dimension property.")
                messagebox.showerror("Validation Error", f"Invalid input for {property_name}: '{new_value_str}'.")
                self.set_refocus_info(shape_id, property_name)
                self.update_properties_panel()
                return

        value = stripped_value

        # --- APPLY VALUE ---
        if property_name in ['X', 'Y', 'Width', 'Height']:
            # These handlers expect raw string (which we replaced with parsed px string)
            if not handler["set"](shape, stripped_value):
                print(f"Controller.handle_property_edit_commit: Failed to set dimension property {property_name}.")
                self.set_refocus_info(shape_id, property_name)
                self.update_properties_panel()
                return
        else:
            try:
                if "type" in handler and callable(handler["type"]):
                    value = handler["type"](stripped_value)
                else:
                    print(f"Controller.handle_property_edit_commit: Unsupported 'type' for property '{property_name}'")
                    return

                if "set" in handler:
                    handler["set"](shape, value)
                else:
                    setattr(shape, self._to_shape_attr_name(property_name), value)
            except ValueError:
                print(f"Controller.handle_property_edit_commit: Invalid type conversion for {property_name}.")
                messagebox.showerror("Type Error", f"Invalid input type for {property_name}: '{new_value_str}'.")
                self.set_refocus_info(shape_id, property_name)
                self.update_properties_panel()
                return
            except Exception as e:
                print(f"Error setting property {property_name}: {e}")
                return

        # --- TEXT CONTENT HANDLING ---
        if shape and property_name in ["Text", "Font Name", "Font Size", "Font Weight", "Justification"]:
            if property_name == "Text":
                shape.text = new_value_str
            shape._draw_text_content()
            self.model.notify_observers()

        # --- NON-TEXT PROPERTIES ---
        elif shape:
            self.model.notify_observers()

        self.set_refocus_info(shape_id, property_name)
        print(f"Controller.handle_property_edit_commit: Model updated for property '{property_name}'. Model notified. Refresh pending.")
        self.view.refresh_all(self.model)

    def _to_shape_attr_name(self, property_name: str) -> str:
            """Helper to convert Property Name to Shape attribute name."""
            return property_name.lower().replace(" ", "_")

    def _calc_wrap_width(self, font, available_width):
        avg_char_width = font.getlength("M")  # More accurate than 'n'
        return max(1, int(available_width / avg_char_width))

    def _max_visible_lines(self, font, available_height):
        line_height = font.getbbox("A")[3]  # Height of capital A
        return max(1, int(available_height // line_height))

    def _get_x_position(self, justification, text_width, container_width):
        return {
            "left": 0,
            "center": (container_width - text_width) // 2,
            "right": container_width - text_width
        }[justification]

    def _get_formatted_shape_properties(self, shape: Shape) -> dict:
        """
        Retrieves a shape's properties and formats dimension values
        (x, y, width, height) to strings with 'px' postfix for display.
        """
        properties = shape.to_dict() # Assuming to_dict gives raw numerical properties
        if properties:
            display_properties = properties.copy()
            
            # Use the getter from PROPERTY_HANDLERS to format for display
            for prop_name in ['X', 'Y', 'Width', 'Height']:
                handler = self.PROPERTY_HANDLERS.get(prop_name)
                if handler and "get" in handler:
                    # Pass the shape object to the getter lambda
                    display_properties[prop_name] = handler["get"](shape)
            return display_properties
        return {}


    def update_properties_panel(self):
        """Updates the properties panel with correct refocus"""
        selected_shape_data = self.model.get_shape(self.model.selected_shape)
        # Pass formatted properties to the view
        formatted_properties = self._get_formatted_shape_properties(selected_shape_data) if selected_shape_data else None
        self.view._update_properties_panel(
            formatted_properties,
            self.get_refocus_info()
        )
        self.reset_refocus_info()
        self.model.notify_observers()

    def set_refocus_info(self, shape_id: Any, property_name: str):
        """Track which property to refocus after a UI refresh."""
        self._refocus_info = (shape_id, property_name)

    def get_refocus_info(self) -> Optional[tuple]:
        """Returns (shape_id, property_name) or None."""
        return self._refocus_info

    def reset_refocus_info(self):
        """Clears the refocus tracking."""
        self._refocus_info = None


    # --- Controller - Application Actions ---

    def start_adding(self, shape_type: str):
        """Sets the current tool for adding a new shape (Controller state)."""
        print(f"\nController.start_adding: Setting tool to '{shape_type}'.")
        self.current_tool = shape_type
        self.select_shape(None) # Deselect any shape when starting to add (Controller method)


    def remove_selected(self):
        """Handles removing the currently selected shape (Controller logic)."""
        if self.view._is_editing_property: # Check View state
             print("remove_selected: Ignored during editing.")
             return

        sid = self.model.selected_shape
        if sid is None:
             print("remove_selected: No shape selected.")
             return

        print(f"remove_selected: Removing shape {sid}")
        self.model.remove_shape(sid) # Model update + notify

    def remove_selected_layer(self):
        """Handles removing the currently selected layer based on Treeview selection."""
        # Check if the View is currently editing a property
        if self.view._is_editing_property: #
             print("remove_selected_layer: Ignored during editing.")
             return

        # Get selected item info from the treeview
        selected_info = self.view.get_selected_treeview_item_info()

        # Ensure a layer is selected
        if selected_info is None or selected_info[0] != "layer":
            print("remove_selected_layer: No layer selected in the treeview.")
            return

        # Get the model layer index from the selected info
        model_layer_idx = selected_info[1] # model_id is the layer index

        print(f"remove_selected_layer: Removing layer at model index {model_layer_idx}.")

        # Call the Model method to perform the data removal
        self.model.remove_layer(model_layer_idx) # Model update + notify

    def move_selected_layer(self, direction: str):
        """Moves the currently selected layer up or down based on Treeview selection."""
        if self.view._is_editing_property:
             print("move_selected_layer: Ignored during editing.")
             return

        selected_info = self.view.get_selected_treeview_item_info()

        # Ensure a layer is selected
        if selected_info is None or selected_info[0] != "layer":
            print(f"move_selected_layer: No layer selected or selected item is not a layer in the treeview. Cannot move {direction}.")
            return

        # Get the model layer index from the selected info
        model_layer_idx = selected_info[1] # model_id is the layer index

        if direction == "up":
            print(f"move_selected_layer: Moving layer at model index {model_layer_idx} up.")
            self.model.move_layer_up(model_layer_idx) # Model update + notify
        elif direction == "down":
            print(f"move_selected_layer: Moving layer at model index {model_layer_idx} down.")
            self.model.move_layer_down(model_layer_idx) # Model update + notify
        else:
            print(f"move_selected_layer: Invalid direction '{direction}'.")
     
    def on_delete_key(self, event):
        """Handles the Delete key press (Controller logic)."""
        self.remove_selected() # Call Controller method

    def toggle_grid(self):
        """Toggles grid visibility (Controller calls Model)."""
        self.model.toggle_grid_visible() # Model update + notify

    def toggle_snap(self):
        """Toggles snap to grid (Controller calls Model)."""
        self.model.toggle_snap_to_grid() # Model update (no notify needed)


    # --- Controller - File Menu Functionality ---

    def new_drawing(self):
        """Starts a new blank drawing (Controller logic)."""
        print("\nController.new_drawing: Creating a new drawing.")
        self.model.reset() # Model reset state and notifies observers
        self.current_file_path = None # Controller state
        self.csv_data_df = None # Controller state
        self.csv_file_path = None # Controller state
        self.view.master.title("Enhanced Vector Editor - Untitled") # Update View title
        self.view.hide_merge_panel() # Update View panel visibility


    def open_drawing(self, file_path=None):
        if not file_path:

            """Opens an existing drawing file (Controller logic)."""
            print("\nController.open_drawing: Opening drawing file dialog.")
            file_path = filedialog.askopenfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if not file_path: print("Controller.open_drawing: File dialog cancelled."); return

        print(f"Controller.open_drawing: Selected file: {file_path}. Loading...")
        try:
            with open(file_path, 'r') as f: data = json.load(f)
            self.model.from_dict(data, self.font_manager) # Load data into the Model (Model updates state)
            self.current_file_path = file_path # Controller state
            self.view.master.title(f"Enhanced Vector Editor - {os.path.basename(file_path)}") # Update View title
            self.view.hide_merge_panel() # Update View panel visibility
            self.csv_data_df = None; self.csv_file_path = None; # Clear Controller state
            print(f"Controller.open_drawing: Successfully loaded drawing from {file_path}.")
            # Model.from_dict notifies observers, triggering view.refresh_all
            # Force an immediate refresh
            self.model.notify_observers()  
            self.view.refresh_all(self.model)  

        except FileNotFoundError: messagebox.showerror("Error", f"File not found:\n{file_path}")
        except json.JSONDecodeError: messagebox.showerror("Error", f"Invalid file format:\n{file_path}")
        except Exception as e: messagebox.showerror("Error", f"An error occurred:\n{e}")

    def save_drawing(self):
        """Saves the current drawing (Controller logic)."""
        if self.current_file_path: self._save_to_file(self.current_file_path)
        else: self.save_drawing_as()

    def save_drawing_as(self):
        """Saves the current drawing to a new file (Controller logic)."""
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file_path: self._save_to_file(file_path)

    def _save_to_file(self, file_path: str):
        """Internal save method (Controller logic)."""
        print(f"\nController._save_to_file: Saving model state to {file_path}.")
        try:
            model_data = self.model.to_dict()
            with open(file_path, 'w') as f: json.dump(model_data, f, indent=4)
            self.current_file_path = file_path # Controller state
            self.view.master.title(f"Enhanced Vector Editor - {os.path.basename(file_path)}") # Update View title
            print(f"Controller._save_to_file: Successfully saved drawing to {file_path}.")
        except Exception as e: messagebox.showerror("Error", f"An error occurred while saving:\n{e}")
    # --- Controller - Import as Component ---

    def import_component_from_file(self, filepath, max_nesting=2):
        data = load_json(filepath)
        component = parse_component_data(data, current_depth=0, max_depth=max_nesting)
        self.model.components.append(component)

    def parse_component_data(self, data, current_depth, max_depth): # Added self
        if current_depth >= max_depth:
            # Assuming flatten_component_to_image is a helper that returns a compatible shape data
            # This part needs to be implemented or defined in your model/shape structure.
            # For now, this is a placeholder.
            print("Warning: `flatten_component_to_image` is a placeholder and not implemented.")
            return {} # Return an empty dict or a simplified representation

        layers = []
        for layer_data in data["layers"]:
            if "component" in layer_data:
                layers.append(self.parse_component_data(layer_data["component"], current_depth + 1, max_depth)) # Added self
            else:
                # Assuming LayerModel.from_dict exists and returns a Layer object
                layers.append(Layer.from_dict(layer_data, self.font_manager)) # Assuming Layer.from_dict for layers

        # Assuming ComponentModel is a class that can take layers
        # This also needs to be defined in your model if it's a specific component structure.
        # For now, just returning a list of layers/data.
        print("Warning: `ComponentModel` is a placeholder concept and not fully implemented.")
        return {"component_layers": layers}


    def create_component_from_selected_layers(self):
        selected = self.layer_panel.get_selected_layers() # layer_panel attribute not defined
        if not selected:
            return
        # This part assumes a ComponentModel and direct manipulation of model.layers
        # This needs more context from your model/view implementation.
        # For now, it's commented out as it relies on undefined attributes/classes.
        # component = ComponentModel(selected)
        # self.model.components.append(component)
        # for layer in selected:
        #     self.model.layers.remove(layer)
        # self.refresh_view()
        print("Warning: `create_component_from_selected_layers` relies on undefined attributes/classes and is not fully implemented.")


    # --- Controller - CSV Import and PDF Export ---

    def import_csv(self, path=None):
        if not path: 
            """Handles importing a CSV file (Controller logic)."""
            print("\nController.import_csv: Opening file dialog for CSV import.")
            path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
            if not path: print("Controller.import_csv: CSV file dialog cancelled."); return

        print(f"Controller.import_csv: Selected CSV file: {path}. Loading...")
        try:
            self.csv_data_df = pd.read_csv(path) # Controller state
            self.csv_file_path = path # Controller state
            print(f"Controller.import_csv: Successfully loaded {len(self.csv_data_df)} entries from {path}.")

            self.view.show_merge_panel() # Update View panel visibility
            # Model state needs to be updated for merge status panel? No, View reads Model/Controller state
            self.view.refresh_all(self.model) # Trigger full View refresh including merge panel
            if not path:
                messagebox.showinfo("Success", f"Loaded {len(self.csv_data_df)} entries from\n{os.path.basename(path)}")
        except Exception as e:
            print(f"Controller.import_csv: Failed to load CSV from {path}: {e}")
            messagebox.showerror("Error", f"Failed to load CSV:\n{e}")
            self.csv_data_df = None; self.csv_file_path = None; # Clear Controller state
            self.view.hide_merge_panel() # Ensure panel is hidden on error
            self.view.refresh_all(self.model) # Refresh View

    def get_csv_data(self) -> Optional[pd.DataFrame]:
         """Provides CSV data to the View (Controller provides data to View)."""
         return self.csv_data_df


    def _on_export_pdf(self):
        """Handles the PDF export menu action (Controller logic)."""
        print("\nController._on_export_pdf: PDF export initiated.")

        # 1) Ask for output file
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")]
        )
        if not path:
            print("Controller._on_export_pdf: Export cancelled.")
            return

        # 2) We check for import data, if it's there we use the import_from_csv(path)

        # 2) Should we use standard card layout?
        use_card = messagebox.askyesno(
            "Export as Cards?",
            "Export using standard card size (2.5×3.5 in or 63.5×89 mm)?"
        )
        width = height = None
        if not use_card:
            dims = simpledialog.askstring(
                "Component Size",
                "Enter width and height in inches (e.g. 5,7):"
            )
            if dims:
                try:
                    w_str, h_str = dims.split(",")
                    width, height = float(w_str), float(h_str)
                    custom_size = (width, height) # Define custom_size here
                except ValueError:
                    messagebox.showerror(
                        "Invalid Input",
                        "Please supply two positive numbers separated by a comma."
                    )
                    return
            else:
                return  # user cancelled
        else:
            custom_size = None # Ensure custom_size is None if not using it


        # 3) Ask page size
        page_choice = simpledialog.askstring(
            "Page Size",
            "Choose page size: LETTER or A4",
            initialvalue="LETTER"
        )
        if page_choice is None:
            return
        page_choice = page_choice.strip().upper()
        if page_choice not in ['LETTER', 'A4']:
            messagebox.showerror(
                "Invalid Input",
                "Page size must be LETTER or A4."
            )
            return

        # 4) If using cards, ask how many per page (8 or 9)
        cards_per_page = None
        rotate_flag = False
        if use_card:
            answer = simpledialog.askinteger(
                "Cards Per Page",
                "How many cards per page? (8 or 9)",
                initialvalue=9,
                minvalue=1,
                maxvalue=9
            )
            if answer not in (8, 9):
                messagebox.showerror(
                    "Invalid Input",
                    "Please enter 8 or 9."
                )
                return
            cards_per_page = answer

            # On A4 with 8-up, we auto-rotate
            if cards_per_page == 8 and page_choice == 'A4':
                rotate_flag = True

         # --- CALL THE EXPORT METHOD ---
        print("Controller._on_export_pdf: Calling export_to_pdf...")
        try:
            self.export_to_pdf(
                export_path=path,
                page=page_choice,
                use_card=use_card,
                custom_size=custom_size, # Pass the custom size tuple
                cards_per_page=cards_per_page,
                rotate_card=rotate_flag
            )
        except Exception as e:
            # The export_to_pdf method already has error handling and messageboxes,
            # but a final catch here can be useful too.
            print(f"Controller._on_export_pdf: Error after calling export_to_pdf: {e}")
            # messagebox.showerror("Export Error", f"An error occurred during PDF export:\n{e}\nCheck console for details.")


    def export_to_pdf(self,
                      export_path: str,
                      page: str = 'LETTER',
                      use_card: bool = False,
                      custom_size: tuple[float, float] | None = None,
                      cards_per_page: int | None = None,
                      rotate_card: bool = False):
        """
        Exports the drawing to a PDF, supporting 8-up/9-up card layouts or custom sizes.
        """
        import io
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.pagesizes import LETTER, A4
        from reportlab.lib.units import inch
        from PIL import Image as PILImage

        print(f"\nExporting PDF to {export_path}, page={page}, use_card={use_card}, cards={cards_per_page}, rotate={rotate_card}")
        pagesize = LETTER if page.upper()=='LETTER' else A4
        pw, ph = pagesize
        RENDER_DPI = 300

        # Standard card dims
        cw_in, ch_in = (2.5,3.5)
        cw_pt, ch_pt = cw_in*inch, ch_in*inch

        # Determine grid layout
        if use_card and cards_per_page in (8,9):
            if cards_per_page==9:
                cols, rows = 3,3; rotate_card=False
                cell_w_pt, cell_h_pt = cw_pt, ch_pt
            else:  # 8-up
                cols, rows = 2,5; rotate_card=True
                cell_w_pt, cell_h_pt = ch_pt, cw_pt
            grid_w_pt, grid_h_pt = cols*cell_w_pt, rows*cell_h_pt
            grid_w_px = int(round(grid_w_pt*RENDER_DPI/72)); grid_h_px = int(round(grid_h_pt*RENDER_DPI/72))
            print(f"Grid {cols}x{rows}, px {grid_w_px}x{grid_h_px}")
            # Prepare PDF
            pdf = pdf_canvas.Canvas(export_path, pagesize=pagesize)
            records = (self.csv_data_df.to_dict('records') if getattr(self,'csv_data_df',None) is not None else [{}]) or [{}]
            mb = self.model.get_model_bounds()
            # Render in batches of cards_per_page
            for start in range(0, len(records), cards_per_page):
                recs = records[start:start+cards_per_page]
                grid_img = PILImage.new('RGBA', (grid_w_px,grid_h_px), (255,255,255,0))
                cell_w_px = int(round(cell_w_pt*RENDER_DPI/72)); cell_h_px = int(round(cell_h_pt*RENDER_DPI/72))
                for i,row in enumerate(recs):
                    cimg = self.view.render_merged_card(row, self.model, mb, (cell_w_pt,cell_h_pt))
                    if rotate_card:
                        cimg = rotate_image_90_clockwise(cimg)
                    if cimg.mode!='RGBA': cimg=cimg.convert('RGBA')
                    # ensure size
                    if cimg.size!=(cell_w_px,cell_h_px):
                        cimg=cimg.resize((cell_w_px,cell_h_px), PILImage.Resampling.LANCZOS)
                    x = (i%cols)*cell_w_px; y = (i//cols)*cell_h_px
                    grid_img.paste(cimg, (x,y), cimg)
                # embed grid_img
                buf = io.BytesIO(); grid_img.save(buf,'PNG'); buf.seek(0)
                # center
                ex = (pw-grid_w_pt)/2; ey = (ph-grid_h_pt)/2
                pdf.drawInlineImage(PILImage.open(buf), ex, ey, width=grid_w_pt, height=grid_h_pt, preserveAspectRatio=False)
                pdf.showPage()
            pdf.save()
            print("PDF export complete.")
            return
        # Fallback: custom or single layout
        pdf = pdf_canvas.Canvas(export_path, pagesize=pagesize)
        records = (self.csv_data_df.to_dict('records') if getattr(self,'csv_data_df',None) is not None else [{}]) or [{}]
        mb = self.model.get_model_bounds()
        # determine cell size
        if use_card:
            cw, ch = cw_pt, ch_pt
        elif custom_size:
            cw, ch = custom_size[0]*inch, custom_size[1]*inch
        else:
            cw, ch = pw, ph
        cols = max(int(pw//cw),1); rows = max(int(ph//ch),1)
        per = cols*rows
        cw = pw/cols; ch = ph/rows
        for start in range(0,len(records),per):
            recs = records[start:start+per]
            for i,row in enumerate(recs):
                x0 = (i%cols)*cw; y0 = ph - ((i//cols)+1)*ch
                cimg = self.view.render_merged_card(row,self.model,mb,(cw,ch))
                buf = io.BytesIO(); cimg.save(buf,'PNG'); buf.seek(0)
                pdf.drawInlineImage(PILImage.open(buf), x0, y0, width=cw, height=ch, preserveAspectRatio=False)
            pdf.showPage()
        pdf.save()
        print("PDF export complete.")

    def _raise_window(self):
            self.root.deiconify() # Ensure window is not minimized
            # Schedule lift and potentially topmost after a short delay
            self.root.after(100, self._perform_raise) # Delay by 100 milliseconds

    def _perform_raise(self):
            self.root.lift()
            self.root.attributes('-topmost', True) # Use topmost here
            self.root.after(100, lambda: self.root.attributes('-topmost', False)) # Turn off topmost
            self.root.focus_force() # Attempt to force focus


def rotate_image_90_clockwise(img: Image) -> Image:
    """Returns a new image rotated 90 degrees clockwise."""
    # Use ROTATE_270 for clockwise rotation
    return img.transpose(Image.Transpose.ROTATE_270)

