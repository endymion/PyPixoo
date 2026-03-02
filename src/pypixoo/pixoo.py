"""Pixoo 64 display client."""

from __future__ import annotations

import atexit
import base64
import json
import os
import threading
from pathlib import Path
from typing import Optional, Sequence, Union

import requests
from PIL import Image

from pypixoo.buffer import Buffer
from pypixoo.native import (
    CycleHandle,
    CycleItem,
    GifFrame,
    GifSequence,
    GifSource,
    OnItemCallback,
    OnLoopCallback,
    TextOverlay,
    UploadMode,
)

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore


class DeviceInUseError(RuntimeError):
    """Raised when connecting to a device IP that another process is already using."""

    def __init__(self, ip_address: str, message: Optional[str] = None):
        self.ip_address = ip_address
        super().__init__(
            message
            or (
                f"Device at {ip_address} is in use by another process. "
                "Close the other app or call close() on the other client."
            )
        )


def _device_lock_path(ip_address: str) -> Path:
    """Path to the lock file for this device IP (one lock per IP)."""
    safe = ip_address.replace(".", "_").replace(":", "_")
    base = Path(os.environ.get("PYPIXOO_LOCK_DIR", os.path.expanduser("~/.pypixoo")))
    base.mkdir(parents=True, exist_ok=True)
    return base / f"device-{safe}.lock"


def _acquire_device_lock(ip_address: str):
    """
    Acquire an exclusive lock for this device IP. Returns an open file object.
    Raises DeviceInUseError if the device is already locked by another process.
    Only runs when PIXOO_REAL_DEVICE=1; otherwise returns None (no lock).
    """
    if os.environ.get("PIXOO_REAL_DEVICE") != "1":
        return None
    if fcntl is None:
        return None
    path = _device_lock_path(ip_address)
    try:
        f = open(path, "w")
    except OSError as e:
        raise DeviceInUseError(ip_address, f"Cannot create lock file {path}: {e}") from e
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        raise DeviceInUseError(ip_address) from None
    return f


