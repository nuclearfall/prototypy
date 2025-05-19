# prototy.py

# Keep necessary imports
from tkinter import messagebox
from typing import TYPE_CHECKING # Keep TYPE_CHECKING

# Remove AppService import
# REMOVE THIS LINE: from app_service import AppService

import pandas as pd # Keep pandas import

# Import the classes that will be instantiated and linked
from utils.font_manager import FontManager # Import FontManager directly
from model import DrawingModel # Import DrawingModel directly
from controller import DrawingApp # Import DrawingApp directly


if __name__ == '__main__':
    import argparse
    import tkinter as tk
    from tkinter import messagebox
    from PIL import Image # Keep PIL Image import for dependency check

    # Argument parsing remains the same
    parser = argparse.ArgumentParser(description='Enhanced Vector Editor')
    parser.add_argument('file', nargs='?', help='JSON file to open')
    parser.add_argument('-i', '--import', dest='csv_path', help='CSV to import')
    parser.add_argument('-e', '--export_pdf', dest='export_pdf', metavar='OUT.pdf', help='Export to PDF and exit')
    parser.add_argument('-c', '--cards', type=int, choices=[8, 9], help="Number of cards per page")
    #parser.add_argument('--use-card', action='store_true', help='Render cards using card layout')
    parser.add_argument('-p', '--page_size', choices=['letter', 'a4'], default='letter', dest='page_size', help='PDF page size')
    parser.add_argument('-s', '--size', dest='custom_size', metavar='W,H', help='Custom component size in inches (W,H)')
    args = parser.parse_args()

    # Initialize Tk as early as possible
    root = tk.Tk()
    root.withdraw() # Hide the main window initially

    # Perform dependency checks (remains the same)
    missing = []
    try:
        Image.new('RGB', (1, 1))
        from PIL import ImageTk, ImageDraw, ImageFont # Ensure these specific imports are checked/available
    except ImportError:
        missing.append('Pillow (PillowTk, ImageDraw, ImageFont)') # More specific error message
    try:
        import pandas as pd
        pd.DataFrame()
    except ImportError:
        missing.append('pandas')

    if missing:
        messagebox.showerror('Missing Dependencies', f"Install the following packages: {', '.join(missing)}")
        root.destroy()
        exit()

    # --- REPLACE AppService initialization with direct instantiation ---

    # 1. Create the FontManager instance first, as others depend on it
    font_manager = FontManager()

    # 2. Create the DrawingModel instance, passing the font_manager
    # The Model needs the FontManager to create Layers and Shapes with font capabilities
    model = DrawingModel(font_manager)

    # 3. Create the DrawingApp (Controller) instance
    # Pass the root window, the model, and the font_manager to the controller
    # NOTE: You MUST update the DrawingApp.__init__ signature in controller.py
    controller = DrawingApp(root, model, font_manager)

    # --- END REPLACE ---


    # Handle command-line arguments that might open dialogs (remains the same, calls controller methods)
    # Ensure controller methods are called AFTER the controller is fully initialized
    if args.file:
        controller.open_drawing(args.file) # This might show a file dialog or error messagebox
    elif args.csv_path: # Use elif to prioritize opening a file over just importing CSV
        # Import CSV first if specified via argument
        controller.import_csv(args.csv_path) # This might show a file dialog or error messagebox
        # Note: If export_pdf is also specified, CSV import happens again below. This is okay.

    # If exporting, perform export and exit without showing the main window (remains the same)
    if args.export_pdf:
        use_card = args.cards is not None
        cards_per_page = args.cards if use_card else None
        rotate_card = use_card and cards_per_page == 8 # Auto-rotate if 8-up card layout

        # If CSV path was provided via --import, ensure it's loaded before export
        if args.csv_path:
            # Call import_csv again just in case the previous elif didn't run (e.g., args.file was also provided)
            # The import_csv method handles if data is already loaded.
            controller.import_csv(str(args.csv_path))
            # Check if import was successful before proceeding with export
            if controller.csv_data_df is None:
                 print("Export cancelled due to failed CSV import.")
                 root.destroy()
                 exit()
        # If no CSV was provided via --import, the controller's export method will handle the case
        # where csv_data_df is None (e.g., exporting a blank or template drawing).


        controller.export_to_pdf(
            export_path=args.export_pdf,
            page=args.page_size.upper(),
            use_card=use_card,
            # custom_size=custom_size_tuple, # Pass the custom size tuple if needed
            cards_per_page=args.cards,
            rotate_card=(args.cards == 8 and args.page_size.upper() == 'A4') # Auto-rotate 8-up on A4
        )
        root.destroy() # Destroy the Tk root window after export is complete
    else:
        # If not exporting, show the main window and start the main loop
        # Ensure the main window is deiconified (shown)
        controller._raise_window() # Call the method to lift/focus the window

        # Perform an initial refresh of the view
        # This is necessary to display the initial state of the model (blank or loaded from file args)
        # The model's reset() or from_dict() notifies observers, which triggers refresh_all,
        # but explicitly calling it here after setting up observers ensures the first draw happens.
        print("prototy.py: Calling initial controller.view.refresh_all.")
        # Pass the model instance to refresh_all
        controller.view.refresh_all(controller.model)

        # Start the Tkinter main event loop
        root.mainloop()