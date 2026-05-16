import os
import math
from PIL import Image
import hashlib

class AtlasNode:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.used = False
        self.right = None
        self.down = None

    def insert(self, width, height):
        if self.used:
            node = self.right.insert(width, height)
            if node is None:
                node = self.down.insert(width, height)
            return node
        elif width <= self.w and height <= self.h:
            self.used = True
            self.down = AtlasNode(self.x, self.y + height, self.w, self.h - height)
            self.right = AtlasNode(self.x + width, self.y, self.w - width, height)
            return self
        return None

def next_power_of_two(n):
    return 2 ** math.ceil(math.log2(n))

class AssetPipeline:
    def __init__(self):
        self.items_dir = "items"
        self.objs_dir = "objs"
        self.output_dir = "output"
        self.masks = []
        self.texture_blocks = {} 
        self.block_references = [] 
        self.final_atlas_size = 2048 

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def load_masks(self):
        for i in range(1, 5):
            mask_path = f"m{i}.png"
            if os.path.exists(mask_path):
                img = Image.open(mask_path).convert("L")
                self.masks.append((f"m{i}", img))
            else:
                print(f"Warning: {mask_path} not found.")

    def process_items(self):
        for filename in os.listdir(self.items_dir):
            if not filename.endswith(".png"):
                continue
            item_path = os.path.join(self.items_dir, filename)
            item_img = Image.open(item_path).convert("RGBA")
            item_name = filename.split('.')[0]
            
            # Add full item texture to blocks for front/back references
            block_hash = self.add_texture_block(item_img)

            for mask_name, mask_img in self.masks:
                self.generate_voxel_model(item_name, item_img, mask_name, mask_img, block_hash)

    def generate_voxel_model(self, item_name, img, mask_name, mask, tex_hash):
        width, height = img.size
        pixels = img.load()
        mask_pixels = mask.load()

        vertices = []
        uvs = []
        faces = []
        
        def add_vertex(x, y, z):
            vertices.append((x, y, z))
            return len(vertices)

        def add_uv(u, v):
            uvs.append((u, v))
            return len(uvs)

        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                if a == 0 or mask_pixels[x, y] < 128:
                    continue

                vx = x
                vy = height - y - 1 
                vz = 0.5 

                u0 = x / width
                v0 = (height - y - 1) / height
                u1 = (x + 1) / width
                v1 = (height - y) / height

                v_f_1 = add_vertex(vx, vy, vz)
                v_f_2 = add_vertex(vx + 1, vy, vz)
                v_f_3 = add_vertex(vx + 1, vy + 1, vz)
                v_f_4 = add_vertex(vx, vy + 1, vz)
                uv_f_1, uv_f_2, uv_f_3, uv_f_4 = add_uv(u0, v0), add_uv(u1, v0), add_uv(u1, v1), add_uv(u0, v1)
                
                faces.append([(v_f_1, uv_f_1), (v_f_2, uv_f_2), (v_f_3, uv_f_3), (v_f_4, uv_f_4)])

                v_b_1 = add_vertex(vx + 1, vy, -vz)
                v_b_2 = add_vertex(vx, vy, -vz)
                v_b_3 = add_vertex(vx, vy + 1, -vz)
                v_b_4 = add_vertex(vx + 1, vy + 1, -vz)
                uv_b_1, uv_b_2, uv_b_3, uv_b_4 = add_uv(u1, v0), add_uv(u0, v0), add_uv(u0, v1), add_uv(u1, v1)
                
                faces.append([(v_b_1, uv_b_1), (v_b_2, uv_b_2), (v_b_3, uv_b_3), (v_b_4, uv_b_4)])

                # Check neighbors for side faces
                neighbors = [
                    (x, y - 1, vx, vy + 1, vz, vx + 1, vy + 1, vz, vx + 1, vy + 1, -vz, vx, vy + 1, -vz), # Top
                    (x, y + 1, vx + 1, vy, vz, vx, vy, vz, vx, vy, -vz, vx + 1, vy, -vz), # Bottom
                    (x - 1, y, vx, vy, vz, vx, vy + 1, vz, vx, vy + 1, -vz, vx, vy, -vz), # Left
                    (x + 1, y, vx + 1, vy + 1, vz, vx + 1, vy, vz, vx + 1, vy, -vz, vx + 1, vy + 1, -vz)  # Right
                ]

                for nx, ny, p1x, p1y, p1z, p2x, p2y, p2z, p3x, p3y, p3z, p4x, p4y, p4z in neighbors:
                    draw_side = False
                    if nx < 0 or nx >= width or ny < 0 or ny >= height:
                        draw_side = True
                    elif pixels[nx, ny][3] == 0 or mask_pixels[nx, ny] < 128:
                        draw_side = True
                    
                    if draw_side:
                        sv1 = add_vertex(p1x, p1y, p1z)
                        sv2 = add_vertex(p2x, p2y, p2z)
                        sv3 = add_vertex(p3x, p3y, p3z)
                        sv4 = add_vertex(p4x, p4y, p4z)
                        
                        suv1, suv2, suv3, suv4 = add_uv(u0, v0), add_uv(u1, v0), add_uv(u1, v1), add_uv(u0, v1)
                        faces.append([(sv1, suv1), (sv2, suv2), (sv3, suv3), (sv4, suv4)])

        self.block_references.append({
            'type': 'item',
            'name': f"{item_name}_{mask_name}",
            'vertices': vertices,
            'uvs': uvs,
            'faces': faces,
            'tex_hash': tex_hash
        })

    def process_objs(self):
        for folder, _, files in os.walk(self.objs_dir):
            for file in files:
                if file.endswith('.obj'):
                    self.parse_obj(os.path.join(folder, file))

    def parse_obj(self, filepath):
        vertices = []
        uvs = []
        normals = []
        faces = []
        current_material = None
        materials = self.load_mtl(filepath.replace('.obj', '.mtl'))

        with open(filepath, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if not parts: continue
                if parts[0] == 'v':
                    vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
                elif parts[0] == 'vt':
                    uvs.append((float(parts[1]), float(parts[2])))
                elif parts[0] == 'vn':
                    normals.append((float(parts[1]), float(parts[2]), float(parts[3])))
                elif parts[0] == 'usemtl':
                    current_material = parts[1]
                elif parts[0] == 'f':
                    face_data = []
                    for p in parts[1:]:
                        vals = p.split('/')
                        vi = int(vals[0]) - 1
                        vti = int(vals[1]) - 1 if len(vals) > 1 and vals[1] else -1
                        vni = int(vals[2]) - 1 if len(vals) > 2 and vals[2] else -1
                        face_data.append((vi, vti, vni))
                    
                    if current_material in materials and vti != -1:
                        tex_img = materials[current_material]
                        face_uvs = [uvs[vd[1]] for vd in face_data]
                        
                        min_u = min(uv[0] for uv in face_uvs)
                        max_u = max(uv[0] for uv in face_uvs)
                        min_v = min(uv[1] for uv in face_uvs)
                        max_v = max(uv[1] for uv in face_uvs)
                        
                        tex_w, tex_h = tex_img.size
                        left = int(min_u * tex_w)
                        right = int(max_u * tex_w)
                        top = int((1.0 - max_v) * tex_h)
                        bottom = int((1.0 - min_v) * tex_h)
                        
                        # Fix out of bounds if float imprecision
                        left, right = max(0, left), min(tex_w, right)
                        top, bottom = max(0, top), min(tex_h, bottom)
                        
                        if right > left and bottom > top:
                            cropped = tex_img.crop((left, top, right, bottom))
                            block_hash = self.add_texture_block(cropped)
                            
                            local_uvs = []
                            for u, v in face_uvs:
                                lu = (u * tex_w - left) / (right - left)
                                lv = (v * tex_h - (tex_h - bottom)) / (bottom - top)
                                local_uvs.append((lu, lv))
                            
                            faces.append({
                                'v': [vd[0] for vd in face_data],
                                'vn': [vd[2] for vd in face_data],
                                'local_uvs': local_uvs,
                                'tex_hash': block_hash
                            })

        obj_name = os.path.basename(filepath).split('.')[0]
        self.block_references.append({
            'type': 'obj',
            'name': obj_name,
            'vertices': vertices,
            'normals': normals,
            'faces': faces
        })

    def load_mtl(self, filepath):
        materials = {}
        if not os.path.exists(filepath): return materials
        
        current_mat = None
        base_dir = os.path.dirname(filepath)
        with open(filepath, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if not parts: continue
                if parts[0] == 'newmtl':
                    current_mat = parts[1]
                elif parts[0] == 'map_Kd':
                    tex_path = os.path.join(base_dir, parts[1])
                    if os.path.exists(tex_path):
                        materials[current_mat] = Image.open(tex_path).convert("RGBA")
        return materials

    def add_texture_block(self, img):
        img_bytes = img.tobytes()
        block_hash = hashlib.md5(img_bytes).hexdigest()
        
        if block_hash not in self.texture_blocks:
            self.texture_blocks[block_hash] = {
                'img': img,
                'node': None 
            }
        return block_hash

    def pack_textures(self):
        blocks = list(self.texture_blocks.values())
        blocks.sort(key=lambda b: b['img'].size[1], reverse=True)

        total_area = sum(b['img'].size[0] * b['img'].size[1] for b in blocks)
        side = next_power_of_two(math.ceil(math.sqrt(total_area)))
        
        while True:
            root = AtlasNode(0, 0, side, side)
            success = True
            for block in blocks:
                w, h = block['img'].size
                node = root.insert(w, h)
                if node:
                    block['node'] = node
                else:
                    success = False
                    break
            if success:
                break
            side = next_power_of_two(side + 1)
            
        self.final_atlas_size = side
        
        atlas_img = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        for block in blocks:
            node = block['node']
            atlas_img.paste(block['img'], (node.x, node.y))
            
        atlas_img.save(os.path.join(self.output_dir, "atlas.png"))
        return side

    def export_models(self, atlas_size):
        with open(os.path.join(self.output_dir, "merged.obj"), "w") as f:
            f.write(f"mtllib merged.mtl\n")
            f.write("usemtl atlas_mat\n")
            
            v_offset = 0
            vt_offset = 0
            vn_offset = 0

            for ref in self.block_references:
                f.write(f"o {ref['name']}\n")
                
                for v in ref['vertices']:
                    f.write(f"v {v[0]} {v[1]} {v[2]}\n")
                    
                if ref['type'] == 'obj' and 'normals' in ref:
                    for vn in ref['normals']:
                        f.write(f"vn {vn[0]} {vn[1]} {vn[2]}\n")

                if ref['type'] == 'item':
                    node = self.texture_blocks[ref['tex_hash']]['node']
                    node_x, node_y, node_w, node_h = node.x, node.y, node.w, node.h
                    
                    uvs_out = []
                    for u, v in ref['uvs']:
                        new_u = (node_x + u * node_w) / atlas_size
                        new_v = 1.0 - ((node_y + (1.0 - v) * node_h) / atlas_size)
                        uvs_out.append((new_u, new_v))
                        f.write(f"vt {new_u} {new_v}\n")
                        
                    for face in ref['faces']:
                        f_str = " ".join([f"{v+1+v_offset}/{vt+1+vt_offset}" for v, vt in face])
                        f.write(f"f {f_str}\n")
                        
                    v_offset += len(ref['vertices'])
                    vt_offset += len(uvs_out)
                    
                elif ref['type'] == 'obj':
                    for face in ref['faces']:
                        node = self.texture_blocks[face['tex_hash']]['node']
                        node_x, node_y, node_w, node_h = node.x, node.y, node.w, node.h
                        
                        face_vts = []
                        for u, v in face['local_uvs']:
                            new_u = (node_x + u * node_w) / atlas_size
                            new_v = 1.0 - ((node_y + (1.0 - v) * node_h) / atlas_size)
                            f.write(f"vt {new_u} {new_v}\n")
                            face_vts.append(vt_offset)
                            vt_offset += 1
                            
                        f_str = []
                        for i in range(len(face['v'])):
                            vi = face['v'][i] + 1 + v_offset
                            vti = face_vts[i] + 1
                            vni = face['vn'][i] + 1 + vn_offset if face['vn'][i] != -1 else ""
                            f_str.append(f"{vi}/{vti}/{vni}")
                        f.write(f"f {' '.join(f_str)}\n")
                        
                    v_offset += len(ref['vertices'])
                    if 'normals' in ref:
                        vn_offset += len(ref['normals'])

        with open(os.path.join(self.output_dir, "merged.mtl"), "w") as f:
            f.write("newmtl atlas_mat\n")
            f.write("Ka 1.000 1.000 1.000\n")
            f.write("Kd 1.000 1.000 1.000\n")
            f.write("map_Kd atlas.png\n")

    def run(self):
        print("Loading masks...")
        self.load_masks()
        print("Processing items...")
        self.process_items()
        print("Processing objs...")
        self.process_objs()
        print("Packing textures...")
        atlas_size = self.pack_textures()
        print(f"Exporting combined data (Atlas Size: {atlas_size}x{atlas_size})...")
        self.export_models(atlas_size)
        print("Done.")

if __name__ == "__main__":
    pipeline = AssetPipeline()
    pipeline.run()