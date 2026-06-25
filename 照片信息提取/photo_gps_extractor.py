import os
import sys
import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import threading


def convert_to_degrees(value):
    """将度分秒转换为度"""
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)
    except (TypeError, ValueError, IndexError):
        return None


def get_exif_data(image):
    """提取图片EXIF数据"""
    exif_data = {}
    try:
        info = image._getexif()
        if info:
            for tag, value in info.items():
                decoded = TAGS.get(tag, tag)
                exif_data[decoded] = value
    except Exception:
        pass
    return exif_data


def get_gps_info(exif_data):
    """提取GPS信息"""
    gps_info = {}
    if 'GPSInfo' in exif_data:
        for tag, value in exif_data['GPSInfo'].items():
            decoded = GPSTAGS.get(tag, tag)
            gps_info[decoded] = value
    return gps_info


def extract_coordinates(gps_info):
    """从GPS信息中提取经纬度坐标"""
    latitude = None
    longitude = None
    
    if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
        lat_value = gps_info['GPSLatitude']
        lat_ref = gps_info['GPSLatitudeRef']
        latitude = convert_to_degrees(lat_value)
        if latitude is not None and lat_ref == 'S':
            latitude = -latitude
    
    if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
        lon_value = gps_info['GPSLongitude']
        lon_ref = gps_info['GPSLongitudeRef']
        longitude = convert_to_degrees(lon_value)
        if longitude is not None and lon_ref == 'W':
            longitude = -longitude
    
    return latitude, longitude


def extract_azimuth(gps_info):
    """提取拍摄方位角（GPSImgDirection）

    返回值为度数，0°=正北，顺时针增加。
    如果照片不含方位角信息则返回 None。
    """
    if 'GPSImgDirection' not in gps_info:
        return None

    direction = gps_info['GPSImgDirection']

    # IFDRational 类型需要做除法
    if isinstance(direction, tuple):
        if direction[1] == 0:
            return None
        return round(float(direction[0]) / float(direction[1]), 2)

    try:
        return round(float(direction), 2)
    except (TypeError, ValueError):
        return None


def get_image_files(folder, target_folder_name):
    """递归获取指定名称文件夹内的图片文件"""
    image_files = []
    
    for root, dirs, files in os.walk(folder):
        if os.path.basename(root) == target_folder_name:
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.heic')):
                    image_files.append(os.path.join(root, file))
            dirs.clear()
    
    return image_files


def process_images(folder, output_file, folder_name, status_callback, progress_callback):
    """处理图片并导出CSV"""
    image_files = get_image_files(folder, folder_name)
    total = len(image_files)
    
    if total == 0:
        status_callback(f"未找到名为'{folder_name}'文件夹内的图片文件")
        return
    
    status_callback(f"找到 {total} 张图片，开始处理...")
    
    results = []
    for i, image_path in enumerate(image_files):
        try:
            image = Image.open(image_path)
            exif_data = get_exif_data(image)
            gps_info = get_gps_info(exif_data)
            latitude, longitude = extract_coordinates(gps_info)
            azimuth = extract_azimuth(gps_info)

            filename = os.path.splitext(os.path.basename(image_path))[0]
            results.append({
                'filename': filename,
                'latitude': latitude if latitude is not None else '',
                'longitude': longitude if longitude is not None else '',
                'azimuth': azimuth if azimuth is not None else ''
            })
            
            progress_callback((i + 1) / total * 100)
            status_callback(f"正在处理: {filename} ({i + 1}/{total})")
            
        except Exception as e:
            results.append({
                'filename': os.path.splitext(os.path.basename(image_path))[0],
                'latitude': '',
                'longitude': '',
                'azimuth': ''
            })

    try:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['filename', 'latitude', 'longitude', 'azimuth']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        status_callback(f"完成！已保存到: {output_file}")
    except Exception as e:
        status_callback(f"保存文件时出错: {str(e)}")


