import { create } from "zustand";
import type { ProgramCommand } from "../types/robot";

interface ProgramState {
  commands: ProgramCommand[];
  setCommands: (commands: ProgramCommand[]) => void;

  isRunning: boolean;
  currentStep: number;
  setRunning: (running: boolean) => void;
  setCurrentStep: (step: number) => void;

  blocklyXml: string;
  setBlocklyXml: (xml: string) => void;
}

export const useProgramStore = create<ProgramState>((set) => ({
  commands: [],
  setCommands: (commands) => set({ commands }),

  isRunning: false,
  currentStep: -1,
  setRunning: (isRunning) => set({ isRunning }),
  setCurrentStep: (currentStep) => set({ currentStep }),

  blocklyXml: "",
  setBlocklyXml: (blocklyXml) => set({ blocklyXml }),
}));
