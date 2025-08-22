import cv2
import time
import os
from object_detection import draw_bbs
import yaml


with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

folder = 'frames/'

while True:
    # Get list of files in folder
    files = os.listdir(folder)
    if not files:
        print("No images found.")
        time.sleep(0.00001)
        continue

    # Get latest file by creation time
    latest_file = max(files, key=lambda x: os.path.getctime(os.path.join(folder, x)))

    # Read and show image
    image = cv2.imread(os.path.join(folder, latest_file))
    if image is None:
        print("Failed to load image.")
        time.sleep(0.00001)
        continue


    frame = draw_bbs(frame=image,
                                 target_classes=config["target_classes"],
                                 bb_color=config["bb_color"],
                                 draw_labels=config["draw_labels"],
                                 conf_threshold=config["conf_threshold"])
    
    cv2.imshow('Image Window', frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cv2.destroyAllWindows()
