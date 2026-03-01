"""Pixoo 64 display client."""

import base64
import json
import requests


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

    def push(self) -> None:
        """Send the buffer to the display."""
        self._send_buffer()

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
        self._counter += 1
        pic_data = base64.b64encode(bytearray(self._buffer)).decode()
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
        data = response.json()
        if data.get("error_code", -1) != 0:
            raise RuntimeError(f"Failed to push: {data}")
