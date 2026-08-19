# License Plate Detector

A Python application for detecting and cropping license plates from
dashcam videos using YOLO and OpenCV. The application provides a NiceGUI
web interface with live processing progress through WebSockets.

## Features

-   Upload dashcam videos through a web interface
-   Extract every frame from a video
-   Detect license plates using a YOLO model
-   Detect multiple plates in the same frame
-   Crop detected license plates
-   Save bounding boxes and confidence scores to CSV
-   Display detected plate crops in the web interface
-   Show live processing progress
-   Upload and use a custom YOLO `.pt` model

## Project Structure

``` text
PlateDetector/
├── README.md
├── app.py
├── models/
│   └── license_plate_detector.pt
└── src/
    ├── __init__.py
    ├── config.py
    ├── detect_plate.py
    ├── extract_frames.py
    ├── progress_ws.py
    └── utils.py
```

## Requirements

-   Python 3.x
-   A compatible YOLO license-plate detection model
-   A video file supported by OpenCV

## Installation

Clone the repository and enter the project directory:

``` bash
git clone <repository-url>
cd PlateDetector
```

Install the required dependencies:

``` bash
pip install nicegui fastapi ultralytics opencv-python tqdm
```

## Model

Place the YOLO license-plate detection model in:

``` text
models/license_plate_detector.pt
```

This is the default model used by the application.

The web interface also supports uploading a custom `.pt` model from the
**Advanced: use a custom model** section.

## Running the Application

Run the application from the project root:

``` bash
python app.py
```

The NiceGUI web interface will start and allow you to upload a dashcam
video.

Click **Read** to start processing.

## How It Works

The processing pipeline is:

``` text
Dashcam Video
      │
      ▼
Frame Extraction
      │
      ▼
PNG Frames
      │
      ▼
YOLO Plate Detection
      │
      ▼
Plate Crops
      │
      ├──► PNG Images
      │
      └──► CSV Detection Log
```

### 1. Frame Extraction

The application extracts every frame from the uploaded video using
OpenCV.

Frames are stored in:

``` text
output/frames/<video_name>/
```

A `frames.csv` file is also created containing:

-   Frame number
-   Timestamp
-   Frame filename

### 2. License Plate Detection

The `PlateDetector` loads the YOLO model and processes every extracted
frame.

Every detection above the configured confidence threshold is saved as an
individual crop. The detector does not perform vehicle tracking or ROI
filtering.

### 3. Plate Cropping

Each detected plate is cropped from the original frame and saved as a
PNG file.

Example:

``` text
frame_000123_p0.png
frame_000456_p0.png
```

### 4. CSV Logging

The detector generates:

``` text
plates.csv
```

with the following columns:

``` text
frame,crop_file,x1,y1,x2,y2,confidence
```

Where:

-   `frame` --- source frame filename
-   `crop_file` --- generated plate crop
-   `x1`, `y1` --- top-left bounding-box coordinates
-   `x2`, `y2` --- bottom-right bounding-box coordinates
-   `confidence` --- YOLO detection confidence

## Configuration

Detection settings are defined in:

``` text
src/config.py
```

Default settings:

``` python
PLATE_MODEL = MODELS / "license_plate_detector.pt"
PLATE_CONFIDENCE = 0.15
PLATE_IMGSZ = 2560
```

The application also creates the required directories automatically:

``` text
input/
output/
output/frames/
output/crops/
models/
```

## Output Structure

After processing a video, the output directory will look like:

``` text
output/
├── frames/
│   └── video_name/
│       ├── frame_000000.png
│       ├── frame_000001.png
│       ├── frame_000002.png
│       └── frames.csv
│
└── crops/
    └── video_name/
        ├── frame_000123_p0.png
        ├── frame_000456_p0.png
        ├── frame_000789_p0.png
        └── plates.csv
```

## Real-Time Progress

Processing can take significant time for long or high-resolution videos.

The application uses a WebSocket connection to provide live progress
updates to the web interface.

Progress information includes:

-   Current frame
-   Total number of frames
-   Number of detected plates

The detection process runs in a worker thread while progress updates are
sent back to the web interface.

## Detection Behavior

The detector processes all extracted frames and saves every plate
detection that passes the configured confidence threshold.

It does not:

-   Track vehicles
-   Select only one detection per frame
-   Restrict detection to a vehicle ROI

This allows multiple plate detections from the same frame to be
retained.

## License

Add your preferred project license here.
