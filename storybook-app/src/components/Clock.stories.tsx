import type { Meta, StoryObj } from "@storybook/react";
import { Clock } from "./Clock";
import { radixDark } from "../radixColors";

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
    centerDotColor: { control: "color" },
    markerMode: { control: "select", options: markerModes },
  },
};

export default meta;

type Story = StoryObj<typeof Clock>;

/** Single hand driven by t (0–1). Use with PyPixoo timestamps for animation. */
export const Default: Story = {
  args: {
    t: 0,
    handColor: radixDark("sand", 12),
    faceColor: radixDark("sand", 1),
  },
};

export const QuarterPast: Story = {
  args: { t: 0.25, handColor: radixDark("sand", 12), faceColor: radixDark("sand", 1) },
};

export const HalfPast: Story = {
  args: { t: 0.5, handColor: radixDark("sand", 12), faceColor: radixDark("sand", 1) },
};

/** Real time: two hands (hour + minute). */
export const Time1245: Story = {
  args: { hour: 12, minute: 45, handColor: radixDark("sand", 12), faceColor: radixDark("sand", 1) },
};

export const Time330: Story = {
  args: { hour: 3, minute: 30, handColor: radixDark("sand", 12), faceColor: radixDark("sand", 1) },
};

/** Three hands: hour, minute, second (showSecondHand true by default; secondHandColor configurable). */
export const TimeWithSeconds: Story = {
  args: {
    hour: 10,
    minute: 9,
    second: 30,
    showSecondHand: true,
    handColor: radixDark("sand", 12),
    secondHandColor: radixDark("red", 9),
    markerMode: "ticks_all_thick_quarters",
    faceColor: radixDark("sand", 1),
  },
};

/** Same as TimeWithSeconds but second hand at 0 (12 o'clock). Use for demos that need a non-30 second. */
export const TimeWithSecondsAtZero: Story = {
  args: {
    hour: 10,
    minute: 9,
    second: 0,
    showSecondHand: true,
    handColor: radixDark("sand", 12),
    secondHandColor: radixDark("red", 9),
    faceColor: radixDark("sand", 1),
  },
};

/** Time without second hand. */
export const TimeNoSecondHand: Story = {
  args: {
    hour: 2,
    minute: 15,
    showSecondHand: false,
    hourHandColor: radixDark("plum", 10),
    minuteHandColor: radixDark("plum", 9),
    markerColor: radixDark("plum", 7),
    topMarkerColor: radixDark("plum", 9),
    faceFade: 1.0,
    markerMode: "dots_all_thick_quarters",
    faceColor: radixDark("sand", 1),
  },
};

/** Parity story for the tuned Python pixooclock face (dot12, no second hand). */
export const PixooclockDefault: Story = {
  args: {
    hour: 2,
    minute: 15,
    second: 0,
    showSecondHand: false,
    markerMode: "dot12",
    faceColor: radixDark("bronze", 1),
    markerColor: radixDark("bronze", 7),
    topMarkerColor: radixDark("bronze", 8),
    hourHandColor: radixDark("bronze", 10),
    minuteHandColor: radixDark("bronze", 11),
    secondHandColor: radixDark("bronze", 6),
    centerDotColor: radixDark("bronze", 7),
    hourLength: 20,
    minuteLength: 27,
    secondLength: 30,
    markerInnerRadius: 26,
    markerOuterRadius: 30,
    markerRadius: 1,
    topMarkerRadius: 2,
    quarterMarkerRadius: 2,
    markerTickThickness: 1,
    topMarkerTickThickness: 2,
    quarterMarkerTickThickness: 2,
    hourHandThickness: 2,
    minuteHandThickness: 2,
    secondHandThickness: 1,
    centerDotRadius: 1,
    faceFade: 1.0,
  },
};
