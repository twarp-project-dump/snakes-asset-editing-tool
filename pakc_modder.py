import os
import subprocess
import argparse
import shutil
import struct
import sys
from pathlib import Path

SOX_AVAILABLE = False
SOX_PATH = None

def check_required_tools():
    """Check for required executables and tools"""
    global SOX_AVAILABLE, SOX_PATH
    
    required_exes = ['decrypt_pakc.exe', 'offzip.exe', 'packzip.exe']
    missing_exes = []
    
    # Check main executables
    for exe in required_exes:
        # Check in current folder
        if os.path.exists(exe):
            continue
            
        # Check in PATH
        found_in_path = False
        for path in os.environ['PATH'].split(os.pathsep):
            exe_path = os.path.join(path, exe)
            if os.path.exists(exe_path):
                found_in_path = True
                break
                
        if not found_in_path:
            missing_exes.append(exe)
    
    # Check for SOX (either in ./sox or PATH)
    sox_path = None
    if os.path.exists("./sox/sox") or os.path.exists("./sox/sox.exe"):
        SOX_AVAILABLE = True
        SOX_PATH = "./sox/sox.exe" if sys.platform == "win32" else "./sox/sox"
    else:
        # Check PATH for sox
        for path in os.environ['PATH'].split(os.pathsep):
            potential_path = os.path.join(path, "sox.exe" if sys.platform == "win32" else "sox")
            if os.path.exists(potential_path):
                SOX_AVAILABLE = True
                SOX_PATH = potential_path
                break
    
    if missing_exes:
        print("\nERROR: The following required executables were not found:")
        for exe in missing_exes:
            print(f"  - {exe}")
        print("\nPlease ensure these files are either:")
        print("1. In the same folder as this script, or")
        print("2. Available in your system PATH\n")
        return False
    
    if not SOX_AVAILABLE:
        print("\nWARNING: SOX audio tool not found. ADP audio conversion will be disabled.")
        print("To enable ADP conversion, either:")
        print("1. Place SOX in a './sox' subfolder, or")
        print("2. Install SOX and ensure it's in your system PATH\n")
    
    return True


def clear_create_dir(temp_dir):
    """Remove and recreate temp directory to ensure clean state"""
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

def decrypt_pakc(input_file, output_file, key=None, key_file=None, key_num=None):
    """Decrypt .pakc file using decrypt_pakc.exe"""
    cmd = ["decrypt_pakc.exe", "-i", input_file, "-o", output_file, "-d"]
    
    if key:
        cmd.extend(["-k", key])
    elif key_file:
        cmd.extend(["-kf", key_file])
    elif key_num:
        cmd.extend(["-n", str(key_num)])
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error decrypting {input_file}: {e}")
        return False

def encrypt_pakc(input_file, output_file, key=None, key_file=None, key_num=None):
    """Encrypt .pak file to .pakc using decrypt_pakc.exe"""
    cmd = ["decrypt_pakc.exe", "-i", input_file, "-o", output_file, "-e"]
    
    if key:
        cmd.extend(["-k", key])
    elif key_file:
        cmd.extend(["-kf", key_file])
    elif key_num:
        cmd.extend(["-n", str(key_num)])
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error encrypting {input_file}: {e}")
        return False

def extract_with_offzip(input_file, output_dir):
    """Extract single .dat from .pak using offzip"""
    cmd = ["offzip.exe", "-a", input_file, output_dir, "0"]
    
    try:
        subprocess.run(cmd, check=True)
        # Find the extracted .dat file (should be only one)
        dat_files = [f for f in os.listdir(output_dir) if f.endswith('.dat')]
        if not dat_files:
            print("Error: No .dat file found in offzip output")
            return None
        return os.path.join(output_dir, dat_files[0])
    except subprocess.CalledProcessError as e:
        print(f"Error extracting with offzip: {e}")
        return None

