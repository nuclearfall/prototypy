import platform
import os 
import re 
import glob     
from typing import Dict, List, Optional, Tuple # For type hinting

from PIL import ImageFont 


class FontManager:
    def __init__(self):
        self.font_cache = {}  # Structure: {family: {weight: path}}
        self.font_name_list = []
        self.font_weights = {
            'Bold Italic': ['bolditalic', 'boldit', 'bi', 'bold-italic'],
            'Bold': ['bold', 'bd', 'b'],
            'Italic': ['italic', 'it', 'i'],
            'Regular': ['regular', 'rg', ''],
            'Medium': ['medium', 'md'],
            'Light': ['light', 'lt']
        }
        self.weight_patterns = [
            (r'(.*?)-(BoldItalic|BoldIt|BI)\.ttf$', 'Bold Italic'),
            (r'(.*?)-(Italic|It|I)\.ttf$', 'Italic'),
            (r'(.*?)-(Bold|Bd|B)\.ttf$', 'Bold'),
            (r'(.*?)-(Medium|Md)\.ttf$', 'Medium'),
            (r'(.*?)-(Light|Lt)\.ttf$', 'Light'),
            (r'(.*?)-(Regular|Rg|R)?\.ttf$', 'Regular'),
            (r'(.*?)\.ttf$', 'Regular')  # Default case
        ]
        self._cache_fonts()

    def _cache_fonts(self):
        """Build font cache with family/weight structure"""
        search_paths = self._get_system_font_paths()
        
        for path in search_paths:
            if not os.path.exists(path):
                continue
            for root, _, files in os.walk(path):
                for file in files:
                    if file.lower().endswith('.ttf'):
                        full_path = os.path.join(root, file)
                        if self._is_valid_font(full_path):
                            family, weight = self._parse_font_name(file)
                            
                            if family not in self.font_cache:
                                self.font_cache[family] = {}
                            
                            # Only add if we don't have this weight already
                            if weight not in self.font_cache[family]:
                                self.font_cache[family][weight] = full_path

        # Build simplified name list for UI
        self.font_name_list = sorted(self.font_cache.keys())

    def _parse_font_name(self, filename):
        """Extract family name and weight from filename"""
        filename = os.path.splitext(filename)[0]  # Remove extension
        
        # Try to match known patterns
        for pattern, weight in self.weight_patterns:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                family = match.group(1).strip('- ')
                # Clean up family name
                family = re.sub(r'[\-_]', ' ', family).title()
                return family, weight
        
        # Fallback for unparsable names
        return filename, 'Regular'

    def _get_system_font_paths(self):
        """Get OS-specific font paths"""
        system = platform.system()
        paths = []
        
        if system == "Darwin":  # macOS
            paths = [
                '/System/Library/Fonts/Supplemental',
                '/Library/Fonts',
                '/System/Library/Fonts'
            ]
        elif system == "Windows":
            paths = [os.path.join(os.environ['WINDIR'], 'Fonts')]
        else:  # Linux
            paths = [
                '/usr/share/fonts',
                '/usr/local/share/fonts',
                os.path.expanduser('~/.fonts')
            ]
        return paths

    def _is_valid_font(self, path):
        """Validate font file can be loaded"""
        try:
            ImageFont.truetype(path, 12)
            return True
        except (OSError, IOError):
            return False

    def get_font(self, family, weight='Regular', size=12):
        """Get font with proper weight handling"""
        weights = self.font_cache.get(family, {})
        
        # Find best matching weight
        weight = weight.capitalize()
        if weight not in weights:
            if "Regular" in weights:
                weight = "Regular"
            elif weights:
                weight = next(iter(weights.keys()))
        
        return ImageFont.truetype(weights[weight], size)

    def get_weights_for_family(self, family):
        """Return available weights for a font family"""
        return sorted(self.font_cache.get(family, {}).keys())

    def get_families(self):
        """Return list of available font families"""
        return self.font_name_list
