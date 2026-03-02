import React from "react";
import { PIXOO_SIZE } from "../pixoo";

export interface RowProps {
  /** Row top position in pixels. Origin is the top edge of the 64x64 canvas (y=0 at top). */
  y: number;
  /** Row height in pixels. */
  height: number;
  /** Optional row background fill color. */
  backgroundColor?: string;
  /** Optional bottom border height in pixels (drawn inside the row). */
  bottomBorderPx?: number;
  /** Bottom border color. Used when bottomBorderPx > 0. */
  bottomBorderColor?: string;
  children?: React.ReactNode;
}

export function Row({
  y,
  height,
  backgroundColor = "transparent",
  bottomBorderPx = 0,
  bottomBorderColor = "transparent",
  children,
}: RowProps) {
  const borderPx = Math.max(0, Math.min(height, Math.floor(bottomBorderPx)));
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        top: Math.floor(y),
        width: PIXOO_SIZE,
        height: Math.max(0, Math.floor(height)),
        background: backgroundColor,
        boxSizing: "border-box",
        borderBottom: borderPx > 0 ? `${borderPx}px solid ${bottomBorderColor}` : undefined,
        overflow: "hidden",
      }}
    >
      {children}
    </div>
  );
}

