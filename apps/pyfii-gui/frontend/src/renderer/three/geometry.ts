export interface DroneGeometrySpec {
  motorRadius: number;
  rotorRadius: number;
  bodyRadius: number;
}

export interface ViewportSize {
  width: number;
  height: number;
}

// SSAA only enlarges the backing buffer. Camera projection continues to use
// the logical viewport so changing sample density cannot change composition.
export function logicalViewportSize(
  backingWidth: number,
  backingHeight: number,
  ssaa: number,
): ViewportSize {
  const sampleScale = Number.isFinite(ssaa) && ssaa > 0 ? ssaa : 1;
  return {
    width: Math.max(1, backingWidth / sampleScale),
    height: Math.max(1, backingHeight / sampleScale),
  };
}

export function perspectiveFovDegrees(viewportHeight: number, projectionDistance: number): number {
  const radians = 2 * Math.atan(viewportHeight / (2 * projectionDistance));
  return Math.min(82, Math.max(18, radians * 180 / Math.PI));
}

// Match the OpenCV viewer: crossing either horizontal boundary continues
// from the equivalent angle on the other side.
export function wrapHorizontalAngle(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return ((value + 180) % 360 + 360) % 360 - 180;
}

export function droneGeometrySpec(device: string | null | undefined): DroneGeometrySpec {
  if (String(device || "").toUpperCase() === "F600") {
    return {
      motorRadius: 12.6 / 2,
      rotorRadius: 17.5 / 2 - (12.6 / 4) * Math.SQRT2,
      bodyRadius: 6.7 / 2,
    };
  }
  return {
    motorRadius: 21 / 2,
    rotorRadius: 14.9 - (21 / 4) * Math.SQRT2,
    bodyRadius: 5,
  };
}

// Core places each motor on a 45-degree diagonal. motorRadius is the
// center-to-motor distance, so each local axis gets radius / sqrt(2).
export function motorAxisOffset(spec: DroneGeometrySpec): number {
  return spec.motorRadius / Math.SQRT2;
}
