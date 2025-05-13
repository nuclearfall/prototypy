
def move_coords_x(shape, new_x):
    coords = shape.get_bbox.copy()
    min_x, max_x = min(coords[0], coords[2]), max(coords[0], coords[2])
    dx = new_x - min_x
    new_coords = [coords[0] + dx, coords[1], coords[2] + dx, coords[3]]
    return _update_coords_if_valid(new_coords)

def move_coords_y(shape, new_y):
    coords = shape.get_bbox.copy()
    min_y, max_y = min(coords[1], coords[3]), max(coords[1], coords[3])
    dy = new_y - min_y
    new_coords = [coords[0], coords[1] + dy, coords[2], coords[3] + dy]
    return _update_coords_if_valid(new_coords)

def resize_width(shape, new_width):
    coords = shape.get_bbox.copy()
    min_x, max_x = min(coords[0], coords[2]), max(coords[0], coords[2])
    # Anchor the left side (min_x) and adjust the right side
    new_coords = [min_x, coords[1], min_x + max(0, new_width), coords[3]]
    return _update_coords_if_valid(new_coords)

def resize_height(shape, new_height):
    coords = shape.get_bbox.copy()
    min_y, max_y = min(coords[1], coords[3]), max(coords[1], coords[3])
    # Anchor the top side (min_y) and adjust the bottom side
    new_coords = [coords[0], min_y, coords[2], min_y + max(0, new_height)]
    return _update_coords_if_valid(new_coords)

def _update_coords_if_valid(shape, new_coords, min_size=5):
    min_x, max_x = min(new_coords[0], new_coords[2]), max(new_coords[0], new_coords[2])
    min_y, max_y = min(new_coords[1], new_coords[3]), max(new_coords[1], new_coords[3])
    if (max_x - min_x) >= min_size and (max_y - min_y) >= min_size:
        if shape.coords != new_coords:
            shape.set_coords(*new_coords)
            return True
    return False


def calculate_snap(model, x, y):
    """Calculates snapped coordinates based on Model's grid size (Controller helper)."""
    return (round(x/model.grid_size)*model.grid_size,
            round(y/model.grid_size)*model.grid_size)


