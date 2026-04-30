import importlib.util
import os
import sys
from typing import List, Type
from .base import MainAPI
from .orchestrator import ProviderManager

class ExtensionManager:
    """
    Handles loading of external Python-based providers from the extensions folder.
    """
    def __init__(self, extensions_dir: str = "extensions"):
        self.extensions_dir = extensions_dir
        if not os.path.exists(self.extensions_dir):
            os.makedirs(self.extensions_dir)
        
        # Add extensions dir to sys.path to allow imports
        abs_path = os.path.abspath(self.extensions_dir)
        if abs_path not in sys.path:
            sys.path.append(abs_path)

    def load_extensions(self, manager: ProviderManager):
        """
        Scans the extensions directory for .py files and registers classes inheriting from MainAPI.
        """
        for filename in os.listdir(self.extensions_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, 
                        os.path.join(self.extensions_dir, filename)
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for classes that inherit from MainAPI
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, MainAPI) and 
                            attr is not MainAPI):
                            
                            # Instantiate and register
                            provider = attr(session=manager.session)
                            manager.register_provider(provider)
                            print(f"Loaded extension: {provider.name}")
                            
                except Exception as e:
                    print(f"Failed to load extension {filename}: {e}")

def load_all_extensions(manager: ProviderManager):
    """Helper to load extensions from the default directory."""
    ext_manager = ExtensionManager()
    ext_manager.load_extensions(manager)
