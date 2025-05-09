import os
import argparse
import io
import tkinter as tk
from tkinter import ttk, simpledialog, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
from typing import List, Dict, Optional, Any
import math
import json
import pandas as pd
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.units import inch
import textwrap
from io import BytesIO

# ─── Constants ──────────────────────────────────────────────────────────────────
GRID_SIZE = 20
CANVAS_WIDTH = 800 # Keep for initial window size hint
CANVAS_HEIGHT = 600 # Keep for initial window size hint
PANEL_WIDTH = 200
TOOLBAR_HEIGHT = 40
SHAPE_BUTTONS = {
    'rectangle': '▭',
    'triangle':  '△',
    'oval':      '◯',
    'hexagon':   '⬢',  # Add hexagon button
}
CONTAINER_TYPES = ['Text', 'Image']
SHAPE_TYPES = list(SHAPE_BUTTONS.keys())

# Property handlers are now used by the Controller to know how to interact with the Model's Shapes
PROPERTY_HANDLERS = {
    "Name": {
        "type": str,
        "get": lambda s: s.name,
        "set": lambda s, v: setattr(s, "name", v),
        "validate": lambda v: v.strip() != "",
        # Removed "on_change": "update_merge_panel" - Controller handles side effects of model changes
    },
    "Shape Type": {
        "validate": lambda v: v in SHAPE_TYPES,
        "get": lambda s: s.type,
        "set": lambda s, v: setattr(s, "shape_type", v),
        # Removed "on_change": "reclassify_shape" - Controller handles this logic
        "options": SHAPE_TYPES
    },
    "X": {
        "type": int,
        # Removed "update_coords" - Controller calls model methods
    },
    "Y": {
        "type": int,
        # Removed "update_coords" - Controller calls model methods
    },
    "Width": {
        "type": int,
        # Removed "update_coords" - Controller calls model methods
    },
    "Height": {
        "type": int,
        # Removed "update_coords" - Controller calls model methods
    },
    "Color": {
        "type": str,
        "get": lambda s: s.color,
        "set": lambda s, v: setattr(s, "color", v), # Basic setter remains
        "validate": lambda v: v.strip() != ""
    },
    "Line Width": {
        "type": int,
        "get": lambda s: s.line_width,
        "set": lambda s, v: setattr(s, "line_width", v), # Basic setter remains
        "validate": lambda v: int(v) >= 0
    },
    "Container Type": {
        "get": lambda s: s.container_type,
        "set": lambda s, v: setattr(s, "container_type", v), # Basic setter remains
        "validate": lambda v: v in CONTAINER_TYPES,
        # Removed "on_change": "set_container" - Controller handles this
        "options": CONTAINER_TYPES # Added options for Combobox
    },
    "Text": {
        "type": str,
        "get": lambda s: s.text,
        "set": lambda s, v: setattr(s, "text", v) # Basic setter remains
    },
    "Path": {
        "type": str,
        "get": lambda s: s.path,
        "set": lambda s, v: setattr(s, "path", v) # Basic setter remains
    }
}

# Utility Functions (Can remain outside classes or be in a Utils module)

def move_coords_x(shape, new_x):
    coords = shape.coords.copy()
    min_x, max_x = min(coords[0], coords[2]), max(coords[0], coords[2])
    dx = new_x - min_x
    new_coords = [coords[0] + dx, coords[1], coords[2] + dx, coords[3]]
    return _update_coords_if_valid(shape, new_coords)

def move_coords_y(shape, new_y):
    coords = shape.coords.copy()
    min_y, max_y = min(coords[1], coords[3]), max(coords[1], coords[3])
    dy = new_y - min_y
    new_coords = [coords[0], coords[1] + dy, coords[2], coords[3] + dy]
    return _update_coords_if_valid(shape, new_coords)

def resize_width(shape, new_width):
    coords = shape.coords.copy()
    min_x, max_x = min(coords[0], coords[2]), max(coords[0], coords[2])
    # Anchor the left side (min_x) and adjust the right side
    new_coords = [min_x, coords[1], min_x + max(0, new_width), coords[3]]
    return _update_coords_if_valid(shape, new_coords)

def resize_height(shape, new_height):
    coords = shape.coords.copy()
    min_y, max_y = min(coords[1], coords[3]), max(coords[1], coords[3])
    # Anchor the top side (min_y) and adjust the bottom side
    new_coords = [coords[0], min_y, coords[2], min_y + max(0, new_height)]
    return _update_coords_if_valid(shape, new_coords)

def _update_coords_if_valid(shape, new_coords, min_size=5):
    min_x, max_x = min(new_coords[0], new_coords[2]), max(new_coords[0], new_coords[2])
    min_y, max_y = min(new_coords[1], new_coords[3]), max(new_coords[1], new_coords[3])
    if (max_x - min_x) >= min_size and (max_y - min_y) >= min_size:
        if shape.coords != new_coords:
            shape.coords = new_coords
            return True
    return False

# ——— Custom Layer Panel Treeview ———————————————————————————————————————————————

class LayerTree(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.tree = ttk.Treeview(self, show="tree", selectmode="extended")
        self.tree.pack(fill="both", expand=True)

        self.items = {}
        self.drag_selection = []
        self.drop_target = None

        self.tree.tag_configure("drop_target", background="#ccccff")

        # Top control buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=4)

        tk.Button(btn_frame, text="Add Layer", command=self.add_layer).pack(side="left")
        tk.Button(btn_frame, text="Delete Selected", command=self.delete_selected).pack(side="left")
        tk.Button(btn_frame, text="Group Selected", command=self.group_selected).pack(side="left")

        self.tree.bind("<ButtonPress-1>", self.on_button_press)
        self.tree.bind("<B1-Motion>", self.on_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self.on_button_release)
        self.tree.bind("<Double-1>", self.on_rename)

        # Add initial layers
        for name in ["Background", "Sketch", "Ink", "Color", "Effects"]:
            self.add_layer(name)

    def add_layer(self, name=None):
        selection = self.tree.selection()
        if selection:
            ref_item = selection[0]
            if self.items.get(ref_item, {}).get("type") == "group":
                parent = ref_item
                index = "end"
            else:
                parent = self.tree.parent(ref_item)
                index = self.tree.index(ref_item)
        else:
            parent = ""
            index = 0

        # Generate unique layer name if not provided
        if not name:
            existing_names = {
                self.tree.item(i, "text")
                for i in self.tree.get_children("")
            }
            i = 1
            while (name := f"Layer {i}") in existing_names:
                i += 1

        # Insert layer
        item_id = self.tree.insert(parent, index, text=name)
        self.items[item_id] = {"type": "layer", "name": name}
        self.tree.selection_set(item_id)
        return item_id

    def delete_selected(self):
        for item in self.tree.selection():
            self.tree.delete(item)
            self.items.pop(item, None)

    def group_selected(self):
        selected = self.tree.selection()
        if len(selected) < 2:
            print("Select at least two layers to group.")
            return
        group_id = self.tree.insert("", "end", text="Group", open=True)
        self.items[group_id] = {"type": "group", "children": []}

        for item in selected:
            self.tree.move(item, group_id, "end")
            self.items[group_id]["children"].append(self.items.pop(item, None))

    def on_button_press(self, event):
        item = self.tree.identify_row(event.y)

        # Let treeview manage selection (supports Ctrl, Shift)
        # Only prepare drag if click is on an item
        if item:
            self.drag_selection = self.tree.selection()
        else:
            self.drag_selection = []

    def on_drag_motion(self, event):
        if not self.drag_selection:
            return
        target = self.tree.identify_row(event.y)

        if self.drop_target and self.drop_target != target:
            self.tree.item(self.drop_target, tags=())

        if target and target not in self.drag_selection:
            self.tree.item(target, tags=("drop_target",))
            self.drop_target = target
        else:
            self.drop_target = None

    def on_button_release(self, event):
        if not self.drag_selection:
            return
        if self.drop_target:
            self.tree.item(self.drop_target, tags=())

            parent = self.tree.parent(self.drop_target)
            index = self.tree.index(self.drop_target)

            for item in self.drag_selection:
                if item == self.drop_target:
                    continue
                self.tree.move(item, parent, index)
                index += 1

        self.drag_selection = []
        self.drop_target = None

    def on_rename(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return

        x, y, width, height = self.tree.bbox(item)
        entry = tk.Entry(self.tree)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, self.tree.item(item, "text"))
        entry.focus()

        def commit_rename(e=None):
            new_text = entry.get()
            self.tree.item(item, text=new_text)
            if item in self.items:
                self.items[item]["name"] = new_text
            entry.destroy()

        def cancel_rename(e=None):
            entry.destroy()

        entry.bind("<Return>", commit_rename)
        entry.bind("<FocusOut>", cancel_rename)
        entry.bind("<Escape>", cancel_rename)

# ─── Model - Data Classes ──────────────────────────────────────────────────────

# Shape, Rectangle, Oval, Triangle classes remain the same as in the previous refactoring step
# They are data containers with geometry-related methods and property getters/setters used by Controller

class Shape:
    property_spec = {
        "Name": {"type": "str"},
        "X": {"type": "float"},
        "Y": {"type": "float"},
        "Width": {"type": "float"},
        "Height": {"type": "float"},
        "Container Type": {"type": "enum", "values": ["Text", "Image"]},
        "Shape Type": {"type": "enum", "values": ["Rectangle", "Oval", "Triangle"]},
    }
    def __init__(self, id: Any, shape_type: str, coords: List[int], name: str):
        self.id = id
        self.shape_type = shape_type
        self.coords = coords
        self.name = name
        self.container_type: str = 'Text'
        self.content: Optional[Any] = None
        self.color: str = 'black'
        self.line_width: int = 1
        self.clip_image: bool = True
        self.path = ''
        self.text = ''

    @property
    def get_bbox(self):
        x1, y1, x2, y2 = self.coords
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

    # prop_get and prop_set are used by the Controller to access/modify properties
    def prop_get(self, prop_name):
        handler = PROPERTY_HANDLERS.get(prop_name)
        if handler and "get" in handler:
            return handler["get"](self)
        if prop_name == "X": return self.get_bbox[0]
        elif prop_name == "Y": return self.get_bbox[1]
        elif prop_name == "Width": return self.get_bbox[2] - self.get_bbox[0]
        elif prop_name == "Height": return self.get_bbox[3] - self.get_bbox[1]
        else:
            return getattr(self, prop_name.lower().replace(" ", "_"), None)

    def prop_set(self, prop_name, value):
         # This method is less used now as Controller calls specific model update methods
         handler = PROPERTY_HANDLERS.get(prop_name)
         if handler and "set" in handler:
             handler["set"](self, value)
         else:
             try: setattr(self, prop_name.lower().replace(" ", "_"), value)
             except AttributeError: pass # Already printed warning in controller

    def handle_contains(self, x, y):
        if not self.coords or len(self.coords) < 4: return False
        x1, y1, x2, y2 = self.coords
        effective_x2 = max(x1, x2)
        effective_y2 = max(y1, y2)
        handle_size = 8
        return (effective_x2 - handle_size <= x <= effective_x2 + handle_size and
                effective_y2 - handle_size <= y <= effective_y2 + handle_size)

    def contains_point(self, x: int, y: int) -> bool:
        return False # Override in subclasses

    def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw]=None):
        pass # Override in subclasses

    def clip_image_to_geometry(self, pil_image: Image.Image) -> Image.Image:
        return pil_image # Override in subclasses


class Rectangle(Shape):
    def __init__(self, id: Any, coords: List[int], name: str):
        super().__init__(id=id, shape_type='rectangle', coords=coords, name=name)

    def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw]=None):
        x1, y1, x2, y2 = self.coords
        if canvas: canvas.create_rectangle(x1, y1, x2, y2, outline=self.color, width=self.line_width, fill='')
        elif draw: draw.rectangle([x1, y1, x2, y2], outline=self.color, width=self.line_width)

    def clip_image_to_geometry(self, pil_image: Image.Image) -> Image.Image:
        x1, y1, x2, y2 = self.get_bbox
        w, h = int(x2 - x1), int(y2 - y1)
        if w <= 0 or h <= 0: return Image.new('RGBA', (1,1))
        im = pil_image.convert('RGBA').resize((w, h), Image.Resampling.LANCZOS)
        mask = Image.new('L', (w, h), 0); mdraw = ImageDraw.Draw(mask); mdraw.rectangle([0,0,w,h], fill=255); im.putalpha(mask)
        return im

    def contains_point(self, x: int, y: int) -> bool:
        x1, y1, x2, y2 = self.get_bbox
        return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


