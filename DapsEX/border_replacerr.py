from PIL import Image
from pathlib import Path

class BorderReplacerr:
    def __init__(self) -> None:
        pass

    def remove_border(self, image_path: Path):
        image = Image.open(image_path)
        width, height = image.size
        crop_area = (25, 25, width - 25, height)

        final_image = image.crop(crop_area)
        bottom_border = Image.new("RGB", (width - 2 * 25, 25), color='black')
        bottom_border_position = (0, final_image.size[1] - 25)
        final_image.paste(bottom_border, bottom_border_position)

        return final_image


