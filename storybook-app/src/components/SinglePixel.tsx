/**
 * Pixel alignment test: exactly one pixel at (0,0) lit up.
 * Use this story to verify pixel grid alignment on the device.
 */
import React from "react";
import { PIXOO_SIZE } from "../pixoo";

export interface SinglePixelProps {
  /** X coordinate (0 = left). */
  x?: number;
  /** Y coordinate (0 = top). */
  y?: number;
  /** Pixel color (default: white). */
  color?: string;
}

/**
 * Renders exactly one pixel at the given position. Default: top-left (0,0), white.
 */
export function SinglePixel({
  x = 0,
  y = 0,
  color = "#fff",
}: SinglePixelProps) {
  return (
    <svg
      width={PIXOO_SIZE}
      height={PIXOO_SIZE}
      viewBox={`0 0 ${PIXOO_SIZE} ${PIXOO_SIZE}`}
      style={{ display: "block", background: "#000" }}
    >
      <rect x={x} y={y} width={1} height={1} fill={color} />
    </svg>
  );
}
