from tkinter import messagebox # For displaying error messages

# Need PIL.Image for the dependency check
from PIL import Image # Or just `import PIL.Image`

import pandas as pd     # For the pandas dependency check

# Assuming AppService is in app_service.py at the root level
from app_service import AppService

if __name__ == '__main__':
    import argparse
    import tkinter as tk
    from tkinter import messagebox
    from PIL import Image

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

    # Perform dependency checks and handle errors (messagebox)
    missing = []
    try:
        Image.new('RGB', (1, 1))
        from PIL import ImageTk, ImageDraw, ImageFont
    except ImportError:
        missing.append('Pillow')
    try:
        import pandas as pd
        pd.DataFrame()
    except ImportError:
        missing.append('pandas')

    if missing:
        # Show messagebox and exit before creating the main app window fully
        messagebox.showerror('Missing Dependencies', f"Install the following packages: {', '.join(missing)}")
        root.destroy()
        exit()

    # Parse custom size (handle potential messagebox)
    # custom_size_tuple = None
    # if args.custom_size:
    #     try:
    #         w_str, h_str = args.custom_size.split(',')
    #         custom_size_tuple = (float(w_str), float(h_str))
    #     except ValueError:
    #         messagebox.showerror("Invalid Argument", "Invalid custom size format. Use W,H (e.g., 5,7).")
    #         root.destroy()
    #         exit()

    # Initialize the application components AFTER initial checks
    app_service = AppService.get_instance(root)
    controller = app_service.controller

    # Handle command-line arguments that might open dialogs
    if args.file:
        controller.open_drawing(args.file) # This might show a file dialog or error messagebox
    elif args.csv_path: # Use elif to prioritize opening a file over just importing CSV
        controller.import_csv(args.csv_path) # This might show a file dialog or error messagebox

    # If exporting, perform export and exit without showing the main window
    if args.export_pdf:
        use_card = args.cards is not None
        cards_per_page = args.cards if use_card else None
        # Auto-rotate if flag set or if 8-up on A4
        rotate_card = use_card and cards_per_page == 8
        if args.csv_path:
            controller.import_csv(str(args.csv_path))

        controller.export_to_pdf(
            export_path=args.export_pdf,
            page=args.page_size.upper(),
            use_card=use_card,
            #custom_size=custom_size_tuple,
            cards_per_page=args.cards,
            rotate_card=(args.cards == 8 and args.page_size.upper() == 'A4')
        )
        root.destroy()
    else:
        # If not exporting, show the main window and start the main loop
        # Call your window raising logic here, after any potential dialogs have been handled.
        # Assuming _raise_window exists in your Controller or AppService
        controller._raise_window() # Call the method to lift/focus the window

        controller.view.refresh_all(controller.model) # Ensure initial refresh
        root.mainloop()