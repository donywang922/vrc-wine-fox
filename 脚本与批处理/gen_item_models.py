import os
import shutil
from PIL import Image

# 路径配置
ITEMS_DIR = "items"
OUTPUT_DIR = "output_item_models"
MASKS_PATHS = ["m1.png", "m2.png", "m3.png", "m4.png"]


def load_mask(filepath):
    """加载遮罩文件，返回2D布尔数组，黑色(True)保留"""
    try:
        img = Image.open(filepath).convert("L")
        if img.size != (16, 16):
            img = img.resize((16, 16), Image.NEAREST)
        mask = []
        for y in range(16):
            row = []
            for x in range(16):
                # 黑色部分灰度值接近0，此处阈值设为128
                row.append(img.getpixel((x, y)) < 128)
            mask.append(row)
        return mask
    except Exception as e:
        print(f"无法读取遮罩 {filepath}: {e}")
        return [[True] * 16 for _ in range(16)]


def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    if not os.path.exists(ITEMS_DIR):
        print(f"未找到 {ITEMS_DIR} 文件夹。")
        return

    # 加载四个遮罩
    masks = [load_mask(p) for p in MASKS_PATHS]

    # 遍历items文件夹中的png图片
    for filename in os.listdir(ITEMS_DIR):
        if not filename.lower().endswith(".png"):
            continue

        item_path = os.path.join(ITEMS_DIR, filename)
        item_name = os.path.splitext(filename)[0]
        output_obj = os.path.join(OUTPUT_DIR, f"{item_name}.obj")
        output_mtl = os.path.join(OUTPUT_DIR, f"{item_name}.mtl")
        output_tex = os.path.join(OUTPUT_DIR, filename)

        # 复制贴图到 obj 文件同级目录
        try:
            shutil.copy2(item_path, output_tex)
        except Exception as e:
            print(f"无法复制贴图文件 {filename}: {e}")
            continue

        # 加载物品贴图获取Alpha通道
        img = Image.open(item_path).convert("RGBA")
        if img.size != (16, 16):
            img = img.resize((16, 16), Image.NEAREST)

        alpha_map = []
        for y in range(16):
            row = []
            for x in range(16):
                _, _, _, a = img.getpixel((x, y))
                row.append(a > 0)  # Alpha大于0判定为非透明
            alpha_map.append(row)

        # 生成MTL文件，指定 utf-8 编码
        with open(output_mtl, "w", encoding="utf-8") as mtl_file:
            mtl_file.write(f"newmtl mat_{item_name}\n")
            # 贴图已复制到同级目录，此处直接使用文件名
            mtl_file.write(f"map_Kd {filename}\n")

        # 生成OBJ文件，指定 utf-8 编码
        with open(output_obj, "w", encoding="utf-8") as obj:
            obj.write(f"mtllib {item_name}.mtl\n")

            # 全局索引计数
            v_idx = 1
            vt_idx = 1
            vn_idx = 1

            # 预定义六个面的法线
            normals = [
                (0, 0, 1),  # 1 前
                (0, 0, -1),  # 2 后
                (0, 1, 0),  # 3 上
                (0, -1, 0),  # 4 下
                (1, 0, 0),  # 5 右
                (-1, 0, 0)  # 6 左
            ]
            for nx, ny, nz in normals:
                obj.write(f"vn {nx} {ny} {nz}\n")

            # 面生成辅助函数
            def write_quad(p1, p2, p3, p4, uv_bl, uv_br, uv_tr, uv_tl, n_idx):
                nonlocal v_idx, vt_idx
                # 写入顶点
                obj.write(f"v {p1[0]} {p1[1]} {p1[2]}\n")
                obj.write(f"v {p2[0]} {p2[1]} {p2[2]}\n")
                obj.write(f"v {p3[0]} {p3[1]} {p3[2]}\n")
                obj.write(f"v {p4[0]} {p4[1]} {p4[2]}\n")
                # 写入UV
                obj.write(f"vt {uv_bl[0]} {uv_bl[1]}\n")
                obj.write(f"vt {uv_br[0]} {uv_br[1]}\n")
                obj.write(f"vt {uv_tr[0]} {uv_tr[1]}\n")
                obj.write(f"vt {uv_tl[0]} {uv_tl[1]}\n")
                # 写入面
                obj.write(
                    f"f {v_idx}/{vt_idx}/{n_idx} {v_idx + 1}/{vt_idx + 1}/{n_idx} {v_idx + 2}/{vt_idx + 2}/{n_idx} {v_idx + 3}/{vt_idx + 3}/{n_idx}\n")
                v_idx += 4
                vt_idx += 4

            # 针对四个遮罩拆分网格体
            for mask_idx, mask in enumerate(masks):
                obj.write(f"o mesh_mask_{mask_idx + 1}\n")
                obj.write(f"usemtl mat_{item_name}\n")

                # 融合不透明度与当前遮罩
                valid_voxels = [[False] * 16 for _ in range(16)]
                for y in range(16):
                    for x in range(16):
                        if alpha_map[y][x] and mask[y][x]:
                            valid_voxels[y][x] = True

                # 生成体素
                for y in range(16):
                    for x in range(16):
                        if not valid_voxels[y][x]:
                            continue

                        # 空间坐标映射
                        x0, x1 = x, x + 1
                        y0, y1 = 15 - y, 16 - y
                        z0, z1 = 0.0, 1.0

                        # UV映射
                        u0 = x / 16.0
                        u1 = (x + 1) / 16.0
                        v0 = (15 - y) / 16.0
                        v1 = (16 - y) / 16.0

                        uv_bl, uv_br = (u0, v0), (u1, v0)
                        uv_tr, uv_tl = (u1, v1), (u0, v1)

                        # 前面 (Z=1)
                        write_quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), uv_bl, uv_br, uv_tr, uv_tl,
                                   1)

                        # 后面 (Z=0)
                        write_quad((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), uv_br, uv_bl, uv_tl, uv_tr,
                                   2)

                        # 上面 (Y=y1)
                        if y == 0 or not valid_voxels[y - 1][x]:
                            write_quad((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0), uv_bl, uv_br, uv_tr,
                                       uv_tl, 3)

                        # 下面 (Y=y0)
                        if y == 15 or not valid_voxels[y + 1][x]:
                            write_quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), uv_bl, uv_br, uv_tr,
                                       uv_tl, 4)

                        # 右面 (X=x1)
                        if x == 15 or not valid_voxels[y][x + 1]:
                            write_quad((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), uv_bl, uv_br, uv_tr,
                                       uv_tl, 5)

                        # 左面 (X=x0)
                        if x == 0 or not valid_voxels[y][x - 1]:
                            write_quad((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), uv_bl, uv_br, uv_tr,
                                       uv_tl, 6)

        print(f"已处理并复制贴图: {filename} -> {output_obj}")


if __name__ == "__main__":
    main()