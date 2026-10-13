import os
from PIL import Image, ImageChops

def make_icon_transparent(icon_path, output_path):
    print(f"Loading {icon_path}...")
    img = Image.open(icon_path).convert("RGBA")
    width, height = img.size
    
    # Let's floodfill from the four corners to turn white/near-white background transparent
    # We will check if the corner pixels are near-white (R>240, G>240, B>240)
    # and use floodfill.
    from PIL import ImageDraw
    
    # We will do a flood fill from corners: (0,0), (width-1, 0), (0, height-1), (width-1, height-1)
    # with a tolerance. To implement tolerance flood fill easily, we can find pixels that are close to the corner color
    # or just do a standard flood fill if the background is solid white.
    # Let's check the corner colors first:
    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    bg_colors = [img.getpixel(c) for c in corners]
    print("Corner colors:", bg_colors)
    
    # Let's create a mask of the background.
    # If the background is white, we can convert all pixels with R > 240, G > 240, B > 240 and A > 0 to transparent
    # if they are connected to the outside, or simply convert all near-white pixels to transparent.
    # Let's do a floodfill with a tolerance using standard floodfill from PIL.ImageDraw.
    # Since ImageDraw.floodfill supports a threshold/tolerance in newer versions, or we can write a simple BFS flood fill.
    
    pixels = img.load()
    visited = set()
    to_visit = []
    
    # Find seed points (corners) that are near-white
    for x, y in corners:
        r, g, b, a = pixels[x, y]
        if r > 200 and g > 200 and b > 200:  # near-white background
            to_visit.append((x, y))
            visited.add((x, y))
            
    # BFS to find all connected background pixels
    while to_visit:
        cx, cy = to_visit.pop(0)
        r, g, b, a = pixels[cx, cy]
        
        # Make this pixel transparent
        pixels[cx, cy] = (r, g, b, 0)
        
        # Check 4-neighbors
        for nx, ny in [(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)]:
            if 0 <= nx < width and 0 <= ny < height:
                if (nx, ny) not in visited:
                    nr, ng, nb, na = pixels[nx, ny]
                    # If neighbor is also near-white, it's part of the background
                    if nr > 200 and ng > 200 and nb > 200:
                        visited.add((nx, ny))
                        to_visit.append((nx, ny))
                        
    # Save the result as an icon with multiple sizes for Windows
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon_images = []
    for size in sizes:
        # Resize using high-quality resampling
        resized = img.resize(size, Image.Resampling.LANCZOS)
        icon_images.append(resized)
        
    img.save(output_path, format="ICO", sizes=sizes)
    print(f"Saved transparent icon to {output_path} successfully!")

if __name__ == "__main__":
    icon_path = "app_icon.ico"
    make_icon_transparent(icon_path, "app_icon.ico")
