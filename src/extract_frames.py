import cv2
from pathlib import Path
from tqdm import tqdm


class FrameExtractor:

    def __init__(self, video_path: str, output_dir: str):

        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract(self):

        cap = cv2.VideoCapture(str(self.video_path))

        if not cap.isOpened():
            raise RuntimeError(f"Cannot open {self.video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"FPS          : {fps}")
        print(f"Resolution   : {width}x{height}")
        print(f"Frame Count  : {total}")

        metadata = []

        with tqdm(total=total) as pbar:

            frame_id = 0

            while True:

                ret, frame = cap.read()

                if not ret:
                    break

                filename = self.output_dir / f"frame_{frame_id:06d}.png"

                cv2.imwrite(str(filename), frame)

                timestamp = frame_id / fps

                metadata.append(
                    (
                        frame_id,
                        timestamp,
                        filename.name
                    )
                )

                frame_id += 1
                pbar.update(1)

        cap.release()

        csv = self.output_dir / "frames.csv"

        with open(csv, "w") as f:

            f.write("frame,timestamp,file\n")

            for row in metadata:

                f.write(
                    f"{row[0]},{row[1]:.6f},{row[2]}\n"
                )

        print()
        print("Extraction complete.")
        print(csv)