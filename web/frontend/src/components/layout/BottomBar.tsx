import { MotorTable } from "../telemetry/MotorTable";
import { EventLog } from "../telemetry/EventLog";

export function BottomBar() {
  return (
    <div className="bg-white border-t border-gray-300 flex shrink-0 h-40 overflow-hidden">
      <div className="flex-1 border-r border-gray-300 overflow-auto p-2">
        <MotorTable />
      </div>
      <div className="w-80 overflow-auto p-2">
        <EventLog />
      </div>
    </div>
  );
}