class Oval(Shape):
    def __init__(self, id: Any, coords: List[int], name: str):
        super().__init__(id=id, shape_type='oval', coords=coords, name=name)

    def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw]=None):
        if not self.coords or len(self.coords) < 4: return
        x1, y1, x2, y2 = self.coords
        if canvas: canvas.create_oval(x1, y1, x2, y2, outline=self.color, width=self.line_width, fill='')
        elif draw: draw.ellipse([x1, y1, x2, y2], outline=self.color, width=self.line_width)

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


class Triangle(Shape):
    def __init__(self, id: Any, coords: List[int], name: str):
         super().__init__(id=id, shape_type='triangle', coords=coords, name=name)

    def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw]=None):
         if not self.coords or len(self.coords) < 4: return
         x1, y1, x2, y2 = self.coords
         base_y = max(y1, y2); apex_y = min(y1, y2)
         left_x = min(x1, x2); right_x = max(x1, x2)
         center_x = (left_x + right_x) // 2
         pts = [left_x, base_y, center_x, apex_y, right_x, base_y]
         if canvas: canvas.create_polygon(*pts, outline=self.color, width=self.line_width, fill='')
         elif draw: draw.polygon(pts, outline=self.color, width=self.line_width)

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

class Hexagon(Shape):
    def __init__(self, id: Any, coords: List[int], name: str):
        super().__init__(id=id, shape_type='hexagon', coords=coords, name=name)

    def draw_shape(self, canvas=None, draw: Optional[ImageDraw.ImageDraw]=None):
            print(f"Hexagon ID {self.id}: Step 1 - Entered draw_shape.") # Very first print
            if not self.coords or len(self.coords) < 4:
                print(f"Hexagon ID {self.id}: Step 2 - Invalid coords: {self.coords}")
                return

            print(f"Hexagon ID {self.id}: Step 3 - Coords are valid: {self.coords}")
            x1, y1, x2, y2 = self.coords
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            print(f"Hexagon ID {self.id}: Step 4 - Calculated dimensions: w={width}, h={height}, center=({center_x}, {center_y})")

            tags = ('shape', f'id{self.id}')

            if canvas:
                print(f"Hexagon ID {self.id}: Step 5 - Drawing on canvas.")
                points = []
                # Use floating-point coordinates for canvas
                for i in range(6):
                    print(f"Hexagon ID {self.id}: Step 6 - Calculating point {i}.")
                    angle_deg = 60 * i - 30
                    angle_rad = math.radians(angle_deg)
                    x = center_x + (width/2) * math.cos(angle_rad)
                    y = center_y + (height/2) * math.sin(angle_rad)
                    points.extend([x, y])
                    print(f"Hexagon ID {self.id}: Step 7 - Point {i} calculated: ({x}, {y}).")

                print(f"Hexagon ID {self.id}: Step 8 - Final points list: {points}")
                item_id = canvas.create_polygon(points, outline=self.color,
                                    width=self.line_width, fill='', tags=tags)
                print(f"Hexagon ID {self.id}: Step 9 - Created canvas item with ID: {item_id} and tags: {tags}")

            elif draw:
                print(f"Hexagon ID {self.id}: Step 10 - Drawing on PIL ImageDraw.")
                points = []
                # Use integer coordinates for PIL drawing
                for i in range(6):
                     print(f"Hexagon ID {self.id}: Step 11 - Calculating PIL point {i}.")
                     angle_deg = 60 * i - 30
                     angle_rad = math.radians(angle_deg)
                     x = int(center_x + (width/2) * math.cos(angle_rad))
                     y = int(center_y + (height/2) * math.sin(angle_rad))
                     points.extend([x, y])
                     print(f"Hexagon ID {self.id}: Step 12 - PIL Point {i} calculated: ({x}, {y}).")
                print(f"Hexagon ID {self.id}: Step 13 - Final PIL points list: {points}")
                draw.polygon(points, outline=self.color, width=self.line_width)
                print(f"Hexagon ID {self.id}: Step 14 - PIL polygon drawn.")

            print(f"Hexagon ID {self.id}: Step 15 - Exited draw_shape.") # Print at the very end

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

# Layer class remains the core data container for shapes within a layer
class Layer:
    def __init__(self, name: str):
        self.name = name
        self.shapes: Dict[Any, Shape] = {} # Dictionary mapping shape ID to Shape object

    def to_dict(self):
        return {
            'name': self.name,
            'shapes': {
                sid: {
                    'shape_type': shape.shape_type,
                    'coords': shape.coords,
                    'name': shape.name,
                    'container_type': shape.container_type,
                    'text': shape.text,
                    'path': shape.path,
                    'color': shape.color,
                    'line_width': shape.line_width,
                } for sid, shape in self.shapes.items()
            }
        }

    @staticmethod
    def from_dict(data):
        layer = Layer(data.get('name', 'Unnamed Layer'))
        for sid_str, shape_data in data.get('shapes', {}).items():
            try: sid_int = int(sid_str)
            except ValueError: continue

            shape_type = shape_data.get('shape_type')
            coords = shape_data.get('coords')
            name = shape_data.get('name', f"Shape {sid_int}")
            container_type = shape_data.get('container_type', 'Text')
            text = shape_data.get('text', '')
            path = shape_data.get('path', shape_data.get('image_path', ''))
            color = shape_data.get('color', 'black')
            line_width = shape_data.get('line_width', 1)

            shape = None
            if shape_type == 'rectangle': shape = Rectangle(id=sid_int, coords=coords, name=name)
            elif shape_type == 'oval': shape = Oval(id=sid_int, coords=coords, name=name)
            elif shape_type == 'triangle':
                 if coords and len(coords) == 4: shape = Triangle(id=sid_int, coords=coords, name=name)
                 else: continue
            else: continue

            shape.container_type = container_type
            shape.text = text
            shape.path = path
            shape.color = color
            shape.line_width = line_width

            if shape: layer.shapes[sid_int] = shape
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


# DrawingModel class remains the core data and state manager
class DrawingModel:
    def __init__(self):
        self.layers: List[Layer] = []
        self.selected_layer_idx = 0
        self.grid_size = GRID_SIZE
        self._shape_map: Dict[Any, Shape] = {} # Maps all shape IDs to shape objects
        self.selected_shape: Optional[Any] = None # ID of the selected shape
        self.grid_visible = True # Model state
        self.snap_to_grid = True # Model state
        # grid_var, snap_var are View state

        self._observers: List = []
        # current_file_path is Controller state

        self.reset()

    @property
    def current_layer(self) -> Layer:
        if 0 <= self.selected_layer_idx < len(self.layers): return self.layers[self.selected_layer_idx]
        return self.layers[0] if self.layers else Layer("Default")

    def reset(self):
        self.layers = [Layer("Background")]
        self.selected_layer_idx = 0
        self.selected_shape = None
        self._shape_map = {}
        # current_file_path reset is Controller responsibility
        self.notify_observers()

    def to_dict(self):
        return {
            'layers': [layer.to_dict() for layer in self.layers],
            'selected_layer_idx': self.selected_layer_idx,
            'grid_size': self.grid_size,
            'grid_visible': self.grid_visible,
            'snap_to_grid': self.snap_to_grid,
        }

    def from_dict(self, data):
        self.layers = [Layer.from_dict(layer_data) for layer_data in data.get('layers', [Layer("Background").to_dict()])]
        if not self.layers: self.layers.append(Layer("Background"))
        self.selected_layer_idx = data.get('selected_layer_idx', 0)
        if not (0 <= self.selected_layer_idx < len(self.layers)): self.selected_layer_idx = 0
        self.grid_size = data.get('grid_size', GRID_SIZE)
        self.grid_visible = data.get('grid_visible', True)
        self.snap_to_grid = data.get('snap_to_grid', True)

        # Reset transient states (Controller responsibility)
        self.selected_shape = None
        # preview_shape, drag_start, is_resizing, is_moving, resize_start are Controller state
        # current_file_path is Controller state

        self._refresh_shape_map()

    def _refresh_shape_map(self):
        self._shape_map = {}
        for layer in self.layers:
            for sid, shape in layer.shapes.items():
                if isinstance(shape, Shape): self._shape_map[sid] = shape

    def add_layer(self, name: Optional[str]=None):
        name = name or f"Layer {len(self.layers)}"
        self.layers.append(Layer(name))
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
        shape.id = iid # Assign the generated unique ID


        # Add the shape to the current layer's shapes dictionary
        self.current_layer.shapes[shape.id] = shape
        # Add the shape to the global shape map
        self._shape_map[shape.id] = shape

        # --- Add this print statement ---
        print(f"DrawingModel.add_shape: Shape ID {shape.id} added to layer '{self.current_layer.name}'. Layer shapes keys BEFORE notify: {list(self.current_layer.shapes.keys())}")
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
        if shape and _update_coords_if_valid(shape, new_coords): self.notify_observers()

    def rename_shape(self, sid: Any, new_name: str):
        shape = self.get_shape(sid)
        if shape and shape.name != new_name: shape.name = new_name; self.notify_observers()

    def set_container(self, sid: Any, container_type: str):
        shape = self.get_shape(sid)
        if shape and shape.container_type != container_type:
             shape.container_type = container_type
             shape.content = None # Clear content on type change for reload
             self.notify_observers()

    def set_text(self, sid: Any, text: str):
        shape = self.get_shape(sid)
        if shape and shape.text != text:
             shape.text = text
             shape.content = text # Update content for Text type
             self.notify_observers()

    def set_path(self, sid: Any, path: str):
        shape = self.get_shape(sid)
        if shape and shape.path != path:
             shape.path = path
             shape.content = None # Clear old image content for reload
             self.notify_observers()

    def set_color(self, sid: Any, color: str):
        shape = self.get_shape(sid)
        if shape and shape.color != color: shape.color = color; self.notify_observers()

    def set_line_width(self, sid: Any, line_width: int):
        shape = self.get_shape(sid)
        if shape and shape.line_width != line_width: shape.line_width = line_width; self.notify_observers()

    def reclassify_shape(self, sid: Any, new_shape_type: str):
        old_shape = self.get_shape(sid)
        if not old_shape or new_shape_type not in SHAPE_TYPES: return
        if new_shape_type == old_shape.shape_type: return

        new_shape = None
        coords_for_new_shape = old_shape.coords

        if new_shape_type == 'rectangle': new_shape = Rectangle(id=sid, coords=coords_for_new_shape, name=old_shape.name)
        elif new_shape_type == 'oval': new_shape = Oval(id=sid, coords=coords_for_new_shape, name=old_shape.name)
        elif new_shape_type == 'triangle':
            bbox = old_shape.get_bbox
            coords_for_new_shape = [bbox[0], bbox[1], bbox[2], bbox[3]]
            new_shape = Triangle(id=sid, coords=coords_for_new_shape, name=old_shape.name)
        elif new_shape_type == 'hexagon':  # Add hexagon case
            new_shape = Hexagon(id=sid, coords=coords_for_new_shape, name=old_shape.name)
        else: return

        new_shape.container_type = old_shape.container_type
        new_shape.text = old_shape.text
        new_shape.path = old_shape.path
        new_shape.color = old_shape.color
        new_shape.line_width = old_shape.line_width
        new_shape.content = old_shape.content

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


# --- View - Handles UI and Drawing ────────────────────────────────────────────

