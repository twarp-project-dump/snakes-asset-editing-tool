import numpy as np
from PIL import Image
from os import listdir
from os.path import isfile, join, isdir
import argparse
import os

class EncodedImage:
    def __init__(self, offset, length):
        self.offset = offset
        self.length = length

def read_spt_file(spt_path_ : str, img_name : str, out_dir : str):
    print(f"Currently reading {img_name}", end="")
    data = np.fromfile(spt_path_, dtype='B', count=-1)

    if len(data) == 0:
        print("its empty")
        return

    spt_type = int(data[0])

    images_stored = int(data[4])
    #print(f"likely {images_stored} images detected")

    image_x = int(data[8])
    image_y = int(data[12])

    color_offset = 13

    color_table = {}

    binner = lambda x: bin(x)[2:]
    padder = lambda x: str(x).zfill(8)
    vec_binner = np.vectorize(binner)
    vec_padder = np.vectorize(padder)

    output_images = []

    x_offset = 0
    y_offset = 0

    # type 2 are single-image files, type 6 are multi-image... with x and y offsets. lol
    if spt_type == 2:
        color_array_len = int(data[color_offset])
    else:
        x_offset = int(data[16])
        y_offset = int(data[20])
        color_offset = color_offset + 8
        color_array_len = int(data[color_offset])

    #print(f"{color_array_len} colors")

    def parse_color(parse_at:int):
        bytes_two = data[parse_at:parse_at+2]
        if len(bytes_two) != 2:
            print("error processing colors")
            return
        bytes_two_binned = vec_padder(vec_binner(bytes_two))
        #this does seem to only ever produce images that have 240 as max values, but it does perfectly match what you see in the emulator (tested by overlaying a screencap of the snakes logo on top of the mainlogo.png), so IDK what to make of it. bump the alpha up by 15 or so if you want fully opaque images. lol
        tr = int(bytes_two_binned[0][0:4], 2)*16
        r = int(bytes_two_binned[0][4:8], 2)*16
        g = int(bytes_two_binned[1][0:4], 2)*16
        b = int(bytes_two_binned[1][4:8], 2)*16
        return np.array([r, g, b, tr], dtype=np.uint8)

    #parse the color table
    def parse_color_chunk(parse_at:int, parse_until:int):
        color_id = 0
        i_ = parse_at
        while i_ < parse_at+parse_until:
            #print(i_)
            color_table[color_id] = parse_color(i_)
            i_ += 2
            color_id+=1

    parse_color_chunk(color_offset + 1, color_array_len*2)

    #print(color_table)

    init_offset = color_array_len*2 + color_offset + 1

    #print(f"getting compressed chunk length at {init_offset}")

    #skip the zeroes in multiimage files. i guess this is a hack but i wrote this half a year ago i dont wanna bother
    while data[init_offset+3] == 0:
        init_offset += 4

    def get_chunk_length(at_where:int):
        #print(f"reading chunk len at {at_where}")
        chunk_len_word = data[at_where:at_where+4]
        #print(chunk_len_word)
        bin_array = vec_binner(chunk_len_word)
        padded_array = vec_padder(bin_array)
        chunk_len = int( ''.join(padded_array), 2 )
        return chunk_len

    current_read_offset = init_offset

    #overcomplicated yeah but just in case. its specifically here because of the prototype's evolver.spt file
    def filter_upper_bits(icolor:int, color_count:int):
        icolor = icolor % 128
        if color_count < 64:
            icolor = icolor % 64
        if color_count < 32:    
            icolor = icolor % 32
        if color_count < 16:
            icolor = icolor % 16
        return icolor

    def read_image(begin : int, length: int):
        out_image = np.array([], dtype=np.int8)
        total_len = 0
        i_ = begin
        while i_ < begin + length:
            current_color = data[i_]

            if (current_color >= 128):
                if color_array_len <= 16:
                    #the 4-bit\e-bit rle thingy
                    inline_rle = int("0b0"+bin(current_color)[3:6], 2)
                else:
                    inline_rle = 0

                current_color = filter_upper_bits(current_color, color_array_len)
                
                if inline_rle == 0:
                    i_ += 1
                    color_length = data[i_]


                    if color_length > 127:
                        i_ += 1

                        #print(f"{color_length} {bin(color_length)} cl {data[i_]} {bin(data[i_])} tr")

                        #extended color length
                        color_length += 128 * (data[i_] - 1)

                        

                    #print(f'rle compressed color {current_color} with length {color_length}')
                    total_len += color_length
                    out_image = np.append(out_image, np.tile(np.array([current_color]), color_length))
                else:
                    #print(f'rle inline compressed color {current_color} with length {inline_rle}')
                    out_image = np.append(out_image, np.tile(np.array([current_color]), inline_rle))
                    total_len += inline_rle
                
            else:
                total_len += 1
                #print(f'normal color {current_color} len 1')
                out_image = np.append(out_image, np.array([current_color]))

            i_ += 1

        pixel_loss = (image_x * image_y) - total_len

        #print(f"got length {total_len} when {int(image_x) * int(image_y)} is intended (probably)")
        #print(f"x {int(image_x)} y {int(image_y)} color count {color_array_len}")

        #some sanity checks for the rle decoder. it used to explode a lot

        if pixel_loss > 0:
            print(f"whered you lose {pixel_loss} pixels huh")
            out_image = np.concatenate([out_image, np.zeros((pixel_loss))], axis=0)

        if pixel_loss < 0:
            print(f"whered you GAIN {pixel_loss * -1} pixels huh")
            out_image = out_image[:(image_x * image_y)]

        output_images.append(out_image)

    encoded_images = []

    for i in range(images_stored):
        chunk_len = get_chunk_length(current_read_offset)
        #print(f"chunk should be {chunk_len} in length")
        encoded_images.append(EncodedImage(current_read_offset+4, chunk_len))
        current_read_offset += chunk_len + 4

    #init_offset + 1
    enc_i : EncodedImage
    for enc_i in encoded_images:
        read_image(enc_i.offset, enc_i.length)
        print(f".", end="")

    output_images_colored = []

    #dict_vec_thing = np.vectorize(color_table.__getitem__)

    for i in output_images:
        colored_img = []
        for j in i:
            max_color = max(color_table.keys())
            j = j % (max_color+1)
            colored_img.append(color_table[j])
        colored_img = np.array(colored_img)
        output_images_colored.append(colored_img)

    if len(output_images_colored) == 1:
        output_path = os.path.join(out_dir, f"{img_name[:-4]}.png")
        Image.fromarray(output_images_colored[0].reshape(image_y, image_x, 4), 'RGBA').save(output_path)
    else:
        for i, img_ in enumerate(output_images_colored):
            output_path = os.path.join(out_dir, f"{img_name[:-4]}[[{x_offset};{y_offset}]]__frame{i}.png")
            Image.fromarray(img_.reshape(image_y, image_x, 4), 'RGBA').save(output_path)
    print(" done.")

