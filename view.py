# view.py

import tkinter as tk      # For core Tkinter widgets and functionality
from tkinter import ttk, messagebox # For themed widgets and message boxes

# For handling and displaying images on the Tkinter canvas
# Import necessary components from PIL
from PIL import Image, ImageTk, ImageDraw # Add ImageDraw here
import pandas as pd
# Note: ImageDraw and ImageFont are likely used within the Shape's
# _draw_text_content method or a PDF export utility, not directly
# in the main DrawingView rendering loop.

import math             # For mathematical calculations (e.g., drawing grid, shape geometry)
from typing import List, Dict, Optional, Any, Tuple # For type hinting

# Assuming the base Shape class is in shapes/base_shape.py
from shapes.base_shape import Shape

# Assuming the DrawingModel is in model.py
from model import DrawingModel, Layer# The view observes and displays the model

# Assuming utility functions like _calculate_snap are in utils/geometry.py
from utils.geometry import calculate_snap # If used in canvas event handlers

# Assuming constants are in a central constants.py at the root level
from constants import CANVAS_WIDTH, CANVAS_HEIGHT, PANEL_WIDTH, TOOLBAR_HEIGHT, PPI # Import necessary constants
from constants import SHAPE_BUTTONS, CONTAINER_TYPES, SHAPE_TYPES# Import all necessary constants
# Need to import DrawingModel for type hinting in set_model
from model import DrawingModel

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

        # Check user's system resolution first, then adjust grid.
        self.ppi = self.canvas.winfo_fpixels("1i")
        # Set grid size to actual ppi of user's native resolution as soon as we grab it.
        self.ppi_to_model_grid(self.controller.model)

        # Bind events to controller methods
        self._bind_events()

        # Initial setup
        master.title("Enhanced Vector Editor - Untitled") # Initial title

    def ppi_to_model_grid(self, model, measure=None):
        # if none, default to last used by the model
        if not measure:
            measure = model.measure
        else:
            model.measure = measure

        if measure == "inch":
            model.grid_ppi = self.ppi
            model.subdivision = 16
            model.division = 4
            model.grid_size = int(model.ppi / model.subdivision)
        if measure == "cm":
            model.grid_ppi = int(self.ppi * 2.54)
            model.subdivision = 10
            model.division = 1
            model.grid_size = int(model.ppi)
            return grid_size

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


        # === Drawing container (with rulers + canvas) ===
        self.drawing_area = tk.Frame(self.pane)
        self.pane.add(self.drawing_area, stretch="always")

        # Canvas (Drawing Surface)
        self.canvas = tk.Canvas(
            self.drawing_area,
            bg='white'
        )
        self.pane.add(self.drawing_area, stretch="always")
  
        # Ruler sizes
        self.ruler_size = 20
        # Top-left corner
        self.corner = tk.Canvas(
            self.drawing_area,
            width=self.ruler_size/2,
            height=self.ruler_size/2,
            bg='lightgray',
            highlightthickness=0
        )
        # Horizontal ruler
        self.horizontal_ruler = tk.Canvas(
            self.drawing_area,
            height=self.ruler_size/2,
            bg='lightgray',
            highlightthickness=0
        )
        # Vertical ruler
        self.vertical_ruler = tk.Canvas(
            self.drawing_area,
            width=self.ruler_size/2,
            bg='lightgray',
            highlightthickness=0
        )

        # Actual drawing surface
        self.canvas = tk.Canvas(
            self.drawing_area,
            bg='white',
            highlightthickness=0,
            xscrollincrement=1,
            yscrollincrement=1,
            width=CANVAS_WIDTH,  # Set initial width using the constant
            height=CANVAS_HEIGHT # Set initial height using the constant
        )

        # Scrollbars attached to drawing canvas
        self.h_scroll = tk.Scrollbar(
            self.drawing_area,
            orient=tk.HORIZONTAL,
            command=self.canvas.xview
        )
        self.v_scroll = tk.Scrollbar(
            self.drawing_area,
            orient=tk.VERTICAL,
            command=self.canvas.yview
        )
        self.canvas.configure(
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set
        )

        # Layout for rulers, canvas, scrollbars
        self.corner.grid(row=0, column=0, sticky='nsew')
        self.horizontal_ruler.grid(row=0, column=1, sticky='ew')
        self.vertical_ruler.grid(row=1, column=0, sticky='ns')
        self.canvas.grid(row=1, column=1, sticky='nsew')
        self.h_scroll.grid(row=2, column=1, sticky='ew')
        self.v_scroll.grid(row=1, column=2, sticky='ns')

        # Make drawing_area expandable
        self.drawing_area.rowconfigure(1, weight=1)
        self.drawing_area.columnconfigure(1, weight=1)


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
        self._draw_grid()
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
            for shape_id in sorted(layer.shapes.keys()):
                 shape = layer.shapes[shape_id]
                 print(f"DrawingView.refresh_all: Drawing shape ID {shape.sid} ('{shape.name}', Type: {shape.shape_type}).")
                 # Use View method to draw the shape
                 self._draw_shape_on_canvas(shape, self.canvas)

        self.draw_selected_shape()

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
        current_layer_shapes_sorted = sorted(layers[selected_layer_idx].shapes.values(), key=lambda s: s.sid)

        for shape in current_layer_shapes_sorted:
            self.shapes_lb.insert(tk.END, shape.name)

        if selected_shape_id is not None:
            shape_ids_in_listbox = [s.sid for s in current_layer_shapes_sorted]
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

    def draw_selected_shape(self):
        model_state = self.controller.model
        selected_shape_id = model_state.selected_shape
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

    def _draw_grid(self):
        """Draws the grid on the canvas (View logic)."""
        grid_size = self.controller.model.grid_size
        canvas_width, canvas_height = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.canvas.delete("grid")
        if self.controller.model.grid_visible and canvas_width > 0 and canvas_height > 0:
            for x in range(0, canvas_width, grid_size):
                self.canvas.create_line(x, 0, x, canvas_height, fill='lightgray', tags="grid")
            for y in range(0, canvas_height, grid_size):
                self.canvas.create_line(0, y, canvas_width, y, fill='lightgray', tags="grid")
        print("Now Drawing Ruler")
        self._draw_ruler()

    def _draw_ruler(self):
        self.horizontal_ruler.delete("all")
        self.vertical_ruler.delete("all")
        grid_size = self.controller.model.grid_size
        divisions = self.controller.model.grid_division
        subdivisions = self.controller.model.grid_subdivision
        subsub = self.controller.model.grid_subsubdivision
        canvas_width, canvas_height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self.controller.model.grid_visible and canvas_width > 0 and canvas_height > 0:
            for i, x in enumerate(range(0, canvas_width, grid_size)):
                if i % divisions == 0 and i % subdivisions != 0:
                    self.horizontal_ruler.create_line(x, 0, x, self.ruler_size/subdivisions, fill='gray', tags="grid")
                elif i % subdivisions == 0:
                    self.horizontal_ruler.create_line(x, 0, x, self.ruler_size/divisions, fill='black', tags="grid")
                else:
                    self.horizontal_ruler.create_line(x, 0, x, self.ruler_size/subsub, fill='gray', tags="grid")
            for i, y in enumerate(range(0, canvas_height, grid_size)):
                if i % divisions == 0 and i % subdivisions != 0:
                    self.vertical_ruler.create_line(0, y, self.ruler_size/subdivisions, y, fill='gray', tags="grid")
                elif i % subdivisions == 0:
                    self.vertical_ruler.create_line(0, y, self.ruler_size/divisions, y, fill='black', tags="grid")
                else:
                    self.vertical_ruler.create_line(0, y, self.ruler_size/subsub, y, fill='gray', tags="grid")

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
        tags = ('shape', f'id{shape.sid}')
        item_id = shape.draw_shape(canvas)

    def _draw_name_label_on_canvas(self, shape: Shape, canvas: tk.Canvas):
        """Draws the name label on the Tkinter canvas (View logic)."""
        if not shape.name: return
        x1, y1, x2, y2 = shape.get_bbox; tx, ty = min(x1, x2), min(y1, y2)
        label_text = shape.name; font_size = 8; padding = 2; label_color = 'black'
        box_fill_color = 'lightgray'; box_outline_color = 'gray'; line_width = 1

        try:
            font = ('Arial Unicode', font_size)
            estimated_char_width = font_size * 0.6; text_width = len(label_text) * estimated_char_width; text_height = font_size
            box_width = text_width + 2 * padding; box_height = text_height + 2 * padding
            if box_width > abs(x2 - x1): box_width = abs(x2 - x1)
            label_x1, label_y1 = tx, ty; label_x2, label_y2 = label_x1 + box_width, label_y1 - box_height

            rect_id = canvas.create_rectangle(label_x1, label_y1, label_x2, label_y2, fill=box_fill_color, outline=box_outline_color, width=line_width, tags=('name_label', f'name_label_of_{shape.sid}'))
            self._shape_id_to_canvas_items.setdefault(shape.sid, []).append(rect_id)

            text_x = label_x1 + padding; text_y = label_y1 - box_height + padding
            text_id = canvas.create_text(text_x, text_y, text=label_text, fill=label_color, font=font, anchor='nw', tags=('name_label_text', f'name_label_text_of_{shape.sid}'))
            self._shape_id_to_canvas_items.setdefault(shape.sid, []).append(text_id)
        except Exception as e: print(f"!! View: Error drawing Tkinter name label for shape {shape.sid}: {e}")

    def _draw_shape_on_canvas(self, shape: Shape, canvas: tk.Canvas):
             """Draws a complete shape on the Tkinter canvas (View logic)."""
             # Clearing is handled by refresh_all or _redraw_shape_and_selection
             self._draw_shape_outline_on_canvas(shape, canvas)
             self._draw_name_label_on_canvas(shape, canvas) # Keep or remove as needed


             # Handle content drawing based on container type
             if shape.container_type == "Text":
                # Ensure text content is generated before attempting to draw it
                # This should ideally be triggered by text/font/size/justification changes
                # If not already generated, call it here as a fallback for drawing
                if not isinstance(shape.content, Image.Image):
                    shape._draw_text_content()

                # Now, if shape.content is a PIL Image, draw it
                if isinstance(shape.content, Image.Image):
                     try:
                         # Convert PIL Image to Tkinter PhotoImage
                         tk_image = ImageTk.PhotoImage(shape.content)

                         # Store a reference to the PhotoImage to prevent garbage collection
                         self._shape_id_to_tk_image[shape.sid] = tk_image

                         # Get the top-left coordinates of the shape
                         x1, y1, x2, y2 = shape.get_bbox
                         draw_x, draw_y = int(min(x1, x2)), int(min(y1, y2))

                         # Create the image item on the canvas
                         image_item_id = canvas.create_image(
                             draw_x, draw_y,
                             image=tk_image,
                             anchor='nw', # Anchor the image by its top-left corner
                             tags=('shape', f'id{shape.sid}', 'text_content')
                         )
                         # Add the image item ID to the list of canvas items for this shape
                         self._shape_id_to_canvas_items.setdefault(shape.sid, []).append(image_item_id)

                     except Exception as e:
                         print(f"!! View: Error drawing text image for shape {shape.sid}: {e}")


             elif shape.container_type == "Image":
                 # Handle drawing image content
                 # The image should have been loaded into shape.content by _load_image_content
                 # when the path was set or the shape was loaded.
                 # Just check if shape.content is a valid PIL Image and draw it.
                 if isinstance(shape.content, Image.Image):
                     try:
                        # shape.content should already be the clipped/resized image from _load_image_content
                        # Use shape.content directly to create the PhotoImage
                        tk_image = ImageTk.PhotoImage(shape.content)

                        # Store a reference
                        self._shape_id_to_tk_image[shape.sid] = tk_image

                        # Get the top-left coordinates of the shape's bounding box for drawing
                        x1, y1, x2, y2 = shape.get_bbox
                        draw_x, draw_y = int(min(x1, x2)), int(min(y1, y2))

                        # Create the image item on the canvas
                        image_item_id = canvas.create_image(
                            draw_x, draw_y,
                            image=tk_image,
                            anchor='nw', # Anchor the image by its top-left corner
                            tags=('shape', f'id{shape.sid}', 'image_content')
                        )
                        # Add the image item ID to the list of canvas items for this shape
                        self._shape_id_to_canvas_items.setdefault(shape.sid, []).append(image_item_id)

                     except Exception as e:
                        print(f"!! View: Error drawing image content for shape {shape.sid}: {e}")
                        # Optionally draw a placeholder or error indicator if image loading failed
                        # e.g., draw a red X or a text error message
                 elif shape.path:
                     print(f"View: Image content for shape {shape.sid} not loaded, but path exists: {shape.path}.\n\tCheck your path to ensure that it exists or ignore this message.\n\tIf the file in the current directory add './' before the file name.)")
                     pass


    def redraw_shape_and_selection(self, shape: Shape, is_selected: bool):
        """Clears and redraws a specific shape, and its selection/handle if selected (View logic)."""
        if not shape: return

        self._clear_shape_drawing_on_canvas(shape.sid)
        self.canvas.delete(f"select_{shape.sid}")
        self.canvas.delete(f"handle_{shape.sid}")

        self._draw_shape_on_canvas(shape, self.canvas)

        self.draw_selected_shape()

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
            if selected_shape.container_type == "Text":
                properties_to_display += ["Text", "Font Name", "Font Size", "Font Weight", "Justification"]

            else:  
                properties_to_display.append("Path")

            for prop_name in properties_to_display:
                handler = self.controller.PROPERTY_HANDLERS.get(prop_name)
                if prop_name == "ID":
                    value = selected_shape.sid
                elif prop_name == "Shape Type":
                    value = selected_shape.shape_type.capitalize()
                elif handler and "get" in handler:
                    value = handler["get"](selected_shape)
                else:
                    value = selected_shape.prop_get(self.controller, prop_name)

                if prop_name in ["X", "Y", "Width", "Height", "Line Width"] and value is not None:
                    value = int(value)

                iid = self.props_tree.insert("", "end", values=(prop_name, value))
                self._tv_item_to_shape_id[iid] = selected_shape.sid

                if sid_to_refocus == selected_shape.sid and prop_to_refocus == prop_name:
                    self.props_tree.focus(iid)
                    self.props_tree.selection_set(iid)
                    self.props_tree.see(iid)

        self.props_tree.focus_set()  # Set focus back to the treeview

        # --- ADD THIS BLOCK ---
        if selected_shape:
            self.redraw_shape_and_selection(selected_shape, True)
        # ---------------------

            # ---------------------

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
        if self._is_editing_property:
            return
        
        tv = self.props_tree
        bbox = tv.bbox(row_id, column_name)
        if not bbox:
            return
        
        x, y, width, height = bbox
        current_value = tv.set(row_id, column_name)
        prop_name = tv.set(row_id, "Property")
        prop_meta = self.controller.PROPERTY_HANDLERS.get(prop_name, {})

        self._cancel_edit()  # Destroy existing editor
        
        # Get the options for this property (if callable, execute with shape context)
        options = prop_meta.get("options")
        if callable(options):
            shape = self.controller.model.get_shape(self._tv_item_to_shape_id.get(row_id))
            try:
                options = options(shape)  # Assuming options is a callable that needs shape as input
            except Exception as e:
                print(f"Error fetching dynamic options for '{prop_name}': {e}")
                options = []  # Fallback to empty list if error occurs
        elif options is None:
            options = []  # Ensure options is always a list
        
        # If there are options, create a Combobox, otherwise an Entry field
        if options:
            self._editor = ttk.Combobox(tv, values=options, state="readonly")
            try:
                current_index = options.index(current_value)
                self._editor.current(current_index)
            except ValueError:
                self._editor.set("")  # Set empty if current value not found
            self._editor.bind("<<ComboboxSelected>>", lambda e: self._commit_edit(row_id))
            self._editor.bind("<Escape>", lambda e: self._cancel_edit())
        else:
            self._editor = tk.Entry(tv)
            self._editor.insert(0, current_value)
            self._editor.bind("<Return>", lambda e: self._commit_edit(row_id))
            self._editor.bind("<Escape>", lambda e: self._cancel_edit())
            self._editor.bind("<FocusOut>", lambda e: self._cancel_edit())  # May need refinement

        # Position the editor and set focus
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

    def _commit_edit(self, row_id):
        """Called by editor widget event when editing is committed."""
        if not self._is_editing_property or not self._editor:
            return

        new_value_str = self._editor.get().strip()
        self._editor.destroy()
        self._editor = None
        self._is_editing_property = False

        tv = self.props_tree
        prop_name = tv.set(row_id, "Property")
        sid = self._tv_item_to_shape_id.get(row_id)

        if sid is None:
            self._update_properties_panel(None)
            return

        # Notify the controller about the committed property change
        self.controller.handle_property_edit_commit(sid, prop_name, new_value_str)

        # Refresh the properties panel to reflect updated values (type-coerced, clamped, etc.)
        updated_shape = self.controller.model.get_shape(sid)
        self._update_properties_panel(updated_shape, refocus_info=(sid, prop_name))

        # Redraw canvas to reflect updated shape appearance
        self.refresh_all(self.controller.model)


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
        Merges CSV data by matching each row field to shapes named '@<field>'.
        Draws all shapes (text and images) into a single RGBA image at the model's native pixel resolution.
        Adjusts for shape.line_width to inset content and avoid border clipping.
        """
        print("\nDrawingView.flatten_card: Starting flattening process.")
        # Compute overall model bounds
        min_x, min_y, max_x, max_y = model.get_model_bounds()
        width = max(1, int(round(max_x - min_x)))
        height = max(1, int(round(max_y - min_y)))
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))

        # Merge CSV data into shapes: for each key, find shape named '@key'
        for key, val in row_data.items():
            shape_name = str(key)
            for layer in model.layers:
                for shape in layer.shapes.values():
                    if shape.name == shape_name:
                        if shape.container_type == 'Text':
                            shape.text = str(val)
                            shape._draw_text_content()
                        elif shape.container_type == 'Image':
                            shape.path = str(val).strip()
                            shape._load_image_content()

        # Draw each shape into the canvas
        for layer in model.layers:
            print(f"DrawingView.flatten_card: Layer '{layer.name}'")
            for sid in sorted(layer.shapes.keys()):
                shape = layer.shapes[sid]
                # raw bbox
                x0, y0, x1, y1 = shape.get_bbox
                # compute inset half border
                inset = (shape.line_width or 0)
                # adjust bbox for content
                adj_x0 = x0 + inset
                adj_y0 = y0 + inset
                adj_x1 = x1 - inset
                adj_y1 = y1 - inset
                # to pixel coords
                px = int(round(adj_x0 - min_x))
                py = int(round(adj_y0 - min_y))
                w  = max(0, int(round(adj_x1 - adj_x0)))
                h  = max(0, int(round(adj_y1 - adj_y0)))
                if w <= 0 or h <= 0:
                    continue

                # paste shape content (text/image) resized to inset area
                content = getattr(shape, 'content', None)
                if isinstance(content, Image.Image):
                    img = content.convert('RGBA')
                    if img.size != (w, h):
                        img = img.resize((w, h), Image.Resampling.LANCZOS)
                    canvas.paste(img, (px, py), img)

                # draw outline on original bbox
                raw_px = int(round(x0 - min_x))
                raw_py = int(round(y0 - min_y))
                raw_w  = int(round(x1 - x0))
                raw_h  = int(round(y1 - y0))
                draw = ImageDraw.Draw(canvas)
                if shape.line_width and shape.color:
                    coords = [raw_px, raw_py, raw_px + raw_w, raw_py + raw_h]
                    try:
                        if shape.shape_type == 'rectangle':
                            draw.rectangle(coords, outline=shape.color, width=shape.line_width)
                        elif shape.shape_type == 'oval':
                            draw.ellipse(coords, outline=shape.color, width=shape.line_width)
                        elif shape.shape_type == 'triangle':
                            cx = (coords[0] + coords[2]) // 2
                            pts = [(coords[0], coords[3]), (cx, coords[1]), (coords[2], coords[3])]
                            draw.polygon(pts, outline=shape.color, width=shape.line_width)
                        elif shape.shape_type == 'hexagon':
                            cx = (coords[0] + coords[2]) / 2
                            cy = (coords[1] + coords[3]) / 2
                            hw = (coords[2] - coords[0]) / 2
                            hh = (coords[3] - coords[1]) / 2
                            pts = [
                                (int(cx + hw * math.cos(math.radians(60 * i - 30))),
                                 int(cy + hh * math.sin(math.radians(60 * i - 30))))
                                for i in range(6)
                            ]
                            draw.polygon(pts, outline=shape.color, width=shape.line_width)
                    except Exception as e:
                        print(f"Outline error for shape {sid}: {e}")

        print("DrawingView.flatten_card: Finished flattening.")
        return canvas

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

