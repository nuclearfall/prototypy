# Prototy.py

**Prototy.py** is a tool for rapid, tabletop, physical component layout and printing or for printing of your own print and play components. It currently accepts csv import and data merge and outputs cards. Other components layouts will be available shortly. 

It takes any column from the csv with names starting with "@"—a convention from inDesign data merge—and places the data into the Shape containers. Mark a shape as an image and it will import the images from the path provided in the csv file. Text shapes merge whatever text is in the container (word wrap is implemented). Just name the Shape containers exactly as the columns.

Create a template using the GUI application or create a json file matching the format of the provided templalte sample.json, add a csv with import data, add a name for the exported pdf file and select whether you want an 8 card layout or 9 card layout. When creating a template card for the time being, ensure you begin at the top left corner or you will have issues.

The command for the 9 card layout is:
```
python prototy.py sample.json -i sample.csv -e sample.pdf -c 9
```

Simply change the -c flag to 8 for an 8 card layout. Using the application from the command line without the -c flag will enlarge or shrink the component to a single page for now.

Forthcoming:
- Component layout of noncard elements in a designated quantity per page
- Components layout of elements which are larger than a single page (eg, game boards)
- Component contstruction using sub components. This will provide for things like scoring tracks to be placed around the border of a gameboard and resized to fit the exact dimensions. Or adding scoring tracks, card placement areas, etc.