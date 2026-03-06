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
    parentType: {
      control: "select",
      options: ["epic", "initiative", "unknown"],
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
    parentType: "epic",
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
      "while preserving spacing",
      "across story variants",
      "and device playback",
      "during long runtimes",
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
      "with deterministic flow",
      "across transition loops",
      "under heavy event load",
      "for real-device checks",
    ],
  },
};

export const TransitionWithParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "epic",
    status: "INPROGRESS",
    kind: "transition",
    parentType: "initiative",
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
      "across nested projects",
      "with clearer prefixes",
      "for display rendering",
      "under queue pressure",
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
      "with robust parsing",
      "and stable card text",
      "for transition views",
      "during rapid updates",
    ],
  },
};

export const CommentTaskWithoutParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "task",
    status: "IN PROGRESS",
    kind: "comment",
    issueLines: [
      "Clock remains default",
      "between event cards",
    ],
    commentLines: [
      "Need tighter wrap and",
      "consistent spacing for",
      "comment body rows now",
      "while keeping header",
      "readability on device",
      "during transition runs",
      "with extra content",
      "filling final row",
      "for no-parent case",
    ],
  },
};

export const CommentTaskWithParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "task",
    status: "IN PROGRESS",
    kind: "comment",
    parentType: "epic",
    parentLines: [
      "Clock runtime initiative",
      "phase 3 visual polish",
      "manual acceptance wave",
    ],
    issueLines: [
      "Task under parent epic",
      "header spacing polish",
    ],
    commentLines: [
      "Task comment sample",
      "verify parent context",
      "stays readable on card",
      "while preserving color",
      "contrast and spacing",
      "for late-night viewing",
    ],
  },
};

export const CommentStoryWithoutParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "story",
    status: "IN PROGRESS",
    kind: "comment",
    issueLines: [
      "Standalone story issue",
      "without parent linkage",
    ],
    commentLines: [
      "Story comment sample",
      "body layout check",
      "contrast and spacing",
      "across multiple rows",
      "and varied issue types",
      "during queue playback",
      "with added test text",
      "to hit lower rows",
      "in no-parent cards",
    ],
  },
};

export const CommentStoryWithParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "story",
    status: "IN PROGRESS",
    kind: "comment",
    parentType: "epic",
    parentLines: [
      "Epic: scene transitions",
      "and information cards",
      "clock integration pass",
    ],
    issueLines: [
      "Story under an epic",
      "comment layout review",
    ],
    commentLines: [
      "Story w/ parent case",
      "check top rows + body",
      "for alignment fidelity",
      "under sustained loops",
      "with transition timing",
      "and clipping behavior",
    ],
  },
};

export const CommentBugWithoutParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "bug",
    status: "IN PROGRESS",
    kind: "comment",
    issueLines: [
      "Standalone bug issue",
      "without parent link",
    ],
    commentLines: [
      "Bug comment sample",
      "repro steps updated",
      "needs final verification",
      "after spacing fixes",
      "and color refinements",
      "on the real device",
      "plus deeper details",
      "for row capacity",
      "validation on screen",
    ],
  },
};

export const CommentBugWithParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "bug",
    status: "IN PROGRESS",
    kind: "comment",
    parentType: "epic",
    parentLines: [
      "Epic: rendering parity",
      "React and device sync",
      "acceptance hardening",
    ],
    issueLines: [
      "Bug under parent epic",
      "font spacing regression",
    ],
    commentLines: [
      "Bug w/ parent case",
      "confirm alert contrast",
      "and typography behavior",
      "under repeated scene",
      "transitions and queue",
      "burst conditions now",
    ],
  },
};

export const CommentEpicWithoutParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "epic",
    status: "IN PROGRESS",
    kind: "comment",
    issueLines: [
      "Standalone epic issue",
      "no initiative parent",
    ],
    commentLines: [
      "Epic comment sample",
      "high-level update text",
      "for wide-scope work",
      "with stable rendering",
      "across all variants",
      "in nightly testing",
      "including overflow",
      "checks for bottom",
      "no-parent text rows",
    ],
  },
};

export const CommentEpicWithParent: Story = {
  args: {
    idPrefix: "PIXO",
    issueType: "epic",
    status: "IN PROGRESS",
    kind: "comment",
    parentType: "initiative",
    parentLines: [
      "Initiative: display UX",
      "cross-project alignment",
      "design system rollout",
    ],
    issueLines: [
      "Epic under initiative",
      "card behavior changes",
    ],
    commentLines: [
      "Epic w/ parent case",
      "initiative context note",
      "ready for review",
      "after integrating card",
      "layout improvements in",
      "storybook and device",
    ],
  },
};

// Keep existing story ID used by the running React demo.
export const CommentCard = CommentTaskWithoutParent;

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
