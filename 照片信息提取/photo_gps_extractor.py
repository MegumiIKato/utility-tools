import os
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


def get_image_files(folder):
    """递归获取所有名为'人工举证照片'文件夹内的图片文件"""
    image_files = []
    target_folder_name = "人工举证照片"
    
    for root, dirs, files in os.walk(folder):
        if os.path.basename(root) == target_folder_name:
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.heic')):
                    image_files.append(os.path.join(root, file))
            dirs.clear()
    
    return image_files


def process_images(folder, output_file, status_callback, progress_callback):
    """处理图片并导出CSV"""
    image_files = get_image_files(folder)
    total = len(image_files)
    
    if total == 0:
        status_callback("未找到名为'人工举证照片'文件夹内的图片文件")
        return
    
    status_callback(f"找到 {total} 张图片，开始处理...")
    
    results = []
    for i, image_path in enumerate(image_files):
        try:
            image = Image.open(image_path)
            exif_data = get_exif_data(image)
            gps_info = get_gps_info(exif_data)
            latitude, longitude = extract_coordinates(gps_info)
            
            filename = os.path.basename(image_path)
            results.append({
                'filename': filename,
                'latitude': latitude if latitude is not None else '',
                'longitude': longitude if longitude is not None else ''
            })
            
            progress_callback((i + 1) / total * 100)
            status_callback(f"正在处理: {filename} ({i + 1}/{total})")
            
        except Exception as e:
            results.append({
                'filename': os.path.basename(image_path),
                'latitude': '',
                'longitude': ''
            })
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['filename', 'latitude', 'longitude']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        status_callback(f"完成！已保存到: {output_file}")
    except Exception as e:
        status_callback(f"保存文件时出错: {str(e)}")


class PhotoGPSExtractor:
    def __init__(self, root):
        self.root = root
        self.root.title("照片GPS信息提取工具")
        self.root.geometry("550x320")
        self.root.minsize(450, 280)
        
        self.folder_path = tk.StringVar()
        self.output_path = tk.StringVar()
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(main_frame, text="选择文件夹:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        folder_frame = ttk.Frame(main_frame)
        folder_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Entry(folder_frame, textvariable=self.folder_path).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(folder_frame, text="浏览...", command=self.browse_folder).grid(row=0, column=1)
        folder_frame.columnconfigure(0, weight=1)
        
        ttk.Label(main_frame, text="输出文件:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Entry(output_frame, textvariable=self.output_path).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(output_frame, text="浏览...", command=self.browse_output).grid(row=0, column=1)
        output_frame.columnconfigure(0, weight=1)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_label = ttk.Label(main_frame, text="请选择包含'人工举证照片'文件夹的目录", wraplength=500)
        self.status_label.grid(row=5, column=0, sticky=tk.W, pady=(0, 10))
        
        ttk.Button(main_frame, text="开始提取", command=self.start_processing).grid(row=6, column=0, pady=(10, 0))
        
        main_frame.columnconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
    
    def browse_folder(self):
        folder = filedialog.askdirectory(title="选择包含'人工举证照片'文件夹的目录")
        if folder:
            self.folder_path.set(folder)
            output_file = os.path.join(folder, "gps_coordinates.csv")
            self.output_path.set(output_file)
    
    def browse_output(self):
        file = filedialog.asksaveasfilename(
            title="保存CSV文件",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file:
            self.output_path.set(file)
    
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def update_progress(self, value):
        self.progress_var.set(value)
        self.root.update_idletasks()
    
    def start_processing(self):
        folder = self.folder_path.get()
        output = self.output_path.get()
        
        if not folder:
            messagebox.showwarning("警告", "请选择文件夹")
            return
        
        if not output:
            messagebox.showwarning("警告", "请选择输出文件")
            return
        
        def run_processing():
            process_images(folder, output, self.update_status, self.update_progress)
            self.root.after(0, lambda: messagebox.showinfo("完成", "GPS信息提取完成！"))
        
        thread = threading.Thread(target=run_processing)
        thread.daemon = True
        thread.start()


if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoGPSExtractor(root)
    root.mainloop()