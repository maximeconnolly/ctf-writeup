#!/usr/bin/env python3
"""
Advanced PNG Content Analyzer and Extractor

This tool can detect:
1. Content that extends beyond declared image dimensions
2. Hidden data in the decompressed image stream
3. Actual image dimensions vs declared dimensions
4. Extra data after filtering that suggests larger image
"""

import sys
import struct
import zlib
from PIL import Image
import numpy as np


def read_png_chunks(filepath):
    """Read all PNG chunks with their data"""
    chunks = []
    try:
        with open(filepath, 'rb') as f:
            # Check PNG signature
            signature = f.read(8)
            expected = b'\x89PNG\r\n\x1a\n'
            
            if signature != expected:
                print(f"Warning: Invalid PNG signature!")
                return None
            
            while True:
                # Read chunk length
                length_data = f.read(4)
                if len(length_data) < 4:
                    break
                    
                length = struct.unpack('>I', length_data)[0]
                
                # Read chunk type
                chunk_type = f.read(4)
                if len(chunk_type) < 4:
                    break
                
                # Read chunk data
                chunk_data = f.read(length)
                
                # Read CRC
                crc = f.read(4)
                crc_value = struct.unpack('>I', crc)[0]
                
                # Calculate expected CRC
                expected_crc = zlib.crc32(chunk_type + chunk_data) & 0xffffffff
                
                chunks.append({
                    'type': chunk_type,
                    'length': length,
                    'data': chunk_data,
                    'crc': crc_value,
                    'crc_valid': crc_value == expected_crc
                })
                
                # IEND marks end of PNG
                if chunk_type == b'IEND':
                    break
                    
    except Exception as e:
        print(f"Error reading chunks: {e}")
        return None
    
    return chunks


def analyze_ihdr(ihdr_data):
    """Analyze IHDR chunk"""
    if len(ihdr_data) < 13:
        return None
    
    width = struct.unpack('>I', ihdr_data[0:4])[0]
    height = struct.unpack('>I', ihdr_data[4:8])[0]
    bit_depth = ihdr_data[8]
    color_type = ihdr_data[9]
    compression = ihdr_data[10]
    filter_method = ihdr_data[11]
    interlace = ihdr_data[12]
    
    color_type_names = {
        0: 'Grayscale',
        2: 'RGB',
        3: 'Indexed',
        4: 'Grayscale + Alpha',
        6: 'RGBA'
    }
    
    # Calculate bytes per pixel
    if color_type == 0:  # Grayscale
        channels = 1
    elif color_type == 2:  # RGB
        channels = 3
    elif color_type == 3:  # Indexed
        channels = 1
    elif color_type == 4:  # Grayscale + Alpha
        channels = 2
    elif color_type == 6:  # RGBA
        channels = 4
    else:
        channels = 0
    
    bytes_per_pixel = (bit_depth * channels) // 8
    if (bit_depth * channels) % 8 != 0:
        bytes_per_pixel += 1
    
    return {
        'width': width,
        'height': height,
        'bit_depth': bit_depth,
        'color_type': color_type,
        'color_type_name': color_type_names.get(color_type, 'Unknown'),
        'compression': compression,
        'filter_method': filter_method,
        'interlace': interlace,
        'channels': channels,
        'bytes_per_pixel': bytes_per_pixel
    }


