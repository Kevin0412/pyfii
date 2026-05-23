import type { DroneFrame, RenderFrame, RenderOptions } from "../types";
import { canvasPalette, droneColor, ledColor } from "../palette";
import { frontViewPoint, rightViewPoint, topViewPoint } from "./layout";

export interface DroneViewPositions {
  top: [number, number];
  front: [number, number];
  right: [number, number];
}

export function viewPositions(drone: DroneFrame): DroneViewPositions {
  return {
    top: topViewPoint(drone.xCm, drone.yCm),
    front: frontViewPoint(drone.xCm, drone.zCm),
    right: rightViewPoint(drone.yCm, drone.zCm),
  };
}

function isF600(device: string | null | undefined): boolean {
  return String(device || "").toUpperCase() === "F600";
}

function drawLed(ctx: CanvasRenderingContext2D, drone: DroneFrame, x: number, y: number, radius: number): void {
  const led = ledColor(drone.ledRgb);
  if (!led) {
    return;
  }
  ctx.save();
  ctx.fillStyle = led;
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawTopDrone(
  ctx: CanvasRenderingContext2D,
  drone: DroneFrame,
  selected: boolean,
  device: string | null | undefined,
): void {
  const [x, y] = topViewPoint(drone.xCm, drone.yCm);
  const angle = (drone.yawDeg / 180) * Math.PI;
  const color = droneColor(drone.id, ((drone.zCm - 125) / 125) * 125);
  const smallDrone = isF600(device);
  const arm = smallDrone ? 12.6 / 2 : 21 / 2;
  const rotor = smallDrone ? 5 : 8;
  const ledRadius = smallDrone ? 3 : 5;
  const offsets = [Math.PI / 4, (3 * Math.PI) / 4, (-3 * Math.PI) / 4, -Math.PI / 4].map((offset) => ({
    x: x - arm * Math.cos(offset + angle),
    y: y + arm * Math.sin(offset + angle),
  }));

  ctx.save();
  ctx.strokeStyle = selected ? canvasPalette.selected : color;
  ctx.fillStyle = color;
  ctx.lineWidth = selected ? 3 : 2;
  ctx.beginPath();
  ctx.moveTo(offsets[0].x, offsets[0].y);
  ctx.lineTo(offsets[2].x, offsets[2].y);
  ctx.moveTo(offsets[1].x, offsets[1].y);
  ctx.lineTo(offsets[3].x, offsets[3].y);
  ctx.stroke();

  for (const point of offsets) {
    ctx.beginPath();
    ctx.arc(point.x, point.y, rotor, 0, Math.PI * 2);
    ctx.stroke();
  }

  drawLed(ctx, drone, x, y, ledRadius);
  ctx.restore();
}

function drawSideDrone(
  ctx: CanvasRenderingContext2D,
  drone: DroneFrame,
  point: [number, number],
  shade: number,
  selected: boolean,
  device: string | null | undefined,
): void {
  const [x, y] = point;
  const color = droneColor(drone.id, shade);
  const smallDrone = isF600(device);
  const bodySpan = smallDrone ? 12.6 : 21;
  const rotorX = bodySpan / Math.sqrt(2) / 2;
  const bodyY = smallDrone ? 4.0 : 7.6;
  const rotorRadiusX = smallDrone ? 5 : 8;
  const rotorRadiusY = 2;
  const ledRadius = smallDrone ? 3 : 5;
  const topY = y - bodyY / 4;
  const bottomY = y - (bodyY * 3) / 4;
  ctx.save();
  ctx.strokeStyle = selected ? canvasPalette.selected : color;
  ctx.lineWidth = selected ? 3 : 2;

  ctx.beginPath();
  ctx.ellipse(x + rotorX, topY, rotorRadiusX, rotorRadiusY, 0, 0, Math.PI * 2);
  ctx.ellipse(x - rotorX, topY, rotorRadiusX, rotorRadiusY, 0, 0, Math.PI * 2);
  ctx.ellipse(x - rotorX, bottomY, rotorRadiusX, rotorRadiusY, 0, 0, Math.PI * 2);
  ctx.ellipse(x + rotorX, bottomY, rotorRadiusX, rotorRadiusY, 0, 0, Math.PI * 2);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(x + rotorX, topY);
  ctx.lineTo(x - rotorX, bottomY);
  ctx.moveTo(x - rotorX, topY);
  ctx.lineTo(x + rotorX, bottomY);
  ctx.stroke();

  drawLed(ctx, drone, x, y - bodyY / 2, ledRadius);
  ctx.restore();
}

export function drawDrones(
  ctx: CanvasRenderingContext2D,
  frame: RenderFrame,
  options: RenderOptions,
  device?: string | null,
): void {
  const byX = [...frame.drones].sort((left, right) => left.xCm - right.xCm);
  const byY = [...frame.drones].sort((left, right) => right.yCm - left.yCm);
  const byZ = [...frame.drones].sort((left, right) => left.zCm - right.zCm);

  for (const drone of byX) {
    drawSideDrone(
      ctx,
      drone,
      rightViewPoint(drone.yCm, drone.zCm),
      ((drone.xCm - 280) / 280) * 125,
      drone.id === options.selectedDroneId,
      device,
    );
  }

  for (const drone of byY) {
    drawSideDrone(
      ctx,
      drone,
      frontViewPoint(drone.xCm, drone.zCm),
      ((280 - drone.yCm) / 280) * 125,
      drone.id === options.selectedDroneId,
      device,
    );
  }

  for (const drone of byZ) {
    drawTopDrone(ctx, drone, drone.id === options.selectedDroneId, device);
  }
}