class Pixoo:
    """Client for Divoom Pixoo 64 display."""

    SIZE = 64

    def __init__(self, ip_address: str):
        self.ip_address = ip_address
        self._url = f"http://{ip_address}/post"
        self._buffer: list[int] = []
        self._counter = 1
        self._lock_file = None
        self._last_playback_mode: Optional[str] = None
        self._active_cycle: Optional[CycleHandle] = None

    def connect(self) -> bool:
        """Test connection and load GIF counter. Returns True if connected.
        When PIXOO_REAL_DEVICE=1, acquires an exclusive lock for this device IP;
        raises DeviceInUseError if another process holds the lock."""
        if self._lock_file is None:
            lock_file = _acquire_device_lock(self.ip_address)
            if lock_file is not None:
                self._lock_file = lock_file
                atexit.register(self._release_device_lock)
        self._load_counter()
        return self._validate_connection()

    def close(self) -> None:
        """Release the device lock if held. Safe to call multiple times."""
        self._release_device_lock()

    def _release_device_lock(self) -> None:
        if self._lock_file is None:
            return
        try:
            self._lock_file.close()
        except OSError:
            pass
        self._lock_file = None

    def fill(self, r: int, g: int, b: int) -> None:
        """Fill the display buffer with a solid RGB color."""
        self._buffer = []
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        for _ in range(self.SIZE * self.SIZE):
            self._buffer.extend([r, g, b])

    def load_image(self, path: Union[str, Path]) -> None:
        """Load an image file into the display buffer. Resizes to 64×64 if needed."""
        img = Image.open(path).convert("RGB")
        if img.size != (self.SIZE, self.SIZE):
            img = img.resize((self.SIZE, self.SIZE), Image.Resampling.NEAREST)
        self._buffer = list(img.getdata())
        self._buffer = [c for pixel in self._buffer for c in pixel]

    def push(self) -> None:
        """Send the current buffer using native HttpGif upload semantics."""
        self._push_frame_data(self._buffer)

    def push_buffer(self, data: list[int]) -> None:
        """Send the given frame data using native HttpGif upload semantics."""
        self._push_frame_data(data)

    @property
    def buffer(self) -> Buffer:
        """Return a snapshot of the display buffer for introspection and assertions."""
        return Buffer(data=tuple(self._buffer))

    def get_http_gif_id(self) -> int:
        """Read current device GIF counter via Draw/GetHttpGifId."""
        data = self._post_command({"Command": "Draw/GetHttpGifId"})
        pic_id = data.get("PicId")
        if pic_id is None:
            raise RuntimeError(f"Missing PicId in response: {data}")
        return int(pic_id)

    def reset_http_gif_id(self) -> int:
        """Reset device GIF counter and return the refreshed PicId."""
        self._post_command({"Command": "Draw/ResetHttpGifId"})
        self._counter = self.get_http_gif_id()
        return self._counter

    def upload_sequence(
        self,
        sequence: GifSequence,
        *,
        mode: UploadMode = UploadMode.FRAME_BY_FRAME,
        chunk_size: int = 40,
    ) -> int:
        """Upload a native HttpGif sequence and return the PicID used."""
        if not sequence.frames:
            raise ValueError("GifSequence requires at least one frame")

        mode = UploadMode(mode)
        if chunk_size <= 0:
            raise ValueError("chunk_size must be >= 1")

        pic_id = self._next_pic_id()
        pic_num = len(sequence.frames)

        if mode == UploadMode.FRAME_BY_FRAME:
            for offset, frame in enumerate(sequence.frames):
                payload = self._build_send_http_gif_payload(
                    frame=frame,
                    pic_id=pic_id,
                    pic_num=pic_num,
                    pic_offset=offset,
                    speed_ms=sequence.speed_ms,
                )
                self._post_command(payload)
        else:
            for start in range(0, pic_num, chunk_size):
                frames_chunk = sequence.frames[start : start + chunk_size]
                command_list = []
                for i, frame in enumerate(frames_chunk):
                    command_list.append(
                        self._build_send_http_gif_payload(
                            frame=frame,
                            pic_id=pic_id,
                            pic_num=pic_num,
                            pic_offset=start + i,
                            speed_ms=sequence.speed_ms,
                        )
                    )
                self._post_command({"Command": "Draw/CommandList", "CommandList": command_list})

        self._last_playback_mode = "httpgif"
        return pic_id

    def play_gif(self, source: GifSource) -> None:
        """Play a GIF from URL, TF file, or TF directory via Device/PlayTFGif."""
        file_type = {
            "tf_file": 0,
            "tf_directory": 1,
            "url": 2,
        }[source.source_type]
        self._post_command(
            {
                "Command": "Device/PlayTFGif",
                "FileType": file_type,
                "FileName": source.value,
            }
        )
        self._last_playback_mode = "playtfgif"

    def send_text_overlay(self, overlay: TextOverlay) -> None:
        """Send overlay text for HttpGif playback context."""
        if self._last_playback_mode == "playtfgif":
            raise ValueError("Text overlay is only supported with uploaded HttpGif playback")
        self._post_command(
            {
                "Command": "Draw/SendHttpText",
                "TextId": overlay.text_id,
                "x": overlay.x,
                "y": overlay.y,
                "dir": overlay.direction,
                "font": overlay.font,
                "TextWidth": overlay.text_width,
                "speed": overlay.speed,
                "TextString": overlay.text,
                "color": overlay.color,
                "align": overlay.align,
            }
        )

    def clear_text_overlay(self) -> None:
        """Clear any Draw/SendHttpText overlays."""
        self._post_command({"Command": "Draw/ClearHttpText"})

    def start_cycle(
        self,
        items: Sequence[CycleItem],
        *,
        loop: Optional[int] = 1,
        on_loop: Optional[OnLoopCallback] = None,
        on_item: Optional[OnItemCallback] = None,
    ) -> CycleHandle:
        """Start asynchronous execution of configured cycle items."""
        if not items:
            raise ValueError("start_cycle requires at least one CycleItem")
        if loop is not None and loop <= 0:
            raise ValueError("loop must be >= 1 or None for infinite")
        if self._active_cycle is not None and self._active_cycle.is_running:
            raise RuntimeError("Cycle already running")

        stop_event = threading.Event()
        done_event = threading.Event()
        item_list = list(items)

        def _run_cycle() -> None:
            try:
                target_loops = 0 if loop is None else loop
                completed_loops = 0
                while target_loops == 0 or completed_loops < target_loops:
                    for idx, item in enumerate(item_list):
                        if stop_event.is_set():
                            return
                        if item.sequence is not None:
                            self.upload_sequence(
                                item.sequence,
                                mode=item.upload_mode,
                                chunk_size=item.chunk_size,
                            )
                        elif item.source is not None:
                            self.play_gif(item.source)
                        if on_item is not None:
                            on_item(idx, item)
                    completed_loops += 1
                    if on_loop is not None:
                        on_loop(completed_loops)
            finally:
                done_event.set()

        thread = threading.Thread(target=_run_cycle, daemon=True)
        handle = CycleHandle(thread=thread, stop_event=stop_event, done_event=done_event)
        self._active_cycle = handle
        thread.start()
        return handle

    def _validate_connection(self) -> bool:
        """Verify connection by calling device API."""
        try:
            response = requests.post(
                self._url,
                json.dumps({"Command": "Channel/GetAllConf"}),
                timeout=5,
            )
            data = response.json()
            return data.get("error_code", -1) == 0
        except requests.exceptions.RequestException:
            return False

    def _load_counter(self) -> None:
        """Load current GIF frame ID from the device."""
        self._counter = self.get_http_gif_id()

    def _next_pic_id(self) -> int:
        self._counter += 1
        return self._counter

    def _build_send_http_gif_payload(
        self,
        *,
        frame: GifFrame,
        pic_id: int,
        pic_num: int,
        pic_offset: int,
        speed_ms: int,
    ) -> dict:
        pic_data = base64.b64encode(bytearray(frame.image.data)).decode()
        return {
            "Command": "Draw/SendHttpGif",
            "PicNum": pic_num,
            "PicWidth": self.SIZE,
            "PicOffset": pic_offset,
            "PicID": pic_id,
            "PicSpeed": speed_ms,
            "PicData": pic_data,
        }

    def _push_frame_data(self, data: list[int]) -> None:
        frame = GifFrame(image=Buffer.from_flat_list(data), duration_ms=1000)
        sequence = GifSequence(frames=[frame], speed_ms=1000)
        self.upload_sequence(sequence, mode=UploadMode.FRAME_BY_FRAME)

    def _post_command(self, payload: dict) -> dict:
        response = requests.post(self._url, json.dumps(payload), timeout=5)
        response_data = response.json()
        if response_data.get("error_code", -1) != 0:
            raise RuntimeError(f"Command failed ({payload.get('Command')}): {response_data}")
        return response_data
