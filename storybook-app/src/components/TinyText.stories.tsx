import type { Meta, StoryObj } from "@storybook/react";
import { TinyText } from "./TinyText";

const meta: Meta<typeof TinyText> = {
  component: TinyText,
  title: "Pixoo/TinyText",
  argTypes: {
    variant: {
      control: "select",
      options: ["alphabet", "numbers", "alert", "warning", "success", "info", "custom"],
    },
    backgroundColor: { control: "color" },
    textColor: { control: "color" },
  },
};

export default meta;

type Story = StoryObj<typeof TinyText>;

/** Full alphabet (upper + lower). Pixel-accurate tiny font. */
export const Alphabet: Story = {
  args: {
    variant: "alphabet",
    backgroundColor: "#000",
    textColor: "#fff",
  },
};

/** Numbers and symbols. */
export const Numbers: Story = {
  args: {
    variant: "numbers",
    backgroundColor: "#000",
    textColor: "#aaa",
  },
};

/** Alert message (red). */
export const Alert: Story = {
  args: {
    variant: "alert",
    backgroundColor: "#200",
    textColor: "#f66",
  },
};

/** Warning message (yellow/amber). */
export const Warning: Story = {
  args: {
    variant: "warning",
    backgroundColor: "#330",
    textColor: "#ff0",
  },
};

/** Success message (green). */
export const Success: Story = {
  args: {
    variant: "success",
    backgroundColor: "#030",
    textColor: "#6f6",
  },
};

/** Info message (blue). */
export const Info: Story = {
  args: {
    variant: "info",
    backgroundColor: "#003",
    textColor: "#6af",
  },
};

/** Custom lines (for demos or one-off screens). */
export const Custom: Story = {
  args: {
    variant: "custom",
    lines: ["Hello", "Pixoo 64", "64x64 px"],
    backgroundColor: "#111",
    textColor: "#0f0",
  },
};
