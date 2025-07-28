import struct
import argparse
import os

def unpack_thing(file_path, out_dir = None):

    if out_dir is None:
        out_dir = os.path.dirname(file_path) or '.'

    with open(file_path, 'rb') as f:
        first_fname = f.read(8)
        header_len = struct.unpack('<i', first_fname[4:8])[0]
        print(header_len)
        f.seek(0)
        header = f.read(header_len)

        header_entry = {
            "fname_len": 0,
            "fname_off": 0,
            "file_content_len": 0,
            "file_content_off": 0,
        }

        offsets = []
        for i in range(0, header_len, 32):
            new_entry = header_entry.copy()

            new_entry["fname_len"] = struct.unpack('<i', header[i:i+4])[0]
            new_entry["fname_off"] = struct.unpack('<i', header[i+4:i+8])[0]
            new_entry["file_content_len"] = struct.unpack('<i', header[i+12:i+16])[0]
            new_entry["file_content_off"] = struct.unpack('<i', header[i+16:i+20])[0]
            offsets.append(new_entry)
        
        for i, offset in enumerate(offsets):
            f.seek(offset["fname_off"])
            data = f.read(offset["fname_len"])

            fl_name = data.decode('unicode_escape')[:-1]

            print(fl_name)
            
            f.seek(offset["file_content_off"])
            data = f.read(offset["file_content_len"])
            
            with open(f'{out_dir}\\{fl_name}', 'wb') as thing_file:
                thing_file.write(data)
            print(f'{fl_name} written')

def main():
    parser = argparse.ArgumentParser(description='Unpack assets from the asset packing file')
    parser.add_argument('input_file', help='Path to the input file to unpack')
    parser.add_argument('-o', '--output', help='Output directory (default: same as input file)')
    
    args = parser.parse_args()
    
    unpack_thing(args.input_file, args.output)

if __name__ == '__main__':
    main()
