"""Animation framework for Pixoo 64 display."""

import threading
import time
from typing import Callable, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from pypixoo.buffer import Buffer


class Frame(BaseModel):
    """Single frame in an animation sequence."""

    image: Buffer
    duration_ms: int = Field(ge=0)


class AnimationSequence(BaseModel):
    """Sequence of frames with optional background for transparency compositing."""

    frames: List[Frame]
    background: Optional[Buffer] = None


class AnimationPlayer:
    """High-level animation player: plays a sequence with loop, end-on, and blend controls."""

    def __init__(
        self,
        sequence: AnimationSequence,
        *,
        loop: Optional[int] = 1,
        end_on: Literal["last_frame", "blank"] = "last_frame",
        blank_background: Optional[Buffer] = None,
        blend_mode: Literal["opaque", "transparent"] = "opaque",
        transparent_color: Tuple[int, int, int] = (0, 0, 0),
        on_finished: Optional[Callable[[], None]] = None,
        on_loop: Optional[Callable[[int], None]] = None,
    ):
        self.sequence = sequence
        self.loop = loop
        self.end_on = end_on
        self.blank_background = blank_background
        self.blend_mode = blend_mode
        self.transparent_color = transparent_color
        self.on_finished = on_finished
        self.on_loop = on_loop
        self._thread: Optional[threading.Thread] = None
        self._done = threading.Event()

    def _composite(
        self,
        frame: Buffer,
        background: Buffer,
        transparent_color: Tuple[int, int, int],
    ) -> list:
        """Composite frame over background; transparent_color pixels show background."""
        result: list = []
        for i in range(64 * 64):
            base = i * 3
            fr = (frame.data[base], frame.data[base + 1], frame.data[base + 2])
            bg = (background.data[base], background.data[base + 1], background.data[base + 2])
            if fr == transparent_color:
                result.extend(bg)
            else:
                result.extend(fr)
        return result

    def _frame_to_push(self, frame: Frame) -> list:
        """Convert frame to flat RGB list for push, applying blend_mode."""
        if self.blend_mode == "opaque":
            return list(frame.image.data)
        # play_async validates sequence.background when blend_mode is transparent
        return self._composite(
            frame.image,
            self.sequence.background,
            self.transparent_color,
        )

    def _run(self, pixoo) -> None:
        """Run the animation loop in a background thread."""
        try:
            iterations = self.loop if self.loop is not None else 0
            loop_count = 0
            completed_loops = 0
            while iterations == 0 or loop_count < iterations:
                for frame in self.sequence.frames:
                    data = self._frame_to_push(frame)
                    pixoo.push_buffer(data)
                    if frame.duration_ms > 0:
                        time.sleep(frame.duration_ms / 1000.0)
                completed_loops += 1
                if self.on_loop is not None:
                    self.on_loop(completed_loops)
                loop_count += 1
                if iterations == 0:
                    loop_count = 0

            if self.end_on == "blank" and self.blank_background is not None:
                pixoo.push_buffer(list(self.blank_background.data))
        finally:
            if self.on_finished is not None:
                self.on_finished()
            self._done.set()

    def play_async(self, pixoo) -> None:
        """Start playback in a background thread; returns immediately."""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("Animation already playing")
        if self.blend_mode == "transparent" and self.sequence.background is None:
            raise ValueError("blend_mode 'transparent' requires sequence.background")
        self._done.clear()
        self._thread = threading.Thread(target=self._run, args=(pixoo,), daemon=True)
        self._thread.start()

    def wait(self) -> None:
        """Block until playback completes."""
        self._done.wait()
