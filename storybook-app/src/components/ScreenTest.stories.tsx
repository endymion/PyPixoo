import type { Meta, StoryObj } from "@storybook/react";
import { SinglePixel } from "./SinglePixel";
import { StripePattern } from "./StripePattern";
import { LetterA } from "./LetterA";

const meta: Meta = {
  title: "Pixoo/ScreenTest",
};

export default meta;

/** One white pixel at top-left (0,0). */
export const SinglePixelTopLeft: StoryObj = {
  render: () => <SinglePixel x={0} y={0} color="#fff" />,
};

/** Vertical strips: every-other pixel on, one blank column between strips. */
export const StripePatternStory: StoryObj = {
  render: () => <StripePattern />,
};

/** Single letter "A" at top-left (Tiny5 font). For font rendering tests. */
export const LetterAStory: StoryObj = {
  render: () => <LetterA />,
};
