#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using VRC.SDKBase.Editor.BuildPipeline;

public class StripAudioForMobile : IVRCSDKPreprocessAvatarCallback
{
    // callbackOrder 决定了脚本被触发的顺序，0 表示最先执行
    public int callbackOrder => 0;

    public bool OnPreprocessAvatar(GameObject avatarGameObject)
    {
        // 检查当前 Unity 编译器所在的目标平台是否为安卓 (Quest) 或 iOS
        if (EditorUserBuildSettings.activeBuildTarget == BuildTarget.Android || 
            EditorUserBuildSettings.activeBuildTarget == BuildTarget.iOS)
        {
            // 查找这个将要被上传的 Avatar 克隆体身上所有的 AudioSource 组件（包括隐藏的）
            AudioSource[] audioSources = avatarGameObject.GetComponentsInChildren<AudioSource>(true);
            
            int count = 0;
            foreach (AudioSource audio in audioSources)
            {
                // 必须使用 DestroyImmediate 而不是 Destroy，因为这是在 Editor 阶段执行的清理
                Object.DestroyImmediate(audio);
                count++;
            }
            
            if (count > 0)
            {
                Debug.Log($"[移动端打包优化] 成功！已自动从 {avatarGameObject.name} 身上移除了 {count} 个不兼容的 AudioSource。");
            }
        }
        
        // 返回 true 告诉 SDK 我们的清理工作做完了，允许它继续后续的打包上传流程
        return true;
    }
}
#endif