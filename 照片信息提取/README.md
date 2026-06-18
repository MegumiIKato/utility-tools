# 照片GPS信息提取工具

## 功能说明
从照片中提取GPS经纬度信息并导出为CSV文件。只扫描名为"人工举证照片"文件夹内的照片。

## 使用方法
1. 双击运行 `photo_gps_extractor.py`
2. 点击"浏览..."按钮选择包含"人工举证照片"文件夹的目录
3. 选择输出CSV文件的位置（默认保存在选择的目录下）
4. 点击"开始提取"按钮
5. 等待处理完成，CSV文件将包含：文件名、纬度、经度

## 支持的图片格式
- JPG/JPEG
- PNG
- TIFF
- HEIC

## 打包为Windows可执行文件
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "照片GPS提取工具" photo_gps_extractor.py
```

## 输出格式
CSV文件使用UTF-8编码，包含三列：
- filename: 图片文件名
- latitude: 纬度（度格式）
- longitude: 经度（度格式）