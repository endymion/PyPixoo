/**
 * Pixel-accurate tiny text for Pixoo 64 (64×64). Uses Tiny5 or similar small pixel font.
 * Designed for crisp rendering: integer font size, no scaling, no anti-aliasing.
 */
import React from "react";
import { PIXOO_SIZE } from "../pixoo";

const FONT_FAMILY = "'Tiny5', monospace";
/** Font size in pixels (integer for pixel-perfect). Tiny5 is readable at 5–6px. */
const FONT_SIZE_PX = 5;
/** Line height must fit font metrics (ascender + descender); too small clips the bottom of glyphs. */
const LINE_HEIGHT_PX = 8;
const PADDING = 2;

export interface TinyTextProps {
  /** Background color (CSS) */
  backgroundColor?: string;
  /** Text color (CSS) */
  textColor?: string;
  /** Content: one of the preset variants or custom lines */
  variant?: "alphabet" | "numbers" | "alert" | "warning" | "success" | "info" | "custom";
  /** For variant "custom", the lines to show (each line is one row). */
  lines?: string[];
}

const PRESETS: Record<string, string[]> = {
  alphabet: [
    "ABCDEFGHIJKLM",
    "NOPQRSTUVWXYZ",
    "abcdefghijklm",
    "nopqrstuvwxyz",
  ],
  numbers: [
    "0123456789",
    "!@#$%^&*()",
    "+-=/.,<>?;':",
    "[ ] { }",
  ],
  alert: [
    "ALERT",
    "",
    "Check device",
    "status now.",
  ],
  warning: [
    "WARNING",
    "",
    "Low battery.",
    "Plug in soon.",
  ],
  success: [
    "OK",
    "",
    "All systems",
    "nominal.",
  ],
  info: [
    "INFO",
    "",
    "Pixoo 64",
    "64x64 px",
  ],
};

function getLines(props: TinyTextProps): string[] {
  if (props.variant === "custom" && props.lines?.length) return props.lines;
  const key = props.variant ?? "alphabet";
  return PRESETS[key] ?? PRESETS.alphabet;
}

/**
 * Full-screen 64×64 tiny text. Use integer font size and pixel-aligned layout
 * so screenshots stay crisp on the device.
 */
export function TinyText({
  backgroundColor = "#000",
  textColor = "#fff",
  variant = "alphabet",
  lines,
}: TinyTextProps) {
  const displayLines = getLines({ variant, lines });

  return (
    <div
      style={{
        width: PIXOO_SIZE,
        height: PIXOO_SIZE,
        overflow: "hidden",
        background: backgroundColor,
        color: textColor,
        fontFamily: FONT_FAMILY,
        fontSize: FONT_SIZE_PX,
        lineHeight: LINE_HEIGHT_PX,
        padding: PADDING,
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-evenly",
        // Keep text crisp: no subpixel, no smoothing
        WebkitFontSmoothing: "none",
        MozOsxFontSmoothing: "unset",
        fontSmooth: "never",
      }}
    >
      {displayLines.map((line, i) => (
        <div
          key={i}
          style={{
            height: LINE_HEIGHT_PX,
            overflow: "hidden",
            display: "flex",
            alignItems: "center",
          }}
        >
          {line || " "}
        </div>
      ))}
    </div>
  );
}
