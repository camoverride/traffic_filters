import cv2
import numpy as np
import yaml
from ultralytics import YOLO



# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Load the YOLOv8n model
MODEL = YOLO(config["yolo_model"])


def draw_bbs(frame : np.ndarray,
             target_classes : list,
             bb_color : tuple,
             draw_labels : bool,
             conf_threshold : float):
    """
    Draw bounding boxes around detected objects in a frame using YOLOv8.

    Parameters
    ----------
    frame : np.ndarray
        Input image frame (BGR).
    target_classes : list
        Classes to detect (e.g., ["person"]).
    bb_color : tuple
        Bounding box color (B, G, R). e.g. (0, 255, 0)
    draw_labels : bool
        Whether to draw labels above boxes.
    conf_threshold : float
        Minimum confidence threshold.

    Returns
    -------
    np.ndarray
        Frame with drawn bounding boxes.
    """
    results = MODEL.predict(frame, conf=conf_threshold, imgsz=768, verbose=False)[0]

    # Iterate through detections
    for box in results.boxes: # type: ignore
        cls_id = int(box.cls[0])
        cls_name = MODEL.names[cls_id]
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
