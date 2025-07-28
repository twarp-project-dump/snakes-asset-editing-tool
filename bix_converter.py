import struct
import sys
import json
import base64
import os
from collections import defaultdict

def bix_to_gltf(bix_data):
    header = {
        'flags': struct.unpack('<I', bix_data[0:4])[0],
        'num_frames': struct.unpack('<I', bix_data[4:8])[0],
        'num_verts': struct.unpack('<I', bix_data[8:12])[0]
    }
    
    vertex_frames = []
    offset = 12
    for _ in range(header['num_frames']):
        frame_verts = []
        for _ in range(header['num_verts']):
            x, y, z = struct.unpack('<fff', bix_data[offset:offset+12])
            frame_verts.extend([x, y, z])
            offset += 12
        vertex_frames.append(frame_verts)
    
    face_offset = 12 + (header["num_verts"] * 12 * header["num_frames"])
    num_faces = struct.unpack('<I', bix_data[face_offset:face_offset+4])[0]
    
    faces = []
    face_offset += 4
    for _ in range(num_faces):
        face_indices = []
        for _ in range(3):
            idx = struct.unpack('<I', bix_data[face_offset:face_offset+4])[0]
            face_indices.append(idx)
            face_offset += 4
        faces.extend([face_indices[0], face_indices[2], face_indices[1]])
    
    #not gonna like I don't really have any idea as to how this then gets turned into gltf files, I asked an LLM for help
    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "BIX to glTF Converter"
        },
        "scenes": [{
            "nodes": [0]
        }],
        "nodes": [{
            "mesh": 0
        }],
        "meshes": [{
            "primitives": [{
                "attributes": {
                    "POSITION": 0
                },
                "indices": 1
            }]
        }],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126, 
                "count": header["num_verts"],
                "type": "VEC3",
                "max": [
                    max(vertex_frames[0][i] for i in range(0, len(vertex_frames[0]), 3)),
                    max(vertex_frames[0][i+1] for i in range(0, len(vertex_frames[0]), 3)),
                    max(vertex_frames[0][i+2] for i in range(0, len(vertex_frames[0]), 3))
                ],
                "min": [
                    min(vertex_frames[0][i] for i in range(0, len(vertex_frames[0]), 3)),
                    min(vertex_frames[0][i+1] for i in range(0, len(vertex_frames[0]), 3)),
                    min(vertex_frames[0][i+2] for i in range(0, len(vertex_frames[0]), 3))
                ]
            },
            {
                "bufferView": 1,
                "componentType": 5125,
                "count": len(faces),
                "type": "SCALAR"
            }
        ],
        "bufferViews": [
            {
                "buffer": 0,
                "byteOffset": 0,
                "byteLength": len(vertex_frames[0]) * 4,
                "target": 34962
            },
            {
                "buffer": 0,
                "byteOffset": len(vertex_frames[0]) * 4,
                "byteLength": len(faces) * 4,
                "target": 34963
            }
        ],
        "buffers": [{
            "uri": "data:application/octet-stream;base64," + 
                   base64.b64encode(
                       struct.pack(f'<{len(vertex_frames[0])}f', *vertex_frames[0]) +
                       struct.pack(f'<{len(faces)}I', *faces)
                   ).decode('utf-8'),
            "byteLength": len(vertex_frames[0]) * 4 + len(faces) * 4
        }]
    }
    
    if header['num_frames'] > 1:
        target_buffer = bytes()
        target_accessors = []
        target_views = []
        
        for i in range(1, header['num_frames']):
            deltas = [
                vertex_frames[i][j] - vertex_frames[0][j] 
                for j in range(len(vertex_frames[0]))
            ]
            target_buffer += struct.pack(f'<{len(deltas)}f', *deltas)
            
            target_accessors.append({
                "bufferView": len(gltf["bufferViews"]) + i - 1,
                "componentType": 5126,
                "count": header["num_verts"],
                "type": "VEC3"
            })
            
            target_views.append({
                "buffer": 1,
                "byteOffset": (i-1) * len(deltas) * 4,
                "byteLength": len(deltas) * 4,
                "target": 34962
            })
        
        gltf["buffers"].append({
            "uri": "data:application/octet-stream;base64," + 
                   base64.b64encode(target_buffer).decode('utf-8'),
            "byteLength": len(target_buffer)
        })
        
        gltf["bufferViews"].extend(target_views)
        gltf["accessors"].extend(target_accessors)
        
        gltf["meshes"][0]["weights"] = [0.0] * (header['num_frames'] - 1)
        gltf["meshes"][0]["primitives"][0]["targets"] = [
            {"POSITION": i+2} for i in range(header['num_frames'] - 1)
        ]
        
        animation = {
            "name": "vertex_animation",
            "samplers": [],
            "channels": []
        }
        
        #edit speed here, i/n is n frames a second
        times = [i/5 for i in range(header['num_frames'])]
        weights = []
        for i in range(header['num_frames']):
            frame_weights = [0.0] * (header['num_frames'] - 1)
            if i > 0:
                frame_weights[i-1] = 1.0
            weights.extend(frame_weights)
        
        anim_buffer = struct.pack(
            f'<{len(times)}f{len(weights)}f', 
            *times, *weights
        )
        
        gltf["buffers"].append({
            "uri": "data:application/octet-stream;base64," + 
                   base64.b64encode(anim_buffer).decode('utf-8'),
            "byteLength": len(anim_buffer)
        })
        
        time_view = {
            "buffer": 2,
            "byteOffset": 0,
            "byteLength": len(times) * 4,
            "target": 34962
        }
        
        weight_view = {
            "buffer": 2,
            "byteOffset": len(times) * 4,
            "byteLength": len(weights) * 4,
            "target": 34962
        }
        
        gltf["bufferViews"].extend([time_view, weight_view])
        
        time_accessor = {
            "bufferView": len(gltf["bufferViews"]) - 2,
            "componentType": 5126,
            "count": len(times),
            "type": "SCALAR",
            "max": [times[-1]],
            "min": [times[0]]
        }
        
        weight_accessor = {
            "bufferView": len(gltf["bufferViews"]) - 1,
            "componentType": 5126,
            "count": len(weights),
            "type": "SCALAR"
        }
        
        gltf["accessors"].extend([time_accessor, weight_accessor])
        
        for i in range(header['num_frames'] - 1):
            animation["samplers"].append({
                "input": len(gltf["accessors"]) - 2,
                "output": len(gltf["accessors"]) - 1, 
                "interpolation": "LINEAR"
            })
            
            animation["channels"].append({
                "sampler": i,
                "target": {
                    "node": 0,
                    "path": "weights",
                    "extras": {"target_index": i}
                }
            })
        
        gltf["animations"] = [animation]
    
    return json.dumps(gltf, indent=2)

