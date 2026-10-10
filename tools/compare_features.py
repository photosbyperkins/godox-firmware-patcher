import sys
import re
from collections import Counter

def extract_strings(data, min_length=4):
    # Find sequence of printable ASCII characters
    # ASCII range 32 (space) to 126 (~)
    pattern = rb'[\x20-\x7E]{' + str(min_length).encode() + rb',}'
    strings = re.findall(pattern, data)
    return [s.decode('ascii') for s in strings]

def compare_firmwares(file1, file2):
    with open(file1, 'rb') as f1:
        data1 = f1.read()
    with open(file2, 'rb') as f2:
        data2 = f2.read()
        
    print(f"File 1 ({file1}): {len(data1)} bytes")
    print(f"File 2 ({file2}): {len(data2)} bytes")
    
    # 1. Block comparison (sliding window or chunks)
    # Let's just find how many exact 256-byte blocks from file1 exist in file2
    block_size = 256
    matched_blocks = 0
    total_blocks = len(data1) // block_size
    
    for i in range(total_blocks):
        block = data1[i*block_size:(i+1)*block_size]
        if block in data2:
            matched_blocks += 1
            
    print(f"\n--- Binary Similarity ---")
    print(f"Identical 256-byte blocks: {matched_blocks} out of {total_blocks} ({(matched_blocks/total_blocks)*100:.2f}%)")
    
    # 2. String analysis
    strings1 = set(extract_strings(data1, 5))
    strings2 = set(extract_strings(data2, 5))
    
    print(f"\n--- String Analysis ---")
    print(f"Strings in File 1: {len(strings1)}")
    print(f"Strings in File 2: {len(strings2)}")
    
    common = strings1.intersection(strings2)
    print(f"Common strings: {len(common)}")
    
    unique_to_1 = sorted(list(strings1 - strings2))
    unique_to_2 = sorted(list(strings2 - strings1))
    
    print(f"\n--- Strings unique to File 1 ({file1}) ---")
    # Print the most interesting ones (e.g. ones with letters, skipping mostly symbolic)
    for s in unique_to_1:
        if any(c.isalpha() for c in s) and len(s) > 5:
            print("  " + s)
            
    print(f"\n--- Strings unique to File 2 ({file2}) ---")
    for s in unique_to_2:
        if any(c.isalpha() for c in s) and len(s) > 5:
            print("  " + s)

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        compare_firmwares(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python tools/compare_features.py <firmware1.bin> <firmware2.bin>")
