import os
import math
from PIL import Image

INPUT_DIRS = ["selected_items", "objs"]
OUTPUT_DIR = "output"


def get_power_of_two(val):
    """获取大于等于val的最小2的次幂"""
    p = 1
    while p < val:
        p *= 2
    return p


def load_mtl(filepath):
    """解析MTL文件，返回材质名到贴图路径的映射"""
    materials = {}
    current_mat = None
    base_dir = os.path.dirname(filepath)

    if not os.path.exists(filepath):
        return materials

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if parts[0] == 'newmtl':
                current_mat = parts[1]
            elif parts[0] == 'map_Kd' and current_mat:
                tex_path = " ".join(parts[1:])
                full_path = os.path.normpath(os.path.join(base_dir, tex_path))
                materials[current_mat] = full_path
    return materials


def parse_obj(filepath):
    """解析OBJ文件，提取顶点、UV、法线、面以及对象/编组信息"""
    vertices = []
    uvs = []
    normals = []
    # 增加记录当前面所属的 object (o) 和 group (g)
    faces = []  # (v_indices, vt_indices, vn_indices, material, object_name, group_name)
    mtllibs = []

    current_mat = None
    current_obj = None
    current_group = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()

            if parts[0] == 'mtllib':
                mtllibs.append(" ".join(parts[1:]))
            elif parts[0] == 'usemtl':
                current_mat = parts[1]
            elif parts[0] == 'o':
                current_obj = " ".join(parts[1:])
            elif parts[0] == 'g':
                current_group = " ".join(parts[1:])
            elif parts[0] == 'v':
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif parts[0] == 'vt':
                uvs.append((float(parts[1]), float(parts[2])))
            elif parts[0] == 'vn':
                normals.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif parts[0] == 'f':
                v_idx = []
                vt_idx = []
                vn_idx = []
                for p in parts[1:]:
                    vals = p.split('/')
                    v_idx.append(int(vals[0]))
                    if len(vals) > 1 and vals[1]:
                        vt_idx.append(int(vals[1]))
                    if len(vals) > 2 and vals[2]:
                        vn_idx.append(int(vals[2]))
                # 将对象和编组信息与面绑定
                faces.append((v_idx, vt_idx, vn_idx, current_mat, current_obj, current_group))

    return vertices, uvs, normals, faces, mtllibs


def resolve_index(idx, total):
    return idx - 1 if idx > 0 else total + idx


def pack_images(images_dict):
    """将不重复的像素块装箱到 2^n 的画布中"""
    sorted_keys = sorted(images_dict.keys(), key=lambda k: images_dict[k].size[1], reverse=True)
    total_area = sum(img.size[0] * img.size[1] for img in images_dict.values())

    start_side = get_power_of_two(int(math.sqrt(total_area)))
    w, h = start_side, start_side

    def try_pack(width, height):
        x, y = 0, 0
        row_h = 0
        positions = {}
        for k in sorted_keys:
            img = images_dict[k]
            img_w, img_h = img.size
            if x + img_w > width:
                y += row_h
                x = 0
                row_h = 0
            if y + img_h > height:
                return None
            positions[k] = (x, y)
            x += img_w
            row_h = max(row_h, img_h)
        return positions

    while True:
        positions = try_pack(w, h)
        if positions is not None:
            return w, h, positions
        if w <= h:
            w *= 2
        else:
            h *= 2


