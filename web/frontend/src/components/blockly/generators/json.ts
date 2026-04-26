import type { ProgramCommand } from "../../../types/robot";

interface BlockData {
  type: string;
  fields: Record<string, string>;
  inputs?: Record<string, { block?: BlockData }>;
  next?: { block?: BlockData };
}

function blockToCommands(block: BlockData | undefined): ProgramCommand[] {
  if (!block) return [];
  const commands: ProgramCommand[] = [];

  let current: BlockData | undefined = block;
  while (current) {
    switch (current.type) {
      case "move_joint":
        commands.push({
          type: "move",
          params: {
            joint: Number(current.fields.JOINT),
            angle: Number(current.fields.ANGLE),
            speed: Number(current.fields.SPEED || 2400),
          },
        });
        break;
      case "move_ik":
        commands.push({
          type: "move_ik",
          params: {
            x: Number(current.fields.X),
            y: Number(current.fields.Y),
            z: Number(current.fields.Z),
          },
        });
        break;
      case "wait_seconds":
        commands.push({
          type: "wait",
          params: { seconds: Number(current.fields.SECONDS) },
        });
        break;
      case "move_home":
        commands.push({ type: "home", params: {} });
        break;
      case "repeat_times": {
        const times = Number(current.fields.TIMES);
        const body = blockToCommands(current.inputs?.DO?.block);
        for (let i = 0; i < times; i++) {
          commands.push(...body);
        }
        break;
      }
    }
    current = current.next?.block;
  }

  return commands;
}

export function workspaceToCommands(
  workspace: { getTopBlocks: (ordered: boolean) => { toJSON: () => BlockData }[] }
): ProgramCommand[] {
  const commands: ProgramCommand[] = [];
  const topBlocks = workspace.getTopBlocks(true);
  for (const block of topBlocks) {
    commands.push(...blockToCommands(block.toJSON()));
  }
  return commands;
}
