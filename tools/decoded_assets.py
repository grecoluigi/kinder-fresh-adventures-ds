"""Read decoded original images only from an explicitly supplied asset directory."""
from pathlib import Path
import json
from PIL import Image

class DecodedAssets:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.inventory = {item['source'].lower():item for item in json.loads((self.root/'inventory.json').read_text())}

    def image(self, metadata, mode='RGBA'):
        path = Path(metadata['png']).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Decoded image lies outside supplied directory: '+str(path))
        with Image.open(path) as image:
            return image.convert(mode)
