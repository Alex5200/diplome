import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, GizmoHelper, GizmoViewport } from "@react-three/drei";
import { RobotModel } from "./RobotModel";
import { JointSliders } from "../controls/JointSliders";

export function RobotScene() {
  return (
    <div className="relative w-full h-full">
      <Canvas
        camera={{ position: [3, 2.5, 3], fov: 50, near: 0.01, far: 100 }}
        className="bg-gray-950"
      >
        <ambientLight intensity={0.4} />
        <directionalLight position={[5, 8, 5]} intensity={0.8} />
        <directionalLight position={[-3, 4, -3]} intensity={0.3} />

        <RobotModel />

        <Grid
          args={[10, 10]}
          cellSize={0.5}
          cellThickness={0.5}
          cellColor="#1f2937"
          sectionSize={2}
          sectionThickness={1}
          sectionColor="#374151"
          fadeDistance={10}
          infiniteGrid
        />

        <OrbitControls
          makeDefault
          maxPolarAngle={Math.PI * 0.85}
          minDistance={1}
          maxDistance={8}
        />

        <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
          <GizmoViewport labelColor="white" axisHeadScale={0.8} />
        </GizmoHelper>
      </Canvas>

      {/* Joint sliders overlay */}
      <div className="absolute bottom-3 left-3 bg-gray-900/90 backdrop-blur-sm border border-gray-800 rounded-lg p-3 w-80">
        <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">
          Joint Control
        </div>
        <JointSliders />
      </div>
    </div>
  );
}
