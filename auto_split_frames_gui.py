import os
import subprocess
import glob
import tkinter as tk
from tkinter import filedialog, messagebox

FPS = 1  # 每秒导出几帧，可以改成 5 或 30
OUTPUT_DIR = "output"

def run_command(cmd):
    print("运行命令:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def process_video(video_file):
    if not video_file:
        messagebox.showwarning("提示", "请选择一个视频文件！")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Step 1: PySceneDetect 分割视频
    messagebox.showinfo("处理中", f"正在分割 {os.path.basename(video_file)}")
    run_command([
        "scenedetect",
        "-i", video_file,
        "detect-content",
        "split-video",
        "-o", OUTPUT_DIR
    ])

    # Step 2: 找到所有片段
    clips = glob.glob(os.path.join(OUTPUT_DIR, "*.mp4")) + \
            glob.glob(os.path.join(OUTPUT_DIR, "*.webm")) + \
            glob.glob(os.path.join(OUTPUT_DIR, "*.mov")) + \
            glob.glob(os.path.join(OUTPUT_DIR, "*.avi")) + \
            glob.glob(os.path.join(OUTPUT_DIR, "*.mkv"))

    if not clips:
        messagebox.showwarning("提示", "没有检测到片段，请检查视频或参数。")
        return

    # Step 3: 每个片段导出帧
    for clip in clips:
        clip_name = os.path.splitext(os.path.basename(clip))[0]
        frame_dir = os.path.join(OUTPUT_DIR, f"{clip_name}_frames")
        os.makedirs(frame_dir, exist_ok=True)

        run_command([
            "ffmpeg", "-i", clip,
            "-vf", f"fps={FPS}",
            os.path.join(frame_dir, f"{clip_name}_%04d.png")
        ])

    messagebox.showinfo("完成", f"处理完成！结果保存在 {OUTPUT_DIR}/ 文件夹。")

def choose_file():
    filetypes = [("视频文件", "*.mp4 *.mov *.avi *.mkv *.webm")]
    filename = filedialog.askopenfilename(title="选择视频文件", filetypes=filetypes)
    if filename:
        process_video(filename)

def main():
    root = tk.Tk()
    root.title("视频智能分割 + 导出帧")
    root.geometry("400x200")

    label = tk.Label(root, text="选择一个视频文件进行智能分割并导出帧", pady=20)
    label.pack()

    button = tk.Button(root, text="选择视频文件", command=choose_file, width=20, height=2)
    button.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()