def unpack_dat(input_file, output_dir=None):
    """Unpack .dat file using unpacker.py"""
    cmd = ["python", "unpacker.py", input_file]
    if output_dir:
        cmd.extend(["-o", output_dir])
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error unpacking {input_file}: {e}")
        return False

def repack_dir(input_dir, output_file):
    """Repack directory into .dat using repacker.py"""
    cmd = ["python", "repacker.py", input_dir, output_file]
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error repacking {input_dir}: {e}")
        return False

def pack_with_packzip(input_file, output_file, original_pak):
    """Pack .dat into .pak using packzip.exe and copy header from original"""
    # First run packzip
    cmd = ["packzip.exe", "-c", "-o", "0x35", input_file,  output_file]
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error packing with packzip: {e}")
        return False
    
    # Copy header from original .pak file
    try:
        with open(original_pak, 'rb') as f:
            header = f.read(0x35)  # Read the header
        
        with open(output_file, 'r+b') as f:
            original_content = f.read()
            f.seek(0)
            f.write(header)
            f.write(original_content[53:])
            
            # Pad with 0xCD to nearest dword boundary
            current_size = f.tell()
            pad_size = (8 - (current_size % 8)) % 8
            f.write(b'\xCD' * pad_size)
        
        return True
    except IOError as e:
        print(f"Error processing pak header: {e}")
        return False

def convert_spt_to_png(input_dir, output_dir=None):
    """Convert SPT files to PNG using spt_to_png_3.py"""
    if output_dir is None:
        output_dir = os.path.join(input_dir, "png_output")
    
    cmd = ["python", "spt_to_png_3.py", input_dir]
    if output_dir:
        cmd.extend(["-o", output_dir])
    
    try:
        subprocess.run(cmd, check=True)
        return output_dir
    except subprocess.CalledProcessError as e:
        print(f"Error converting SPT to PNG: {e}")
        return None

def convert_png_to_spt(input_dir, output_dir=None):
    """Convert PNG files back to SPT using png_to_spt.py"""
    if output_dir is None:
        output_dir = os.path.join(input_dir, "spt_output")
    
    cmd = ["python", "png_to_spt.py", input_dir]
    if output_dir:
        cmd.extend(["-o", output_dir])
    
    try:
        subprocess.run(cmd, check=True)
        return output_dir
    except subprocess.CalledProcessError as e:
        print(f"Error converting PNG to SPT: {e}")
        return None

def convert_bix_to_gltf(input_path, output_path):
    """Convert BIX to GLTF using bix_converter.py"""
    cmd = ["python", "bix_converter.py", "--bix-to-gltf", input_path, output_path]
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting BIX to GLTF: {e}")
        return False

def convert_gltf_to_bix(input_path, output_path):
    """Convert GLTF to BIX using bix_converter.py"""
    cmd = ["python", "bix_converter.py", "--gltf-to-bix", input_path, output_path]
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting GLTF to BIX: {e}")
        return False

