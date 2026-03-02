/**
 * Single letter "A" at top-left in Tiny5 for font/screen testing.
 * Positioned flush to (0,0); line-height 1 and no padding.
 */
import React from "react";
import { PIXOO_SIZE } from "../pixoo";

const FONT_FAMILY = "'Tiny5', monospace";
const FONT_SIZE_PX = 5;

export function LetterA() {
  return (
    <div
      style={{
        width: PIXOO_SIZE,
        height: PIXOO_SIZE,
        position: "relative",
        overflow: "hidden",
        background: "#000",
        color: "#fff",
        fontFamily: FONT_FAMILY,
        fontSize: FONT_SIZE_PX,
        lineHeight: 1,
        padding: 0,
        boxSizing: "border-box",
        WebkitFontSmoothing: "none",
        MozOsxFontSmoothing: "unset",
        fontSmooth: "never",
      }}
    >
      <span style={{ position: "absolute", left: 0, top: 0 }}>
        A
      </span>
    </div>
  );
}
