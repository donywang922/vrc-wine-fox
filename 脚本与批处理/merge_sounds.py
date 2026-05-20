import os
import subprocess
import re

def get_audio_duration(file_path):
    """使用 ffprobe 获取音频文件时长，如果失败则尝试用 ffmpeg"""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        try:
            cmd = ['ffmpeg', '-i', file_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = result.stderr
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
            if match:
                hours, minutes, seconds = match.groups()
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except Exception:
            pass
    return 0.0

def format_time(seconds):
    """将秒数格式化为 HH:MM:SS.mmm"""
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        seconds += 1
        ms -= 1000
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d}.{ms:03d}"

def main():
    sounds_dir = "Sounds"
    output_audio = "combined.ogg"
    output_txt = "timeline.txt"
    silence_file = "temp_silence.ogg"
    
    if not os.path.exists(sounds_dir):
        print(f"错误: 未找到 '{sounds_dir}' 文件夹。")
        return
        
    ogg_files = sorted([f for f in os.listdir(sounds_dir) if f.lower().endswith('.ogg')])
    
    if not ogg_files:
        print(f"错误: '{sounds_dir}' 文件夹中没有找到 .ogg 文件。")
        return
        
    print(f"找到 {len(ogg_files)} 个 .ogg 文件，正在计算时间线...")
    
    timeline = []
    current_time = 0.0
    
    for i, file_name in enumerate(ogg_files):
        file_path = os.path.join(sounds_dir, file_name)
        duration = get_audio_duration(file_path)
        
        start_time = current_time
        end_time = current_time + duration
        
        timeline.append({
            "name": file_name,
            "start": start_time,
            "end": end_time
        })
        
        current_time = end_time + 1.0

    with open(output_txt, "w", encoding="utf-8") as f:
        for item in timeline:
            f.write(f"文件: {item['name']}\n")
            f.write(f"开始时间: {item['start']:.3f} 秒 ({format_time(item['start'])})\n")
            f.write(f"结束时间: {item['end']:.3f} 秒 ({format_time(item['end'])})\n")
            f.write("-" * 40 + "\n")
            
    print(f"已生成时间线记录: {output_txt}")

    print("正在生成1秒静音过渡段...")
    try:
        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
            '-t', '1', '-c:a', 'libvorbis', silence_file
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print("生成静音文件失败，请确保系统已安装 ffmpeg。", e.stderr.decode())
        return

    cmd = ['ffmpeg', '-y']
    input_indices = []
    current_idx = 0
    
    for i, file_name in enumerate(ogg_files):
        file_path = os.path.join(sounds_dir, file_name)
        cmd.extend(['-i', file_path])
        input_indices.append(current_idx)
        current_idx += 1
        
        if i < len(ogg_files) - 1:
            cmd.extend(['-i', silence_file])
            input_indices.append(current_idx)
            current_idx += 1

    filter_parts = []
    concat_inputs = ""
    for idx in input_indices:
        filter_parts.append(f"[{idx}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{idx}]")
        concat_inputs += f"[a{idx}]"
        
    filter_complex_str = "; ".join(filter_parts) + f"; {concat_inputs}concat=n={len(input_indices)}:v=0:a=1[outa]"
    cmd.extend(['-filter_complex', filter_complex_str, '-map', '[outa]', '-c:a', 'libvorbis', output_audio])
    
    print("正在合并音频文件...")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"音频合并成功，输出文件: {output_audio}")
    except subprocess.CalledProcessError as e:
        print("合并音频失败:", e.stderr.decode())
    finally:
        if os.path.exists(silence_file):
            os.remove(silence_file)

if __name__ == "__main__":
    main()
