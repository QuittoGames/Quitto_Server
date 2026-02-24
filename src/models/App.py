from dataclasses import dataclass
from pathlib import Path

@dataclass
class App:
    name:str
    app_path:Path 
