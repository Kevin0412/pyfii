import type { RenderInput } from "../types";
import { drawBackground } from "./drawBackground";
import { drawDrones } from "./drawDrone";
import { drawSafetyMarkers } from "./drawSafety";
import { drawInfoGrid } from "./drawText";
import { PYFII_CLASSIC_LAYOUT } from "./layout";

export class PyfiiCanvasRenderer {
  private readonly canvas: HTMLCanvasElement;
  private readonly ctx: CanvasRenderingContext2D;

  constructor(canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      throw new Error("2D canvas context is not available.");
    }
    this.canvas = canvas;
    this.ctx = ctx;
    this.ctx.imageSmoothingEnabled = false;
    this.resizeForDevicePixelRatio();
  }

  resizeForDevicePixelRatio(): void {
    const rect = this.canvas.getBoundingClientRect();
    const cssWidth = rect.width || PYFII_CLASSIC_LAYOUT.canvasWidth;
    const cssHeight = rect.height || cssWidth / 2 || PYFII_CLASSIC_LAYOUT.canvasHeight;
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round(cssWidth * dpr));
    const height = Math.max(1, Math.round(cssHeight * dpr));

    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    this.ctx.imageSmoothingEnabled = false;
  }

  draw(input: RenderInput): void {
    this.resizeForDevicePixelRatio();
    const scaleX = this.canvas.width / PYFII_CLASSIC_LAYOUT.canvasWidth;
    const scaleY = this.canvas.height / PYFII_CLASSIC_LAYOUT.canvasHeight;

    this.ctx.save();
    this.ctx.setTransform(scaleX, 0, 0, scaleY, 0, 0);
    this.ctx.clearRect(0, 0, PYFII_CLASSIC_LAYOUT.canvasWidth, PYFII_CLASSIC_LAYOUT.canvasHeight);
    drawBackground(this.ctx, input.meta);
    drawDrones(this.ctx, input.frame, input.options);
    if (input.options.showSafetyMarkers) {
      drawSafetyMarkers(this.ctx, input.frame, input.safetyEvents);
    }
    drawInfoGrid(this.ctx, input.frame, input.options);
    this.ctx.restore();
  }
}
