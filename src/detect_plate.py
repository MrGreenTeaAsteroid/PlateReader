from pathlib import Path
import csv

import cv2
from ultralytics import YOLO


class PlateDetector:
    """Detects and crops every plate in every frame — no vehicle
    tracking, no ROI. Every detection above the confidence threshold
    gets its own crop and a row in the CSV."""

    def __init__(self,
                 model_path="models/license_plate_detector.pt",
                 confidence=0.15,
                 imgsz=2560):

        self.model = YOLO(model_path)
        self.confidence = confidence
        self.imgsz = imgsz

    def detect_folder(
        self,
        frame_folder,
        crop_folder,
        csv_path=None,
        progress_callback=None,
    ):
        """
        Detects plates in every frame in frame_folder. All detections
        per frame are saved (not just the top one) and logged to CSV.

        progress_callback(current_index, total_frames, plates_found_so_far)
        is called after each frame, if given — decouples this from
        however progress ends up displayed (WebSocket, CLI, etc).
        """

        frame_folder = Path(frame_folder)
        crop_folder = Path(crop_folder)

        crop_folder.mkdir(parents=True, exist_ok=True)

        if csv_path is None:
            csv_path = crop_folder / "plates.csv"
        else:
            csv_path = Path(csv_path)

        frames = sorted(frame_folder.glob("*.png"))
        total = len(frames)

        rows = []
        found = 0

        for i, frame_path in enumerate(frames):

            image = cv2.imread(str(frame_path))

            if image is None:
                if progress_callback:
                    progress_callback(i + 1, total, found)
                continue

            results = self.model.predict(
                image,
                verbose=False,
                conf=self.confidence,
                imgsz=self.imgsz,
            )

            plate_index = 0

            for r in results:
                for box in r.boxes:

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    confidence = float(box.conf[0])

                    crop = image[max(0, y1):y2, max(0, x1):x2]

                    if crop.size == 0:
                        continue

                    crop_name = f"{frame_path.stem}_p{plate_index}.png"

                    cv2.imwrite(str(crop_folder / crop_name), crop)

                    rows.append([
                        frame_path.name, crop_name,
                        x1, y1, x2, y2,
                        f"{confidence:.4f}",
                    ])

                    plate_index += 1
                    found += 1

            if progress_callback:
                progress_callback(i + 1, total, found)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "crop_file", "x1", "y1", "x2", "y2", "confidence"])
            writer.writerows(rows)

        return csv_path
