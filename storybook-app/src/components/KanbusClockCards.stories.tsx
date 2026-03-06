import type { Meta, StoryObj } from "@storybook/react";
import { KanbusCard } from "./KanbusCard";

const meta: Meta<typeof KanbusCard> = {
  component: KanbusCard,
  title: "Pixoo/KanbusClockCards",
  args: {
    idPrefix: "PIXO",
    issueType: "task",
    status: "INPROGRESS",
    kind: "created",
    issueLines: ["Implement card redesign", "for kanbus clock", "and verify on device"],
  },
  argTypes: {
    issueType: {
      control: "select",
      options: ["task", "bug", "story", "epic", "unknown"],
    },
    kind: {
      control: "select",
      options: ["created", "transition", "comment", "unknown"],
    },
  },
};

export default meta;
type Story = StoryObj<typeof KanbusCard>;

export const CreatedWithParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "task",
    status: "INPROGRESS",
    kind: "created",
    parentLines: [
      "Clock reliability workstream",
      "phase 2 acceptance checks",
      "nightly stabilization tasks",
    ],
    issueLines: [
      "Implement metadata-header",
      "card layout for transitions",
      "and created events now",
      "with final visual pass",
    ],
  },
};

export const CreatedWithoutParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "story",
    status: "OPEN",
    kind: "created",
    issueLines: [
      "User can trigger alerts",
      "from watcher events in",
      "kanbus clock repl mode",
      "while keeping smooth",
      "clock rendering active",
      "without frame stalls",
      "during queue bursts",
    ],
  },
};

export const TransitionWithParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "epic",
    status: "INPROGRESS",
    kind: "transition",
    parentLines: [
      "Workspace discovery",
      "quality and correctness",
      "follow-up integration",
    ],
    issueLines: [
      "Switched to single-root",
      "kbs usage and added",
      "project-root show path",
      "for reliable metadata",
    ],
  },
};

export const TransitionWithoutParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "bug",
    status: "DONE",
    kind: "transition",
    issueLines: [
      "Fixed NO DESCRIPTION",
      "by passing project-root",
      "into kbs show calls",
      "and validating in",
      "live device loop",
      "after restart cycles",
      "across multiple repos",
    ],
  },
};

export const CommentCard: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "task",
    status: "INPROGRESS",
    kind: "comment",
    issueLines: [
      "Clock remains default",
      "between event cards",
    ],
    commentLines: [
      "Need tighter wrap and",
      "consistent spacing for",
      "comment body rows now",
    ],
  },
};

export const UnknownEventFallback: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "unknown",
    status: "OPEN",
    kind: "unknown",
    issueLines: [
      "EVENT RETRIED",
      "unknown payload type",
      "watcher kept running",
      "no transition crash",
      "clock returned safely",
    ],
  },
};

export const LongHeaderOverflow: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "task",
    status: "REOPENEDFORVALIDATION",
    kind: "created",
    issueLines: [
      "Header intentionally",
      "overflows to verify",
      "left-justified behavior",
      "without truncation",
      "in storybook preview",
      "before device tuning",
      "for final acceptance",
    ],
  },
};

export const TypeColorTask: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "task",
    status: "INPROGRESS",
    kind: "created",
    issueLines: ["Task palette check"],
  },
};

export const TypeColorBug: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "bug",
    status: "OPEN",
    kind: "created",
    issueLines: ["Bug palette check"],
  },
};

export const TypeColorStory: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "story",
    status: "OPEN",
    kind: "created",
    issueLines: ["Story palette check"],
  },
};

export const TypeColorEpic: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "epic",
    status: "OPEN",
    kind: "created",
    issueLines: ["Epic palette check"],
  },
};

