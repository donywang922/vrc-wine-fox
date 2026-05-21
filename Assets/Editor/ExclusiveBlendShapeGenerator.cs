using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.IO;

public class ExclusiveBlendShapeGenerator : EditorWindow
{
    private GameObject targetObject;
    private string relativePath = "";
    private Vector2 scrollPos;
    
    // 用于记录列表状态
    private class ShapeState
    {
        public string name;
        public bool isSelected;
    }
    private List<ShapeState> shapeList = new List<ShapeState>();

    [MenuItem("MyTools/互斥形态键动画生成器")]
    public static void ShowWindow()
    {
        GetWindow<ExclusiveBlendShapeGenerator>("互斥动画生成");
    }

    private void OnGUI()
    {
        GUILayout.Label("1. 目标设置", EditorStyles.boldLabel);
        
        GameObject newTarget = (GameObject)EditorGUILayout.ObjectField("包含 SkinnedMesh 的物体", targetObject, typeof(GameObject), true);
        
        // 当目标改变时，重新读取形态键列表
        if (newTarget != targetObject)
        {
            targetObject = newTarget;
            shapeList.Clear();
            if (targetObject != null)
            {
                relativePath = targetObject.name; // 默认路径名
                SkinnedMeshRenderer smr = targetObject.GetComponent<SkinnedMeshRenderer>();
                if (smr != null && smr.sharedMesh != null)
                {
                    for (int i = 0; i < smr.sharedMesh.blendShapeCount; i++)
                    {
                        shapeList.Add(new ShapeState { name = smr.sharedMesh.GetBlendShapeName(i), isSelected = false });
                    }
                }
            }
        }

        relativePath = EditorGUILayout.TextField("动画相对路径 (Relative Path)", relativePath);
        EditorGUILayout.HelpBox("提示: 如果 Animator 在根目录，此处填目标物体相对于根目录的层级路径，比如 'Body' 或 'Armature/Head/Face'。", MessageType.Info);

        if (shapeList.Count == 0)
        {
            EditorGUILayout.HelpBox("请先放入带有 SkinnedMeshRenderer 的物体。", MessageType.Warning);
            return;
        }

        GUILayout.Space(10);
        GUILayout.Label("2. 选择要加入【互斥组】的形态键", EditorStyles.boldLabel);
        
        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("全选")) shapeList.ForEach(s => s.isSelected = true);
        if (GUILayout.Button("全不选")) shapeList.ForEach(s => s.isSelected = false);
        EditorGUILayout.EndHorizontal();

        // 滚动列表显示所有形态键
        scrollPos = EditorGUILayout.BeginScrollView(scrollPos, "box", GUILayout.Height(300));
        foreach (var shape in shapeList)
        {
            shape.isSelected = EditorGUILayout.ToggleLeft(shape.name, shape.isSelected);
        }
        EditorGUILayout.EndScrollView();

        GUILayout.Space(10);
        
        // 统计选中的数量
        int selectedCount = shapeList.FindAll(s => s.isSelected).Count;
        GUI.enabled = selectedCount > 1; // 至少选中2个才允许生成
        if (GUILayout.Button($"3. 生成互斥动画 (当前选中: {selectedCount}个)", GUILayout.Height(40)))
        {
            GenerateExclusiveAnimations();
        }
        GUI.enabled = true;
    }

    private void GenerateExclusiveAnimations()
    {
        string folderPath = "Assets/ExclusiveAnims_" + targetObject.name;
        if (!AssetDatabase.IsValidFolder(folderPath))
        {
            AssetDatabase.CreateFolder("Assets", "ExclusiveAnims_" + targetObject.name);
        }

        // 获取所有被选中的形态键
        List<string> selectedShapes = new List<string>();
        foreach (var s in shapeList)
        {
            if (s.isSelected) selectedShapes.Add(s.name);
        }

        // 为每一个选中的形态键生成一个专属的“开启”动画
        foreach (string activeShape in selectedShapes)
        {
            AnimationClip clip = new AnimationClip();
            clip.name = activeShape + "_Exclusive";

            // 遍历互斥组内的所有形态键，写入曲线
            foreach (string shapeInGroup in selectedShapes)
            {
                string propertyName = "blendShape." + shapeInGroup;
                EditorCurveBinding binding = EditorCurveBinding.FloatCurve(relativePath, typeof(SkinnedMeshRenderer), propertyName);
                
                AnimationCurve curve = new AnimationCurve();
                
                // 如果是当前的主角，值为 100；否则将其“强行按死”在 0
                float targetValue = (shapeInGroup == activeShape) ? 100f : 0f;
                
                curve.AddKey(0f, targetValue);
                curve.AddKey(1f / 60f, targetValue); // 确保有两帧长度
                
                AnimationUtility.SetEditorCurve(clip, binding, curve);
            }

            // 保存单个动画文件
            AssetDatabase.CreateAsset(clip, $"{folderPath}/{clip.name}.anim");
        }

        // 额外生成一个 "All_Off" (全部归零) 的待机动画，非常有用
        AnimationClip offClip = new AnimationClip();
        offClip.name = "All_Exclusive_Off";
        foreach (string shapeInGroup in selectedShapes)
        {
            string propertyName = "blendShape." + shapeInGroup;
            EditorCurveBinding binding = EditorCurveBinding.FloatCurve(relativePath, typeof(SkinnedMeshRenderer), propertyName);
            AnimationCurve curve = new AnimationCurve();
            curve.AddKey(0f, 0f);
            curve.AddKey(1f / 60f, 0f);
            AnimationUtility.SetEditorCurve(offClip, binding, curve);
        }
        AssetDatabase.CreateAsset(offClip, $"{folderPath}/{offClip.name}.anim");

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        
        Debug.Log($"生成完毕！共生成 {selectedShapes.Count + 1} 个互斥动画片段。");
    }
}