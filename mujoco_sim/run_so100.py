#!/usr/bin/env python3
"""Run SO-ARM100 in MuJoCo viewer."""
import mujoco
import mujoco.viewer

import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "so100", "so100.xml")


def main():
    if not os.path.exists(MODEL_PATH):
        print(f"Model not found: {MODEL_PATH}")
        return

    print(f"Loading model from: {MODEL_PATH}")
    model = mujoco.MjModel.from_xml_path(MODEL_PATH)
    data = mujoco.MjData(model)

    print(f"Model loaded successfully!")
    print(f"Joints: {model.njnt}")
    print(f"Bodies: {model.nbody}")
    print(f"Actuators: {model.nu}")

    with mujoco.viewer.launch_passive(model, data) as viewer:
        print("Viewer launched. Press ESC or close the window to exit.")
        print("Controls: Click and drag to rotate, scroll to zoom, right-click to pan.")
        while viewer.is_running():
            mujoco.mj_step(model, data)
            viewer.sync()


if __name__ == "__main__":
    main()