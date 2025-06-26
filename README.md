# blender-curve-to-svg-2
a Blender 3.6+ Curve to SVG add-on

I came across [this older version](https://github.com/aryelgois/blender-curve-to-svg) and it seemed perfect for my use, but it was made for Blender 2.77 and didn't work on more modern versions.

So Claude and I adapted it for 3.6+

# Install
- Download .py file from this repo 
- Go to Add-ons tab in the User Preferences
- Click Install Add-on from File...
- Find and select curve_to_svg_modern_2.py
- Enable the add-on by clicking on its checkbox

# Usage

First select your curve object that you want to export, and then under File -> Export -> Curves to SVG

There's a few options in the top right of the export dialogue box.

- Scale: by default it's 100, the range is 0.1 to 1000 and there's some override if your Blender unit scale is outside that range (I was getting errors with teeny tiny exports). SVG is a weird format because it both has a nominal pixel scale value and also is a vector so doesn't care about raster scaling at all. Here, scale = 100 means that a 1 Blender unit curve will be 100 pixels wide in the file.

- Precision: how many decimals to save each point to. Higher values are more precise, but slightly larger file size. The default is 3, but maybe I should increase it to more. I'm not sure what kind of curves y'all are going to try to export. File size is barely an issue with SVGs anyway.

- Minify: exports as a single line instead of nice XML formatting. Personally, I was looking through the SVG code itself during this process, so my default is for verbose file export.

- Include fill: this was a feature from the original repo but I actually don't think it works right now for modern Blender because it's looking at the colour value for the material, not for the colour value of a node-based BSDF shader. It would be trivial to add this lookup into the loop, but for my uses (laser cutting and CNC files) I don't care about colour at all so this will have to remain a to-do. Worst case, if colour was important, you can manually add it to your SVG file by opening and editing it as text. The fill="#ffffff" stroke="#ffffff" stroke-width="1.00" values are right there. It'd just be nice to automate this on export. If you're doing fancy art with gradients and stuff you can open the file in Illustrator or Inkscape.

# Troubleshooting

I've been viewing my resulting SVGs with [SVGviewer.dev](https://www.svgviewer.dev/). You can also open them with any web browser directly, but it's possible that by default it loads a white shape over a white background and you can't see anything without futzing with the CSS in the console. The SVG viewer gives you background options and shows you the resulting SVG code directly, so you can sort of look through it for obvious errors or defined colours.

The curve HAS to be 2D in the Blender curve data panel.
