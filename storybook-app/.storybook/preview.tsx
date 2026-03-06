import type { Preview } from "@storybook/react";
import React from "react";
import { Clock } from "../src/components/Clock";

const PIXOO_SIZE = 64;

declare global {
  interface Window {
    __pixooReady?: boolean;
    __pixooReadyError?: string;
  }
}

if (typeof window !== "undefined") {
  window.__pixooReady = false;
  const markReady = () => {
    // Give the browser one paint after fonts resolve so glyph rasters settle.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        window.__pixooReady = true;
      });
    });
  };
  const failReady = (reason: string) => {
    window.__pixooReadyError = reason;
    window.__pixooReady = false;
  };
  const waitForPixooFonts = async () => {
    try {
      if (!document.fonts || !document.fonts.ready || !document.fonts.check) {
        failReady("document.fonts API unavailable");
        return;
      }
      await document.fonts.ready;
      for (const fontName of ["Tiny5", "Bytesized"]) {
        await Promise.race([
          Promise.resolve(document.fonts.load(`8px "${fontName}"`)),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error(`Timed out loading ${fontName}`)), 2000)
          ),
        ]);
      }
      if (!document.fonts.check('5px "Tiny5"')) {
        failReady("Tiny5 font not available");
        return;
      }
      if (!document.fonts.check('8px "Bytesized"')) {
        failReady("Bytesized font not available");
        return;
      }
      markReady();
    } catch {
      failReady("Pixoo font load failed");
    }
  };
  void waitForPixooFonts();
}

/** Parse hour, minute, second (and optional colors) from URL for realtime clock demo. */
function getClockParamsFromUrl(): {
  hour?: number;
  minute?: number;
  second?: number;
  faceColor?: string;
  handColor?: string;
  showSecondHand?: boolean;
  secondHandColor?: string;
} | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const hour = params.get("hour");
  const minute = params.get("minute");
  const second = params.get("second");
  if (hour === null || minute === null || second === null) return null;
  const h = parseInt(hour, 10);
  const m = parseInt(minute, 10);
  const s = parseInt(second, 10);
  if (Number.isNaN(h) || Number.isNaN(m) || Number.isNaN(s)) return null;
  const out: ReturnType<typeof getClockParamsFromUrl> = {
    hour: h % 12,
    minute: m % 60,
    second: s % 60,
  };
  const face = params.get("faceColor");
  const hand = params.get("handColor");
  const showSecond = params.get("showSecondHand");
  const secondHand = params.get("secondHandColor");
  if (face != null) out.faceColor = face;
  if (hand != null) out.handColor = hand;
  if (showSecond != null) out.showSecondHand = showSecond !== "false" && showSecond !== "0";
  if (secondHand != null) out.secondHandColor = secondHand;
  return out;
}

const preview: Preview = {
  parameters: {
    layout: "fullscreen",
    viewport: {
      defaultViewport: "pixoo64",
      viewports: {
        pixoo64: {
          name: "Pixoo 64",
          styles: { width: `${PIXOO_SIZE}px`, height: `${PIXOO_SIZE}px` },
          type: "responsive",
        },
      },
    },
  },
  decorators: [
    (Story, context) => {
      const urlParams =
        context.id === "pixoo-clock--time-with-seconds"
          ? getClockParamsFromUrl()
          : null;
      if (urlParams != null) {
        return (
          <div
            style={{
              width: PIXOO_SIZE,
              height: PIXOO_SIZE,
              overflow: "hidden",
              background: "#000",
            }}
          >
            <Clock {...context.args} {...urlParams} />
          </div>
        );
      }
      return (
        <div
          style={{
            width: PIXOO_SIZE,
            height: PIXOO_SIZE,
            overflow: "hidden",
            background: "#000",
          }}
        >
          <Story />
        </div>
      );
    },
  ],
};

export default preview;
