# app_service.py

import tkinter as tk # Need for root type hint
from typing import Optional # For type hint

# Import the components that AppService will create and manage
from utils.font_manager import FontManager
from model import DrawingModel
from view import DrawingView
from controller import DrawingApp # Import the Controller class (DrawingApp)


class AppService:
    _instance = None

    @classmethod
    def get_instance(cls, root=None):
        if cls._instance is None:
            if root is None:
                raise ValueError("AppService.get_instance() must be passed root on first call.")
            cls._instance = cls(root)
        return cls._instance

    def __init__(self, root):
        self.root = root
        self.font_manager = FontManager()  # Replace with your actual font manager class
        self.controller = DrawingApp(self.root, self.font_manager)
        self.model = self.controller.model
        self.view = self.controller.view 

    def get_font_manager(self):
        return self.font_manager

    def get_controller(self):
        return self.controller