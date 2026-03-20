from ultralytics import YOLO
model = YOLO("best (4).pt")
model.export(format="onnx", imgsz=640)