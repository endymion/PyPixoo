"""Pixoo 64 display client."""

import base64
import json
from pathlib import Path
from typing import Union

import requests
from PIL import Image

from pypixoo.buffer import Buffer


class Pixoo:
    """Client for Divoom Pixoo 64 display."""

    SIZE = 64

    def __init__(self, ip_address: str):
        self.ip_address = ip_address
        self._url = f"http://{ip_address}/post"
        self._buffer: list[int] = []
        self._counter = 1

    def connect(self) -> bool:
        """Test connection and load GIF counter. Returns True if connected."""
        self._load_counter()
        return self._validate_connection()

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
        # Flatten to R,G,B,R,G,B...
        self._buffer = [c for pixel in self._buffer for c in pixel]

    def push(self) -> None:
        """Send the buffer to the display."""
        self._send_buffer()

    def push_buffer(self, data: list) -> None:
        """Send the given buffer data to the display without modifying internal buffer."""
        self._send_buffer_data(data)

    @property
    def buffer(self) -> Buffer:
        """Return a snapshot of the display buffer for introspection and assertions."""
        return Buffer(data=tuple(self._buffer))

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
        """Load the current GIF frame ID from the device."""
        response = requests.post(
            self._url,
            '{"Command": "Draw/GetHttpGifId"}',
            timeout=5,
        )
        data = response.json()
        if data.get("error_code", -1) != 0:
            raise RuntimeError(f"Failed to load counter: {data}")
        self._counter = int(data["PicId"])

    def _send_buffer(self) -> None:
        """Send the buffer to the device."""
        self._send_buffer_data(self._buffer)

    def _send_buffer_data(self, data: list) -> None:
        """Send the given buffer data to the device."""
        self._counter += 1
        pic_data = base64.b64encode(bytearray(data)).decode()
        payload = json.dumps({
            "Command": "Draw/SendHttpGif",
            "PicNum": 1,
            "PicWidth": self.SIZE,
            "PicOffset": 0,
            "PicID": self._counter,
            "PicSpeed": 1000,
            "PicData": pic_data,
        })
        response = requests.post(self._url, payload, timeout=5)
        response_data = response.json()
        if response_data.get("error_code", -1) != 0:
            raise RuntimeError(f"Failed to push: {response_data}")
