import type { RenderFrame, SafetyEvent } from "../types";
import { canvasPalette } from "../palette";
import { viewPositions } from "./drawDrone";

function drawCircle(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number): void {
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.stroke();
}

export function drawSafetyMarkers(
  ctx: CanvasRenderingContext2D,
  frame: RenderFrame,
  events: SafetyEvent[],
): void {
  const activeIds = new Set<number>();

  for (const event of events) {
    if (event.level !== "error" || Math.abs(event.time_ms - frame.timeMs) >= 500) {
      continue;
    }
    if (event.drone_a) {
      activeIds.add(event.drone_a);
    }
    if (event.drone_b) {
      activeIds.add(event.drone_b);
    }
  }

  if (activeIds.size === 0) {
    return;
  }

  ctx.save();
  ctx.strokeStyle = canvasPalette.error;
  ctx.lineWidth = 3;
  ctx.setLineDash([8, 4]);

  for (const drone of frame.drones) {
    if (!activeIds.has(drone.id)) {
      continue;
    }
    const positions = viewPositions(drone);
    drawCircle(ctx, positions.top[0], positions.top[1], 22);
    drawCircle(ctx, positions.front[0], positions.front[1], 18);
    drawCircle(ctx, positions.right[0], positions.right[1], 18);
  }

  ctx.restore();
}
