export const toolbox = {
  kind: "categoryToolbox",
  contents: [
    {
      kind: "category",
      name: "Движение",
      colour: 160,
      contents: [
        { kind: "block", type: "move_joint" },
        { kind: "block", type: "move_ik" },
        { kind: "block", type: "move_home" },
      ],
    },
    {
      kind: "category",
      name: "Управление",
      colour: 260,
      contents: [
        { kind: "block", type: "repeat_times" },
        { kind: "block", type: "wait_seconds" },
      ],
    },
  ],
};