class DrawingView(tk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller # View holds a reference to the Controller
        self.pack(fill=tk.BOTH, expand=True)

        # View state for managing Tkinter items and PhotoImages
        self._shape_id_to_canvas_items: Dict[Any, List[int]] = {}
        self._shape_id_to_tk_image: Dict[Any, ImageTk.PhotoImage] = {}
        self._tv_item_to_shape_id: Dict[str, Any] = {} # Map Treeview item ID to shape ID
        self._is_editing_property = False # View state for inline editor
        self._editor: Optional[tk.Widget] = None # Current inline editor widget

        # Tkinter variables for Checkbuttons (View state)
        self.grid_var = tk.BooleanVar(value=True)
        self.snap_var = tk.BooleanVar(value=True)


        # Build UI
        self._build_ui()

        # Bind events to controller methods
        self._bind_events()

        # Initial setup
        master.title("Enhanced Vector Editor - Untitled") # Initial title

    def _build_ui(self):
        # Toolbar
        self.toolbar = tk.Frame(self, height=TOOLBAR_HEIGHT, bd=1, relief=tk.RAISED)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        # Buttons call controller methods
        tk.Button(self.toolbar, text="Remove Selected", command=self.controller.remove_selected).pack(side=tk.LEFT, padx=2)
        self.grid_frame = ttk.Frame(self.toolbar)
        self.grid_frame.pack(side=tk.LEFT, padx=5)

        # Checkbuttons are bound to View's variables, command calls controller
        self.grid_check = ttk.Checkbutton(
            self.grid_frame, text="Grid",
            command=self.controller.toggle_grid, # Calls controller method
            variable=self.grid_var) # Bind to View's variable
        self.grid_check.pack(side=tk.LEFT)

        self.snap_check = ttk.Checkbutton(
            self.grid_frame, text="Snap",
            command=self.controller.toggle_snap, # Calls controller method
            variable=self.snap_var) # Bind to View's variable
        self.snap_check.pack(side=tk.LEFT)

        # Paned Window
        self.pane = tk.PanedWindow(self, sashrelief=tk.RAISED, orient=tk.HORIZONTAL)
        self.pane.pack(fill=tk.BOTH, expand=True)

        # Left Panel (Shapes, Properties, Layers)
        self.left_panel = tk.Frame(self.pane, width=PANEL_WIDTH)
        self.pane.add(self.left_panel, minsize=150)

        # Shapes Listbox and Buttons
        tk.Label(self.left_panel, text="Shapes (Current Layer)").pack(anchor='w')
        self.shapes_lb = tk.Listbox(self.left_panel)
        self.shapes_lb.pack(fill=tk.BOTH, expand=True)

        btn_frame = tk.Frame(self.left_panel)
        btn_frame.pack(fill=tk.X)
        for stype, icon in SHAPE_BUTTONS.items():
            # Buttons call controller methods
            tk.Button(btn_frame, text=icon,
                      command=lambda s=stype: self.controller.start_adding(s)).pack(side=tk.LEFT, expand=True)

        # Properties Treeview
        tk.Label(self.left_panel, text="Properties").pack(anchor='w')
        self.props_tree = ttk.Treeview(
            self.left_panel,
            columns=("Property", "Value"),
            show="headings",
            selectmode="browse",
            height=8
        )
        self.props_tree.heading("Property", text="Property")
        self.props_tree.column("Property", width=120, anchor="w")
        self.props_tree.heading("Value", text="Value")
        self.props_tree.column("Value", width=180, anchor="w")
        self.props_tree.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Layers Listbox and Buttons
        tk.Label(self.left_panel, text="Layers").pack(anchor='w')
        self.layers_lb = tk.Listbox(self.left_panel)
        self.layers_lb.pack(fill=tk.BOTH, expand=True)

        layer_btns = tk.Frame(self.left_panel)
        layer_btns.pack(fill=tk.X)
        # Buttons call controller methods
        tk.Button(layer_btns, text="+", command=self.controller.model.add_layer).pack(side=tk.LEFT)
        tk.Button(layer_btns, text="–", command=self.controller.remove_selected_layer).pack(side=tk.LEFT)
        tk.Button(layer_btns, text="↑", command=self.controller.model.move_layer_up).pack(side=tk.LEFT)
        tk.Button(layer_btns, text="↓", command=self.controller.model.move_layer_down).pack(side=tk.LEFT)

        # Canvas (Drawing Area)
        self.canvas = tk.Canvas(self.pane, bg='white', width=600)
        self.pane.add(self.canvas, stretch="always")

        # Right Panel (Data Merge Status)
        self.right_panel = tk.Frame(self.pane, width=PANEL_WIDTH)
        tk.Label(self.right_panel, text="Data Merge Status").pack(anchor='w')
        self.merge_status_tree = ttk.Treeview(
            self.right_panel,
            columns=('Status',),
            show='tree headings'
        )
        self.merge_status_tree.heading('#0', text='CSV Column')
        self.merge_status_tree.heading('Status', text='Status')
        self.merge_status_tree.column('#0', stretch=tk.YES, minwidth=80, width=120)
        self.merge_status_tree.column('Status', stretch=tk.NO, minwidth=40, width=40, anchor='center')
        self.merge_status_tree.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)


    def _bind_events(self):
        # Bind canvas events to controller methods     
        self.canvas.bind("<ButtonPress-1>", self.controller.on_canvas_press)
        self.canvas.bind("<B1-Motion>",    self.controller.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.controller.on_canvas_release)
        self.canvas.bind("<Configure>", self.controller.on_canvas_configure)

        # Bind listbox events to controller methods
        self.shapes_lb.bind("<<ListboxSelect>>", self.controller.on_shape_select)
        self.layers_lb.bind("<<ListboxSelect>>", self.controller.on_layer_select)

        # Bind treeview double-click to controller method
        self.props_tree.bind("<Double-1>", self.controller._on_treeview_double_click)

        # Bind hotkeys to controller methods (bind_all because events can happen anywhere)
        self.master.bind_all("<Delete>", self.controller.on_delete_key)
        self.master.bind_all("<BackSpace>", self.controller.on_delete_key)
        self.master.bind_all("<Control-n>", lambda e: self.controller.new_drawing())
        self.master.bind_all("<Control-o>", lambda e: self.controller.open_drawing())
        self.master.bind_all("<Control-s>", lambda e: self.controller.save_drawing())
        self.master.bind_all("<Control-Shift-S>", lambda e: self.controller.save_drawing_as())
        # Add Cmd bindings for Mac users
        self.master.bind_all("<Command-n>", lambda e: self.controller.new_drawing())
        self.master.bind_all("<Command-o>", lambda e: self.controller.open_drawing())
        self.master.bind_all("<Command-s>", lambda e: self.controller.save_drawing())
        self.master.bind_all("<Command-Shift-S>", lambda e: self.controller.save_drawing_as())


    # --- View - Methods to update the display (Called by Controller or Model Observer) ---

    def refresh_all(self, model_state): # View update method receives model state or reads from model directly
        """Redraws canvas, listboxes, and property/merge panels to match the model state."""
        print("\nDrawingView.refresh_all: Starting refresh_all.")
        # Read model state (View accesses Model)
        layers = model_state.layers
        selected_layer_idx = model_state.selected_layer_idx
        grid_visible = model_state.grid_visible
        selected_shape_id = model_state.selected_shape
        grid_size = model_state.grid_size

        # --- 1) Canvas ---
        self.canvas.delete("all") # Clear ALL items
        self._shape_id_to_canvas_items.clear() # Clear internal tracking
        self._shape_id_to_tk_image.clear() # Clear PhotoImage references

        print("DrawingView.refresh_all: Canvas cleared ('all'). Internal item tracking cleared.")

        # Draw grid based on model state
        self._draw_grid(grid_visible, grid_size, self.canvas.winfo_width(), self.canvas.winfo_height())
        print("DrawingView.refresh_all: Grid drawn.")

        # Draw shapes in layer-stacking order (bottom layer first on canvas)
        print("DrawingView.refresh_all: Drawing shapes layer by layer.")
        # Iterate through layers in the order they are in the model list
        for layer in model_state.layers: # Access layers from model_state
            print(f"DrawingView.refresh_all: Drawing shapes in layer '{layer.name}'.")
            # --- Add this print statement ---
            print(f"DrawingView.refresh_all: Layer '{layer.name}' contains shapes: {list(layer.shapes.keys())} BEFORE drawing loop.")
            # -------------------------------
            # Iterate through shapes in a consistent order (e.g., by ID)
            for shp_id in sorted(layer.shapes.keys()):
                 shp = layer.shapes[shp_id]
                 print(f"DrawingView.refresh_all: Drawing shape ID {shp.id} ('{shp.name}', Type: {shp.shape_type}).")
                 # Use View method to draw the shape
                 self._draw_shape_on_canvas(shp, self.canvas)

        if selected_shape_id is not None:
            selected_shape = model_state.get_shape(selected_shape_id) # View gets shape from model
            if selected_shape:
                print(f"Drawing selection and handle for selected shape ID {selected_shape_id}.")
                x1, y1, x2, y2 = selected_shape.get_bbox
                # Professional-style selection box
                self.canvas.create_rectangle(
                    min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2),
                    dash=(2, 2),  # More subtle dash pattern
                    outline="#555555",  # Dark gray instead of bright blue
                    width=1,  # Thinner line
                    tags=("selection", f"select_{selected_shape_id}")
                )
                
                # Modern resize handle design
                handle_size = 6
                handle_pad = 2
                handle_x = max(x1, x2) + handle_pad
                handle_y = max(y1, y2) + handle_pad
                
                # Create handle with subtle border and fill
                self.canvas.create_rectangle(
                    handle_x - handle_size, handle_y - handle_size,
                    handle_x, handle_y,
                    fill="#FFFFFF",  # White fill
                    outline="#333333",  # Dark border
                    width=1,
                    tags=("handle", f"handle_{selected_shape_id}")
                )
            else:
                 print(f"DrawingView.refresh_all: Selected shape ID {selected_shape_id} not found in model for drawing selection/handle.")


        else:
            print("DrawingView.refresh_all: No shape selected, skipping selection/handle drawing.")


        # --- 2) Layers Listbox ---
        print("DrawingView.refresh_all: Updating layers listbox.")
        self.layers_lb.delete(0, tk.END)
        for idx, layer in enumerate(reversed(layers)):
            model_idx = len(layers) - 1 - idx
            mark = "✓ " if model_idx == selected_layer_idx else "  "
            self.layers_lb.insert(tk.END, f"{mark}{layer.name}")

        selected_listbox_idx = len(layers) - 1 - selected_layer_idx
        if 0 <= selected_listbox_idx < self.layers_lb.size():
            self.layers_lb.selection_clear(0, tk.END)
            self.layers_lb.selection_set(selected_listbox_idx)
            self.layers_lb.activate(selected_listbox_idx)
        print("DrawingView.refresh_all: Layers listbox updated.")


        # --- 3) Shapes Listbox ---
        print("DrawingView.refresh_all: Updating shapes listbox.")
        self.shapes_lb.delete(0, tk.END)
        current_layer_shapes_sorted = sorted(layers[selected_layer_idx].shapes.values(), key=lambda s: s.id)

        for shp in current_layer_shapes_sorted:
            self.shapes_lb.insert(tk.END, shp.name)

        if selected_shape_id is not None:
            shape_ids_in_listbox = [s.id for s in current_layer_shapes_sorted]
            if selected_shape_id in shape_ids_in_listbox:
                idx = shape_ids_in_listbox.index(selected_shape_id)
                self.shapes_lb.selection_clear(0, tk.END)
                self.shapes_lb.selection_set(idx)
                self.shapes_lb.activate(idx)
        print("DrawingView.refresh_all: Shapes listbox updated.")


        # --- 4) Properties Panel ---
        print("DrawingView.refresh_all: Updating properties panel.")
        # Pass selected shape data to the View method
        selected_shape_data = model_state.get_shape(selected_shape_id)
        # Controller will pass refocus info if needed
        self._update_properties_panel(selected_shape_data, self.controller.get_refocus_info())
        print("DrawingView.refresh_all: Properties panel updated.")
        # Controller resets refocus info after view update


        # --- 5) Merge Status Panel ---
        print("DrawingView.refresh_all: Updating merge status panel.")
        # Pass necessary data from Controller (CSV data) and Model (shapes)
        self._populate_merge_status(self.controller.get_csv_data(), model_state.layers)
        print("DrawingView.refresh_all: Merge status panel updated.")

        print("DrawingView.refresh_all: refresh_all finished.")


    def _draw_grid(self, visible: bool, grid_size: int, canvas_width: int, canvas_height: int):
        """Draws the grid on the canvas (View logic)."""
        self.canvas.delete("grid")
        if visible and canvas_width > 0 and canvas_height > 0:
            for x in range(0, canvas_width, grid_size):
                self.canvas.create_line(x, 0, x, canvas_height, fill='lightgray', tags="grid")
            for y in range(0, canvas_height, grid_size):
                self.canvas.create_line(0, y, canvas_width, y, fill='lightgray', tags="grid")

    def _clear_shape_drawing_on_canvas(self, shape_id):
        """Clears all canvas items and PhotoImage references associated with a shape (View logic)."""
        if shape_id in self._shape_id_to_canvas_items:
            for item_id in self._shape_id_to_canvas_items[shape_id]:
                if item_id in self.canvas.find_all():
                     self.canvas.delete(item_id)
            del self._shape_id_to_canvas_items[shape_id]

        if shape_id in self._shape_id_to_tk_image:
             del self._shape_id_to_tk_image[shape_id]

    def _draw_shape_outline_on_canvas(self, shape: Shape, canvas: tk.Canvas):
        """Draws the outline of a shape on the Tkinter canvas and stores the item ID (View logic)."""
        item_id = None
        tags = ('shape', f'id{shape.id}')

        if shape.shape_type == 'rectangle':
            x1, y1, x2, y2 = shape.coords
            item_id = canvas.create_rectangle(x1, y1, x2, y2, outline=shape.color, width=shape.line_width, fill='', tags=tags)
        elif shape.shape_type == 'oval':
            if not shape.coords or len(shape.coords) < 4: return
            x1, y1, x2, y2 = shape.coords
            item_id = canvas.create_oval(x1, y1, x2, y2, outline=shape.color, width=shape.line_width, fill='', tags=tags)
        elif shape.shape_type == 'triangle':
             if not shape.coords or len(shape.coords) < 4: return
             x1, y1, x2, y2 = shape.coords
             base_y = max(y1, y2); apex_y = min(y1, y2)
             left_x = min(x1, x2); right_x = max(x1, x2)
             center_x = (left_x + right_x) // 2
             pts = [left_x, base_y, center_x, apex_y, right_x, base_y]
             item_id = canvas.create_polygon(*pts, outline=shape.color, width=shape.line_width, fill='', tags=tags)
        elif shape.shape_type == 'hexagon':
            if not shape.coords or len(shape.coords) < 4:
                return
            x1, y1, x2, y2 = shape.coords
            width  = abs(x2 - x1)
            height = abs(y2 - y1)
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            pts = []
            for i in range(6):
                θ = math.radians(60*i)
                pts.extend([
                    cx + (width/2)  * math.cos(θ),
                    cy + (height/2) * math.sin(θ),
                ])

            item_id = canvas.create_polygon(
                *pts,
                outline=shape.color,
                width=shape.line_width,
                fill='',
                tags=tags
            )
            # self._shape_id_to_canvas_items.setdefault(shape.id, []).append(item_id)

        #if item_id is not None: self._shape_id_to_canvas_items.setdefault(shape.id, []).append(item_id)


    def _draw_content_on_canvas(self, shape: Shape, canvas: tk.Canvas):
        """Draws the content (text or image) of a shape on the Tkinter canvas (View logic)."""
        item_id = None
        x1, y1, x2, y2 = shape.get_bbox

        if shape.container_type == 'Text':
            text = str(shape.content) or shape.text
            if not text: return
            cx = (x1 + x2) / 2; cy = (y1 + y2) / 2
            item_id = canvas.create_text(cx, cy, text=text, fill=shape.color, font=(None, 12), anchor='center', tags=('shape_content', f'content_of_{shape.id}'))

        elif shape.container_type == 'Image' and shape.path:
             try:
                 # Image loading can happen here in the View when needed for display
                 if shape.content is None and shape.path:
                     try: shape.content = Image.open(shape.path).convert("RGBA")
                     except Exception as e: print(f"!! View: Failed to load image {shape.path} for display: {e}"); shape.content = None

                 if shape.content:
                      bbox_w = int(abs(x2 - x1)); bbox_h = int(abs(y2 - y1))
                      if bbox_w > 0 and bbox_h > 0:
                           clipped_img = shape.clip_image_to_geometry(shape.content)
                           resized_img = clipped_img.resize((bbox_w, bbox_h), Image.Resampling.LANCZOS)
                           tk_img = ImageTk.PhotoImage(resized_img)
                           self._shape_id_to_tk_image[shape.id] = tk_img # Store reference
                           item_id = canvas.create_image(min(x1, x2), min(y1, y2), image=tk_img, anchor='nw', tags=('shape_content', f'content_of_{shape.id}'))
             except Exception as e:
                 print(f"!! View: Error drawing Tkinter image content for shape {shape.id}: {e}")

        #if item_id is not None: self._shape_id_to_canvas_items.setdefault(shape.id, []).append(item_id)


    def _draw_name_label_on_canvas(self, shape: Shape, canvas: tk.Canvas):
        """Draws the name label on the Tkinter canvas (View logic)."""
        if not shape.name: return
        x1, y1, x2, y2 = shape.get_bbox; tx, ty = min(x1, x2), min(y1, y2)
        label_text = shape.name; font_size = 8; padding = 2; label_color = 'black'
        box_fill_color = 'lightgray'; box_outline_color = 'gray'; line_width = 1

        try:
            font = ('Arial', font_size)
            estimated_char_width = font_size * 0.6; text_width = len(label_text) * estimated_char_width; text_height = font_size
            box_width = text_width + 2 * padding; box_height = text_height + 2 * padding
            if box_width > abs(x2 - x1): box_width = abs(x2 - x1)
            label_x1, label_y1 = tx, ty; label_x2, label_y2 = label_x1 + box_width, label_y1 + box_height

            rect_id = canvas.create_rectangle(label_x1, label_y1, label_x2, label_y2, fill=box_fill_color, outline=box_outline_color, width=line_width, tags=('name_label', f'name_label_of_{shape.id}'))
            self._shape_id_to_canvas_items.setdefault(shape.id, []).append(rect_id)

            text_x = label_x1 + padding; text_y = label_y1 + padding
            text_id = canvas.create_text(text_x, text_y, text=label_text, fill=label_color, font=font, anchor='nw', tags=('name_label_text', f'name_label_text_of_{shape.id}'))
            self._shape_id_to_canvas_items.setdefault(shape.id, []).append(text_id)
        except Exception as e: print(f"!! View: Error drawing Tkinter name label for shape {shape.id}: {e}")

    def _draw_shape_on_canvas(self, shape: Shape, canvas: tk.Canvas):
         """Draws a complete shape on the Tkinter canvas (View logic)."""
         # Clearing is handled by refresh_all or _redraw_shape_and_selection
         self._draw_shape_outline_on_canvas(shape, canvas)
         self._draw_content_on_canvas(shape, canvas)
         self._draw_name_label_on_canvas(shape, canvas)


    # --- View - PIL Drawing Methods (Used for Export Rendering) ---

    def _draw_shape_outline_on_pil(self, shape: Shape, draw: ImageDraw.ImageDraw):
         """Draws the outline of a shape on the PIL drawing context (View logic)."""
         if not shape.coords or len(shape.coords) < 4: return
         shape.draw_shape(canvas=None, draw=draw) # Delegate to shape's specific PIL draw_shape

    def _draw_content_on_pil(self, shape: Shape, draw: ImageDraw.ImageDraw):
         """Draws the content (text) of a shape on the PIL drawing context (View logic)."""
         if shape.container_type == 'Text':
              text = str(shape.content) or shape.text
              if not text: return
              x1, y1, x2, y2 = shape.get_bbox; width = x2 - x1; height = y2 - y1
              if width <= 0 or height <= 0: return
              try: font = ImageFont.truetype("arial.ttf", size=12);
              except IOError:
                   try: font = ImageFont.truetype("LiberationSans-Regular.ttf", size=12);
                   except IOError: font = ImageFont.load_default();

              lines = []; avg_char_width = font.getlength('n') if hasattr(font, 'getlength') else 7; max_chars = max(int(width // avg_char_width), 1);
              for raw_line in text.split('\n'): wrapped = textwrap.fill(raw_line, width=max_chars); lines.extend(wrapped.split('\n'));

              try: bbox = font.getbbox('Ay'); line_height = bbox[3] - bbox[1];
              except Exception:
                   try: line_height = font.getsize('Ay')[1];
                   except Exception: line_height = 12;
              max_lines = int(height // line_height); visible = lines[:max_lines];

              for idx, line in enumerate(visible):
                  y_offset = y1 + idx * line_height
                  draw.text((x1, y_offset), line, fill=shape.color, font=font)

         # PIL Image content pasting is handled in _draw_shape_on_pil using clip_image_to_geometry

    def _draw_shape_on_pil(self, shape: Shape, draw: ImageDraw.ImageDraw, image: Image.Image):
         """Draws a complete shape on a PIL drawing context (View logic)."""
         self._draw_shape_outline_on_pil(shape, draw)
         self._draw_content_on_pil(shape, draw)

         if shape.container_type == 'Image' and shape.content:
             x1, y1, x2, y2 = shape.get_bbox
             bx, by = int(min(x1, x2)), int(min(y1, y2))

             try:
                  clipped_img = shape.clip_image_to_geometry(shape.content)
                  image.paste(clipped_img, (bx, by), clipped_img if clipped_img.mode == 'RGBA' else None)
             except Exception as e:
                  print(f"!! View: Error pasting PIL image content for shape {shape.id}: {e}")


    def redraw_shape_and_selection(self, shape: Shape, is_selected: bool):
        """Clears and redraws a specific shape, and its selection/handle if selected (View logic)."""
        if not shape: return

        self._clear_shape_drawing_on_canvas(shape.id)
        self.canvas.delete(f"select_{shape.id}")
        self.canvas.delete(f"handle_{shape.id}")

        self._draw_shape_on_canvas(shape, self.canvas)

        if is_selected:
            x1, y1, x2, y2 = shape.get_bbox
            self.canvas.create_rectangle(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2),
                                         dash=(4,2), outline="blue", width=2,
                                         tags=("selection", f"select_{shape.id}"))
            size = 8
            self.canvas.create_rectangle(max(x1,x2) - size, max(y1,y2) - size, max(x1,x2) + size, max(y1,y2) + size,
                                         fill="red",
                                         tags=("handle", f"handle_{shape.id}"))

    def create_preview_shape(self, tool: str, start_x: int, start_y: int):
        print("DrawingView.create_preview_shape: Creating preview shape.")
        if hasattr(self, '_preview_shape_id') and self._preview_shape_id:
             self.canvas.delete(self._preview_shape_id)

        tags = ("preview",)
        preview_id = None

        if tool == "rectangle": preview_id = self.canvas.create_rectangle(start_x, start_y, start_x, start_y, outline='gray', dash=(2,2), tags=tags)
        elif tool == "oval": preview_id = self.canvas.create_oval(start_x, start_y, start_x, start_y, outline='gray', dash=(2,2), tags=tags)
        elif tool == "triangle":
            base_y = start_y; apex_y = start_y; left_x = start_x; right_x = start_x; center_x = start_x
            pts = [left_x, base_y, center_x, apex_y, right_x, base_y]
            preview_id = self.canvas.create_polygon(*pts, outline='gray', dash=(2,2), tags=tags)
        elif tool == "hexagon":
            center_x = start_x; center_y = start_y
            points = []
            for i in range(6):
                angle_deg = 60 * i - 30
                angle_rad = math.pi / 180 * angle_deg
                x = center_x + 1 * math.cos(angle_rad)
                y = center_y + 1 * math.sin(angle_rad)
                points.extend([x, y])
            preview_id = self.canvas.create_polygon(points, outline='gray', dash=(2,2), tags=tags)

        self._preview_shape_id = preview_id
        print(f"DrawingView.create_preview_shape: Preview shape created with ID {self._preview_shape_id}.")

    def update_preview_shape(self, tool: str, start_x: int, start_y: int, current_x: int, current_y: int):
        if hasattr(self, '_preview_shape_id') and self._preview_shape_id and tool:
            if tool in ["rectangle", "oval"]: 
                self.canvas.coords(self._preview_shape_id, start_x, start_y, current_x, current_y)
            elif tool == "triangle":
                base_y = current_y; apex_y = start_y
                left_x = start_x; right_x = current_x; center_x = (left_x + right_x) // 2
                pts = [left_x, base_y, center_x, apex_y, right_x, base_y]
                self.canvas.coords(self._preview_shape_id, *pts)
            elif tool == "hexagon":
                width = abs(current_x - start_x)
                height = abs(current_y - start_y)
                center_x = (start_x + current_x) / 2
                center_y = (start_y + current_y) / 2
                points = []
                for i in range(6):
                    angle_deg = 60 * i - 30
                    angle_rad = math.pi / 180 * angle_deg
                    x = center_x + width/2 * math.cos(angle_rad)
                    y = center_y + height/2 * math.sin(angle_rad)
                    points.extend([x, y])
                self.canvas.coords(self._preview_shape_id, *points)

    def clear_preview_shape(self):
         """Clears the preview shape from the canvas (View logic)."""
         if hasattr(self, '_preview_shape_id') and self._preview_shape_id:
              self.canvas.delete(self._preview_shape_id)
              self._preview_shape_id = None # Clear the View state


    def _update_properties_panel(self, selected_shape: Optional[Shape], refocus_info=None):
        """Populates the properties treeview (View logic)."""
        self.props_tree.delete(*self.props_tree.get_children())
        self._tv_item_to_shape_id.clear()

        sid_to_refocus, prop_to_refocus = refocus_info if refocus_info else (None, None)

        if selected_shape:
            properties_to_display = [
                "ID", "Shape Type", "Name", "X", "Y", "Width", "Height",
                "Color", "Line Width", "Container Type"
            ]
            if selected_shape.container_type == "Text": properties_to_display.append("Text")
            else: properties_to_display.append("Path")

            for prop_name in properties_to_display:
                handler = PROPERTY_HANDLERS.get(prop_name)
                if prop_name == "ID": value = selected_shape.id
                elif prop_name == "Shape Type": value = selected_shape.shape_type.capitalize()
                elif handler and "get" in handler: value = handler["get"](selected_shape)
                else: value = selected_shape.prop_get(prop_name)

                if prop_name in ["X", "Y", "Width", "Height", "Line Width"] and value is not None: value = int(value)

                iid = self.props_tree.insert("", "end", values=(prop_name, value))
                self._tv_item_to_shape_id[iid] = selected_shape.id

                if sid_to_refocus == selected_shape.id and prop_to_refocus == prop_name:
                     self.props_tree.focus(iid); self.props_tree.selection_set(iid); self.props_tree.see(iid);

        self.props_tree.focus_set() # Set focus back to the treeview

    # Methods for inline editing in the properties treeview (View logic)
    def start_editing_treeview_cell(self, event): # Called by Controller
         tv = self.props_tree
         region = tv.identify("region", event.x, event.y)
         if region != "cell": return

         row_id = tv.identify_row(event.y)
         col = tv.identify_column(event.x)
         try: col_index = int(col[1:]) - 1; col_name = tv["columns"][col_index];
         except (ValueError, IndexError): return

         if col_name != "Value": return

         if row_id:
              self._start_editing_widget(row_id, col_name)


    def _start_editing_widget(self, row_id, column_name):
        if self._is_editing_property: return
        tv = self.props_tree; bbox = tv.bbox(row_id, column_name);
        if not bbox: return
        x, y, width, height = bbox; current_value = tv.set(row_id, column_name);
        prop_name = tv.set(row_id, "Property"); prop_meta = PROPERTY_HANDLERS.get(prop_name, {}); options = prop_meta.get("options");

        self._cancel_edit() # Destroy existing editor

        if options:
             self._editor = ttk.Combobox(tv, values=options, state="readonly")
             try: current_index = options.index(current_value); self._editor.current(current_index);
             except ValueError: self._editor.set("");
             self._editor.bind("<<ComboboxSelected>>", lambda e: self._commit_edit(row_id))
             self._editor.bind("<Escape>", lambda e: self._cancel_edit())
        else:
             self._editor = tk.Entry(tv); self._editor.insert(0, current_value);
             self._editor.bind("<Return>", lambda e: self._commit_edit(row_id))
             self._editor.bind("<Escape>", lambda e: self._cancel_edit())
             self._editor.bind("<FocusOut>", lambda e: self._cancel_edit()) # May need refinement

        self._editor.place(x=x, y=y, width=width, height=height)
        self._editor.focus_set()
        self._is_editing_property = True

    def _commit_edit(self, row_id): # Called by editor widget event
        if not self._is_editing_property or not self._editor: return
        new_value_str = self._editor.get().strip()
        self._editor.destroy(); self._editor = None; self._is_editing_property = False;

        tv = self.props_tree; prop_name = tv.set(row_id, "Property");
        sid = self._tv_item_to_shape_id.get(row_id);

        if sid is None: self.update_properties_panel(None); return # Shape gone, refresh panel
        # Notify controller about the committed change
        self.controller.handle_property_edit_commit(sid, prop_name, new_value_str)

    def _cancel_edit(self): # Called by editor widget event or manually
        if self._is_editing_property and self._editor:
            self._editor.destroy(); self._editor = None; self._is_editing_property = False;

    def get_edited_property_info(self) -> Optional[tuple]:
         """Returns info about the currently edited property if any (View state)."""
         if self._is_editing_property and self._editor:
             try:
                  row_id = self.props_tree.focus() # Get the focused row (should be the edited one)
                  prop_name = self.props_tree.set(row_id, "Property")
                  sid = self._tv_item_to_shape_id.get(row_id)
                  if sid is not None:
                       return (sid, prop_name)
             except Exception:
                  pass # Ignore errors if focus/selection is lost unexpectedly
         return None


    def _populate_merge_status(self, csv_data_df: Optional[pd.DataFrame], model_layers: List[Layer]):
        """Populates the merge status treeview (View logic)."""
        self.merge_status_tree.delete(*self.merge_status_tree.get_children())
        if csv_data_df is not None:
            csv_columns = csv_data_df.columns.tolist()
            model_shape_names = set()
            for layer in model_layers:
                 for shape in layer.shapes.values():
                      if shape.name.startswith('@'): model_shape_names.add(shape.name)

            for column_name in csv_columns:
                status = "❌ No Match";
                if column_name in model_shape_names: status = "✅ Match";
                self.merge_status_tree.insert('', 'end', text=column_name, values=(status,))
        else:
            self.merge_status_tree.insert('', 'end', text='No CSV data loaded.', values=('',))


    def show_merge_panel(self):
        """View-only operation to show the data merge status panel."""
        if self.right_panel not in self.pane.panes():
            self.pane.add(self.right_panel, minsize=150)

    def hide_merge_panel(self):
        """View-only operation to hide the data merge status panel."""
        if self.right_panel in self.pane.panes():
            self.pane.forget(self.right_panel)

    # --- View - Data access methods for Controller ---
    # Controller queries the View for state related to UI interactions

    def get_canvas_coords(self, event):
        """Returns raw canvas coordinates from an event."""
        return (event.x, event.y)

    def get_selected_shape_listbox_index(self) -> Optional[int]:
        """Returns the index of the selected item in the shapes listbox."""
        sel = self.shapes_lb.curselection()
        return sel[0] if sel else None

    def get_selected_layer_listbox_index(self) -> Optional[int]:
         """Returns the index of the selected item in the layers listbox."""
         sel = self.layers_lb.curselection()
         return sel[0] if sel else None

    def get_property_treeview_item_shape_id(self, item_id: str) -> Optional[Any]:
         """Gets the shape ID associated with a property treeview item ID."""
         return self._tv_item_to_shape_id.get(item_id)

    def get_property_treeview_cell_info(self, event) -> Optional[tuple]:
         """Gets info about the treeview cell double-clicked (item_id, column_name)."""
         tv = self.props_tree
         region = tv.identify("region", event.x, event.y)
         if region != "cell": return None

         row_id = tv.identify_row(event.y)
         col = tv.identify_column(event.x)
         try: col_index = int(col[1:]) - 1; col_name = tv["columns"][col_index];
         except (ValueError, IndexError): return None

         if col_name != "Value": return None

         return (row_id, col_name)
    # Render a card as an image. This will be used in the future to render a Component class
    # but is primarily used for card exporting at the time.   
    def flatten_card(self, row_data: dict, model: DrawingModel) -> Image.Image:
        """
        Renders the full card into a high-resolution, unscaled image (flattened).
        All data is merged, and all shapes drawn into one image at model's native pixel resolution.
        This image can later be resized or stretched as needed.

        Returns:
            A PIL.Image in RGBA mode.
        """
        from PIL import Image, ImageDraw, ImageFont
        import math
        import textwrap

        # Determine bounds
        min_x, min_y, max_x, max_y = model.get_model_bounds()
        width = int(round(max_x - min_x))
        height = int(round(max_y - min_y))
        if width <= 0 or height <= 0:
            width, height = 1, 1

        # Create a blank RGBA image
        image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)

        # Find a background shape (covers entire bounds)
        background_shape = None
        for layer in model.layers:
            for shape in layer.shapes.values():
                if shape.container_type == 'Image':
                    bbox = shape.get_bbox
                    if (abs(bbox[0] - min_x) < 1e-6 and
                        abs(bbox[1] - min_y) < 1e-6 and
                        abs(bbox[2] - max_x) < 1e-6 and
                        abs(bbox[3] - max_y) < 1e-6):
                        background_shape = shape
                        break
            if background_shape:
                break

        if background_shape and isinstance(background_shape.content, Image.Image):
            bg = background_shape.content.resize((width, height), Image.Resampling.LANCZOS)
            image.paste(bg, (0, 0))

        # Draw other shapes
        for layer in model.layers:
            for sid in sorted(layer.shapes.keys()):
                shape = layer.shapes[sid]
                if shape == background_shape:
                    continue

                # CSV merge
                if shape.name.startswith('@'):
                    val = row_data.get(shape.name, '')
                    if shape.container_type == 'Text':
                        shape.content = str(val) if val is not None else ''
                    elif shape.container_type == 'Image':
                        try:
                            shape.content = Image.open(val).convert('RGBA') if val else None
                        except Exception as e:
                            print(f"!! Failed to load image for shape {shape.name}: {e}")
                            shape.content = None

                # Bounding box
                bbox = shape.get_bbox
                x1, y1, x2, y2 = map(int, bbox)
                w, h = x2 - x1, y2 - y1

                # Outline
                if shape.shape_type == 'rectangle':
                    draw.rectangle([x1, y1, x2, y2], outline=shape.color, width=shape.line_width)
                elif shape.shape_type == 'oval':
                    draw.ellipse([x1, y1, x2, y2], outline=shape.color, width=shape.line_width)
                elif shape.shape_type == 'triangle':
                    cx = (x1 + x2) // 2
                    pts = [(x1, y2), (cx, y1), (x2, y2)]
                    draw.polygon(pts, outline=shape.color, width=shape.line_width)
                elif shape.shape_type == 'hexagon':
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                    hw, hh = (x2 - x1) / 2, (y2 - y1) / 2
                    hex_pts = [
                        (int(cx + hw * math.cos(math.radians(60 * i - 30))),
                         int(cy + hh * math.sin(math.radians(60 * i - 30))))
                        for i in range(6)
                    ]
                    draw.polygon(hex_pts, outline=shape.color, width=shape.line_width)

                # Content
                if shape.container_type == 'Text' and isinstance(shape.content, str):
                    try:
                        font_size = int(h * 0.8)
                        try:
                            font = ImageFont.truetype("arial.ttf", font_size)
                        except IOError:
                            font = ImageFont.load_default()

                        avg_char_width = font.getlength('n') if hasattr(font, 'getlength') else 7
                        max_chars = max(int(w // avg_char_width), 1)
                        wrapped = textwrap.fill(shape.content, width=max_chars)
                        lines = wrapped.split('\n')

                        line_height = font.getbbox('Ay')[3] - font.getbbox('Ay')[1] if hasattr(font, 'getbbox') else font.getsize('Ay')[1]
                        max_lines = int(h // line_height)
                        for i, line in enumerate(lines[:max_lines]):
                            draw.text((x1 + 2, y1 + i * line_height + 2), line, font=font, fill=shape.color)
                    except Exception as e:
                        print(f"!! Failed to draw text in shape {shape.name}: {e}")

                elif shape.container_type == 'Image' and isinstance(shape.content, Image.Image):
                    img = shape.content.resize((w, h), Image.Resampling.LANCZOS)
                    if hasattr(shape, 'clip_image_to_geometry'):
                        img = shape.clip_image_to_geometry(img)
                    image.paste(img, (x1, y1), img if img.mode == 'RGBA' else None)

        return image

    def render_merged_card(self,
                           row_data: dict,
                           model: DrawingModel,
                           model_bounds: tuple[float, float, float, float],
                           target_size_points: tuple[float, float]) -> Image.Image:
        flattened = self.flatten_card(row_data, model)

        from PIL import Image
        RENDER_DPI = 300
        tw_points, th_points = target_size_points
        tw_pixels = max(1, int(round(tw_points * RENDER_DPI / 72.0)))
        th_pixels = max(1, int(round(th_points * RENDER_DPI / 72.0)))

        return flattened.resize((tw_pixels, th_pixels), Image.Resampling.LANCZOS)


# --- Controller - Application Logic and Interaction ───────────────────────────

class DrawingApp: # DrawingApp is now the Controller
    def __init__(self, root: tk.Tk):
        self.root = root

        # Assign the passed-in Model and View instances
        self.model = DrawingModel()
        self.view = DrawingView(root, self)

        # Add this line to register the View as an observer
        self.model.add_observer(lambda: self.view.refresh_all(self.model))

        # Controller state for drawing/interaction
        self.current_tool: Optional[str] = None
        self.start_x: int = 0
        self.start_y: int = 0
        self.drag_start = (0, 0)
        self.is_resizing = False
        self.is_moving = False
        self.resize_start = (0, 0)

        # Controller state for file management and data
        self.current_file_path: Optional[str] = None
        self.csv_data_df: Optional[pd.DataFrame] = None
        self.csv_file_path: Optional[str] = None
        self._refocus_info: Optional[tuple] = None

        # Note: View's internal state (like _shape_id_to_canvas_items, _is_editing_property)
        # and Tkinter variables (grid_var, snap_var) remain in the View.

        # Model's state (grid_visible, snap_to_grid, selected_shape etc.) remains in the Model.

        # Link View's Tkinter variables to Controller's toggle methods (optional, can also link to Model)
        # This is done in View's _build_ui now: command=self.controller.toggle_grid, variable=self.grid_var


        # The View's refresh_all is registered as an observer of the Model
        # in the main execution block AFTER the View and Controller are created.

        # Build Menubar (Controller responsibility)
        self._build_menubar()

        # Initial state sync - Controller updates View's variables from Model
        self.view.grid_var.set(self.model.grid_visible)
        self.view.snap_var.set(self.model.snap_to_grid)


        # Initial refresh is triggered in the main block AFTER everything is wired.
        # self.view.refresh_all(self.model) # Moved this initial call

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
        print(f"\nController.on_canvas_press: ({e.x}, {e.y})")
        self.is_resizing = False; self.is_moving = False; # Reset at the start

        click_x, click_y = self.view.get_canvas_coords(e)
        snapped_x, snapped_y = (self._calculate_snap(click_x, click_y)
                               if self.model.snap_to_grid else (click_x, click_y))
        self.start_x, self.start_y = snapped_x, snapped_y

        # Check resize handle first
        if self.model.selected_shape is not None:
             selected_shape_instance = self.model.get_shape(self.model.selected_shape)
             # Check if click is within the handle of the *currently* selected shape
             if selected_shape_instance and selected_shape_instance.handle_contains(click_x, click_y):
                 print(f"Controller.on_canvas_press: Resize handle clicked for shape ID {self.model.selected_shape}.")
                 self.is_resizing = True; self.resize_start = (snapped_x, snapped_y);
                 self.view.canvas.focus_set()
                 return # Exit as we are resizing

        # Find the topmost shape containing the click point in the current layer
        found_shape_id = None
        current_layer_shapes = self.model.current_layer.shapes
        current_layer_shape_ids_sorted_desc = sorted(current_layer_shapes.keys(), reverse=True)

        for shape_id in current_layer_shape_ids_sorted_desc:
            shape = current_layer_shapes[shape_id]
            if shape.contains_point(click_x, click_y):
                print(f"Controller.on_canvas_press: Click ({click_x}, {click_y}) is inside shape ID {shape_id}.")
                found_shape_id = shape_id
                break

        # If a shape was found
        if found_shape_id is not None:
             if self.model.selected_shape != found_shape_id:
                  # If selecting a *new* shape, call select_shape (updates model, triggers full refresh)
                  print(f"Controller.on_canvas_press: Selecting new shape ID {found_shape_id}.")
                  self.select_shape(found_shape_id) # This triggers refresh_all which draws selection/handle
                  # The rest of the logic (is_moving, drag_start, focus) happens in _post_selection_ui_update
                  # scheduled by select_shape's call to after().
             else:
                 # If clicking the *already* selected shape
                 print(f"Controller.on_canvas_press: Selected shape ID {found_shape_id} clicked again. Preparing for move.")
                 # No model state change needed. Selection visuals should already be present.
                 # Just prepare for moving and ensure focus.
                 selected_shape_instance = self.model.get_shape(found_shape_id);
                 if selected_shape_instance:
                      self.view.canvas.focus_set() # Ensure focus
                      self.is_moving = True; # Controller state
                      shape_bbox = selected_shape_instance.get_bbox;
                      shape_tl_x, shape_tl_y = shape_bbox[0], shape_bbox[1];
                      if self.model.snap_to_grid:
                            snapped_x, snapped_y = self._calculate_snap(e.x, e.y)
                            self.drag_start = (snapped_x - shape_tl_x, snapped_y - shape_tl_y)
                      else:
                            self.drag_start = (click_x - shape_tl_x, click_y - shape_tl_y);

                 else:
                      print(f"Controller.on_canvas_press: Error: Clicked selected shape ID {found_shape_id} but shape not found in model.")
                      self.select_shape(None) # Deselect if shape is missing


             return # Exit after handling selection/moving

        # If no shape or handle was clicked, deselect
        print("Controller.on_canvas_press: No selectable item clicked. Deselecting.")
        self.select_shape(None) # This triggers refresh_all which removes selection

        # If no shape was selected and a tool is active, start drawing
        if self.model.selected_shape is None and self.current_tool:
            print(f"Controller.on_canvas_press: No shape selected and tool '{self.current_tool}' active. Starting to add shape.")
            self.view.create_preview_shape(self.current_tool, self.start_x, self.start_y)

    def on_canvas_drag(self, e):
        x, y = (self._calculate_snap(e.x, e.y)
               if self.model.snap_to_grid else (e.x, e.y))

        # Update preview shape if drawing a new shape
        if self.current_tool: # Check tool state in Controller
             self.view.update_preview_shape(self.current_tool, self.start_x, self.start_y, x, y) # View updates preview


        # Handle moving or resizing the selected shape
        if self.model.selected_shape is not None:
             selected_shape_instance = self.model.get_shape(self.model.selected_shape)
             if not selected_shape_instance:
                  print(f"Controller.on_canvas_drag: Selected shape {self.model.selected_shape} not found during drag.")
                  self.is_moving = self.is_resizing = False # Controller state
                  self.select_shape(None) # Controller method
                  return

             if self.is_resizing:
                 min_size = 5
                 x1, y1, x2, y2 = selected_shape_instance.coords
                 fx, fy = min(x1, x2), min(y1, y2)
                 new_x2 = x; new_y2 = y;
                 if abs(new_x2 - fx) < min_size: new_x2 = fx + (min_size if new_x2 > fx else -min_size)
                 if abs(new_y2 - fy) < min_size: new_y2 = fy + (min_size if new_y2 > fy else -min_size)

                 # Update shape coords in Model (Model notifies observers if changed)
                 self.model.update_shape_coords(selected_shape_instance.id, [x1, y1, new_x2, new_y2])
                 # View's refresh_all (triggered by model) will redraw and update panels


             elif self.is_moving:
                 new_tl_x = x - self.drag_start[0]; new_tl_y = y - self.drag_start[1];
                 current_bbox = selected_shape_instance.get_bbox
                 width = current_bbox[2] - current_bbox[0]; height = current_bbox[3] - current_bbox[1];
                 new_coords = [new_tl_x, new_tl_y, new_tl_x + width, new_tl_y + height]

                 # Update shape coords in Model (Model notifies observers if changed)
                 self.model.update_shape_coords(selected_shape_instance.id, new_coords)
                 # View's refresh_all (triggered by model) will redraw and update panels


    def on_canvas_release(self, e):
        print(f"Controller.on_canvas_release: ({e.x}, {e.y})")
        x, y = (self._calculate_snap(e.x, e.y)
               if self.model.snap_to_grid else (e.x, e.y))

        # Handle finishing a new shape creation
        if self.current_tool: # Check tool state in Controller
            print("Controller.on_canvas_release: Finishing new shape creation.")
            final_x = x; final_y = y; min_dim = 5;
            effective_width = abs(final_x - self.start_x); effective_height = abs(final_y - self.start_y);
            if effective_width < min_dim: final_x = self.start_x + (min_dim if final_x > self.start_x else -min_dim);
            if effective_height < min_dim: final_y = self.start_y + (min_dim if final_y > self.start_y else -min_dim);

            # Create shape object and add to Model (Controller logic)
            new_shape_id = self._create_final_shape_object(final_x, final_y)

            # Clear preview shape from View
            self.view.clear_preview_shape()
            self.current_tool = None # Reset tool state in Controller

            # Select the newly created shape (Controller method)
            if new_shape_id is not None: self.select_shape(new_shape_id)


        # Handle finishing a shape move or resize
        elif self.model.selected_shape is not None and (self.is_moving or self.is_resizing):
            print(f"Controller.on_canvas_release: Finishing move/resize for shape ID {self.model.selected_shape}.")
            # Coords were updated in on_canvas_drag.
            # Model was notified during drag, triggering View updates.
            # Ensure a final refresh if needed (model notify in drag might cover this)
            # self.model.notify_observers() # Redundant if model notified in drag

        # Reset Controller state
        self.is_resizing = False; self.is_moving = False;


    def on_canvas_configure(self, event):
        """Handles canvas resize (Controller logic triggering View update)."""
        # Canvas dimensions updated automatically by Tkinter (View).
        # Trigger a full refresh to redraw grid and shapes scaled to new size.
        self.view.refresh_all(self.model) # View refreshes based on Model state


    def _calculate_snap(self, x, y):
        """Calculates snapped coordinates based on Model's grid size (Controller helper)."""
        return (round(x/self.model.grid_size)*self.model.grid_size,
                round(y/self.model.grid_size)*self.model.grid_size)


    def _create_final_shape_object(self, x, y) -> Optional[Any]:
        """Creates the shape object and adds it to the Model (Controller logic)."""
        all_shape_ids = set(self.model._shape_map.keys())
        iid = 0
        while iid in all_shape_ids:
            iid += 1

        ordered_coords = [min(self.start_x, x), min(self.start_y, y), max(self.start_x, x), max(self.start_y, y)]
        new_shape = None;
        if self.current_tool == 'rectangle': new_shape = Rectangle(id=iid, coords=ordered_coords, name=f"Rectangle {iid}");
        elif self.current_tool == 'oval': new_shape = Oval(id=iid, coords=ordered_coords, name=f"Oval {iid}");
        elif self.current_tool == 'triangle': new_shape = Triangle(id=iid, coords=ordered_coords, name=f"Triangle {iid}");
        elif self.current_tool == 'hexagon': new_shape = Hexagon(id=iid, coords=ordered_coords, name=f"Hexagon {iid}");
        else: return None

        if new_shape:
             self.model.add_shape(new_shape) # Model update + notify
             return new_shape.id
        return None

    def select_shape(self, sid: Optional[Any]):
        if self.model.selected_shape == sid:
            self.root.after(1, lambda: self._post_selection_ui_update(sid))
            return
        self.model.selected_shape = sid
        self.view.refresh_all(self.model)  # Force immediate refresh
        self.root.after(1, lambda: self._post_selection_ui_update(sid))

    def _post_selection_ui_update(self, sid: Optional[Any]):
        pass

    # --- Controller - Listbox and Treeview Event Handlers ---

    def on_shape_select(self, e):
        """Handles selection changes in the Shapes listbox (Controller logic)."""
        if self.view._is_editing_property: return # Ignore during property edit

        listbox_idx = self.view.get_selected_shape_listbox_index()
        if listbox_idx is not None:
            current_layer_shapes_sorted = sorted(self.model.current_layer.shapes.values(), key=lambda shp: shp.id)
            if 0 <= listbox_idx < len(current_layer_shapes_sorted):
                shape_id_to_select = current_layer_shapes_sorted[listbox_idx].id
                if self.model.selected_shape != shape_id_to_select:
                     print(f"\nController.on_shape_select: Listbox selection changed to index {listbox_idx}, shape ID {shape_id_to_select}. Calling select_shape.")
                     self.select_shape(shape_id_to_select) # Controller method
                else:
                     print(f"\nController.on_shape_select: Listbox selection is already selected shape ID {shape_id_to_select}.")
                     pass
                     # If already selected, ensure properties panel is updated/refocused
                     # self.set_refocus_info(shape_id_to_select, None) # Controller state
                     # self.update_properties_panel() # Controller updates View panel

            else: # Invalid index
                 self.select_shape(None)
        else: # Listbox selection cleared
            self.select_shape(None)


    def on_layer_select(self, e):
        """Handles selection changes in the Layers listbox (Controller logic)."""
        if self.view._is_editing_property: return

        listbox_idx = self.view.get_selected_layer_listbox_index()
        if listbox_idx is not None:
            model_layer_idx = len(self.model.layers) - 1 - listbox_idx
            if 0 <= model_layer_idx < len(self.model.layers):
                 if self.model.selected_layer_idx != model_layer_idx:
                     print(f"\nController.on_layer_select: Layer listbox selection changed to listbox index {listbox_idx}, model layer index {model_layer_idx}. Calling model.select_layer.")
                     self.model.select_layer(model_layer_idx) # Model update + notify

                     # Optional: Select the last shape (highest ID) in the newly selected layer
                     shapes_in_layer = self.model.layers[model_layer_idx].shapes
                     if shapes_in_layer:
                         last_shape_id = max(shapes_in_layer.keys())
                         print(f"Controller.on_layer_select: New layer has shapes, attempting to select last shape ID: {last_shape_id}")
                         # Use after(0, ...) to allow the current event handler to finish
                         # and the refresh_all triggered by model.select_layer to start,
                         # before initiating a new selection.
                         self.root.after(1, lambda: self.select_shape(last_shape_id)) # Controller method
                     else:
                         print("Controller.on_layer_select: New layer has no shapes, deselecting shape.")
                         self.root.after(1, lambda: self.select_shape(None)) # Controller method

                 else:
                     print(f"\nController.on_layer_select: Layer listbox selection is already selected model layer index {model_layer_idx}.")
                     # If same layer, just ensure properties panel is updated
                     self.update_properties_panel() # Controller updates View panel

        # No need to handle else (selection cleared) as listbox mode="browse"


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

        handler = PROPERTY_HANDLERS.get(property_name)
        if not handler:
            print(f"Controller.handle_property_edit_commit: No handler defined for property '{property_name}'.")
            self.update_properties_panel() # Refresh panel
            return

        stripped_value = new_value_str.strip()

        if "validate" in handler:
            if not handler["validate"](stripped_value):
                 print(f"Controller.handle_property_edit_commit: Validation failed.")
                 self.set_refocus_info(shape_id, property_name) # Controller state
                 self.update_properties_panel() # Refresh panel
                 return

        value = stripped_value
        if "type" in handler:
            try: value = handler["type"](stripped_value)
            except ValueError:
                print(f"Controller.handle_property_edit_commit: Invalid type.")
                self.set_refocus_info(shape_id, property_name) # Controller state
                self.update_properties_panel() # Refresh panel
                return

        # --- Apply the change to the Model using Model methods ---
        # Controller calls Model methods based on property and validated value
        if property_name == "X": self.model.update_shape_coords(shape_id, [value, shape.coords[1], shape.coords[2], shape.coords[3]])
        elif property_name == "Y": self.model.update_shape_coords(shape_id, [shape.coords[0], value, shape.coords[2], shape.coords[3]])
        elif property_name == "Width": self.model.update_shape_coords(shape_id, [shape.get_bbox[0], shape.get_bbox[1], shape.get_bbox[0] + max(0, value), shape.get_bbox[3]])
        elif property_name == "Height": self.model.update_shape_coords(shape_id, [shape.get_bbox[0], shape.get_bbox[1], shape.get_bbox[2], shape.get_bbox[1] + max(0, value)])
        elif property_name == "Shape Type": self.model.reclassify_shape(shape_id, new_shape_type=value)
        elif property_name == "Container Type": self.model.set_container(shape_id, container_type=value)
        elif property_name == "Name": self.model.rename_shape(shape_id, new_name=value)
        elif property_name == "Color": self.model.set_color(shape_id, color=value)
        elif property_name == "Line Width": self.model.set_line_width(shape_id, line_width=value)
        elif property_name == "Text": self.model.set_text(shape_id, text=value)
        elif property_name == "Path": self.model.set_path(shape_id, path=value)
        # ... add other property updates here ...

        # If the change was a geometric one (X, Y, Width, Height), the Model's update_shape_coords
        # already notified observers if the coordinates changed.
        # If the change was Name, Type, Container, Color, Line Width, Text, Path,
        # the respective model setters already notified observers.
        # The View's refresh_all (triggered by Model notification) will update the panel.
        # Set refocus info *before* the Model notification triggers refresh_all
        self.set_refocus_info(shape_id, property_name)

        print(f"Controller.handle_property_edit_commit: Model updated for property '{property_name}'. Model notified. Refresh pending.")


    def update_properties_panel(self):
        """Updates the properties panel with correct refocus"""
        selected_shape_data = self.model.get_shape(self.model.selected_shape)
        self.view._update_properties_panel(
            selected_shape_data, 
            self.get_refocus_info()
        )
        self.reset_refocus_info()

    def set_refocus_info(self, refocus_tuple: Optional[tuple]):
        """Sets refocus info in Controller state for View to use."""
        self._refocus_info = refocus_tuple

    def get_refocus_info(self) -> Optional[tuple]:
        """Returns refocus info as (sid, prop_name) tuple"""
        return self._refocus_info

    def reset_refocus_info(self):
         """Resets refocus info in Controller state."""
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

    def remove_selected_layer(self): # This method is called by the button command in the View
        """Handles removing the currently selected layer (Controller logic)."""
        # Check if the View is currently editing a property
        if self.view._is_editing_property:
             print("remove_selected_layer: Ignored during editing.")
             return

        # Get the selected layer index from the View's listbox
        listbox_idx = self.view.get_selected_layer_listbox_index()
        if listbox_idx is None:
            print("remove_selected_layer: No layer selected in the listbox.")
            return

        # Convert the listbox index (reversed order) to the model index
        model_layer_idx = len(self.model.layers) - 1 - listbox_idx
        print(f"remove_selected_layer: Removing layer at model index {model_layer_idx}.")

        # Call the Model method to perform the data removal
        self.model.remove_layer(model_layer_idx) # Model update + notify

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
            with open(file_path, 'r') as f: data = json.load(f);
            self.model.from_dict(data) # Load data into the Model (Model updates state)
            self.current_file_path = file_path # Controller state
            self.view.master.title(f"Enhanced Vector Editor - {os.path.basename(file_path)}") # Update View title
            self.view.hide_merge_panel() # Update View panel visibility
            self.csv_data_df = None; self.csv_file_path = None; # Clear Controller state
            print(f"Controller.open_drawing: Successfully loaded drawing from {file_path}.")
            # Model.from_dict notifies observers, triggering view.refresh_all
            # Force an immediate refresh
            self.view.refresh_all(self.model)            
        except FileNotFoundError: messagebox.showerror("Error", f"File not found:\n{file_path}");
        except json.JSONDecodeError: messagebox.showerror("Error", f"Invalid file format:\n{file_path}");
        except Exception as e: messagebox.showerror("Error", f"An error occurred:\n{e}");

    def save_drawing(self):
        """Saves the current drawing (Controller logic)."""
        if self.current_file_path: self._save_to_file(self.current_file_path);
        else: self.save_drawing_as();

    def save_drawing_as(self):
        """Saves the current drawing to a new file (Controller logic)."""
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")]);
        if file_path: self._save_to_file(file_path);

    def _save_to_file(self, file_path: str):
        """Internal save method (Controller logic)."""
        print(f"\nController._save_to_file: Saving model state to {file_path}.")
        try:
            model_data = self.model.to_dict();
            with open(file_path, 'w') as f: json.dump(model_data, f, indent=4);
            self.current_file_path = file_path; # Controller state
            self.view.master.title(f"Enhanced Vector Editor - {os.path.basename(file_path)}"); # Update View title
            print(f"Controller._save_to_file: Successfully saved drawing to {file_path}.")
        except Exception as e: messagebox.showerror("Error", f"An error occurred while saving:\n{e}");
    # --- Controller - Import as Component ---

    def import_component_from_file(self, filepath, max_nesting=2):
        data = load_json(filepath)
        component = parse_component_data(data, current_depth=0, max_depth=max_nesting)
        self.model.components.append(component)

    def parse_component_data(data, current_depth, max_depth):
        if current_depth >= max_depth:
            return flatten_component_to_image(data)  # return a ShapeModel with the image

        layers = []
        for layer_data in data["layers"]:
            if "component" in layer_data:
                layers.append(parse_component_data(layer_data["component"], current_depth + 1, max_depth))
            else:
                layers.append(LayerModel.from_dict(layer_data))

        return ComponentModel(layers)

    def create_component_from_selected_layers(self):
        selected = self.layer_panel.get_selected_layers()
        if not selected:
            return
        component = ComponentModel(selected)
        self.model.components.append(component)
        for layer in selected:
            self.model.layers.remove(layer)
        self.refresh_view()


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
                except ValueError:
                    messagebox.showerror(
                        "Invalid Input",
                        "Please supply two positive numbers separated by a comma."
                    )
                    return
            else:
                return  # user cancelled

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

    def export_to_pdf(self,
                          export_path: str,
                          page: str = 'LETTER',
                          use_card: bool = False,
                          custom_size: Optional[tuple] = None,
                          cards_per_page: Optional[int] = None,
                          rotate_card: bool = False):
            """
            Exports the drawing to a PDF file. For 8-up and 9-up layouts,
            renders the entire grid as a single image centered on the page.
            Otherwise, uses a fallback layout fitting cards individually.
            """
            print(f"\nController.export_to_pdf: Exporting to PDF: {export_path}")
            try:
                from reportlab.lib.pagesizes import LETTER, A4
                from reportlab.lib.units import inch
                from reportlab.pdfgen import canvas as pdf_canvas
                from PIL import Image as PILImage, ImageDraw
                import io
                import traceback

                # 1) Page setup
                pagesize = LETTER if page.upper() == 'LETTER' else A4
                pw, ph   = pagesize

                # No margins for the grid placement - the single image will be centered
                mx, my = 0, 0 # Margins for the PDF canvas

                # Card dimensions in portrait
                card_portrait_width_inch = 2.5
                card_portrait_height_inch = 3.5
                card_portrait_width_pt = card_portrait_width_inch * inch
                card_portrait_height_pt = card_portrait_height_inch * inch

                # DPI for rendering the grid image in pixels
                RENDER_DPI = 300

                # 2) Layout based on cards_per_page
                cols = 0
                rows = 0
                # Dimensions of the grid in points (for PDF placement)
                total_grid_width_pt = 0
                total_grid_height_pt = 0
                # Dimensions of the grid in pixels (for PIL rendering)
                total_grid_width_px = 0
                total_grid_height_px = 0

                if cards_per_page == 9:
                    cols, rows  = 3, 3
                    # Total grid dimensions in points
                    total_grid_width_pt = cols * card_portrait_width_pt
                    total_grid_height_pt = rows * card_portrait_height_pt
                    # Total grid dimensions in pixels
                    total_grid_width_px = int(round(total_grid_width_pt * RENDER_DPI / 72.0))
                    total_grid_height_px = int(round(total_grid_height_pt * RENDER_DPI / 72.0))
                    rotate_card = False # No rotation for 9-up
                    print("Controller.export_to_pdf: 9-up → 3×3 grid, 2.5x3.5 inch portrait cards, render as single image.")

                elif cards_per_page == 8:
                    cols, rows  = 2, 4 # 2 columns, 4 rows for portrait page on a portrait page
                     # Card dimensions on the page (rotated) are 3.5x2.5
                    card_landscape_width_pt = card_portrait_height_inch * inch # 3.5 inches
                    card_landscape_height_pt = card_portrait_width_inch * inch # 2.5 inches
                    # Total grid dimensions in points
                    total_grid_width_pt = cols * card_landscape_width_pt
                    total_grid_height_pt = rows * card_landscape_height_pt
                     # Total grid dimensions in pixels
                    total_grid_width_px = int(round(total_grid_width_pt * RENDER_DPI / 72.0))
                    total_grid_height_px = int(round(total_grid_height_pt * RENDER_DPI / 72.0))
                    rotate_card = True # Explicitly set rotate for 8-up
                    print("Controller.export_to_pdf: 8-up → 2×4 grid, 3.5x2.5 inch landscape cells (for rotated cards), render as single image.")

                # 3) PDF canvas
                pdf = pdf_canvas.Canvas(export_path, pagesize=pagesize)

                # 4) Records
                records = (self.csv_data_df.to_dict('records')
                           if self.csv_data_df is not None else [{}])
                if not records:
                    records = [{}]
                    print("Controller.export_to_pdf: No CSV data → blank card")

                # 5) Model bounds
                model_bounds = self.model.get_model_bounds()

                # 6) Render and draw pages
                if cards_per_page in [8, 9]:
                     # --- Render the entire grid as a single image ---
                     if total_grid_width_px <= 0 or total_grid_height_px <= 0:
                          print("Controller.export_to_pdf: Calculated grid pixel dimensions are zero or negative.")
                          # Fallback to drawing individual cards if grid size is invalid
                          cards_per_page = None # Forces fallback logic
                     else:
                         for start in range(0, len(records), cards_per_page):
                             page_recs = records[start:start + cards_per_page]

                             # Create a large canvas for the entire grid page in pixels
                             grid_image = PILImage.new('RGBA', (total_grid_width_px, total_grid_height_px), (255, 255, 255, 0))
                             # No need for ImageDraw on the grid_image unless adding grid lines later

                             # Calculate pixel dimensions for a single card based on RENDER_DPI
                             single_card_render_width_px = int(round(card_portrait_width_pt * RENDER_DPI / 72.0))
                             single_card_render_height_px = int(round(card_portrait_height_pt * RENDER_DPI / 72.0))

                             # Calculate pixel dimensions of a cell in the grid
                             cell_width_px = int(round(total_grid_width_pt / cols * RENDER_DPI / 72.0))
                             cell_height_px = int(round(total_grid_height_pt / rows * RENDER_DPI / 72.0))


                             for idx, row in enumerate(page_recs):
                                 # Calculate position within the grid (0-indexed, top-left is 0,0)
                                 col_idx = idx % cols
                                 row_idx_in_grid = idx // cols

                                 # Render a single card
                                 # The target size for rendering content is always the portrait card size
                                 single_card_image = self.view.render_merged_card(
                                      row, self.model, model_bounds,
                                      (card_portrait_width_pt, card_portrait_height_pt) # Target size for rendering content in points
                                 )

                                 # Rotate the single card image if needed for 8-up layout
                                 if rotate_card:
                                     single_card_image = rotate_image_90_clockwise(single_card_image)
                                     # After rotation, the pixel dimensions of single_card_image
                                     # should correspond to the landscape size (3.5x2.5 inches at RENDER_DPI)

                                 # Calculate the pixel position on the grid_image where this card should be pasted
                                 # Paste position is top-left corner of the cell in pixels
                                 paste_x_px = col_idx * cell_width_px
                                 paste_y_px = row_idx_in_grid * cell_height_px


                                 # Paste the rendered single card image onto the grid image
                                 # Ensure the single_card_image dimensions match the cell dimensions in pixels if rotated.
                                 # If not rotated, they match the portrait card dimensions in pixels.
                                 # The pasting logic should handle potential size mismatches if scaling is needed here.
                                 # However, render_merged_card should output at the requested size in points * RENDER_DPI/72.
                                 # Let's ensure the rendered single card size matches the cell size before pasting.

                                 # Re-rendering single card with target size matching the *cell* size in points
                                 target_single_card_pt = (card_portrait_width_pt, card_portrait_height_pt)
                                 if rotate_card:
                                      target_single_card_pt = (card_landscape_width_pt, card_landscape_height_pt) # Render at landscape size for 8-up

                                 single_card_image = self.view.render_merged_card(
                                      row, self.model, model_bounds,
                                      target_single_card_pt # Target size in points for the cell
                                 )

                                 # Now single_card_image has pixel dimensions corresponding to target_single_card_pt at RENDER_DPI

                                 # Rotate if needed (applied after rendering to target cell size)
                                 if rotate_card:
                                      single_card_image = rotate_image_90_clockwise(single_card_image)
                                      # After rotation, pixel dims match landscape size at RENDER_DPI


                                 # Paste the rendered single card image onto the grid image
                                 # The size of single_card_image in pixels should now match cell_width_px x cell_height_px if rotated,
                                 # or portrait_width_px x portrait_height_px if not rotated.
                                 # The paste position is the top-left of the cell.
                                 # If not rotated (9-up), paste a portrait card into a portrait cell.
                                 # If rotated (8-up), paste a rotated landscape card into a landscape cell.

                                 # Ensure the image being pasted has the correct pixel dimensions for the cell
                                 # If the rendered single card image's pixel size doesn't exactly match cell_width_px/cell_height_px,
                                 # we should resize it before pasting to avoid distortion or gaps.

                                 expected_paste_width_px = cell_width_px
                                 expected_paste_height_px = cell_height_px

                                 if single_card_image.width != expected_paste_width_px or single_card_image.height != expected_paste_height_px:
                                      print(f"Controller.export_to_pdf: Resizing single card image for pasting: {single_card_image.size} -> ({expected_paste_width_px}, {expected_paste_height_px})")
                                      single_card_image = single_card_image.resize((expected_paste_width_px, expected_paste_height_px), Image.Resampling.LANCZOS)


                                 grid_image.paste(single_card_image, (paste_x_px, paste_y_px))


                             # --- Embed the finished grid image onto the PDF page ---
                             # Convert grid_image to RGB for embedding in PDF
                             if grid_image.mode == 'RGBA':
                                bg = PILImage.new('RGB', grid_image.size, (255,255,255))
                                bg.paste(grid_image, mask=grid_image.split()[3])
                                grid_image = bg
                             elif grid_image.mode != 'RGB':
                                grid_image = grid_image.convert('RGB')

                             buf = io.BytesIO()
                             grid_image.save(buf, format='PNG')
                             buf.seek(0)

                             # Calculate position to center the grid image on the PDF page
                             center_x_page = pw / 2
                             center_y_page = ph / 2

                             # Bottom-left position for embedding the grid image
                             embed_x = center_x_page - total_grid_width_pt / 2
                             embed_y = center_y_page - total_grid_height_pt / 2

                             # Embed the grid image. ReportLab will scale the pixel image
                             # to fit the specified width and height in points.
                             pdf.drawInlineImage(
                                PILImage.open(buf),
                                embed_x, embed_y,
                                width=total_grid_width_pt, # Embed at the total grid width in points
                                height=total_grid_height_pt, # Embed at the total grid height in points
                                preserveAspectRatio=False # Force image to fill the space
                             )


                             if start + cards_per_page < len(records):
                                 pdf.showPage()

                else:
                    # --- Fallback: Draw individual cards directly onto the PDF ---
                    # This is the previous logic for fitting as many as possible

                    # Calculate cell size by fitting to the page
                    cell_width, cell_height = None, None
                    fallback_cols, fallback_rows = 0, 0

                    if use_card:
                        cell_width_init, cell_height_init = (card_portrait_width_pt, card_portrait_height_pt)
                    elif custom_size:
                        cell_width_init, cell_height_init = (custom_size[0]*inch, custom_size[1]*inch)
                    else:
                        cell_width_init, cell_height_init = (pw, ph) # Fit one per page

                    fallback_cols = max(int(pw // cell_width_init), 1)
                    fallback_rows = max(int(ph // cell_height_init), 1)
                    fallback_cards_per_page = fallback_cols * fallback_rows

                    cell_width, cell_height = pw/fallback_cols, ph/fallback_rows # Recalculate cell size based on fitted grid


                    print(f"Controller.export_to_pdf: auto-fit fallback → {fallback_cols}×{fallback_rows} = {fallback_cards_per_page}")

                    for start in range(0, len(records), fallback_cards_per_page):
                        page_recs = records[start:start + fallback_cards_per_page]
                        for idx, row in enumerate(page_recs):
                            # Calculate position in the grid (0-indexed, top-left is 0,0)
                            col_idx = idx % fallback_cols
                            row_idx_in_grid = idx // fallback_cols

                            # Calculate drawing position on the PDF page (bottom-left corner of the cell)
                            # Position from top-left of the page with no margins in this mode
                            x0 = col_idx * cell_width
                            y0 = ph - (row_idx_in_grid + 1) * cell_height


                            # Determine the target rendering size for a single card in points
                            # For the fallback, render at the calculated cell size
                            target_render_pt = (cell_width, cell_height)

                            # Render a single card image
                            single_card_image = self.view.render_merged_card(
                                 row, self.model, model_bounds,
                                 target_render_pt # Target size for rendering content in points (cell size)
                            )

                            # No rotation in fallback mode
                            # No need to paste onto a grid image, draw directly

                            # Convert to RGB for embedding
                            if single_card_image.mode == 'RGBA':
                                bg = PILImage.new('RGB', single_card_image.size, (255,255,255))
                                bg.paste(single_card_image, mask=single_card_image.split()[3])
                                single_card_image = bg
                            elif single_card_image.mode != 'RGB':
                                 single_card_image = single_card_image.convert('RGB')

                            buf = io.BytesIO()
                            single_card_image.save(buf, format='PNG')
                            buf.seek(0)

                            # Embed the single card image
                            pdf.drawInlineImage(
                                PILImage.open(buf),
                                x0, y0,
                                width=cell_width,
                                height=cell_height,
                                preserveAspectRatio=False # Force fill the cell
                            )

                        if start + fallback_cards_per_page < len(records):
                            pdf.showPage()


                # 7) Save
                pdf.save()
                messagebox.showinfo('Export PDF',
                                    f'Exported {len(records)} card(s) to\n{export_path}')

            except ImportError:
                messagebox.showerror("Missing Dependency",
                                     "Please install ReportLab (`pip install reportlab`).")
            except Exception as e:
                # Print the full traceback for debugging
                traceback.print_exc()
                messagebox.showerror("Export Error", f"An error occurred during PDF export:\n{e}\nCheck console for details.")

# Keep the rotate_image_90_clockwise function as is
def rotate_image_90_clockwise(img: Image) -> Image:
    """Returns a new image rotated 90 degrees clockwise."""
    # Use ROTATE_270 for clockwise rotation
    return img.transpose(Image.Transpose.ROTATE_270)

# Add render_merged_card to DrawingView

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Enhanced Vector Editor')
    parser.add_argument('file', nargs='?', help='JSON file to open')
    parser.add_argument('-i','--import',dest='csv_path',help='CSV to import')
    parser.add_argument('-e','--export_pdf',dest='export_pdf',metavar='OUT.pdf',help='Export to PDF and exit')
    parser.add_argument('-c','--cards',type=int,choices=[8,9],help="Number of cards per page")
    parser.add_argument('--use-card', action='store_true', help='Render cards using card layout')
    parser.add_argument('-p','--page_size',choices=['letter','a4'],default='letter',dest='page_size',help='PDF page size')
    parser.add_argument('-s','--size',dest='custom_size',metavar='W,H',help='Custom component size in inches (W,H)')
    args = parser.parse_args()

    # Initialize Tk
    root = tk.Tk()
    root.lift()

    # Check only for truly fatal GUI / library misses;
    # we no longer pre‐check for reportlab here.
    missing = []
    try:
        Image.new('RGB',(1,1))
        from PIL import ImageTk, ImageDraw, ImageFont
    except ImportError:
        missing.append('Pillow')
    try:
        import pandas as pd
        pd.DataFrame()
    except ImportError:
        missing.append('pandas')

    if missing:
        messagebox.showerror('Missing Dependencies',
                             f"Install the following packages: {', '.join(missing)}")
        root.destroy()
        exit()

    # Parse custom size if given
    custom_size_tuple = None
    if args.custom_size:
        try:
            w_str, h_str = args.custom_size.split(',')
            custom_size_tuple = (float(w_str), float(h_str))
        except ValueError:
            messagebox.showerror("Invalid Argument",
                                 "Invalid custom size format. Use W,H (e.g., 5,7).")
            root.destroy()
            exit()

    # Instantiate and wire up Controller / View / Model
    controller = DrawingApp(root)

    # Handle file & CSV import
    if args.file:
        controller.open_drawing(args.file)
    if args.csv_path:
        controller.import_csv(args.csv_path)

    # If export requested, call export_to_pdf (ReportLab import error will be caught there)
    if args.export_pdf:
        use_card = args.use_card
        if args.use_card and custom_size_tuple:
            print("Warning: Both --use-card and --size specified. Using --size.")
            use_card = False
        elif custom_size_tuple:
            use_card = False

        controller.export_to_pdf(
            export_path     = args.export_pdf,
            page            = args.page_size.upper(),
            use_card        = use_card,
            custom_size     = custom_size_tuple,
            cards_per_page  = args.cards,
            rotate_card     = (args.cards == 8 and args.page_size.upper() == 'A4')
        )
        root.destroy()
    else:
        controller.view.refresh_all(controller.model)
        root.mainloop()
