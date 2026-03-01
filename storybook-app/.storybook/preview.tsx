import type { Preview } from "@storybook/react";
import React from "react";
import { Clock } from "../src/components/Clock";

const PIXOO_SIZE = 64;

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
