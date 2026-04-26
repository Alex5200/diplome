import { useMemo } from "react";
import { useRobotStore } from "../../stores/robotStore";
import { forwardKinematics } from "../../utils/kinematics";
import { SCALE, LINK_COLORS } from "../../utils/constants";
import * as THREE from "three";

function JointSphere({ position, color }: { position: THREE.Vector3; color: string }) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[0.04, 16, 16]} />
      <meshStandardMaterial color={color} metalness={0.3} roughness={0.6} />
    </mesh>
  );
}

function LinkCylinder({
  start,
  end,
  color,
}: {
  start: THREE.Vector3;
  end: THREE.Vector3;
  color: string;
}) {
  const { position, quaternion, length } = useMemo(() => {
    const dir = new THREE.Vector3().subVectors(end, start);
    const len = dir.length();
    const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
    const quat = new THREE.Quaternion();
    if (len > 0.001) {
      const up = new THREE.Vector3(0, 1, 0);
      quat.setFromUnitVectors(up, dir.normalize());
    }
    return { position: mid, quaternion: quat, length: len };
  }, [start, end]);

  if (length < 0.001) return null;

  return (
    <mesh position={position} quaternion={quaternion}>
      <cylinderGeometry args={[0.02, 0.02, length, 8]} />
      <meshStandardMaterial color={color} metalness={0.4} roughness={0.5} />
    </mesh>
  );
}

function EndEffectorAxes({ position }: { position: THREE.Vector3 }) {
  const size = 0.12;
  return (
    <group position={position}>
      <arrowHelper args={[new THREE.Vector3(1, 0, 0), undefined, size, 0xff4444, 0.03, 0.02]} />
      <arrowHelper args={[new THREE.Vector3(0, 1, 0), undefined, size, 0x44ff44, 0.03, 0.02]} />
      <arrowHelper args={[new THREE.Vector3(0, 0, 1), undefined, size, 0x4444ff, 0.03, 0.02]} />
    </group>
  );
}

function BasePlatform() {
  return (
    <mesh position={[0, -0.02, 0]}>
      <cylinderGeometry args={[0.12, 0.14, 0.04, 24]} />
      <meshStandardMaterial color="#6b7280" metalness={0.6} roughness={0.3} />
    </mesh>
  );
}

export function RobotModel() {
  const jointAngles = useRobotStore((s) => s.jointAngles);

  const positions = useMemo(() => {
    const fk = forwardKinematics(jointAngles);
    // Конвертация мм → единицы сцены, ось Y вверх (Z в kinematics → Y в Three.js)
    return fk.map(
      ([x, y, z]) =>
        new THREE.Vector3(x * SCALE, z * SCALE, -y * SCALE)
    );
  }, [jointAngles]);

  return (
    <group>
      <BasePlatform />

      {/* Links */}
      {positions.slice(0, -1).map((start, i) => (
        <LinkCylinder
          key={`link-${i}`}
          start={start}
          end={positions[i + 1]}
          color={LINK_COLORS[i % LINK_COLORS.length]}
        />
      ))}

      {/* Joints */}
      {positions.map((pos, i) => (
        <JointSphere
          key={`joint-${i}`}
          position={pos}
          color={i === 0 ? "#6b7280" : LINK_COLORS[(i - 1) % LINK_COLORS.length]}
        />
      ))}

      {/* End effector axes */}
      <EndEffectorAxes position={positions[positions.length - 1]} />
    </group>
  );
}