def unfilter_scanline(scanline, prev_scanline, filter_type, bytes_per_pixel):
    """Apply PNG unfiltering to a scanline"""
    result = bytearray(scanline)
    
    if filter_type == 0:  # None
        return result
    elif filter_type == 1:  # Sub
        for i in range(bytes_per_pixel, len(result)):
            result[i] = (result[i] + result[i - bytes_per_pixel]) & 0xFF
    elif filter_type == 2:  # Up
        for i in range(len(result)):
            result[i] = (result[i] + prev_scanline[i]) & 0xFF
    elif filter_type == 3:  # Average
        for i in range(len(result)):
            left = result[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
            up = prev_scanline[i]
            result[i] = (result[i] + ((left + up) // 2)) & 0xFF
    elif filter_type == 4:  # Paeth
        for i in range(len(result)):
            left = result[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
            up = prev_scanline[i]
            up_left = prev_scanline[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
            
            p = left + up - up_left
            pa = abs(p - left)
            pb = abs(p - up)
            pc = abs(p - up_left)
            
            if pa <= pb and pa <= pc:
                pr = left
            elif pb <= pc:
                pr = up
            else:
                pr = up_left
            
            result[i] = (result[i] + pr) & 0xFF
    
    return bytes(result)


def analyze_image_data(chunks, ihdr_info):
    """Analyze the actual decompressed image data to find real dimensions"""
    
    print("\nAnalyzing decompressed image data...")
    
    # Get all IDAT chunks
    idat_chunks = [c for c in chunks if c['type'] == b'IDAT']
    combined_idat = b''.join(c['data'] for c in idat_chunks)
    
    # Decompress
    try:
        decompressed = zlib.decompress(combined_idat)
    except Exception as e:
        print(f"Error decompressing: {e}")
        return None
    
    print(f"Decompressed data size: {len(decompressed)} bytes")
    
    # Calculate expected size based on declared dimensions
    declared_width = ihdr_info['width']
    declared_height = ihdr_info['height']
    bytes_per_pixel = ihdr_info['bytes_per_pixel']
    
    # Each scanline has: 1 byte filter type + (width * bytes_per_pixel) data
    expected_scanline_size = 1 + (declared_width * bytes_per_pixel)
    expected_total_size = declared_height * expected_scanline_size
    
    print(f"\nDeclared dimensions: {declared_width} x {declared_height}")
    print(f"Bytes per pixel: {bytes_per_pixel}")
    print(f"Expected scanline size: {expected_scanline_size} bytes")
    print(f"Expected total size: {expected_total_size} bytes")
    print(f"Actual decompressed size: {len(decompressed)} bytes")
    print(f"Difference: {len(decompressed) - expected_total_size} bytes")
    
    # Try to determine actual dimensions
    if len(decompressed) > expected_total_size:
        print(f"\n🔍 FOUND EXTRA DATA! {len(decompressed) - expected_total_size} extra bytes")
        
        # Try to calculate what the real height might be
        actual_scanlines = len(decompressed) // expected_scanline_size
        remaining = len(decompressed) % expected_scanline_size
        
        print(f"\nCalculating actual dimensions:")
        print(f"  Actual scanlines: {actual_scanlines}")
        print(f"  Remaining bytes: {remaining}")
        
        if remaining == 0:
            actual_height = actual_scanlines
            print(f"  → Actual height appears to be: {actual_height}")
            return {
                'actual_width': declared_width,
                'actual_height': actual_height,
                'decompressed_data': decompressed,
                'scanline_size': expected_scanline_size,
                'bytes_per_pixel': bytes_per_pixel
            }
        else:
            # Maybe the width is different?
            print(f"\n  Trying to find actual width...")
            for width_guess in range(declared_width - 100, declared_width + 500):
                if width_guess <= 0:
                    continue
                scanline_guess = 1 + (width_guess * bytes_per_pixel)
                if len(decompressed) % scanline_guess == 0:
                    height_guess = len(decompressed) // scanline_guess
                    print(f"  Possible dimensions: {width_guess} x {height_guess}")
                    
                    # Use the first match that's reasonable
                    if height_guess > declared_height:
                        return {
                            'actual_width': width_guess,
                            'actual_height': height_guess,
                            'decompressed_data': decompressed,
                            'scanline_size': scanline_guess,
                            'bytes_per_pixel': bytes_per_pixel
                        }
    
    return None


def reconstruct_full_image(analysis, ihdr_info, output_path):
    """Reconstruct the full image from raw data"""
    
    print(f"\nReconstructing full image...")
    print(f"Target dimensions: {analysis['actual_width']} x {analysis['actual_height']}")
    
    width = analysis['actual_width']
    height = analysis['actual_height']
    scanline_size = analysis['scanline_size']
    bytes_per_pixel = analysis['bytes_per_pixel']
    channels = ihdr_info['channels']
    
    # Unfilter the image data
    decompressed = analysis['decompressed_data']
    raw_data = bytearray()
    
    prev_scanline = bytearray(width * bytes_per_pixel)
    
    for y in range(height):
        offset = y * scanline_size
        filter_type = decompressed[offset]
        scanline = decompressed[offset + 1:offset + scanline_size]
        
        unfiltered = unfilter_scanline(scanline, prev_scanline, filter_type, bytes_per_pixel)
        raw_data.extend(unfiltered)
        prev_scanline = bytearray(unfiltered)
    
    # Convert to numpy array based on color type
    if ihdr_info['color_type'] == 6:  # RGBA
        img_array = np.frombuffer(raw_data, dtype=np.uint8).reshape((height, width, 4))
        mode = 'RGBA'
    elif ihdr_info['color_type'] == 2:  # RGB
        img_array = np.frombuffer(raw_data, dtype=np.uint8).reshape((height, width, 3))
        mode = 'RGB'
    elif ihdr_info['color_type'] == 0:  # Grayscale
        img_array = np.frombuffer(raw_data, dtype=np.uint8).reshape((height, width))
        mode = 'L'
    else:
        print(f"Unsupported color type: {ihdr_info['color_type']}")
        return False
    
    # Create PIL image
    img = Image.fromarray(img_array, mode=mode)
    
    # Save
    img.save(output_path, 'PNG')
    print(f"✓ Full image saved to: {output_path}")
    
    return True


def main():
    if len(sys.argv) < 2:
        print("Advanced PNG Content Analyzer")
        print("=" * 60)
        print("Usage: python png_advanced_fix.py <input.png> [output.png]")
        print("\nThis tool analyzes PNG files to detect:")
        print("  • Hidden content beyond declared dimensions")
        print("  • Actual image size vs declared size")
        print("  • Corrupted chunks and structure issues")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.rsplit('.', 1)[0] + '_full.png'
    
    print(f"Analyzing: {input_path}")
    print("=" * 60)
    
    # Read chunks
    chunks = read_png_chunks(input_path)
    if not chunks:
        print("✗ Failed to read PNG chunks")
        sys.exit(1)
    
    print(f"\nFound {len(chunks)} chunks:")
    for chunk in chunks:
        chunk_type = chunk['type'].decode('ascii', errors='replace')
        crc_status = "✓" if chunk['crc_valid'] else "✗ INVALID"
        print(f"  {chunk_type:8s} - {chunk['length']:6d} bytes - CRC: {crc_status}")
    
    # Get IHDR
    ihdr_chunk = next((c for c in chunks if c['type'] == b'IHDR'), None)
    if not ihdr_chunk:
        print("✗ No IHDR chunk found")
        sys.exit(1)
    
    ihdr_info = analyze_ihdr(ihdr_chunk['data'])
    print(f"\nDeclared Image Information:")
    print(f"  Dimensions: {ihdr_info['width']} x {ihdr_info['height']}")
    print(f"  Color Type: {ihdr_info['color_type_name']}")
    print(f"  Bit Depth: {ihdr_info['bit_depth']}")
    print(f"  Channels: {ihdr_info['channels']}")
    
    # Analyze actual data
    analysis = analyze_image_data(chunks, ihdr_info)
    
    if analysis:
        print(f"\n{'='*60}")
        print("🎉 HIDDEN CONTENT DETECTED!")
        print("=" * 60)
        print(f"Declared size: {ihdr_info['width']} x {ihdr_info['height']}")
        print(f"Actual size:   {analysis['actual_width']} x {analysis['actual_height']}")
        
        # Reconstruct the full image
        success = reconstruct_full_image(analysis, ihdr_info, output_path)
        
        if success:
            print(f"\n{'='*60}")
            print("✓ SUCCESS!")
            print(f"Full image extracted to: {output_path}")
            print("=" * 60)
        else:
            print("\n✗ Failed to reconstruct full image")
            sys.exit(1)
    else:
        print("\n✓ No hidden content detected")
        print("Image dimensions match the decompressed data")
    
    sys.exit(0)


if __name__ == "__main__":
    main()