def rename_photos(folder, status_callback, progress_callback):
    """将所有子文件夹内的照片重命名为'文件夹后五位-序号'格式"""
    IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.tiff', '.heic')

    # 收集所有子文件夹及其照片
    subfolders = []
    for entry in os.scandir(folder):
        if entry.is_dir():
            photos = []
            for f in os.scandir(entry.path):
                if f.is_file() and f.name.lower().endswith(IMAGE_EXTENSIONS):
                    photos.append(f.path)
            if photos:
                subfolders.append((entry.name, photos))

    if not subfolders:
        status_callback("所选目录下未找到包含照片的子文件夹")
        return 0

    total_renamed = 0
    total_folders = len(subfolders)

    for folder_idx, (folder_name, photos) in enumerate(subfolders):
        # 提取文件夹名称后五位
        suffix = folder_name[-5:] if len(folder_name) >= 5 else folder_name
        status_callback(f"正在处理文件夹: {folder_name} ({folder_idx + 1}/{total_folders})")

        # 按文件名排序，保证顺序一致
        photos.sort()

        for i, photo_path in enumerate(photos, start=1):
            ext = os.path.splitext(photo_path)[1]
            new_name = f"{suffix}-{i}{ext}"
            new_path = os.path.join(os.path.dirname(photo_path), new_name)

            # 避免重名冲突（目标文件已存在且不是自身）
            if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(photo_path):
                # 尝试递增序号
                seq = i + 1
                while os.path.exists(os.path.join(os.path.dirname(photo_path), f"{suffix}-{seq}{ext}")):
                    seq += 1
                new_name = f"{suffix}-{seq}{ext}"
                new_path = os.path.join(os.path.dirname(photo_path), new_name)

            try:
                os.rename(photo_path, new_path)
                total_renamed += 1
            except Exception as e:
                status_callback(f"重命名失败: {os.path.basename(photo_path)} -> {e}")

        progress_callback((folder_idx + 1) / total_folders * 100)

    status_callback(f"重命名完成！共处理 {total_renamed} 张照片")
    return total_renamed


def process_all_images(folder, status_callback, progress_callback):
    """处理所有照片文件夹并导出两个CSV文件"""
    folder_configs = [
        ("人工举证照片", "人工举证照片坐标信息.csv"),
        ("无人机举证照片", "无人机举证照片坐标信息.csv")
    ]
    
    all_results = []
    
    for folder_name, csv_filename in folder_configs:
        image_files = get_image_files(folder, folder_name)
        total = len(image_files)
        
        if total == 0:
            status_callback(f"未找到名为'{folder_name}'文件夹内的图片文件")
            continue
        
        status_callback(f"找到 {total} 张{folder_name}图片，开始处理...")
        
        results = []
        for i, image_path in enumerate(image_files):
            try:
                image = Image.open(image_path)
                exif_data = get_exif_data(image)
                gps_info = get_gps_info(exif_data)
                latitude, longitude = extract_coordinates(gps_info)
                azimuth = extract_azimuth(gps_info)

                filename = os.path.splitext(os.path.basename(image_path))[0]
                results.append({
                    'filename': filename,
                    'latitude': latitude if latitude is not None else '',
                    'longitude': longitude if longitude is not None else '',
                    'azimuth': azimuth if azimuth is not None else ''
                })
                
                progress_callback((i + 1) / total * 100)
                status_callback(f"正在处理 {folder_name}: {filename} ({i + 1}/{total})")
                
            except Exception as e:
                results.append({
                    'filename': os.path.splitext(os.path.basename(image_path))[0],
                    'latitude': '',
                    'longitude': '',
                    'azimuth': ''
                })

        output_file = os.path.join(folder, csv_filename)
        try:
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['filename', 'latitude', 'longitude', 'azimuth']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
            
            status_callback(f"完成！已保存到: {output_file}")
            all_results.append((folder_name, output_file))
        except Exception as e:
            status_callback(f"保存文件时出错: {str(e)}")
    
    return all_results


