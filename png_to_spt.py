import numpy as np
from PIL import Image
import os
import argparse
from collections import defaultdict

def create_spt_file(output_path: str, images: list, palette_size: int = 256, x_offset = 0, y_offset = 0):
    """
    Create an .spt file from a list of PIL Images
    :param output_path: Path to save the .spt file
    :param images: List of PIL Images (must all be same size)
    :param palette_size: Maximum number of colors to use (default 256)
    """
    if not images:
        raise ValueError("No images provided")
    
    if (palette_size > 256):
        raise ValueError("Palette size cannot be bigger than 256 due to math reasons")

    width, height = images[0].size
    for img in images:
        if img.size != (width, height):
            raise ValueError("All images must be the same dimensions")
    
    images_rgba = [img.convert("RGBA") for img in images]
    
    all_pixels = []
    for img in images_rgba:
        all_pixels.extend(img.getdata())

    color_counts = defaultdict(int)
    for pixel in all_pixels:
        color_counts[pixel] += 1

    #just in case you add a ton of random colors to a sequence of animated images
    sorted_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)

    if len(sorted_colors) > palette_size:
        print(f"Cutting down the pallette from {sorted_colors} colors to {palette_size} colors")

    palette = [color[0] for color in sorted_colors[:palette_size]]
    
    color_table = bytearray()
    for color in palette:
        r, g, b, a = color
        argb = (
            ((a >> 4) & 0xF) << 12 | 
            ((r >> 4) & 0xF) << 8 | 
            ((g >> 4) & 0xF) << 4 | 
            ((b >> 4) & 0xF)
        )
        color_table.extend(argb.to_bytes(2, byteorder='big'))
    
    # Determine .spt type (2 for single image, 6 for multiple)
    spt_type = 2 if len(images) == 1 else 6

    if (spt_type == 2 and (x_offset != 0 or y_offset != 0)):
        print(f"WARNING: single-image SPT files do not have x and y offset fields :p")
    
    # Create header
    header = bytearray()
    header.extend(spt_type.to_bytes(4, byteorder='little'))  # SPT type
    header.extend(len(images).to_bytes(4, byteorder='little'))  # Number of images
    header.extend(width.to_bytes(4, byteorder='little'))  # Width

    # Height
    if spt_type == 6:
        header.extend(height.to_bytes(4, byteorder='little'))  # Height
    else:
        header.extend(height.to_bytes(1, byteorder='little'))  # Height
    
    if spt_type == 6:
        # For multi-image SPT files there are x and y offsets. for whatever reason? not single image ones
        header.extend(x_offset.to_bytes(4, byteorder='little'))  # X Offset
        header.extend(y_offset.to_bytes(1, byteorder='little'))  # Y Offset
    
    header.extend(len(palette).to_bytes(1, byteorder='little'))  # Number or colors
    header.extend(color_table)
    
    image_data = bytearray()
    for img in images_rgba:
        pixels = []
        for pixel in img.getdata():
            try:
                index = palette.index(pixel)
            except ValueError:
                index = min(range(len(palette)), 
                          key=lambda i: sum((a-b)**2 for a, b in zip(palette[i], pixel)))
            pixels.append(index)
        
        rle_data = bytearray()
        i = 0
        n = len(pixels)
        
        while i < n:
            current_val = pixels[i]
            run_length = 1
            
            # get the run length
            while i + run_length < n and pixels[i + run_length] == current_val and run_length < 16383:
                run_length += 1
            
            if run_length > 1:
                # encode the rle
                if run_length <= 7 and len(palette) <= 16:
                    # 4-bit (3-bit, really) rle
                    encoded = (0x80 | ((run_length & 0x7) << 4) | (current_val & 0xF))
                    rle_data.append(encoded)
                else:
                    # use normal rle if its too long or too many colors are there
                    rle_data.append(0x80 | (current_val & 0x7F))
                    
                    if run_length <= 127:
                        rle_data.append(run_length & 0x7F)
                    else:
                        # long run length
                        high = (run_length // 128)
                        low = run_length % 128
                        rle_data.append(low | 0x80)
                        rle_data.append(high)
            else:
                # just a color that's 1 in length
                rle_data.append(current_val & 0x7F)
            
            i += run_length
        
        image_data.extend(len(rle_data).to_bytes(4, byteorder='big'))
        image_data.extend(rle_data)
    
    with open(output_path, 'wb') as f:
        f.write(header)
        f.write(image_data)

def process_png_to_spt(input_path: str, output_dir: str):
    """
    Process PNG file(s) to SPT format
    :param input_path: Can be a single PNG file or a directory of PNGs
    :param output_dir: Directory to save the SPT file(s)
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if os.path.isfile(input_path):
        # process single one
        img = Image.open(input_path)
        output_path = os.path.join(output_dir, os.path.splitext(os.path.basename(input_path))[0] + '.spt')
        create_spt_file(output_path, [img])
        print(f"Created {output_path}")
    elif os.path.isdir(input_path):
        # ...or a directory, try and group them by name for animated spts
        png_files = [f for f in os.listdir(input_path) 
                    if os.path.isfile(os.path.join(input_path, f)) and f.lower().endswith('.png')]
        
        if not png_files:
            print(f"No PNG files found in {input_path}")
            return
        
        # grouping images
        file_groups = defaultdict(list)
        for f in png_files:
            if (f.count("__frame") > 0):
                base_name = f.split("__frame")[0]  # so "image[[1;2]]__frame0.png", "image[[1;2]]__frame1.png" and so on
            else:
                base_name = f.replace(".png", "")
            file_groups[base_name].append(f)
        
        for base_name, files in file_groups.items():
            files.sort()
            images = [Image.open(os.path.join(input_path, f)) for f in files]

            if len(images) == 1:
                output_path = os.path.join(output_dir, base_name.replace(".png", "") + '.spt')
                create_spt_file(output_path, images)
            else:
                # get the offsets encoded like "[[1;2]]" in the filename. they should be the same for the whole image group or it will split them in two and cause you issues
                output_path = os.path.join(output_dir, base_name.split("[[")[0] + '.spt')
                offsets = base_name.split("[[")[1].split("]]")[0].split(";")
                create_spt_file(output_path, images, 256, int(offsets[0]), int(offsets[1]))
                
            
            print(f"Created {output_path} with {len(images)} images")

def main():
    parser = argparse.ArgumentParser(description='Convert PNG images to .spt format')
    parser.add_argument('input_path', help='Input PNG file or directory containing PNGs')
    parser.add_argument('-o', '--output', help='Output directory (default: input_path + "_spt")')
    
    args = parser.parse_args()
    
    input_path = args.input_path
    output_dir = args.output if args.output else f"{input_path}_spt"
    
    process_png_to_spt(input_path, output_dir)

if __name__ == '__main__':
    main()