def process_spt_files(input_path: str, output_dir: str):
    if not os.path.exists(input_path):
        print(f"no input path named '{input_path}'")
        return

    if isdir(input_path):
        # Process directory
        spt_files = [f for f in listdir(input_path) 
                    if isfile(join(input_path, f)) and f.lower().endswith('.spt')]

        if not spt_files:
            print(f"no .spt files in input directory named {input_path}")
            return

        print(f"...found {len(spt_files)} .spt files to process")

        for filename in spt_files:
            input_file_path = join(input_path, filename)
            read_spt_file(input_file_path, filename, output_dir)
        
        print(f"wrote like {len(spt_files)} .pngs to {output_dir}")
    else:
        # Process single file
        if not input_path.lower().endswith('.spt'):
            print("input file is not an .spt file")
            return
            
        filename = os.path.basename(input_path)
        read_spt_file(input_path, filename, output_dir)
        print(f"wrote converted file to {output_dir}")

def main():
    parser = argparse.ArgumentParser(description='Convert .spt images to .png ones')
    parser.add_argument('input_path', help='Input file or directory containing .spt files')
    parser.add_argument('-o', '--output', help='Output directory (default: input_dir + "_output" for directories or same directory as input file)')
    
    args = parser.parse_args()
    
    input_path = args.input_path
    if isdir(input_path):
        output_dir = args.output if args.output else f"{input_path}_output"
    else:
        output_dir = args.output if args.output else os.path.dirname(input_path)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    process_spt_files(input_path, output_dir)

if __name__ == '__main__':
    main()