def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    texture_cache = {}
    crops_db = {}
    face_mapping = {}

    obj_files = []
    for d in INPUT_DIRS:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d):
            if f.lower().endswith(".obj"):
                obj_files.append(os.path.join(d, f))

    # 阶段1：遍历所有OBJ提取面级别像素特征
    parsed_data = {}
    for filepath in obj_files:
        vertices, uvs, normals, faces, mtllibs = parse_obj(filepath)
        parsed_data[filepath] = (vertices, uvs, normals, faces)

        mat_to_tex = {}
        base_dir = os.path.dirname(filepath)
        for mtl_file in mtllibs:
            mtl_path = os.path.join(base_dir, mtl_file)
            mat_to_tex.update(load_mtl(mtl_path))

        for face_idx, face in enumerate(faces):
            # 解包更新后的元组结构
            _, vt_idx, _, mat, _, _ = face
            if not vt_idx or not mat or mat not in mat_to_tex:
                continue

            tex_path = mat_to_tex[mat]
            if not os.path.exists(tex_path):
                continue

            if tex_path not in texture_cache:
                texture_cache[tex_path] = Image.open(tex_path).convert("RGBA")
            img = texture_cache[tex_path]
            W, H = img.size

            u_vals = []
            v_vals = []
            for idx in vt_idx:
                u, v = uvs[resolve_index(idx, len(uvs))]
                u_vals.append(max(0.0, min(1.0, u)))
                v_vals.append(max(0.0, min(1.0, v)))

            px_min = int(round(min(u_vals) * W))
            px_max = int(round(max(u_vals) * W))
            py_min = int(round((1.0 - max(v_vals)) * H))
            py_max = int(round((1.0 - min(v_vals)) * H))

            if px_min == px_max: px_max += 1
            if py_min == py_max: py_max += 1

            crop = img.crop((px_min, py_min, px_max, py_max))
            hash_key = (crop.size[0], crop.size[1], crop.tobytes())

            if hash_key not in crops_db:
                crops_db[hash_key] = crop

            face_mapping[(filepath, face_idx)] = (hash_key, px_min, py_min, W, H)

    if not crops_db:
        return

    # 阶段2：装箱及合并贴图
    atlas_w, atlas_h, positions = pack_images(crops_db)
    atlas_img = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))
    for k, pos in positions.items():
        atlas_img.paste(crops_db[k], pos)

    atlas_filename = "combined_atlas.png"
    atlas_img.save(os.path.join(OUTPUT_DIR, atlas_filename))

    mtl_filename = "combined.mtl"
    with open(os.path.join(OUTPUT_DIR, mtl_filename), "w", encoding="utf-8") as mtl:
        mtl.write("newmtl mat_combined\n")
        mtl.write(f"map_Kd {atlas_filename}\n")

    # 阶段3：重写OBJ更新UV，并恢复层级结构
    for filepath, data in parsed_data.items():
        vertices, uvs, normals, faces = data
        out_filename = os.path.basename(filepath)
        out_filepath = os.path.join(OUTPUT_DIR, out_filename)

        with open(out_filepath, "w", encoding="utf-8") as out:
            out.write(f"mtllib {mtl_filename}\n")

            for v in vertices:
                out.write(f"v {v[0]} {v[1]} {v[2]}\n")
            for vn in normals:
                out.write(f"vn {vn[0]} {vn[1]} {vn[2]}\n")

            new_vt_count = 1
            out.write("usemtl mat_combined\n")

            last_obj = None
            last_group = None

            for face_idx, face in enumerate(faces):
                v_idx, vt_idx, vn_idx, _, obj_name, group_name = face

                # 检测到对象变化时，写入新的 o 标签
                if obj_name != last_obj:
                    if obj_name is not None:
                        out.write(f"o {obj_name}\n")
                    last_obj = obj_name

                # 检测到编组变化时，写入新的 g 标签
                if group_name != last_group:
                    if group_name is not None:
                        out.write(f"g {group_name}\n")
                    last_group = group_name

                if (filepath, face_idx) in face_mapping:
                    hash_key, px_min, py_min, orig_W, orig_H = face_mapping[(filepath, face_idx)]
                    ax, ay = positions[hash_key]

                    new_vt_indices = []
                    for idx in vt_idx:
                        orig_u, orig_v = uvs[resolve_index(idx, len(uvs))]

                        rel_x = orig_u * orig_W - px_min
                        rel_y = (1.0 - orig_v) * orig_H - py_min

                        new_u = (ax + rel_x) / atlas_w
                        new_v = 1.0 - (ay + rel_y) / atlas_h

                        out.write(f"vt {new_u:.6f} {new_v:.6f}\n")
                        new_vt_indices.append(new_vt_count)
                        new_vt_count += 1

                    face_parts = []
                    for i in range(len(v_idx)):
                        vi = v_idx[i]
                        vti = new_vt_indices[i]
                        vni = vn_idx[i] if vn_idx else ""
                        if vn_idx:
                            face_parts.append(f"{vi}/{vti}/{vni}")
                        else:
                            face_parts.append(f"{vi}/{vti}")
                    out.write("f " + " ".join(face_parts) + "\n")
                else:
                    face_parts = []
                    for i in range(len(v_idx)):
                        vi = v_idx[i]
                        vni = vn_idx[i] if vn_idx else ""
                        if vn_idx:
                            face_parts.append(f"{vi}//{vni}")
                        else:
                            face_parts.append(f"{vi}")
                    out.write("f " + " ".join(face_parts) + "\n")


if __name__ == "__main__":
    main()