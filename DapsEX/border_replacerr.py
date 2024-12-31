from pathlib import Path

from PIL import Image


class BorderReplacerr:
    def __init__(self, custom_color=None) -> None:
        self.custom_color = custom_color

    def remove_border(self, image_path: Path):
        image = Image.open(image_path)
        width, height = image.size
        crop_area = (25, 25, width - 25, height)

        final_image = image.crop(crop_area)
        bottom_border = Image.new("RGB", (width - 2 * 25, 25), color="black")
        bottom_border_position = (0, final_image.size[1] - 25)
        final_image.paste(bottom_border, bottom_border_position)
        final_image = final_image.resize((1000, 1500)).convert("RGB")

        return final_image

    def replace_border(self, image_path: Path):
        image = Image.open(image_path)
        width, height = image.size
        crop_area = (25, 25, width - 25, height - 25)
        cropped_image = image.crop(crop_area)
        new_image = Image.new("RGB", (width, height), color=self.custom_color)
        new_image.paste(cropped_image, (25, 25))
        final_image = new_image.resize((1000, 1500)).convert("RGB")
        return final_image
