import type { ProjectMeta } from "../types";
import { canvasPalette } from "../palette";
import { PYFII_CLASSIC_LAYOUT } from "./layout";
import { drawPanelText } from "./drawText";

function strokeRect(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number): void {
  ctx.strokeRect(x, y, width, height);
}

export function drawBackground(ctx: CanvasRenderingContext2D, meta: ProjectMeta | null): void {
  const layout = PYFII_CLASSIC_LAYOUT;
  ctx.save();
  ctx.fillStyle = canvasPalette.background;
  ctx.fillRect(0, 0, layout.canvasWidth, layout.canvasHeight);

  ctx.lineWidth = 1;
  ctx.strokeStyle = canvasPalette.border;
  strokeRect(ctx, layout.topView.x, layout.topView.y, layout.topView.width, layout.topView.height);

  for (let x = 0; x < 12; x += 1) {
    for (let y = 0; y < 12; y += 1) {
      const cellX = x === 11 ? 570 : x * 50 + 20;
      const cellY = y === 11 ? 20 : 580 - (y * 50 + 50);
      const cellWidth = x === 11 ? 10 : 50;
      const cellHeight = y === 11 ? 10 : 50;
      ctx.fillStyle = (x + y) % 2 === 0 ? canvasPalette.gridDark : canvasPalette.gridLight;
      ctx.fillRect(cellX, cellY, cellWidth, cellHeight);
    }
  }

  ctx.strokeStyle = canvasPalette.border;
  strokeRect(ctx, layout.frontView.x, layout.frontView.y, layout.frontView.width, layout.frontView.height);
  strokeRect(ctx, layout.rightView.x, layout.rightView.y, layout.rightView.width, layout.rightView.height);
  strokeRect(ctx, layout.infoGrid.x, layout.infoGrid.y, layout.infoGrid.width, layout.infoGrid.height);

  for (let tick = 0; tick < 18; tick += 1) {
    const frontY = tick * 10 + 20;
    const rightY = tick * 10 + 290;
    const length = tick % 5 === 0 ? 40 : 20;
    ctx.beginPath();
    ctx.moveTo(600, frontY);
    ctx.lineTo(600 + length, frontY);
    ctx.moveTo(600, rightY);
    ctx.lineTo(600 + length, rightY);
    ctx.stroke();
  }

  const field = meta?.field ?? 6;
  if (field === 4) {
    ctx.strokeStyle = canvasPalette.border;
    strokeRect(ctx, 20, 220, 360, 360);
    ctx.beginPath();
    ctx.moveTo(1000, 0);
    ctx.lineTo(1000, 540);
    ctx.stroke();
    drawPanelText(ctx, "4m", 386, 236, 12, canvasPalette.subtleText);
  }

  drawPanelText(ctx, "front", 604, 260);
  drawPanelText(ctx, "right", 604, 530);
  drawPanelText(ctx, meta ? `${meta.device ?? "device"} / field ${meta.field ?? "?"}` : "drop a Fii zip", 22, 24, 13, canvasPalette.subtleText);
  ctx.restore();
}
