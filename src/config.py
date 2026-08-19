from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INPUT = ROOT / "input"

OUTPUT = ROOT / "output"

FRAMES = OUTPUT / "frames"

CROPS = OUTPUT / "crops"

MODELS = ROOT / "models"

DIRECTORIES = [
    INPUT,
    OUTPUT,
    FRAMES,
    CROPS,
    MODELS,
]

PLATE_MODEL = MODELS / "license_plate_detector.pt"

PLATE_CONFIDENCE = 0.15

# Full resolution by default. YOLO resizes to imgsz internally, so
# small/distant plates in a large frame can get lost below this.
PLATE_IMGSZ = 2560
