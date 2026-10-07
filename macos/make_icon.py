"""Generate the app's Retina cross-and-open-Bible icon using bundled Pillow."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

destination = Path(sys.argv[1])
destination.mkdir(parents=True, exist_ok=True)
size = 1024
icon = Image.new("RGBA", (size, size))
gradient = Image.new("RGBA", (size, size))
draw = ImageDraw.Draw(gradient)
for y in range(size):
    fraction = y / size
    draw.line((0, y, size, y), fill=(int(37 - 18 * fraction), int(45 - 23 * fraction), int(32 - 17 * fraction), 255))
mask = Image.new("L", (size, size))
ImageDraw.Draw(mask).rounded_rectangle((32, 32, 992, 992), radius=210, fill=255)
icon.paste(gradient, (0, 0), mask)
draw = ImageDraw.Draw(icon)
gold = (226, 183, 111, 255)
cream = (246, 238, 215, 255)
draw.rounded_rectangle((72, 72, 952, 952), radius=175, outline=(155, 128, 80, 170), width=3)
draw.rounded_rectangle((482, 175, 542, 690), radius=13, fill=gold)
draw.rounded_rectangle((320, 310, 704, 364), radius=12, fill=gold)
draw.polygon([(204, 645), (204, 800), (340, 780), (512, 850), (684, 780), (820, 800), (820, 645), (684, 625), (512, 695), (340, 625)], fill=cream)
draw.line([(204, 817), (340, 797), (512, 868), (684, 797), (820, 817)], fill=gold, width=16, joint="curve")
draw.line((512, 696, 512, 845), fill=(122, 99, 61, 255), width=8)
for offset in (0, 37, 74):
    draw.line([(253, 675 + offset), (340, 662 + offset), (460, 713 + offset)], fill=(149, 129, 88, 210), width=5, joint="curve")
    draw.line([(564, 713 + offset), (684, 662 + offset), (771, 675 + offset)], fill=(149, 129, 88, 210), width=5, joint="curve")
for points in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        suffix = "@2x" if scale == 2 else ""
        icon.resize((points * scale, points * scale), Image.Resampling.LANCZOS).save(destination / f"icon_{points}x{points}{suffix}.png")
