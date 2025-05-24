import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkFont
import os
import platform
import re
from typing import Optional

# Import PIL/Pillow for image rendering
from PIL import Image, ImageDraw, ImageFont, ImageTk

# Import ReportLab modules
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont 
from reportlab.lib.pagesizes import letter 
from reportlab.lib.units import inch 

# --- FontManager Class ---
class FontManager:
    """
    Manages scanning and indexing of system fonts to find file paths for both PIL and ReportLab.
    Aims to provide "best guess" font file paths based on system font discovery and naming conventions.
    """
    _STYLE_WEIGHT_SLANT_SUFFIXES = [
        re.compile(r'(?:(?:bold|heavy|black)(?:[\s_\-])?(?:italic|oblique))', re.IGNORECASE),
        re.compile(r'(?:(?:bold|heavy|black))', re.IGNORECASE),
        re.compile(r'(?:(?:italic|oblique))', re.IGNORECASE),
        re.compile(r'(?:regular|normal|roman)', re.IGNORECASE),
        re.compile(r'(?:light|thin|medium|semibold|demi|extrabold)', re.IGNORECASE),
        re.compile(r'(?:condensed|extended|narrow|wide)', re.IGNORECASE),
        re.compile(r'(?:serif|sans|display|oldstyle|newstyle|text|headline)', re.IGNORECASE),
        re.compile(r'\b\d{1,3}(?:\s*pt)?\b', re.IGNORECASE)
    ]

    def __init__(self):
        # Cache Tkinter's known font families for better indexing
        self._tk_families_set = set(tkFont.families())
        self._system_fonts_by_family = self._index_system_fonts()
        
        self._default_font_path = self._set_default_font_path()
        
        if not self._default_font_path:
            print("Warning: Could not find a reliable default system font path. Font display/export might be impacted.")


    def _set_default_font_path(self):
        """Attempts to find a reliable default font path for fallbacks."""
        common_defaults = []
        if platform.system() == 'Windows':
            win_fonts = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
            common_defaults.extend([
                os.path.join(win_fonts, 'arial.ttf'),
                os.path.join(win_fonts, 'segoeui.ttf'), # A modern Windows font
                os.path.join(win_fonts, 'times.ttf')
            ])
        elif platform.system() == 'Linux':
            common_defaults.extend([
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
                '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf' # If msttcorefonts are installed
            ])
        elif platform.system() == 'Darwin':
            mac_fonts = [
                '/Library/Fonts', 
                '/System/Library/Fonts', 
                '/System/Library/Fonts/Supplemental', # Included
                os.path.expanduser('~/Library/Fonts')
            ]
            # Prioritize single .ttf files over .ttc collections for simplicity unless explicitly needed
            for base_dir in mac_fonts:
                common_defaults.extend([
                    os.path.join(base_dir, 'Arial.ttf'),
                    os.path.join(base_dir, 'Helvetica.ttf'), # Less common as single TTF now, but may exist
                    os.path.join(base_dir, 'Times New Roman.ttf'),
                    os.path.join(base_dir, 'Lucida Grande.ttf')
                ])
            # Last resort for Mac, if only .ttc is widely available
            if os.path.exists('/System/Library/Fonts/Helvetica.ttc'):
                common_defaults.append('/System/Library/Fonts/Helvetica.ttc')


        for path in common_defaults:
            if path and os.path.exists(path):
                return path
        
        # If no explicit common default found, try to pick the first 'normal' variant from our indexed fonts
        if self._system_fonts_by_family:
            for family_variants in self._system_fonts_by_family.values():
                path = family_variants.get('normal', {}).get('roman') \
                       or family_variants.get('normal', {}).get('regular') \
                       or next(iter(family_variants.get('normal', {}).values()), None) # Any 'normal' variant
                if path:
                    return path
        
        return None # No default font path found

    def get_families(self):
        print(self._tk_families_set)
        return sorted(list(self._tk_families_set))

    # Existing method for Tkinter fonts (renamed for clarity as per previous suggestions)
    def get_tk_font(self, family: str, size: int = 12, weight: str = 'normal', slant: str = 'roman') -> tkFont.Font:
        """
        Get a Tkinter font object (tkFont.Font) for the specified font family, size, weight, and slant.
        Tkinter handles the font resolution internally.

        Args:
            family (str): The desired font family name (e.g., "Arial").
            size (int): The desired font size in points (Tkinter uses points, PIL uses pixels).
            weight (str): The desired font weight ('normal' or 'bold').
            slant (str): The desired font slant ('roman' or 'italic').

        Returns:
            tkinter.font.Font: The Tkinter font object.
        """
        # Tkinter font creation is direct using its attributes.
        # It handles its own internal fallbacks if a specific combination isn't available.
        return tkFont.Font(family=family, size=size, weight=weight, slant=slant)

    # NEW METHOD for PIL fonts
    def get_pil_font(self, family: str, size: int = 12, weight: str = 'normal', slant: str = 'roman') -> Optional[ImageFont.ImageFont]:
        """
        Returns a PIL font (ImageFont.ImageFont) for the specified font family, size, weight, and slant.
        This attempts to find the actual font file on the system.

        Args:
            family (str): The desired font family name (e.g., "Arial").
            size (int): The desired font size in pixels for PIL.
            weight (str): The desired font weight ('normal' or 'bold').
            slant (str): The desired font slant ('roman' or 'italic').

        Returns:
            PIL.ImageFont.ImageFont: The PIL font object, or None if not found.
        """
        font_path = self.get_font_filepath(family, weight, slant)
        if font_path:
            try:
                # PIL font size is typically in pixels for ImageDraw.text
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                print(f"FontManager: Error loading PIL font from {font_path} (size: {size}): {e}")
                return None
        else:
            print(f"FontManager: No font file found for PIL family '{family}' weight '{weight}' slant '{slant}'.")
            return None # Return None if no font file is found

    def get_weights_for_family(self, family):
        """
        Returns a sorted list of available weights (e.g., 'normal', 'bold', 'light')
        for the given font family, as identified by Tkinter.

        Args:
            family (str): The desired font family name (e.g., "Arial").

        Returns:
            list: A list of available weight strings. Returns an empty list if
                  the family is not found in the indexed system fonts.
        """
        family_variants = self._system_fonts_by_family.get(family)

        if not family_variants:
            # If the exact family name wasn't a top-level key in our index,
            # try canonicalizing it to match potential system font names.
            canonical_family = self._get_canonical_base_name(family)
            family_variants = self._system_fonts_by_family.get(canonical_family)
        
        if family_variants:
            # Extract keys from the weight dictionary (these are the available weights)
            weights = list(family_variants.keys())
            
            # Define a custom order for common weights to ensure consistent display
            weight_order = {
                'thin': 1, 'hairline': 1, 'extra-light': 2, 'ultralight': 2, 'light': 3, 
                'normal': 4, 'regular': 4, 'book': 4, 'medium': 5, 'demi': 6, 'semibold': 6, 
                'bold': 7, 'extra-bold': 8, 'ultrabold': 8, 'heavy': 9, 'black': 9, 'fat': 10
            }
            
            # Sort weights first by their semantic order, then alphabetically for ties or unknown weights
            sorted_weights = sorted(weights, key=lambda w: (weight_order.get(w.lower(), 99), w.lower()))
            return sorted_weights
        else:
            return [] # Family not found in our indexed fonts

    def _scan_common_font_dirs(self):
        font_dirs = []
        if platform.system() == 'Windows':
            font_dirs = [os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')]
        elif platform.system() == 'Linux':
            font_dirs = [
                '/usr/share/fonts/truetype',
                '/usr/local/share/fonts',
                os.path.expanduser('~/.fonts')
            ]
        elif platform.system() == 'Darwin':
            font_dirs = [
                '/Library/Fonts',
                '/System/Library/Fonts',
                '/System/Library/Fonts/Supplemental', # Added this directory for macOS
                os.path.expanduser('~/Library/Fonts')
            ]

        found_fonts = []
        for d in font_dirs:
            if os.path.exists(d):
                for root, _, files in os.walk(d):
                    for f in files:
                        if f.lower().endswith(('.ttf', '.otf', '.ttc')):
                            path = os.path.join(root, f)
                            display_name = os.path.splitext(f)[0].replace('_', ' ')
                            found_fonts.append((display_name, path))
        
        unique_fonts = {} 
        for display_name, path in found_fonts:
            # Simple scoring: Longer display names (more specific) or certain keywords preferred
            score = len(display_name) + (10 if any(s in display_name.lower() for s in ['bold', 'italic', 'regular', 'normal']) else 0)
            if path not in unique_fonts or score > unique_fonts[path][1]:
                unique_fonts[path] = (display_name, score)
        
        return sorted([(name_score[0], path) for path, name_score in unique_fonts.items()], key=lambda x: x[0].lower())

    def _get_canonical_base_name(self, name_to_clean):
        """Attempts to strip common style/weight/slant suffixes to get the base family name."""
        cleaned_name = name_to_clean
        
        patterns = [
            re.compile(r'[\s_\-](?:bold|heavy|black)[\s_\-](?:italic|oblique)', re.IGNORECASE),
            re.compile(r'[\s_\-](?:italic|oblique)[\s_\-](?:bold|heavy|black)', re.IGNORECASE),
            re.compile(r'[\s_\-](?:bold|heavy|black)', re.IGNORECASE),
            re.compile(r'[\s_\-](?:italic|oblique)', re.IGNORECASE),
            re.compile(r'[\s_\-](?:regular|normal|roman|thin|light|medium|semibold|demi|extrabold|condensed|extended|narrow|wide)', re.IGNORECASE),
            re.compile(r'[\s_\-](?:serif|sans|display|oldstyle|newstyle|text|headline)', re.IGNORECASE),
            re.compile(r'\b\d{1,3}(?:\s*pt)?\b', re.IGNORECASE)
        ]

        for pattern in patterns:
            cleaned_name = pattern.sub('', cleaned_name).strip()
        
        cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()
        cleaned_name = ' '.join(word.capitalize() for word in cleaned_name.split())
        return cleaned_name if cleaned_name else name_to_clean

    def _index_system_fonts(self):
        indexed_fonts = {} # {family: {weight: {slant: filepath}}}
        raw_found_fonts = self._scan_common_font_dirs()

        style_keywords = {
            'bold': [r'bold', r'heavy', r'black', r'demi', r'semibold', r'extrabold'],
            'italic': [r'italic', r'oblique'],
            'normal': [r'regular', r'normal', r'roman']
        }
        
        for display_name, filepath in raw_found_fonts:
            current_weight = 'normal'
            current_slant = 'roman'
            
            is_bold = any(re.search(kw, display_name, re.IGNORECASE) for kw in style_keywords['bold'])
            is_italic = any(re.search(kw, display_name, re.IGNORECASE) for kw in style_keywords['italic'])

            if is_bold: current_weight = 'bold'
            if is_italic: current_slant = 'italic'

            if not is_bold and not is_italic:
                if any(re.search(kw, display_name, re.IGNORECASE) for kw in style_keywords['normal']):
                    current_weight = 'normal'
                    current_slant = 'roman'
            
            # Decide the primary family key:
            # 1. Prefer the full display_name if Tkinter recognizes it as a family.
            # 2. Otherwise, use the canonical base name if Tkinter recognizes that.
            # 3. Fallback to display_name if neither is a recognized Tkinter family.
            family_key = display_name
            if display_name not in self._tk_families_set:
                potential_canonical_name = self._get_canonical_base_name(display_name)
                if potential_canonical_name in self._tk_families_set:
                    family_key = potential_canonical_name
            
            indexed_fonts.setdefault(family_key, {}).setdefault(current_weight, {})[current_slant] = filepath
            
        return indexed_fonts

    def get_font_filepath(self, tk_family, weight="normal", slant="roman"):
        """
        Attempts to find the actual font file path (TTF/OTF/TTC) that best matches
        the given Tkinter font family, weight, and slant.
        Prioritizes exact Tkinter family match first.
        """
        # 1. Try exact Tkinter family name first
        family_variants = self._system_fonts_by_family.get(tk_family)

        if not family_variants:
            # 2. If exact Tkinter family name wasn't a top-level key, try canonicalizing
            canonical_tk_family = self._get_canonical_base_name(tk_family)
            family_variants = self._system_fonts_by_family.get(canonical_tk_family)

        if not family_variants:
            print(f"FontManager: No variants found for '{tk_family}' (canonical '{canonical_tk_family}'). Returning default.")
            return self._default_font_path 

        # Define a prioritized search order for variants within the found family
        search_preferences = []

        # 1. Exact match for requested weight/slant
        search_preferences.append((weight, slant))

        # 2. Common fallbacks based on requested weight/slant
        if weight == 'bold':
            if slant == 'roman':
                search_preferences.append(('bold', 'italic')) 
            else: # slant == 'italic'
                search_preferences.append(('bold', 'roman'))
        elif weight == 'normal':
            if slant == 'roman':
                search_preferences.append(('normal', 'regular')) # 'regular' is common alias for 'roman'
            else: # slant == 'italic'
                search_preferences.append(('normal', 'roman'))

        # 3. Broader fallbacks for same weight, different slant
        search_preferences.append((weight, 'roman' if slant == 'italic' else 'italic')) # Toggle slant

        # 4. Fallbacks for different weight, same slant
        if weight == 'bold': search_preferences.append(('normal', slant))
        else: search_preferences.append(('bold', slant))

        # 5. General fallbacks (least specific but ensures a path if available)
        search_preferences.extend([
            ('normal', 'roman'), ('normal', 'regular'), 
            ('normal', 'italic'),
            ('bold', 'roman'),
            ('bold', 'italic')
        ])
        
        # Remove duplicates while preserving order
        unique_search_preferences = []
        seen = set()
        for item in search_preferences:
            if item not in seen:
                unique_search_preferences.append(item)
                seen.add(item)

        for w_check, s_check in unique_search_preferences:
            if w_check in family_variants and s_check in family_variants[w_check]:
                return family_variants[w_check][s_check]

        print(f"FontManager: Could not find a precise variant for '{tk_family}' (weight: {weight}, slant: {slant}). Returning default.")
        return self._default_font_path



# import platform
# import os 
# import re 
# import glob     
# from typing import Dict, List, Optional, Tuple # For type hinting

# from PIL import ImageFont 


# class FontManager:
#     def __init__(self):
#         self.font_cache = {}  # Structure: {family: {weight: path}}
#         self.font_name_list = []
#         self.font_weights = {
#             'Bold Italic': ['bolditalic', 'boldit', 'bi', 'bold-italic'],
#             'Bold': ['bold', 'bd', 'b'],
#             'Italic': ['italic', 'it', 'i'],
#             'Regular': ['regular', 'rg', ''],
#             'Medium': ['medium', 'md'],
#             'Light': ['light', 'lt']
#         }
#         self.weight_patterns = [
#             (r'(.*?)-(BoldItalic|BoldIt|BI)\.ttf$', 'Bold Italic'),
#             (r'(.*?)-(Italic|It|I)\.ttf$', 'Italic'),
#             (r'(.*?)-(Bold|Bd|B)\.ttf$', 'Bold'),
#             (r'(.*?)-(Medium|Md)\.ttf$', 'Medium'),
#             (r'(.*?)-(Light|Lt)\.ttf$', 'Light'),
#             (r'(.*?)-(Regular|Rg|R)?\.ttf$', 'Regular'),
#             (r'(.*?)\.ttf$', 'Regular')  # Default case
#         ]
#         self._cache_fonts()

#     def _cache_fonts(self):
#         """Build font cache with family/weight structure"""
#         search_paths = self._get_system_font_paths()
        
#         for path in search_paths:
#             if not os.path.exists(path):
#                 continue
#             for root, _, files in os.walk(path):
#                 for file in files:
#                     if file.lower().endswith('.ttf'):
#                         full_path = os.path.join(root, file)
#                         if self._is_valid_font(full_path):
#                             family, weight = self._parse_font_name(file)
                            
#                             if family not in self.font_cache:
#                                 self.font_cache[family] = {}
                            
#                             # Only add if we don't have this weight already
#                             if weight not in self.font_cache[family]:
#                                 self.font_cache[family][weight] = full_path

#         # Build simplified name list for UI
#         self.font_name_list = sorted(self.font_cache.keys())

#     def _parse_font_name(self, filename):
#         """Extract family name and weight from filename"""
#         filename = os.path.splitext(filename)[0]  # Remove extension
        
#         # Try to match known patterns
#         for pattern, weight in self.weight_patterns:
#             match = re.match(pattern, filename, re.IGNORECASE)
#             if match:
#                 family = match.group(1).strip('- ')
#                 # Clean up family name
#                 family = re.sub(r'[\-_]', ' ', family).title()
#                 return family, weight
        
#         # Fallback for unparsable names
#         return filename, 'Regular'

#     def _get_system_font_paths(self):
#         """Get OS-specific font paths"""
#         system = platform.system()
#         paths = []
        
#         if system == "Darwin":  # macOS
#             paths = [
#                 '/System/Library/Fonts/Supplemental',
#                 '/Library/Fonts',
#                 '/System/Library/Fonts'
#             ]
#         elif system == "Windows":
#             paths = [os.path.join(os.environ['WINDIR'], 'Fonts')]
#         else:  # Linux
#             paths = [
#                 '/usr/share/fonts',
#                 '/usr/local/share/fonts',
#                 os.path.expanduser('~/.fonts')
#             ]
#         return paths

#     def _is_valid_font(self, path):
#         """Validate font file can be loaded"""
#         try:
#             ImageFont.truetype(path, 12)
#             return True
#         except (OSError, IOError):
#             return False

#     def get_font(self, family, size=12, weight='Regular'):
#         """Get font with proper weight handling"""
#         weights = self.font_cache.get(family, {})
        
#         # Find best matching weight
#         weight = weight.capitalize()
#         if weight not in weights:
#             if "Regular" in weights:
#                 weight = "Regular"
#             elif weights:
#                 weight = next(iter(weights.keys()))
        
#         return ImageFont.truetype(weights[weight], size)

#     def get_weights_for_family(self, family):
#         """Return available weights for a font family"""
#         return sorted(self.font_cache.get(family, {}).keys())

#     def get_families(self):
#         """Return list of available font families"""
#         return self.font_name_list