def gltf_to_bix(gltf_data):
    """Convert glTF data back to BIX format, specifically works with Blender exports or bix_to_obj_3 exports"""
    try:
        gltf = json.loads(gltf_data)
        
        # Find the first mesh with vertices and indices
        mesh = None
        for m in gltf.get('meshes', []):
            if m.get('primitives'):
                for prim in m['primitives']:
                    if 'POSITION' in prim.get('attributes', {}):
                        mesh = m
                        break
                if mesh:
                    break
        
        if not mesh:
            raise ValueError("No valid mesh found in GLTF")
        
        prim = mesh['primitives'][0]
        attributes = prim['attributes']
        
        # Get vertex positions
        pos_acc_idx = attributes['POSITION']
        pos_acc = gltf['accessors'][pos_acc_idx]
        pos_view = gltf['bufferViews'][pos_acc['bufferView']]
        buffer = gltf['buffers'][pos_view['buffer']]
        
        # Handle both embedded and external buffer data
        if 'uri' in buffer:
            if buffer['uri'].startswith('data:'):
                buffer_data = base64.b64decode(buffer['uri'].split(',')[1])
            else:
                raise ValueError("External buffer references not supported")
        else:
            raise ValueError("No buffer data found")
        
        vertices = list(struct.unpack(f'<{pos_acc["count"]*3}f',
                                   buffer_data[pos_view["byteOffset"]:pos_view["byteOffset"]+pos_view["byteLength"]]))
        
        # Get indices - handle cases where indices might be in a different buffer
        if 'indices' not in prim:
            # Some Blender exports might not have explicit indices
            # In this case, we'll generate sequential indices
            indices = list(range(len(vertices)//3))
        else:
            idx_acc_idx = prim['indices']
            idx_acc = gltf['accessors'][idx_acc_idx]
            idx_view = gltf['bufferViews'][idx_acc['bufferView']]
            idx_buffer = gltf['buffers'][idx_view['buffer']]
            
            if 'uri' in idx_buffer:
                if idx_buffer['uri'].startswith('data:'):
                    idx_data = base64.b64decode(idx_buffer['uri'].split(',')[1])
                else:
                    raise ValueError("External buffer references not supported")
            else:
                raise ValueError("No indices buffer data found")
            
            component_type = idx_acc['componentType']
            if component_type == 5123:  # UNSIGNED_SHORT
                indices = list(struct.unpack(f'<{idx_acc["count"]}H',
                                          idx_data[idx_view["byteOffset"]:idx_view["byteOffset"]+idx_view["byteLength"]]))
            elif component_type == 5125:  # UNSIGNED_INT
                indices = list(struct.unpack(f'<{idx_acc["count"]}I',
                                          idx_data[idx_view["byteOffset"]:idx_view["byteOffset"]+idx_view["byteLength"]]))
            else:
                raise ValueError(f"Unsupported index component type: {component_type}")
        
        # Reconstruct faces (BIX format)
        faces = []

        for i in range(0, len(indices), 3):
            if i+2 >= len(indices):
                continue  # Skip incomplete triangles
            # Reverse winding order for BIX format
            faces.extend([indices[i], indices[i+2], indices[i+1]])

        # Handle morph targets (Blender calls them shape keys)
        frames = [vertices]
        if 'targets' in prim:
            for target in prim['targets']:
                if 'POSITION' not in target:
                    continue
                    
                target_acc_idx = target['POSITION']
                target_acc = gltf['accessors'][target_acc_idx]
                target_view = gltf['bufferViews'][target_acc['bufferView']]
                target_buffer = gltf['buffers'][target_view['buffer']]
                
                if 'uri' in target_buffer:
                    if target_buffer['uri'].startswith('data:'):
                        target_data = base64.b64decode(target_buffer['uri'].split(',')[1])
                    else:
                        continue  # Skip external buffers
                else:
                    continue  # Skip if no buffer data
                
                deltas = list(struct.unpack(f'<{target_acc["count"]*3}f',
                                         target_data[target_view["byteOffset"]:target_view["byteOffset"]+target_view["byteLength"]]))
                
                # Apply deltas to base vertices
                frame_vertices = [vertices[i] + deltas[i] for i in range(len(vertices))]
                frames.append(frame_vertices)
        
        # Prepare BIX data
        bix_data = bytearray()
        
        # Header: flags (0), num_frames, num_verts
        bix_data.extend(struct.pack('<III', 0, len(frames), len(vertices)//3))
        
        # Vertex data for each frame
        for frame in frames:
            for i in range(0, len(frame), 3):
                bix_data.extend(struct.pack('<fff', frame[i], frame[i+1], frame[i+2]))
        
        # Faces: num_faces followed by face indices
        bix_data.extend(struct.pack('<I', len(faces)//3))
        for i in range(0, len(faces), 3):
            if i+2 >= len(faces):
                break  # Skip incomplete faces
            bix_data.extend(struct.pack('<III', faces[i], faces[i+1], faces[i+2]))
        
        return bytes(bix_data)
        
    except Exception as e:
        print(f"Error converting GLTF to BIX: {str(e)}")
        raise

def convert_bix_to_gltf(input_path, output_path=None):
    if os.path.isdir(input_path):
        process_bix_directory(input_path)
    elif os.path.isfile(input_path) and input_path.lower().endswith('.bix'):
        process_bix_file(input_path, output_path)
    else:
        print(f"Error: {input_path} is not a valid .bix file or directory")
        sys.exit(1)

def convert_gltf_to_bix(input_path, output_path=None):
    if os.path.isdir(input_path):
        process_gltf_directory(input_path)
    elif os.path.isfile(input_path) and input_path.lower().endswith('.gltf'):
        process_gltf_file(input_path, output_path)
    else:
        print(f"Error: {input_path} is not a valid .gltf file or directory")
        sys.exit(1)

def process_bix_file(input_path, output_path=None):
    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + '.gltf'
    
    with open(input_path, 'rb') as f:
        input_data = f.read()
    
    gltf_content = bix_to_gltf(input_data)
    with open(output_path, 'w') as f:
        f.write(gltf_content)
    
    print(f"Converted {input_path} to {output_path}")

def process_gltf_file(input_path, output_path=None):
    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + '.bix'
    
    with open(input_path, 'r') as f:
        input_data = f.read()
    
    bix_content = gltf_to_bix(input_data)
    with open(output_path, 'wb') as f:
        f.write(bix_content)
    
    print(f"Converted {input_path} to {output_path}")

def process_bix_directory(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.bix'):
                input_path = os.path.join(root, file)
                process_bix_file(input_path)

def process_gltf_directory(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.gltf'):
                input_path = os.path.join(root, file)
                process_gltf_file(input_path)

def print_usage():
    print("Usage:")
    print("  Convert BIX to glTF: python bix_converter.py --bix-to-gltf <input_path> [output_path]")
    print("  Convert glTF to BIX: python bix_converter.py --gltf-to-bix <input_path> [output_path]")
    print("\n<input_path> can be either a .bix/.gltf file or a directory containing them")
    print("[output_path] is optional - will use input filename with opposite extension if not provided")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)
    
    direction = sys.argv[1]
    input_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    if direction == "--bix-to-gltf":
        convert_bix_to_gltf(input_path, output_path)
    elif direction == "--gltf-to-bix":
        convert_gltf_to_bix(input_path, output_path)
    else:
        print("Error: First argument must be either --bix-to-gltf or --gltf-to-bix")
        print_usage()
        sys.exit(1)