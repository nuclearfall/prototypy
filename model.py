from typing import List, Dict, OrderedDict, Optional, Any # For type hinting
import tkinter as tk
# Assuming FontManager is in utils/font_manager.py
from utils.font_manager import FontManager

# Assuming Shape and its subclasses' factory method is in shapes/base_shape.py
# The Layer class will call Shape.from_dict, so we need to import the base Shape class
from shapes.base_shape import Shape # Import the base Shape class

# Assuming geometry utility functions are in utils/geometry.py
from utils.geometry import _update_coords_if_valid, parse_dimension # For updating shape coordinates

# Assuming constants are in a central constants.py at the root level
from constants import PPI, GRID_SIZE, SHAPE_TYPES # Example constant

# Note: The specific shape subclasses (Rectangle, Oval, etc.) are not directly
# imported here because the Layer.from_dict method will use the Shape.from_dict
# factory method, which handles importing and instantiating the correct subclass.

class Layer:
    def __init__(self, name, font_manager):
        self.name = name
        self.font_manager = font_manager
        self.shapes: OrderedDict[Any, Shape] = {} # Dictionary mapping shape ID to Shape object

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Layer instance to a dictionary using Shape.to_dict()."""
        return {
            'name': self.name,
            'shapes': {
                # Call shape.to_dict() for each shape
                str(sid): shape.to_dict() # Convert sid to string for JSON keys
                for sid, shape in self.shapes.items()
                if isinstance(shape, Shape) # Ensure it's a Shape instance
            }
        }


    @staticmethod
    # Accept font_manager (passed from DrawingModel.from_dict)
    def from_dict(data: Dict[str, Any], font_manager: FontManager):
        """Creates a Layer instance from a dictionary using Shape.from_dict()."""
        # Note: font_manager is passed from DrawingModel.from_dict
        # Pass font_manager to the Layer constructor too, as Layer needs it for new shapes
        layer = Layer(data.get('name', 'Unnamed Layer'), font_manager)

        shapes_data = data.get('shapes', {})
        # Ensure shapes_data is a dictionary before iterating
        if not isinstance(shapes_data, dict):
             print(f"Layer.from_dict: Warning: 'shapes' data is not a dictionary for layer '{layer.name}'. Skipping shapes from this layer.")
             return layer # Return layer with no shapes


        for sid_str, shape_data in shapes_data.items():
            # Ensure shape_data is a dictionary
            if not isinstance(shape_data, dict):
                 print(f"Layer.from_dict: Warning: Shape data for key '{sid_str}' is not a dictionary in layer '{layer.name}'. Skipping.")
                 continue # Skip invalid shape data

            try:
                # The key in the dictionary IS the string version of the shape ID
                # Convert the string key back to an integer ID for the Shape object
                sid = int(sid_str)
                # Add the integer sid to the shape_data dictionary, as Shape.from_dict expects it
                shape_data['id'] = sid # Use 'id' to match the Shape.__init__ parameter name

                # Use the Shape.from_dict factory method to create the shape instance
                # Pass the full shape_data dictionary and the font_manager
                shape = Shape.from_dict(shape_data, font_manager)

                if shape:
                     # Add the created shape to the layer's shapes dictionary
                     # Use the shape's actual ID as the key
                     layer.shapes[shape.sid] = shape
                else:
                     print(f"Layer.from_dict: Failed to create shape from data for key '{sid_str}' in layer '{layer.name}': {shape_data}")

            except ValueError:
                 print(f"Layer.from_dict: Warning: Invalid shape ID key (not an integer string) in data for layer '{layer.name}': '{sid_str}'. Skipping.")
            except Exception as e:
                 print(f"Layer.from_dict: Unexpected error processing shape data for key '{sid_str}' in layer '{layer.name}': {e}")
                 import traceback
                 traceback.print_exc()


        return layer

class ComponentModel:
    def __init__(self, layers, name=None):
        self.layers = layers  # list of LayerModel or pre-flattened Shapes
        self.name = name or "Component"
        self.id = uuid.uuid4().hex
        self.flatten_cache = None
        self.dirty = True

    def get_bounds(self):
        pass


class DrawingModel:
    def __init__(self, font_manager):
        self.font_manager = font_manager

        # ── Detect true screen PPI ──────────────────────────────────────────
        root = tk.Tk()
        px_width  = root.winfo_screenwidth()     # e.g. 1920 px
        mm_width  = root.winfo_screenmmwidth()   # e.g. 509 mm
        root.destroy()
        # Convert mm → inches → pixels per inch
        self.ppi = px_width / (mm_width / 25.4)

        # ── Measurement unit (two-letter code matched by parse_dimension) ───
        self.measure = "in"   # or "cm", "mm", etc.

        # ── Grid configuration ───────────────────────────────────────────────
        # How many *full-unit* ticks per unit? (e.g. 1 for inches)
        self.grid_division      = 1

        # How many *minor* ticks per full-unit? (e.g. 4 → 1/4″)
        self.grid_subdivision   = 8

        # How many micro-ticks per full-unit? (used if you want 16th-inch)
        self.grid_subsubdivision = 16

        # How many *mid-ticks* per full-unit? (e.g. 2 → 1/2″)
        #                                                    ^–– this is your “quarter of full”
        self.grid_mid_division  = 4

        # ── Compute pixel spacings ─────────────────────────────────────────
        # 1 full unit (1 in) → px
        one_unit_px = parse_dimension(f"1 {self.measure}", ppi=self.ppi)

        # Minor tick spacing (e.g. ¼″)
        self.grid_minor_px = one_unit_px / self.grid_subdivision

        # Mid tick spacing (e.g. ½″) — you can also compute as minor * (subdivision/mid_division)
        self.grid_mid_px   = one_unit_px / self.grid_mid_division

        # Major tick spacing (e.g. 1″)
        self.grid_major_px = one_unit_px / self.grid_division

        # ── Other model state ──────────────────────────────────────────────
        self.layers: List[Layer] = []
        self.selected_layer_idx = 0
        self._shape_map: Dict[Any, Shape] = {}
        self.selected_shape: Optional[Any] = None
        self.grid_visible = True
        self.snap_to_grid = True

        # Observer callbacks
        self._observers: List[Callable] = []

        # Initialize model data
        self.reset()

    def reset(self):
        self.layers = [Layer("Background", self.font_manager)]

    @property
    def current_layer(self) -> Layer:
        if 0 <= self.selected_layer_idx < len(self.layers): return self.layers[self.selected_layer_idx]
        return self.layers[0] if self.layers else Layer("Default")

    def reset(self):
        self.layers = [Layer("Background", self.font_manager)]
        self.selected_layer_idx = 0
        self.selected_shape = None
        self._shape_map = {}
        # current_file_path reset is Controller responsibility
        self.notify_observers()

    def to_dict(self):
        return {
            'layers': [layer.to_dict() for layer in self.layers],
            #'selected_layer_idx': self.selected_layer_idx,
            #'grid_size': self.grid_size,
            #'grid_visible': self.grid_visible,
            #'snap_to_grid': self.snap_to_grid,
        }


    def from_dict(self, data: Dict[str, Any], font_manager: FontManager): # Accept the font_manager
        # Ensure font_manager is available when creating Layers and Shapes
        # It's already an instance attribute of DrawingModel

        loaded_layers_data = data.get('layers', [Layer("Background", self.font_manager).to_dict()])
        if not isinstance(loaded_layers_data, list):
             print("DrawingModel.from_dict: Warning: 'layers' data is not a list. Using default layer.")
             loaded_layers_data = [Layer("Background", self.font_manager).to_dict()]

        # Pass self.font_manager to Layer.from_dict
        self.layers = [Layer.from_dict(layer_data, self.font_manager) for layer_data in loaded_layers_data]

        if not self.layers:
            self.layers.append(Layer("Background", self.font_manager)) # Ensure at least one layer

        self.selected_layer_idx = data.get('selected_layer_idx', 0)
        if not (0 <= self.selected_layer_idx < len(self.layers)):
            self.selected_layer_idx = 0

        # Load grid settings
        # Assuming GRID_SIZE is imported from constants
        # self.grid_size = data.get('grid_size', GRID_SIZE)
        # self.grid_visible = data.get('grid_visible', True)
        # self.snap_to_grid = data.get('snap_to_grid', True)


        self.selected_shape = None # Reset transient state
        self._refresh_shape_map() # Rebuild the shape map after loading layers

        # Don't notify observers here if loading is part of a larger operation (e.g., open_drawing).
        # The controller's open_drawing method will call view.refresh_all after loading the model.
        # If you do notify here, ensure it's safe to redraw before the controller is fully set up.
        # self.notify_observers()


    def _refresh_shape_map(self):
        self._shape_map = {}
        for layer in self.layers:
            for sid, shape in layer.shapes.items():
                if isinstance(shape, Shape): self._shape_map[sid] = shape

    def add_layer(self, name: Optional[str]=None):
        name = name or f"Layer {len(self.layers)}"
        self.layers.append(Layer(name, self.font_manager))
        self.selected_layer_idx = len(self.layers)-1
        self.notify_observers()

    def remove_layer(self, idx: int): # Renamed for clarity, takes index
        if len(self.layers) <= 1: print("Cannot remove the last layer."); return
        if idx == 0 and self.layers[0].name == "Background": print("Cannot remove the Background layer."); return
        if not (0 <= idx < len(self.layers)): return # Validate index

        shapes_to_remove_ids = list(self.layers[idx].shapes.keys())
        del self.layers[idx]
        self.selected_layer_idx = min(self.selected_layer_idx, len(self.layers) - 1)
        self.selected_shape = None # Deselect if selected shape was in removed layer

        for sid in shapes_to_remove_ids:
             if sid in self._shape_map: del self._shape_map[sid]

        self.notify_observers()

    def move_layer_up(self, idx: int): # Takes index
        if idx >= len(self.layers)-1 or idx < 0 or (idx == 0 and self.layers[0].name == "Background"): return
        self.layers[idx], self.layers[idx+1] = self.layers[idx+1], self.layers[idx]
        if self.selected_layer_idx == idx: self.selected_layer_idx += 1
        elif self.selected_layer_idx == idx + 1: self.selected_layer_idx -= 1
        self.notify_observers()

    def move_layer_down(self, idx: int): # Takes index
        if idx <= 0 or idx >= len(self.layers) or (idx == 1 and self.layers[0].name == "Background"): return
        self.layers[idx], self.layers[idx-1] = self.layers[idx-1], self.layers[idx]
        if self.selected_layer_idx == idx: self.selected_layer_idx -= 1
        elif self.selected_layer_idx == idx - 1: self.selected_layer_idx += 1
        self.notify_observers()

    def select_layer(self, idx: int):
            if 0 <= idx < len(self.layers):
                self.selected_layer_idx = idx
                self.selected_shape = None # Deselect shape when layer changes
                self.notify_observers()

    def get_shape(self, sid: Any) -> Optional[Shape]:
        return self._shape_map.get(sid)

    def get_sid(self, shape):
        for k, v in self._shape_map.items():
            if v == shape:
                return k 

    ## Currently being used strictly for export but may be handy elsewhere...
    def get_model_bounds(self) -> tuple[int, int, int, int]:
        xs, ys = [], []
        for layer in self.layers:
            for shape in layer.shapes.values():
                min_x, min_y, max_x, max_y = shape.get_bbox
                xs.extend([min_x, max_x])
                ys.extend([min_y, max_y])

        if not xs or not ys:
            return (0, 0, 100, 100)
        return (min(xs), min(ys), max(xs), max(ys))

    # In the DrawingModel class, inside the add_shape method, BEFORE self.notify_observers():
    def add_shape(self, shape: Shape):
        """Adds a shape to the current layer and the global shape map."""
        if not isinstance(shape, Shape):
             print("DrawingModel.add_shape: Error: Attempted to add a non-Shape object.")
             return

        if not self._shape_map:
            iid = 0
        else:
            iid = max(self._shape_map.keys()) + 1
        shape.sid = iid # Assign the generated unique ID


        # Add the shape to the current layer's shapes dictionary
        self.current_layer.shapes[shape.sid] = shape
        # Add the shape to the global shape map
        self._shape_map[shape.sid] = shape

        # --- Add this print statement ---
        print(f"DrawingModel.add_shape: Shape ID {shape.sid} added to layer '{self.current_layer.name}'. Layer shapes keys BEFORE notify: {list(self.current_layer.shapes.keys())}")
        # -------------------------------

        self.notify_observers() # Notify observers that the model has changed


    def remove_shape(self, sid: Any):
        shape_to_remove = self.get_shape(sid)
        if shape_to_remove is None: return

        found_layer = None
        for layer in self.layers:
            if sid in layer.shapes: found_layer = layer; break

        if found_layer:
            del found_layer.shapes[sid]
            if sid in self._shape_map: del self._shape_map[sid]
            if self.selected_shape == sid: self.selected_shape = None
            self.notify_observers()

    # Model methods for updating shape properties - called by Controller
    def update_shape_coords(self, sid: Any, new_coords: List[int]):
        shape = self.get_shape(sid)
        if shape and _update_coords_if_valid(shape, new_coords):
            self.notify_observers()

    def rename_shape(self, sid: Any, new_name: str):
        shape = self.get_shape(sid)
        if shape and shape.name != new_name: 
            shape.name = new_name; 
            self.notify_observers()

    def set_container(self, sid: Any, container_type: str):
        shape = self.get_shape(sid)
        if shape and shape.container_type != container_type:
             shape.container_type = container_type
             shape.content = None # Clear content on type change for reload
             self.notify_observers()

    def set_path(self, sid: Any, path: str):
        shape = self.get_shape(sid)
        if shape and shape.path != path:
             shape.path = path
             shape.content = None # Clear old image content for reload
             self.notify_observers()

    # Handled directly by the shape.
    # def set_line_width(self, sid: Any, line_width: int):
    #     shape = self.get_shape(sid)
    #     if shape and shape.line_width != line_width: shape.line_width = line_width; self.notify_observers()

    def reclassify_shape(self, sid: Any, new_shape_type: str):
        old_shape = self.get_shape(sid)
        if not old_shape or new_shape_type not in SHAPE_TYPES: return
        if new_shape_type == old_shape.shape_type: return

        coords_for_new_shape = old_shape.coords

        # if new_shape_type == 'rectangle': new_shape = Rectangle(id=sid, coords=coords_for_new_shape, name=old_shape.name)
        # elif new_shape_type == 'oval': new_shape = Oval(id=sid, coords=coords_for_new_shape, name=old_shape.name)
        # elif new_shape_type == 'triangle':
        #     bbox = old_shape.get_bbox
        #     coords_for_new_shape = [bbox[0], bbox[1], bbox[2], bbox[3]]
        #     new_shape = Triangle(id=sid, coords=coords_for_new_shape, name=old_shape.name)
        # elif new_shape_type == 'hexagon':  # Add hexagon case
        #     new_shape = Hexagon(id=sid, coords=coords_for_new_shape, name=old_shape.name)
        # else: return
        print("attempting to reclassify")
        old_shape_data = old_shape.to_dict()
        old_shape_data['shape_type'] = new_shape_type
        print(old_shape_data)
        new_shape = Shape.from_dict(old_shape_data, self.font_manager)
        print(new_shape.sid, new_shape.shape_type)

        found_layer = None
        for layer in self.layers:
            if sid in layer.shapes: found_layer = layer; break

        if found_layer and new_shape:
             found_layer.shapes[sid] = new_shape
             self._shape_map[sid] = new_shape
             self.notify_observers()

    def toggle_grid_visible(self): # Renamed
        self.grid_visible = not self.grid_visible
        self.notify_observers()

    def toggle_snap_to_grid(self): # Renamed
        self.snap_to_grid = not self.snap_to_grid
        # No notify_observers here as snap state doesn't change drawing directly

    def add_observer(self, fn):
        if callable(fn): self._observers.append(fn)

    def notify_observers(self):
        for cb in list(self._observers):
            try: cb()
            except Exception as e: print(f"Error calling model observer callback {cb.__name__}: {e}")
