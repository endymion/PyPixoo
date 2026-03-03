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
from pypixoo.fonts import DEFAULT_FONT_LIST_URL, FontRegistry, fetch_font_registry
from pypixoo.native import (
    CycleHandle,
    CycleItem,
    DisplayItem,
    GifFrame,
    GifSequence,
    GifSource,
    NoiseTool,
    OnItemCallback,
    OnLoopCallback,
    ScoreBoardTool,
    StopWatchTool,
    TimerTool,
    TextOverlay,
    UploadMode,
    WhiteBalance,
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
    """
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
        Acquires an exclusive lock for this device IP when available; raises
        DeviceInUseError if another process holds the lock."""
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
        """Upload a native HttpGif sequence and return the PicID used.

        This pushes raw frame data from the client to the device. The device
        does not fetch anything from the network in this path.
        """
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
        """Play a GIF from URL, TF file, or TF directory via Device/PlayTFGif.

        For URL sources, the device performs the download and playback.
        """
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
        """Send overlay text for an uploaded HttpGif sequence.

        The device renders the text on top of the last uploaded animation.
        """
        if self._last_playback_mode == "playtfgif":
            raise ValueError("Text overlay is only supported with uploaded HttpGif playback")
        self._post_command(
            {
                "Command": "Draw/SendHttpText",
                "TextId": overlay.text_id,
                "x": overlay.x,
                "y": overlay.y,
                "dir": overlay.direction,
                "font": int(overlay.font),
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

    def upload_sequence_with_overlays(
        self,
        sequence: GifSequence,
        overlays: Sequence[TextOverlay],
        *,
        clear_before: bool = True,
        mode: UploadMode = UploadMode.COMMAND_LIST,
        chunk_size: int = 40,
    ) -> int:
        """Upload a sequence and then send overlays in order.

        This is a convenience wrapper for device-side overlays after upload.
        """
        pic_id = self.upload_sequence(sequence, mode=mode, chunk_size=chunk_size)
        if clear_before:
            self.clear_text_overlay()
        for overlay in overlays:
            self.send_text_overlay(overlay)
        return pic_id

    def list_fonts(self, url: str = DEFAULT_FONT_LIST_URL) -> FontRegistry:
        """Fetch the official display list font registry (external service)."""
        return fetch_font_registry(url=url).registry

    def command(self, command: str, payload: Optional[dict] = None) -> dict:
        """Send a raw command payload with a Command string."""
        body = {"Command": command}
        if payload:
            body.update(payload)
        return self._post_command(body)

    def set_brightness(self, brightness: int) -> None:
        """Set device brightness (0-100)."""
        self._post_command({"Command": "Channel/SetBrightness", "Brightness": brightness})

    def set_channel_index(self, index: int) -> None:
        """Select the device channel by index."""
        self._post_command({"Command": "Channel/SetIndex", "SelectIndex": index})

    def set_custom_page_index(self, index: int) -> None:
        """Select custom channel page index."""
        self._post_command({"Command": "Channel/SetCustomPageIndex", "CustomPageIndex": index})

    def set_eq_position(self, index: int) -> None:
        """Select visualizer EQ position index."""
        self._post_command({"Command": "Channel/SetEqPosition", "EqPosition": index})

    def set_cloud_index(self, index: int) -> None:
        """Select cloud gallery index."""
        self._post_command({"Command": "Channel/CloudIndex", "Index": index})

    def get_channel_index(self) -> int:
        """Get current channel index."""
        data = self._post_command({"Command": "Channel/GetIndex"})
        return int(data.get("SelectIndex", 0))

    def get_all_conf(self) -> dict:
        """Get all device configuration (Channel/GetAllConf)."""
        return self._post_command({"Command": "Channel/GetAllConf"})

    def set_time_zone(self, value: str) -> None:
        """Set device time zone (e.g. GMT-5)."""
        self._post_command({"Command": "Sys/TimeZone", "TimeZoneValue": value})

    def set_weather_location(self, longitude: str, latitude: str) -> None:
        """Set device longitude/latitude for weather data."""
        self._post_command({"Command": "Sys/LogAndLat", "Longitude": longitude, "Latitude": latitude})

    def set_utc_time(self, utc_seconds: int) -> None:
        """Set device UTC time (seconds since epoch)."""
        self._post_command({"Command": "Device/SetUTC", "Utc": utc_seconds})

    def set_screen_on(self, on: bool) -> None:
        """Turn the screen on or off."""
        self._post_command({"Command": "Channel/OnOffScreen", "OnOff": 1 if on else 0})

    def get_device_time(self) -> dict:
        """Get device time info."""
        return self._post_command({"Command": "Device/GetDeviceTime"})

    def set_temperature_mode(self, mode: int) -> None:
        """Set temperature display mode (0=C, 1=F)."""
        self._post_command({"Command": "Device/SetDisTempMode", "Mode": mode})

    def set_screen_rotation(self, mode: int) -> None:
        """Set screen rotation angle mode."""
        self._post_command({"Command": "Device/SetScreenRotationAngle", "Mode": mode})

    def set_mirror_mode(self, mode: int) -> None:
        """Set mirror mode."""
        self._post_command({"Command": "Device/SetMirrorMode", "Mode": mode})

    def set_time_24_flag(self, mode: int) -> None:
        """Set 24-hour flag (1=24h, 0=12h)."""
        self._post_command({"Command": "Device/SetTime24Flag", "Mode": mode})

    def set_high_light_mode(self, mode: int) -> None:
        """Set highlight mode."""
        self._post_command({"Command": "Device/SetHighLightMode", "Mode": mode})

    def set_white_balance(self, balance: WhiteBalance | tuple[int, int, int]) -> None:
        """Set screen white balance (R,G,B)."""
        if isinstance(balance, tuple):
            balance = WhiteBalance(r=balance[0], g=balance[1], b=balance[2])
        self._post_command(
            {
                "Command": "Device/SetWhiteBalance",
                "RValue": balance.r,
                "GValue": balance.g,
                "BValue": balance.b,
            }
        )

    def get_weather_info(self) -> dict:
        """Get device weather info (device-side weather mode data)."""
        return self._post_command({"Command": "Device/GetWeatherInfo"})

    def reboot(self) -> None:
        """Reboot the device."""
        self._post_command({"Command": "Device/SysReboot"})

    def set_clock_select_id(self, clock_id: int) -> None:
        """Select clock face ID."""
        self._post_command({"Command": "Channel/SetClockSelectId", "ClockId": clock_id})

    def get_clock_info(self) -> dict:
        """Get current clock info."""
        return self._post_command({"Command": "Channel/GetClockInfo"})

    def send_display_list(self, items: Sequence[DisplayItem]) -> None:
        """Send a display item list (Draw/SendHttpItemList).

        This uses dial/display-list fonts from the Divoom font list service.
        """
        payload_items = []
        for item in items:
            payload_items.append(
                {
                    "TextId": item.text_id,
                    "type": item.item_type,
                    "x": item.x,
                    "y": item.y,
                    "dir": item.direction,
                    "font": item.font,
                    "TextWidth": item.text_width,
                    "Textheight": item.text_height,
                    "TextString": item.text or "",
                    "speed": item.speed,
                    "color": item.color,
                }
            )
        self._post_command({"Command": "Draw/SendHttpItemList", "ItemList": payload_items})

    def play_buzzer(self, active_ms: int, off_ms: int, total_ms: int) -> None:
        """Play device buzzer for a duration."""
        self._post_command(
            {
                "Command": "Device/PlayBuzzer",
                "ActiveTimeInCycle": active_ms,
                "OffTimeInCycle": off_ms,
                "PlayTotalTime": total_ms,
            }
        )

    def play_remote_gif(self, file_id: str) -> None:
        """Play a remote GIF by FileId (Draw/SendRemote)."""
        self._post_command({"Command": "Draw/SendRemote", "FileId": file_id})

    def use_http_command_source(self, url: str) -> None:
        """Use a remote HTTP command list file (Draw/UseHTTPCommandSource)."""
        self._post_command({"Command": "Draw/UseHTTPCommandSource", "Url": url})

    def set_countdown_timer(self, tool: TimerTool | tuple[int, int, int]) -> None:
        """Control countdown timer tool."""
        if isinstance(tool, tuple):
            tool = TimerTool(minute=tool[0], second=tool[1], status=tool[2])
        self._post_command(
            {
                "Command": "Tools/SetTimer",
                "Minute": tool.minute,
                "Second": tool.second,
                "Status": tool.status,
            }
        )

    def set_stopwatch(self, tool: StopWatchTool | int) -> None:
        """Control stopwatch tool."""
        if isinstance(tool, int):
            tool = StopWatchTool(status=tool)
        self._post_command({"Command": "Tools/SetStopWatch", "Status": tool.status})

    def set_scoreboard(self, tool: ScoreBoardTool | tuple[int, int]) -> None:
        """Control scoreboard tool."""
        if isinstance(tool, tuple):
            tool = ScoreBoardTool(blue_score=tool[0], red_score=tool[1])
        self._post_command(
            {
                "Command": "Tools/SetScoreBoard",
                "BlueScore": tool.blue_score,
                "RedScore": tool.red_score,
            }
        )

    def set_noise_status(self, tool: NoiseTool | int) -> None:
        """Control noise tool."""
        if isinstance(tool, int):
            tool = NoiseTool(noise_status=tool)
        self._post_command({"Command": "Tools/SetNoiseStatus", "NoiseStatus": tool.noise_status})

    @staticmethod
    def find_devices(timeout: int = 8) -> dict:
        """Find devices on local network via official service."""
        url = "https://app.divoom-gz.com/Device/ReturnSameLANDevice"
        response = requests.post(url, timeout=timeout)
        return response.json()

    @staticmethod
    def get_img_upload_list(device_id: int, device_mac: str, page: int = 1) -> dict:
        """Fetch uploaded image list from official service."""
        url = "https://app.divoom-gz.com/Device/GetImgUploadList"
        response = requests.post(
            url,
            json={"DeviceId": device_id, "DeviceMac": device_mac, "Page": page},
            timeout=8,
        )
        return response.json()

    @staticmethod
    def get_img_like_list(device_id: int, device_mac: str, page: int = 1) -> dict:
        """Fetch liked image list from official service."""
        url = "https://app.divoom-gz.com/Device/GetImgLikeList"
        response = requests.post(
            url,
            json={"DeviceId": device_id, "DeviceMac": device_mac, "Page": page},
            timeout=8,
        )
        return response.json()
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
