# draw_bbs.py
import cv2
from ultralytics import YOLO

# Load the YOLOv8n model only once
model = YOLO("yolov8n.pt")  # You can swap in yolov5n, yolonas_nano, etc.

def draw_bbs(
    frame,
    target_classes=["person"],
    bb_color=(0, 255, 0),
    draw_labels=True,
    conf_threshold=0.3
):
    """
    Draw bounding boxes around detected objects in a frame using YOLOv8.

    Args:
        frame (np.ndarray): Input image frame (BGR).
        target_classes (list): Classes to detect (e.g., ["person"]).
        bb_color (tuple): Bounding box color (B, G, R).
        draw_labels (bool): Whether to draw labels above boxes.
        conf_threshold (float): Minimum confidence threshold.

    Returns:
        np.ndarray: Frame with drawn bounding boxes.
    """
    results = model.predict(frame, conf=conf_threshold, verbose=False)[0]

    # Iterate through detections
    for box in results.boxes:
        cls_id = int(box.cls[0])
        cls_name = model.names[cls_id]
        conf = float(box.conf[0])

        if cls_name not in target_classes:
            continue

        # Bounding box coordinates
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        # Draw rectangle
        cv2.rectangle(frame, (x1, y1), (x2, y2), bb_color, 2)

        if draw_labels:
            label = f"{cls_name} {conf:.2f}"
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - 20), (x1 + w, y1), bb_color, -1)
            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    return frame
