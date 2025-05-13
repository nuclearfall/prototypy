import tkinter as tk
from tkinter import ttk, simpledialog

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

    def create_component_from_selected_layers(self):
        selected_layers = self.layer_panel.get_selected_layers()
        if not selected_layers:
            return

        new_component = ComponentModel(layers=selected_layers)
        self.model.components.append(new_component)

        # Optionally remove these layers from main drawing view
        for layer in selected_layers:
            self.model.layers.remove(layer)

# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Layer Tree Manager")
    root.geometry("300x400")
    app = LayerTree(root)
    app.pack(fill="both", expand=True)
    root.mainloop()