def convert_adp_to_wav(input_path, output_path=None):
    """Convert ADP to WAV using sox"""
    if not SOX_AVAILABLE:
        print("ADP conversion disabled - SOX not found")
        return None
        
    if output_path is None:
        output_path = input_path.replace('.adp', '.wav')
    
    cmd = [SOX_PATH, "-t", "ima", "-r", "8000", "-e", "ima-adpcm", input_path, "-t", "wav", output_path]
    
    try:
        subprocess.run(cmd, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Error converting ADP to WAV: {e}")
        return None

def convert_wav_to_adp(input_path, output_path=None):
    """Convert WAV to ADP using sox"""
    if output_path is None:
        output_path = input_path.replace('.wav', '.adp')
    
    cmd = ["./sox/sox", input_path, "-t", "ima", "-r", "8000", "-e", "ima-adpcm", output_path]
    
    try:
        subprocess.run(cmd, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Error converting WAV to ADP: {e}")
        return None

def batch_convert_files(input_dir, extension, conversion_func, output_suffix="_converted", output_extension = None):
    """Batch convert files with given extension using the specified conversion function"""
    output_dir = os.path.join(input_dir, f"{extension[1:]}{output_suffix}")
    os.makedirs(output_dir, exist_ok=True)
    
    converted_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith(extension):
                input_path = os.path.join(root, file)
                rel_path = os.path.relpath(input_path, input_dir)
                output_path = os.path.join(output_dir, rel_path)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                if output_extension is not None:
                    output_path = output_path.replace(extension, output_extension)
                
                if conversion_func(input_path, output_path):
                    converted_files.append(output_path)
    
    return output_dir if converted_files else None

def process_pakc(pakc_file, output_base_dir, key=None, key_file=None, key_num=None):
    """Full processing pipeline for .pakc file"""
    temp_dir = os.path.join(output_base_dir, "temp")
    extracted_dir = os.path.join(output_base_dir, "extracted")
    repacked_dir = os.path.join(output_base_dir, "repacked")
    adp_temp_dir = os.path.join(temp_dir, "adp_originals")
    
    clear_create_dir(temp_dir)
    os.makedirs(extracted_dir, exist_ok=True)
    clear_create_dir(repacked_dir)
    clear_create_dir(adp_temp_dir)
    
    # decrypt .pakc to .pak
    pak_file = os.path.join(temp_dir, os.path.basename(pakc_file).replace(".pakc", ".pak"))
    if not decrypt_pakc(pakc_file, pak_file, key, key_file, key_num):
        return False
    
    # extract the .dat from .pak with offzip
    offzip_output = os.path.join(temp_dir, "offzip_out")
    os.makedirs(offzip_output, exist_ok=True)
    dat_file = extract_with_offzip(pak_file, offzip_output)
    
    if not dat_file:
        return False
    
    # unpack the .dat file
    if not unpack_dat(dat_file, extracted_dir):
        return False

    initial_file_list = []
    for entry in os.listdir(extracted_dir):
        full_path = os.path.join(extracted_dir, entry)
        if os.path.isfile(full_path):
            initial_file_list.append(entry)
    
    # save original ADP files to temp directory before any conversion
    for root, _, files in os.walk(extracted_dir):
        for file in files:
            if file.endswith('.adp'):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, extracted_dir)
                dest_path = os.path.join(adp_temp_dir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(src_path, dest_path)
    
    print(f"\nExtraction complete! Files are in: {extracted_dir}")
    
    # Come down to the boardwalk, we have SPT, we've got BIX, ADP, best on the boardwalk 
    convert_choice = input("Do you want to convert the assets for editing? (SPT/BIX/ADP) (y/n): ").lower()
    
    if convert_choice == 'y':
        spt_choice = input("Convert SPT to PNG? (y/n): ").lower()
        if spt_choice == 'y':
            png_output_dir = convert_spt_to_png(extracted_dir)
            if png_output_dir:
                print(f"PNG files created in: {png_output_dir}")
        
        bix_choice = input("Convert BIX to GLTF? (y/n): ").lower()
        if bix_choice == 'y':
            gltf_output_dir = batch_convert_files(extracted_dir, ".bix", convert_bix_to_gltf, "_converted", ".gltf")
            if gltf_output_dir:
                print(f"GLTF files created in: {gltf_output_dir}")
        
        adp_choice = input("Convert ADP to WAV? (y/n): ").lower()
        if adp_choice == 'y':
            wav_output_dir = batch_convert_files(extracted_dir, ".adp", convert_adp_to_wav, "_converted", ".wav")
            if wav_output_dir:
                print(f"WAV files created in: {wav_output_dir}")
        
        print("\nEdit the converted files, then press Enter when ready to continue...")
        input()
        
        if spt_choice == 'y' and png_output_dir:
            spt_output_dir = convert_png_to_spt(png_output_dir, extracted_dir)
            if not spt_output_dir:
                return False
            print("Converted PNG files back to SPT format")
        
        if bix_choice == 'y' and gltf_output_dir:
            for root, _, files in os.walk(gltf_output_dir):
                for file in files:
                    if file.endswith('.gltf'):
                        gltf_path = os.path.join(root, file)
                        rel_path = os.path.relpath(gltf_path, gltf_output_dir)
                        bix_path = os.path.join(extracted_dir, rel_path.replace('.gltf', '.bix'))
                        os.makedirs(os.path.dirname(bix_path), exist_ok=True)
                        if not convert_gltf_to_bix(gltf_path, bix_path):
                            return False
            print("Converted GLTF files back to BIX format")
        
        if adp_choice == 'y' and wav_output_dir:
            for root, _, files in os.walk(wav_output_dir):
                for file in files:
                    if file.endswith('.wav'):
                        wav_path = os.path.join(root, file)
                        rel_path = os.path.relpath(wav_path, wav_output_dir)
                        adp_path = os.path.join(extracted_dir, rel_path.replace('.wav', '.adp'))
                        os.makedirs(os.path.dirname(adp_path), exist_ok=True)
                        if not convert_wav_to_adp(wav_path, adp_path):
                            return False
            print("Converted WAV files back to ADP format")
    else:
        print("You can now edit the files directly. When ready to repack, press Enter to continue...")
        input()
    
    for root, _, files in os.walk(extracted_dir):
        for file in files:
            if file.endswith('.adp'):
                current_path = os.path.join(root, file)
                rel_path = os.path.relpath(current_path, extracted_dir)
                original_path = os.path.join(adp_temp_dir, rel_path)
                
                if os.path.exists(original_path):
                    original_size = os.path.getsize(original_path)
                    current_size = os.path.getsize(current_path)
                    
                    if current_size > original_size:
                        print(f"Truncating {rel_path} from {current_size} to {original_size} bytes")
                        with open(current_path, 'r+b') as f:
                            data = f.read(original_size)
                            f.seek(0)
                            f.write(data)
                            f.truncate()
    
    edited_file_list = []
    for entry in os.listdir(extracted_dir):
        full_path = os.path.join(extracted_dir, entry)
        if os.path.isfile(full_path):
            edited_file_list.append(entry)
    
    if edited_file_list != initial_file_list:
        print()
        print("   WARNING: Changing the filenames/adding extra files will likely cause the game to crash when loading the .pakc")
        print()

    # repack the directory
    repacked_dat = os.path.join(repacked_dir, "repacked.dat")
    if not repack_dir(extracted_dir, repacked_dat):
        return False
    
    # pack .dat back to .pak
    repacked_pak = os.path.join(temp_dir, "repacked.pak")
    if not pack_with_packzip(repacked_dat, repacked_pak, pak_file):
        return False
    
    # encrypt back to .pakc
    output_pakc = os.path.join(output_base_dir, os.path.basename(pakc_file))
    if not encrypt_pakc(repacked_pak, output_pakc, key, key_file, key_num):
        return False
    
    print(f"\nRepacking complete! Final file is: {output_pakc}")
    return True

def main():
    parser = argparse.ArgumentParser(description='Snakes asset modding toolchain')
    parser.add_argument('input_file', help='Path to the input .pakc file')
    parser.add_argument('output_dir', help='Directory for output files')
    parser.add_argument('-k', '--key', help='Encryption/decryption key (string)')
    parser.add_argument('-kf', '--key-file', help='Read key from file')
    parser.add_argument('-n', '--key-num', type=int, choices=range(1, 6), 
                        help='Use predefined key number (1-5)')
    
    args = parser.parse_args()

    if not check_required_tools():
        return
    
    if not os.path.isfile(args.input_file):
        print(f"Error: The input file {args.input_file} does not exist")
        return
    
    if not args.input_file.lower().endswith('.pakc'):
        print("Error: The input file should have the .pakc extension")
        return
    
    if process_pakc(args.input_file, args.output_dir, args.key, args.key_file, args.key_num):
        print("Processed successfully!")
    else:
        print("it didn't go as planned.")

if __name__ == "__main__":
    main()