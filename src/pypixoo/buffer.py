"""Display buffer model for introspection and assertions."""

from pydantic import BaseModel, Field


class Buffer(BaseModel):
    """Immutable 64×64 RGB display buffer with introspection for assertions."""

    width: int = Field(default=64, frozen=True)
    height: int = Field(default=64, frozen=True)
    data: tuple[int, ...] = Field(..., min_length=64 * 64 * 3, max_length=64 * 64 * 3)

    @classmethod
    def from_flat_list(cls, data: list) -> "Buffer":
        """Create a Buffer from a flat list of RGB values (R,G,B,R,G,B,...)."""
        return cls(data=tuple(data))

    def get_pixel(self, x: int, y: int) -> tuple[int, int, int]:
        """Return RGB at (x, y). (0,0) is top-left."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Pixel ({x}, {y}) out of range {self.width}x{self.height}")
        i = (y * self.width + x) * 3
        return (self.data[i], self.data[i + 1], self.data[i + 2])