class PhotoGPSExtractor:
    def __init__(self, root):
        self.root = root
        self.root.title("照片GPS信息提取工具")
        self.root.geometry("550x380")
        self.root.minsize(450, 340)
        
        self.folder_path = tk.StringVar()
        self.rename_path = tk.StringVar()

        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # GPS提取区域
        ttk.Label(main_frame, text="GPS提取 - 选择文件夹:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        folder_frame = ttk.Frame(main_frame)
        folder_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Entry(folder_frame, textvariable=self.folder_path).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(folder_frame, text="浏览...", command=self.browse_folder).grid(row=0, column=1)
        folder_frame.columnconfigure(0, weight=1)

        ttk.Button(main_frame, text="开始提取", command=self.start_processing).grid(row=2, column=0, pady=(0, 15), sticky=tk.W)

        # 分隔线
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 15))

        # 重命名区域
        ttk.Label(main_frame, text="照片重命名 - 选择文件夹:").grid(row=4, column=0, sticky=tk.W, pady=(0, 5))
        rename_frame = ttk.Frame(main_frame)
        rename_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Entry(rename_frame, textvariable=self.rename_path).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(rename_frame, text="浏览...", command=self.browse_rename_folder).grid(row=0, column=1)
        rename_frame.columnconfigure(0, weight=1)

        ttk.Button(main_frame, text="照片重命名", command=self.start_rename).grid(row=6, column=0, pady=(0, 10), sticky=tk.W)

        # 状态栏
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.status_label = ttk.Label(main_frame, text="就绪", wraplength=500)
        self.status_label.grid(row=8, column=0, sticky=tk.W)

        main_frame.columnconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
    
    def browse_folder(self):
        folder = filedialog.askdirectory(title="选择包含照片文件夹的目录")
        if folder:
            self.folder_path.set(folder)

    def browse_rename_folder(self):
        folder = filedialog.askdirectory(title="选择包含子文件夹的照片目录")
        if folder:
            self.rename_path.set(folder)
    
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def update_progress(self, value):
        self.progress_var.set(value)
        self.root.update_idletasks()
    
    def start_processing(self):
        folder = self.folder_path.get()
        
        if not folder:
            messagebox.showwarning("警告", "请选择文件夹")
            return
        
        def run_processing():
            results = process_all_images(folder, self.update_status, self.update_progress)
            if results:
                msg = "GPS信息提取完成！\n\n"
                for folder_name, output_file in results:
                    msg += f"• {folder_name}: {os.path.basename(output_file)}\n"
                self.root.after(0, lambda: messagebox.showinfo("完成", msg))
            else:
                self.root.after(0, lambda: messagebox.showwarning("警告", "未找到任何照片文件夹"))
        
        thread = threading.Thread(target=run_processing)
        thread.daemon = True
        thread.start()

    def start_rename(self):
        folder = self.rename_path.get()

        if not folder:
            messagebox.showwarning("警告", "请选择重命名文件夹")
            return

        confirm = messagebox.askyesno(
            "确认重命名",
            "将把所选目录下所有子文件夹内的照片重命名为'文件夹后五位-序号'格式。\n\n此操作不可撤销，是否继续？"
        )
        if not confirm:
            return

        def run_rename():
            try:
                total = rename_photos(folder, self.update_status, self.update_progress)
                if total > 0:
                    self.root.after(0, lambda: messagebox.showinfo("完成", f"重命名完成！共处理 {total} 张照片"))
                else:
                    self.root.after(0, lambda: messagebox.showwarning("警告", "未找到包含照片的子文件夹"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"重命名过程出错:\n{str(e)}"))

        thread = threading.Thread(target=run_rename)
        thread.daemon = True
        thread.start()


if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoGPSExtractor(root)
    root.mainloop()
    
    exe_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    log_dir = os.path.join(exe_dir, "log")
    if os.path.isdir(log_dir) and not os.listdir(log_dir):
        os.rmdir(log_dir)