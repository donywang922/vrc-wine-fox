import os
import json
import math

INPUT_DIR = "wine_fox_out"
MODEL_FILE = os.path.join(INPUT_DIR, "main.json")
ANIM_FILE = os.path.join(INPUT_DIR, "merged.animation.json")
OUTPUT_FILE = os.path.join(INPUT_DIR, "optimized.animation.json")

def get_pivots(model_path):
    """从模型文件中动态提取所有骨骼的锚点(Pivot)"""
    pivots = {}
    if not os.path.exists(model_path):
        print(f"警告: 未找到模型文件 {model_path}，将使用默认锚点 [0, 0, 0]")
        return pivots
        
    with open(model_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            bones = data.get("minecraft:geometry", [{}])[0].get("bones", [])
            for bone in bones:
                pivots[bone["name"]] = bone.get("pivot", [0, 0, 0])
        except Exception as e:
            print(f"解析模型文件出错: {e}")
            
    return pivots

def to_list3(v, default_val):
    """将单一值(数字/字符串)或短数组标准化为3元素数组"""
    if isinstance(v, list):
        res = list(v)
        while len(res) < 3:
            res.append(default_val)
        return res[:3]
    # 如果是单值(如单个molang字符串或全局缩放数字)，则自动应用到XYZ三轴
    return [v, v, v]

def add_values(v1, v2):
    """叠加位置或旋转，支持数字与Molang字符串混合"""
    l1 = to_list3(v1, 0)
    l2 = to_list3(v2, 0)
    res = []
    for i in range(3):
        val1, val2 = l1[i], l2[i]
        if isinstance(val1, str) or isinstance(val2, str):
            s1 = str(val1)
            s2 = str(val2)
            if s1 in ("0", "0.0"): res.append(val2)
            elif s2 in ("0", "0.0"): res.append(val1)
            else: res.append(f"({s1}) + ({s2})")
        else:
            res.append(round(float(val1) + float(val2), 5))
    return res

def multiply_values(v1, v2):
    """叠加缩放值(Scale)"""
    l1 = to_list3(v1, 1)
    l2 = to_list3(v2, 1)
    res = []
    for i in range(3):
        val1, val2 = l1[i], l2[i]
        if isinstance(val1, str) or isinstance(val2, str):
            s1 = str(val1)
            s2 = str(val2)
            if s1 in ("1", "1.0"): res.append(val2)
            elif s2 in ("1", "1.0"): res.append(val1)
            else: res.append(f"({s1}) * ({s2})")
        else:
            res.append(round(float(val1) * float(val2), 5))
    return res

def normalize_channel(data):
    """统一数据结构，防范字符串/数字/列表类型直接调用字典方法导致报错"""
    if data is None:
        return {}
    if isinstance(data, dict):
        return data.copy()
    # 若为单值或列表，统一转换为带时间轴的标准格式
    return {"0.0": data}

def extract_val(v):
    """提取复杂字典或简写字典的基础值"""
    if isinstance(v, dict) and "post" in v:
        return v["post"]
    return v

def merge_channel(base, overlay, channel_type="add"):
    """合并两个动画通道的数据并保留缓动属性"""
    base_dict = normalize_channel(base)
    overlay_dict = normalize_channel(overlay)
    
    all_keys = set(base_dict.keys()) | set(overlay_dict.keys())
    result = {}
    
    default_val = [1, 1, 1] if channel_type == "multiply" else [0, 0, 0]
    
    for k in sorted(all_keys, key=float):
        v_base = base_dict.get(k, default_val)
        v_over = overlay_dict.get(k, default_val)
        
        val_b = extract_val(v_base)
        val_o = extract_val(v_over)
        
        if channel_type == "multiply":
            merged_val = multiply_values(val_b, val_o)
        else:
            merged_val = add_values(val_b, val_o)
            
        if isinstance(v_base, dict) and "post" in v_base:
            new_v = v_base.copy()
            new_v["post"] = merged_val
            result[k] = new_v
        elif isinstance(v_over, dict) and "post" in v_over:
            new_v = v_over.copy()
            new_v["post"] = merged_val
            result[k] = new_v
        else:
            result[k] = merged_val
            
    return result

def calc_pivot_offset(rot_list, p_parent, p_child):
    """计算由于父级锚点与自身锚点不同导致的实际空间位移量"""
    if any(isinstance(x, str) for x in rot_list):
        # 若包含Molang表达式无法静态计算三角函数，跳过该帧空间偏移补偿
        return [0, 0, 0]
        
    rx, ry, rz = [math.radians(float(a)) for a in rot_list]
    
    dx = p_child[0] - p_parent[0]
    dy = p_child[1] - p_parent[1]
    dz = p_child[2] - p_parent[2]
    
    cx, sx = math.cos(rx), math.sin(rx)
    y1 = dy * cx - dz * sx
    z1 = dy * sx + dz * cx
    x1 = dx
    
    cy, sy = math.cos(ry), math.sin(ry)
    x2 = x1 * cy + z1 * sy
    z2 = -x1 * sy + z1 * cy
    y2 = y1
    
    cz, sz = math.cos(rz), math.sin(rz)
    x3 = x2 * cz - y2 * sz
    y3 = x2 * sz + y2 * cz
    z3 = z2
    
    return [round(x3 - dx, 5), round(y3 - dy, 5), round(z3 - dz, 5)]

def apply_rotation_offset_to_pos(base_pos, overlay_rot, p_parent, p_child):
    """将父级的旋转引发的位移叠加到子级的 Position 轴中"""
    base_dict = normalize_channel(base_pos)
    over_dict = normalize_channel(overlay_rot)
    
    all_keys = set(base_dict.keys()) | set(over_dict.keys())
    result = {}
    
    for k in sorted(all_keys, key=float):
        v_pos = base_dict.get(k, [0, 0, 0])
        v_rot = over_dict.get(k, [0, 0, 0])
        
        val_pos = extract_val(v_pos)
        val_rot = extract_val(v_rot)
        
        # 标准化为三轴数组以进行空间运算
        l_rot = to_list3(val_rot, 0)
        
        offset = calc_pivot_offset(l_rot, p_parent, p_child)
        merged_pos = add_values(val_pos, offset)
        
        if isinstance(v_pos, dict) and "post" in v_pos:
            new_v = v_pos.copy()
            new_v["post"] = merged_pos
            result[k] = new_v
        else:
            result[k] = merged_pos
            
    return result

def main():
    if not os.path.exists(ANIM_FILE):
        print(f"未找到动画文件: {ANIM_FILE}")
        return

    pivots = get_pivots(MODEL_FILE)
    mroot_pivot = pivots.get("MRoot", [0, 12, 0])
    root_pivot = pivots.get("Root", [0, 0, 0])

    with open(ANIM_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if "animations" not in data:
        return

    for anim_name, anim_data in data["animations"].items():
        if "bones" not in anim_data:
            continue
            
        bones = anim_data["bones"]
        
        gui_root = bones.pop("GuiRoot", None)
        m_root = bones.pop("MRoot", None)
        
        if not gui_root and not m_root:
            continue
            
        if "Root" not in bones:
            bones["Root"] = {}
        root = bones["Root"]

        if gui_root:
            if "position" in gui_root:
                root["position"] = merge_channel(root.get("position"), gui_root["position"], "add")
            if "rotation" in gui_root:
                root["rotation"] = merge_channel(root.get("rotation"), gui_root["rotation"], "add")
            if "scale" in gui_root:
                root["scale"] = merge_channel(root.get("scale"), gui_root["scale"], "multiply")

        if m_root:
            if "rotation" in m_root:
                root["position"] = apply_rotation_offset_to_pos(
                    root.get("position"), 
                    m_root["rotation"], 
                    mroot_pivot, 
                    root_pivot
                )
                root["rotation"] = merge_channel(root.get("rotation"), m_root["rotation"], "add")
            
            if "position" in m_root:
                root["position"] = merge_channel(root.get("position"), m_root["position"], "add")
                
            if "scale" in m_root:
                root["scale"] = merge_channel(root.get("scale"), m_root["scale"], "multiply")

        if not root:
            del bones["Root"]

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    print(f"优化完成！结果已输出至: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()