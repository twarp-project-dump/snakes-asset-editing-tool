import struct
import argparse
import os

def get_file_order_from_dat(dat_file):
    """Extract the original file order from a .dat file"""
    with open(dat_file, 'rb') as f:
        first_fname = f.read(8)
        header_len = struct.unpack('<i', first_fname[4:8])[0]
        f.seek(0)
        header = f.read(header_len)

        file_order = []
        for i in range(0, header_len, 32):
            fname_len = struct.unpack('<i', header[i:i+4])[0]
            fname_off = struct.unpack('<i', header[i+4:i+8])[0]
            
            f.seek(fname_off)
            data = f.read(fname_len)
            filename = data.decode('unicode_escape')[:-1]
            file_order.append(filename)
            
        return file_order


def repack_thing(input_dir, output_file, reference_dat=None):
    """Repack a folder back into a .dat, optionally with preserved file order"""
    files = []
    for filename in os.listdir(input_dir):
        filepath = os.path.join(input_dir, filename)
        if os.path.isfile(filepath):
            files.append(filename)
    
    if reference_dat:
        try:
            files = get_file_order_from_dat(reference_dat)
        except Exception as e:
            print(f"couldn't read the reference .dat for the file order. {e}")

    header_entries = []
    current_fname_offset = 32 * len(files)  # Header size
    current_data_offset = current_fname_offset

    for filename in files:
        filename_encoded = filename.encode('unicode_escape') + b'\x00'
        current_data_offset += len(filename_encoded)
    
    for i, filename in enumerate(files):
        filename_encoded = filename.encode('unicode_escape') + b'\x00'
        fname_len = len(filename_encoded)
        
        filepath = os.path.join(input_dir, filename)
        file_size = os.path.getsize(filepath)
        
        word6 = 0x20 * (i - 1) if i >= 2 else 0
        
        word7 = 0x20 * (i + 1) if i != len(files) - 1 else 0
        
        entry = struct.pack('<i', fname_len)  # filename length
        entry += struct.pack('<i', current_fname_offset)  # filename offset
        entry += struct.pack('<i', 0)  # unknown (padding)
        entry += struct.pack('<i', file_size)  # file content length
        entry += struct.pack('<i', current_data_offset)  # file content offset
        entry += struct.pack('<i', 0)  # unknown (padding)
        entry += struct.pack('<i', word6)  # numbering system (word 6)
        entry += struct.pack('<i', word7)  # numbering system (word 7)
        
        header_entries.append(entry)
        
        current_fname_offset += fname_len
        current_data_offset += file_size
    
    with open(output_file, 'wb') as out_f:
        for entry in header_entries:
            out_f.write(entry)
        
        for filename in files:
            filename_encoded = filename.encode('unicode_escape') + b'\x00'
            out_f.write(filename_encoded)
        
        for filename in files:
            filepath = os.path.join(input_dir, filename)
            with open(filepath, 'rb') as in_f:
                out_f.write(in_f.read())

def main():
    parser = argparse.ArgumentParser(description='Repack assets into the asset packing file')
    parser.add_argument('input_dir', help='Directory containing files to repack')
    parser.add_argument('output_file', help='Path to the output .dat file')
    parser.add_argument('-r', '--reference', help='Reference .dat file to maintain original file order', default=None)
    
    args = parser.parse_args()
    
    repack_thing(args.input_dir, args.output_file, args.reference)
    print(f"Successfully repacked files into {args.output_file}")

if __name__ == '__main__':
    main()