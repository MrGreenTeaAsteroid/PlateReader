import asyncio
import uuid
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect
from nicegui import ui, run, app as nicegui_app

from src.config import DIRECTORIES, INPUT, FRAMES, CROPS, PLATE_MODEL, PLATE_CONFIDENCE, PLATE_IMGSZ
from src.utils import make_directories
from src.extract_frames import FrameExtractor
from src.detect_plate import PlateDetector
from src.progress_ws import broadcaster, make_progress_callback, push_done, push_error

make_directories(DIRECTORIES)

state = {
    "video_path": None,
    "model_path": str(PLATE_MODEL),
}


# ---------------------------------------------------------------------------
# WebSocket route — one channel per run, fed by the detection loop
# running in a worker thread.
# ---------------------------------------------------------------------------

@nicegui_app.on_startup
def bind_broadcaster_loop():
    broadcaster.bind_loop(asyncio.get_event_loop())


@nicegui_app.websocket("/ws/progress/{run_id}")
async def progress_socket(websocket: WebSocket, run_id: str):
    await websocket.accept()
    queue = broadcaster.subscribe(run_id)

    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)

            if payload.get("type") in ("done", "error"):
                break

    except WebSocketDisconnect:
        pass

    finally:
        broadcaster.unsubscribe(run_id, queue)


# ---------------------------------------------------------------------------
# Pipeline (runs in a worker thread)
# ---------------------------------------------------------------------------

def run_pipeline(video_path: str, model_path: str, run_id: str):

    video_path = Path(video_path)
    stem = video_path.stem

    frame_dir = FRAMES / stem
    crop_dir = CROPS / stem

    extractor = FrameExtractor(video_path=str(video_path), output_dir=str(frame_dir))
    extractor.extract()

    detector = PlateDetector(
        model_path=model_path,
        confidence=PLATE_CONFIDENCE,
        imgsz=PLATE_IMGSZ,
    )

    csv_path = detector.detect_folder(
        frame_dir,
        crop_dir,
        progress_callback=make_progress_callback(run_id),
    )

    crops = list(crop_dir.glob("*.png"))
    push_done(run_id, len(crops))

    return crop_dir, csv_path


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

@ui.page("/download_csv")
def download_csv(path: str):
    return ui.download(path)


@ui.page("/")
def main_page():

    async def handle_upload(e):
        dest = INPUT / e.file.name
        await e.file.save(dest)

        state["video_path"] = dest
        status_label.set_text(f"Uploaded: {e.file.name}")
        read_button.enable()
        results_column.clear()

    def reset_upload():
        state["video_path"] = None
        upload_component.reset()
        status_label.set_text("No video uploaded yet.")
        read_button.disable()
        results_column.clear()

    async def handle_model_upload(e):
        dest = Path("models") / e.file.name
        await e.file.save(dest)

        state["model_path"] = str(dest)
        model_status_label.set_text(f"Using custom model: {e.file.name}")

    def reset_model():
        state["model_path"] = str(PLATE_MODEL)
        model_status_label.set_text("Using default model.")

    def show_results(crop_dir: Path, csv_path: Path):
        crop_dir = Path(crop_dir)
        csv_path = Path(csv_path)

        crops = sorted(crop_dir.glob("*.png"))

        with results_column:
            ui.label(f"Found {len(crops)} plate crop(s).").classes("text-lg font-bold")

            if csv_path.exists():
                ui.link("Download CSV log", f"/download_csv?path={csv_path}").classes("text-blue-400")

            if not crops:
                ui.label("No plates were detected in this video.")
                return

            with ui.grid(columns=6).classes("gap-2 mt-2"):
                for crop in crops:
                    with ui.card().tight().classes("p-1"):
                        ui.image(str(crop)).classes("w-32")
                        ui.label(crop.name).classes("text-xs text-center")

    async def on_read_click():
        if state["video_path"] is None:
            ui.notify("Upload a video first.", type="warning")
            return

        run_id = str(uuid.uuid4())

        read_button.disable()
        upload_component.disable()
        results_column.clear()

        progress_bar.set_value(0)
        progress_bar.set_visibility(True)
        progress_text.set_text("Starting...")

        # WebSocket client for live progress — full-res detection can take
        # 15-20 min on a long video, so a static spinner isn't good enough.
        ui.run_javascript(f"""
            (() => {{
                const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
                const ws = new WebSocket(`${{proto}}://${{window.location.host}}/ws/progress/{run_id}`);

                ws.onmessage = (event) => {{
                    const data = JSON.parse(event.data);

                    if (data.type === 'progress') {{
                        const pct = data.total > 0 ? data.current / data.total : 0;
                        window.__plateProgress = {{
                            pct: pct,
                            text: `Frame ${{data.current}} / ${{data.total}} — ${{data.plates_found}} plate(s) found so far`
                        }};
                    }} else if (data.type === 'done') {{
                        window.__plateProgress = {{ pct: 1.0, text: `Done — ${{data.crop_count}} plate crop(s) found.` }};
                        ws.close();
                    }} else if (data.type === 'error') {{
                        window.__plateProgress = {{ pct: 0, text: `Error: ${{data.message}}` }};
                        ws.close();
                    }}
                }};
            }})();
        """)

        # NiceGUI elements are server-rendered, so this polls the JS-side
        # state to reflect the WebSocket updates into the progress bar.
        async def poll_progress():
            while True:
                await asyncio.sleep(0.5)
                result = await ui.run_javascript("window.__plateProgress || null")
                if result:
                    progress_bar.set_value(result["pct"])
                    progress_text.set_text(result["text"])
                    if result["pct"] >= 1.0 or result["text"].startswith("Error"):
                        break

        poll_task = asyncio.ensure_future(poll_progress())

        try:
            crop_dir, csv_path = await run.io_bound(
                run_pipeline, str(state["video_path"]), state["model_path"], run_id
            )
            await poll_task
            show_results(crop_dir, csv_path)

        except Exception as exc:
            push_error(run_id, str(exc))
            poll_task.cancel()
            try:
                await poll_task
            except asyncio.CancelledError:
                pass
            ui.notify(f"Processing failed: {exc}", type="negative")
            progress_text.set_text(f"Error: {exc}")

        finally:
            read_button.enable()
            upload_component.enable()

    ui.label("License Plate Cropper").classes("text-2xl font-bold")
    ui.label(
        "Upload a dashcam video. Every license plate detected in every frame "
        "will be cropped and logged to a CSV, with live progress below."
    ).classes("text-sm text-gray-500 mb-2")

    with ui.card().classes("w-full"):
        upload_component = ui.upload(
            label="Browse for a video",
            auto_upload=True,
            on_upload=handle_upload,
        ).props("accept=video/*")

        status_label = ui.label("No video uploaded yet.")

        with ui.row():
            ui.button("Upload another", on_click=reset_upload)
            read_button = ui.button("Read", on_click=on_read_click)
            read_button.disable()

        progress_bar = ui.linear_progress(value=0, show_value=False).classes("mt-2")
        progress_bar.set_visibility(False)
        progress_text = ui.label("")

    with ui.expansion("Advanced: use a custom model").classes("w-full mt-2"):
        ui.upload(
            label="Upload a .pt model file",
            auto_upload=True,
            on_upload=handle_model_upload,
        ).props("accept=.pt")
        model_status_label = ui.label("Using default model.")
        ui.button("Reset to default model", on_click=reset_model)

    results_column = ui.column().classes("w-full mt-4")


ui.run(title="License Plate Cropper")
