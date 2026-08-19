import asyncio
import json


class ProgressBroadcaster:
    """One asyncio.Queue per active run_id. Detection thread calls
    push(), subscribed WebSocket clients get it via subscribe()."""

    def __init__(self):
        self._queues: dict[str, list[asyncio.Queue]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop):
        """Call once on app startup — lets push() from a worker
        thread schedule delivery onto the main event loop."""
        self._loop = loop

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(run_id, []).append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        listeners = self._queues.get(run_id, [])
        if queue in listeners:
            listeners.remove(queue)
        if not listeners and run_id in self._queues:
            del self._queues[run_id]

    def push(self, run_id: str, payload: dict):
        """Safe to call from a non-async thread."""
        if self._loop is None:
            return

        listeners = self._queues.get(run_id, [])

        for queue in listeners:
            self._loop.call_soon_threadsafe(queue.put_nowait, payload)


broadcaster = ProgressBroadcaster()


def make_progress_callback(run_id: str):
    """Matches the signature PlateDetector.detect_folder expects:
    (current_index, total_frames, plates_found_so_far)."""
    def _callback(current, total, plates_found):
        broadcaster.push(
            run_id,
            {
                "type": "progress",
                "current": current,
                "total": total,
                "plates_found": plates_found,
            },
        )

    return _callback


def push_done(run_id: str, crop_count: int):
    broadcaster.push(
        run_id,
        {"type": "done", "crop_count": crop_count},
    )


def push_error(run_id: str, message: str):
    broadcaster.push(
        run_id,
        {"type": "error", "message": message},
    )
