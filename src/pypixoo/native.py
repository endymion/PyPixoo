"""V2 native Pixoo models for GIF upload/playback and sequencing."""

from __future__ import annotations

import threading
from enum import Enum
from typing import Callable, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field, model_validator

from pypixoo.buffer import Buffer
from pypixoo.fonts import BuiltinFont


class UploadMode(str, Enum):
    """Upload transport for Draw/SendHttpGif sequences."""

    FRAME_BY_FRAME = "frame_by_frame"
    COMMAND_LIST = "command_list"


class GifFrame(BaseModel):
    """Single frame container for sequence construction."""

    image: Buffer
    duration_ms: int = Field(default=100, ge=0)


class GifSequence(BaseModel):
    """Native HttpGif sequence: ordered frames with a device-level frame speed."""

    frames: List[GifFrame]
    speed_ms: int = Field(default=100, ge=0)


class GifSource(BaseModel):
    """Native GIF playback source for Device/PlayTFGif."""

    source_type: Literal["url", "tf_file", "tf_directory"]
    value: str

    @classmethod
    def url(cls, value: str) -> "GifSource":
        return cls(source_type="url", value=value)

    @classmethod
    def tf_file(cls, value: str) -> "GifSource":
        return cls(source_type="tf_file", value=value)

    @classmethod
    def tf_directory(cls, value: str) -> "GifSource":
        return cls(source_type="tf_directory", value=value)


class TextOverlay(BaseModel):
    """Payload model for Draw/SendHttpText.

    The device renders this text on top of the last uploaded animation.
    Built-in animation fonts are limited to IDs 0-7.
    """

    text_id: int = Field(default=1, ge=0)
    x: int = 0
    y: int = 0
    direction: int = Field(default=0, ge=0)
    font: int | BuiltinFont = Field(default=BuiltinFont.FONT_4)
    text_width: int = Field(default=64, ge=0)
    speed: int = Field(default=10, ge=0)
    text: str
    color: str = "#FFFF00"
    align: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def _validate_font_range(self) -> "TextOverlay":
        font_value = int(self.font)
        if font_value < 0 or font_value > 7:
            raise ValueError("TextOverlay font must be between 0 and 7 for Draw/SendHttpText")
        return self


class DisplayItem(BaseModel):
    """Item entry for Draw/SendHttpItemList display lists.

    Display list fonts are separate from overlay fonts and come from the
    Divoom font list services.
    """

    text_id: int = Field(default=1, ge=0)
    item_type: int = Field(..., ge=0)
    x: int = 0
    y: int = 0
    direction: int = Field(default=0, ge=0)
    font: int = Field(default=0, ge=0)
    text_width: int = Field(default=16, ge=0)
    text_height: int = Field(default=16, ge=0)
    text: Optional[str] = None
    speed: int = Field(default=10, ge=0)
    color: str = "#FFFF00"
    align: int = Field(default=1, ge=0)


class TimerTool(BaseModel):
    """Payload model for Tools/SetTimer (device countdown tool)."""

    minute: int = Field(ge=0)
    second: int = Field(ge=0)
    status: int = Field(ge=0)


class StopWatchTool(BaseModel):
    """Payload model for Tools/SetStopWatch (device stopwatch)."""

    status: int = Field(ge=0)


class ScoreBoardTool(BaseModel):
    """Payload model for Tools/SetScoreBoard (device scoreboard)."""

    blue_score: int = Field(ge=0)
    red_score: int = Field(ge=0)


class NoiseTool(BaseModel):
    """Payload model for Tools/SetNoiseStatus (device noise tool)."""

    noise_status: int = Field(ge=0)


class WhiteBalance(BaseModel):
    """Payload model for Device/SetWhiteBalance."""

    r: int = Field(ge=0)
    g: int = Field(ge=0)
    b: int = Field(ge=0)


class CycleItem(BaseModel):
    """Single cycle item executed by Pixoo.start_cycle."""

    sequence: Optional[GifSequence] = None
    source: Optional[GifSource] = None
    upload_mode: UploadMode = UploadMode.COMMAND_LIST
    chunk_size: int = Field(default=40, ge=1)

    @model_validator(mode="after")
    def _validate_one_source(self) -> "CycleItem":
        if (self.sequence is None) == (self.source is None):
            raise ValueError("CycleItem requires exactly one of sequence or source")
        return self


class CycleHandle:
    """Handle for an asynchronous cycle runner."""

    def __init__(
        self,
        thread: threading.Thread,
        stop_event: threading.Event,
        done_event: threading.Event,
    ):
        self._thread = thread
        self._stop_event = stop_event
        self._done_event = done_event

    def stop(self) -> None:
        """Signal the cycle worker to stop."""
        self._stop_event.set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for completion; returns True when finished."""
        return self._done_event.wait(timeout)

    @property
    def is_running(self) -> bool:
        """Whether the worker thread is still alive."""
        return self._thread.is_alive()


OnLoopCallback = Callable[[int], None]
OnItemCallback = Callable[[int, CycleItem], None]
CycleItems = Sequence[CycleItem]
