import os
import json
import glob

INPUT_DIR = "wine_fox"
OUTPUT_DIR = "wine_fox_out"


def has_bone_keyframes(anim_data):
    """判断动画是否包含骨骼关键帧（忽略时间线、粒子、声音）"""
    if "bones" not in anim_data or not anim_data["bones"]:
        return False

    # 只要有任意一个骨骼包含 rotation, position 或 scale，即视为有效
    for bone_name, bone_data in anim_data["bones"].items():
        if "rotation" in bone_data or "position" in bone_data or "scale" in bone_data:
            return True

    return False


def get_children(bones_dict, parent_name):
    """获取指定骨骼的所有子骨骼名称"""
    return [k for k, v in bones_dict.items() if v.get("parent") == parent_name]


def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # ==========================================
    # 任务 1：处理并合并所有动画文件
    # ==========================================
    raw_animations = {}
    anim_files = glob.glob(os.path.join(INPUT_DIR, "*.animation.json"))

    for file_path in anim_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if "animations" in data:
                    for name, anim_data in data["animations"].items():
                        raw_animations[name] = anim_data
            except Exception as e:
                print(f"无法解析动画文件 {file_path}: {e}")

    # 清除没有骨骼关键帧的动画
    filtered_animations = {k: v for k, v in raw_animations.items() if has_bone_keyframes(v)}

    # 去重：如果关键帧完全相同，保留名字更短的那个
    unique_anims = {}
    for name, data in filtered_animations.items():
        # 转为字符串作为哈希比对依据
        content_str = json.dumps(data, sort_keys=True)
        if content_str in unique_anims:
            existing_name = unique_anims[content_str]
            if len(name) < len(existing_name):
                unique_anims[content_str] = name
        else:
            unique_anims[content_str] = name

    # 最终决定保留的动画
    final_animations = {name: filtered_animations[name] for name in unique_anims.values()}

    # 统计所有在保留动画中出现过骨骼关键帧的组
    animated_bones = set()
    for anim_data in final_animations.values():
        if "bones" in anim_data:
            for bone_name in anim_data["bones"].keys():
                animated_bones.add(bone_name)

    # ==========================================
    # 任务 2：清理模型文件
    # ==========================================
    main_json_path = os.path.join(INPUT_DIR, "main.json")
    if not os.path.exists(main_json_path):
        print(f"未找到模型文件: {main_json_path}")
        return

    with open(main_json_path, 'r', encoding='utf-8') as f:
        model_data = json.load(f)

    bones_list = model_data.get("minecraft:geometry", [{}])[0].get("bones", [])
    bones_dict = {b["name"]: b for b in bones_list}

    # 迭代应用模型清理规则，直到结构不再发生变化
    changed = True
    while changed:
        changed = False

        for name in list(bones_dict.keys()):
            if name not in bones_dict:
                continue

            bone = bones_dict[name]
            parent = bone.get("parent")
            children = get_children(bones_dict, name)
            cubes = bone.get("cubes", [])

            # a. 如果这个组从未在动画中出现，就地解散
            if name not in animated_bones:
                # 保护机制：没有父级的根节点如果包含方块则不解散，以防方块丢失
                if parent is None and len(cubes) > 0:
                    pass
                else:
                    # 内部方块移动至该组的父级
                    if parent and parent in bones_dict:
                        parent_bone = bones_dict[parent]
                        if cubes:
                            if "cubes" not in parent_bone: parent_bone["cubes"] = []
                            parent_bone["cubes"].extend(cubes)

                    # 子级重定向至父级
                    for child in children:
                        if parent:
                            bones_dict[child]["parent"] = parent
                        else:
                            if "parent" in bones_dict[child]:
                                del bones_dict[child]["parent"]

                    del bones_dict[name]
                    changed = True
                    break

                    # 判断条件：这个组中只有另一个组（即：子级数量为1 且 自身没有方块）
            if len(children) == 1 and len(cubes) == 0:
                child_name = children[0]
                child_bone = bones_dict[child_name]

                is_parent_anim = name in animated_bones
                is_child_anim = child_name in animated_bones

                # b. 只有一个组在动画中出现过，合并并保留有动画的那个组
                if is_parent_anim != is_child_anim:
                    if is_parent_anim:
                        # 保留当前组（父），销毁子级
                        if child_bone.get("cubes"):
                            if "cubes" not in bone: bone["cubes"] = []
                            bone["cubes"].extend(child_bone["cubes"])
                        for grandchild in get_children(bones_dict, child_name):
                            bones_dict[grandchild]["parent"] = name
                        del bones_dict[child_name]
                    else:
                        # 保留子级，销毁当前组（父）
                        if parent:
                            child_bone["parent"] = parent
                        elif "parent" in child_bone:
                            del child_bone["parent"]
                        del bones_dict[name]
                    changed = True
                    break

                # c. 如果这个组中只有另一个组且两个组的偏移(pivot)相同，合并并将动画重定向
                pivot_parent = bone.get("pivot", [0, 0, 0])
                pivot_child = child_bone.get("pivot", [0, 0, 0])

                if pivot_parent == pivot_child:
                    # 默认策略：保留当前组（父），合并子级的内容
                    if child_bone.get("cubes"):
                        if "cubes" not in bone: bone["cubes"] = []
                        bone["cubes"].extend(child_bone["cubes"])
                    for grandchild in get_children(bones_dict, child_name):
                        bones_dict[grandchild]["parent"] = name

                    # 如果被删除的子组在动画中出现，将其关键帧重定向到保留的父组
                    if is_child_anim:
                        for anim in final_animations.values():
                            if "bones" in anim and child_name in anim["bones"]:
                                if name not in anim["bones"]:
                                    anim["bones"][name] = anim["bones"][child_name]
                                else:
                                    # 深度合并子组的关键帧数据到父组中
                                    for channel in ["rotation", "position", "scale"]:
                                        if channel in anim["bones"][child_name]:
                                            if channel not in anim["bones"][name]:
                                                anim["bones"][name][channel] = anim["bones"][child_name][channel]
                                            else:
                                                # 如果双方都有该通道的帧数据(字典形式)，则进行 update 覆盖
                                                if isinstance(anim["bones"][name][channel], dict) and isinstance(
                                                        anim["bones"][child_name][channel], dict):
                                                    anim["bones"][name][channel].update(
                                                        anim["bones"][child_name][channel])
                                                else:
                                                    anim["bones"][name][channel] = anim["bones"][child_name][channel]
                                del anim["bones"][child_name]
                        animated_bones.add(name)
                        animated_bones.discard(child_name)

                    del bones_dict[child_name]
                    changed = True
                    break

    # ==========================================
    # 任务 3：保存输出
    # ==========================================
    model_data["minecraft:geometry"][0]["bones"] = list(bones_dict.values())
    out_model_path = os.path.join(OUTPUT_DIR, "main.json")
    with open(out_model_path, 'w', encoding='utf-8') as f:
        json.dump(model_data, f, ensure_ascii=False, indent=4)

    out_anim_path = os.path.join(OUTPUT_DIR, "merged.animation.json")
    anim_output = {
        "format_version": "1.8.0",
        "animations": final_animations
    }
    with open(out_anim_path, 'w', encoding='utf-8') as f:
        json.dump(anim_output, f, ensure_ascii=False, indent=4)

    print(
        f"处理完成！\n已自动剔除无骨骼关键帧动画，合并后共保留 {len(final_animations)} 个动画。\n相关模型与动画文件已输出至 {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()