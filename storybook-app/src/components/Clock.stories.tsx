import type { Meta, StoryObj } from "@storybook/react";
import { Clock } from "./Clock";

const markerModes = [
  "dot12",
  "dots_quarters",
  "ticks_all",
  "dots_all_thick_quarters",
  "ticks_all_thick_quarters",
] as const;

const meta: Meta<typeof Clock> = {
  component: Clock,
  title: "Pixoo/Clock",
  argTypes: {
    t: { control: { type: "range", min: 0, max: 1, step: 0.01 } },
    hour: { control: { type: "range", min: 0, max: 11, step: 1 } },
    minute: { control: { type: "range", min: 0, max: 59, step: 1 } },
    second: { control: { type: "range", min: 0, max: 59, step: 1 } },
    faceFade: { control: { type: "range", min: 0, max: 1, step: 0.05 } },
    showSecondHand: { control: "boolean" },
    hourHandColor: { control: "color" },
    minuteHandColor: { control: "color" },
    secondHandColor: { control: "color" },
    markerColor: { control: "color" },
    topMarkerColor: { control: "color" },
    markerMode: { control: "select", options: markerModes },
  },
};

export default meta;

type Story = StoryObj<typeof Clock>;

/** Single hand driven by t (0–1). Use with PyPixoo timestamps for animation. */
export const Default: Story = {
  args: {
    t: 0,
    handColor: "white",
    faceColor: "black",
  },
};

export const QuarterPast: Story = {
  args: { t: 0.25, handColor: "white", faceColor: "black" },
};

export const HalfPast: Story = {
  args: { t: 0.5, handColor: "white", faceColor: "black" },
};

/** Real time: two hands (hour + minute). */
export const Time1245: Story = {
  args: { hour: 12, minute: 45, handColor: "white", faceColor: "black" },
};

export const Time330: Story = {
  args: { hour: 3, minute: 30, handColor: "white", faceColor: "black" },
};

/** Three hands: hour, minute, second (showSecondHand true by default; secondHandColor configurable). */
export const TimeWithSeconds: Story = {
  args: {
    hour: 10,
    minute: 9,
    second: 30,
    showSecondHand: true,
    handColor: "white",
    secondHandColor: "rgba(255,100,100,0.9)",
    markerMode: "ticks_all_thick_quarters",
    faceColor: "black",
  },
};

/** Same as TimeWithSeconds but second hand at 0 (12 o'clock). Use for demos that need a non-30 second. */
export const TimeWithSecondsAtZero: Story = {
  args: {
    hour: 10,
    minute: 9,
    second: 0,
    showSecondHand: true,
    handColor: "white",
    secondHandColor: "rgba(255,100,100,0.9)",
    faceColor: "black",
  },
};

/** Time without second hand. */
export const TimeNoSecondHand: Story = {
  args: {
    hour: 2,
    minute: 15,
    showSecondHand: false,
    hourHandColor: "rgba(242,232,255,0.6)",
    minuteHandColor: "rgba(242,232,255,0.5)",
    markerColor: "rgba(255,0,255,0.5)",
    topMarkerColor: "rgba(255,0,255,0.8)",
    faceFade: 1.0,
    markerMode: "dots_all_thick_quarters",
    faceColor: "black",
  },
};
