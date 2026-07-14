import * as THREE from "three";

import { droneRgb } from "../palette";
import type { DroneFrame, RenderInput, SafetyEvent, ThreeRenderSettings } from "../types";
import { droneGeometrySpec, motorAxisOffset } from "./geometry";

type DroneRenderParts = {
  device: string;
  renderScale: number;
  group: THREE.Group;
  body: THREE.Mesh;
  led: THREE.Mesh;
  marker: THREE.Mesh;
  projectionLine: THREE.Mesh;
  shadow: THREE.Mesh;
};

const BASE_WIDTH = 1200;
const BASE_HEIGHT = 600;
const HEIGHT_MAX = 300;
const GRAVITY_CM_S2 = 980;
const LOCAL_UP = new THREE.Vector3(0, 1, 0);
const wingForce = new THREE.Vector3();
const tiltQuaternion = new THREE.Quaternion();
const yawQuaternion = new THREE.Quaternion();

function setDroneAttitude(
  target: THREE.Quaternion,
  acceleration: [number, number, number],
  yawDeg: number,
): void {
  const [ax, ay, az] = acceleration;

  // core: wing_force = acceleration - (0, 0, -980)
  // PyFii (x, y, z) maps to Three.js (x, z, -y).
  wingForce.set(ax, az + GRAVITY_CM_S2, -ay);
  const lengthSquared = wingForce.lengthSq();
  if (!Number.isFinite(lengthSquared) || lengthSquared < 1e-12) {
    wingForce.copy(LOCAL_UP);
  } else {
    wingForce.multiplyScalar(1 / Math.sqrt(lengthSquared));
  }

  tiltQuaternion.setFromUnitVectors(LOCAL_UP, wingForce);
  yawQuaternion.setFromAxisAngle(LOCAL_UP, THREE.MathUtils.degToRad(yawDeg));
  target.copy(tiltQuaternion).multiply(yawQuaternion).normalize();
}

function fieldSize(field: number | null | undefined): number {
  return field === 4 ? 360 : 560;
}

function fieldCenter(field: number | null | undefined): THREE.Vector3 {
  const center = field === 4 ? 180 : 280;
  return new THREE.Vector3(center, 165, -center);
}

function pyfiiPoint(x: number, y: number, z: number): THREE.Vector3 {
  return new THREE.Vector3(x, z, -y);
}

function colorFromRgb(rgb: [number, number, number]): THREE.Color {
  return new THREE.Color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255);
}

function ledOrDroneColor(drone: DroneFrame): THREE.Color {
  const [r, g, b] = drone.ledRgb;
  if (r >= 0 && g >= 0 && b >= 0) {
    return colorFromRgb([r, g, b]);
  }
  return colorFromRgb(droneRgb(drone.id));
}

function ledIsOn(drone: DroneFrame): boolean {
  const [r, g, b] = drone.ledRgb;
  return r >= 0 && g >= 0 && b >= 0;
}

function cameraDirection(aDeg: number, bDeg: number): THREE.Vector3 {
  const a = THREE.MathUtils.degToRad(aDeg);
  const b = THREE.MathUtils.degToRad(bDeg);
  return new THREE.Vector3(
    Math.cos(a) * Math.cos(b),
    Math.sin(b),
    -Math.sin(a) * Math.cos(b),
  ).normalize();
}

function materialColor(material: THREE.Material | THREE.Material[], color: THREE.Color): void {
  if (Array.isArray(material)) return;
  const colored = material as THREE.Material & { color?: THREE.Color; emissive?: THREE.Color };
  colored.color?.copy(color);
  colored.emissive?.copy(color);
}

function makeTextSprite(text: string, color = "#d8d8d8"): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 160;
  canvas.height = 40;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = "20px monospace";
    ctx.fillStyle = color;
    ctx.fillText(text, 2, 26);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true }));
  sprite.scale.set(44, 11, 1);
  return sprite;
}

export class PyfiiThreeRenderer {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene = new THREE.Scene();
  private readonly perspectiveCamera = new THREE.PerspectiveCamera(54, 2, 1, 6000);
  private readonly orthographicCamera = new THREE.OrthographicCamera(-600, 600, 300, -300, 1, 6000);
  private readonly world = new THREE.Group();
  private readonly fieldGroup = new THREE.Group();
  private readonly droneParts = new Map<number, DroneRenderParts>();
  private activeField: number | null = null;
  private activeRenderScale = 1;
  private width = BASE_WIDTH;
  private height = BASE_HEIGHT;

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(1);
    this.renderer.setClearColor(0x000000, 1);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.scene.background = new THREE.Color(0x000000);
    this.scene.add(this.world);
    this.world.add(this.fieldGroup);
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.62));

    const keyLight = new THREE.DirectionalLight(0xffffff, 0.78);
    keyLight.position.set(240, 620, 360);
    this.scene.add(keyLight);
  }

  dispose(): void {
    this.renderer.dispose();
  }

  setSize(width: number, height: number): void {
    this.width = Math.max(1, width);
    this.height = Math.max(1, height);
    this.renderer.setSize(this.width, this.height, false);
    this.perspectiveCamera.aspect = this.width / this.height;
    this.perspectiveCamera.updateProjectionMatrix();
    this.updateOrthographicFrustum(1);
  }

  draw(input: RenderInput, settings: ThreeRenderSettings): void {
    const field = input.meta?.field ?? 6;
    const renderScale = THREE.MathUtils.clamp(settings.renderScale || 1, 0.5, 4);
    const scaleChanged = Math.abs(this.activeRenderScale - renderScale) > 0.001;
    if (this.activeField !== field || scaleChanged) {
      this.activeRenderScale = renderScale;
      this.rebuildField(field);
      this.activeField = field;
    }

    this.updateDrones(
      input.frame.drones,
      input.safetyEvents,
      input.frame.timeMs,
      input.meta?.device ?? "F400",
      input.options.selectedDroneId,
    );
    const camera = this.configureCamera(field, settings);
    this.renderer.render(this.scene, camera);
  }

  private configureCamera(field: number | null | undefined, settings: ThreeRenderSettings): THREE.Camera {
    const center = fieldCenter(field);
    const direction = cameraDirection(settings.viewAngleA, settings.viewAngleB);
    const position = center.clone().sub(direction.multiplyScalar(settings.observerDistance));
    const camera = settings.projection === "perspective" ? this.perspectiveCamera : this.orthographicCamera;

    if (camera instanceof THREE.PerspectiveCamera) {
      const fov = 2 * Math.atan(this.height / (2 * settings.projectionDistance)) * THREE.MathUtils.RAD2DEG;
      camera.fov = THREE.MathUtils.clamp(fov, 18, 82);
      camera.aspect = this.width / this.height;
      camera.updateProjectionMatrix();
    } else {
      this.updateOrthographicFrustum(settings.observerDistance / 600);
    }

    camera.position.copy(position);
    camera.up.set(0, 1, 0);
    camera.lookAt(center);
    return camera;
  }

  private updateOrthographicFrustum(scale: number): void {
    const safeScale = THREE.MathUtils.clamp(scale, 0.2, 4);
    const halfWidth = (BASE_WIDTH / 2) * safeScale;
    const halfHeight = (BASE_HEIGHT / 2) * safeScale;
    this.orthographicCamera.left = -halfWidth;
    this.orthographicCamera.right = halfWidth;
    this.orthographicCamera.top = halfHeight;
    this.orthographicCamera.bottom = -halfHeight;
    this.orthographicCamera.updateProjectionMatrix();
  }

  private rebuildField(field: number | null | undefined): void {
    this.fieldGroup.clear();
    const size = fieldSize(field);
    const lineMaterial = new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 1 });
    const axisX = new THREE.LineBasicMaterial({ color: 0xff3b30 });
    const axisY = new THREE.LineBasicMaterial({ color: 0x42d47d });
    const axisZ = new THREE.LineBasicMaterial({ color: 0x4aa3ff });
    const gridMinor = new THREE.LineBasicMaterial({ color: 0x303030 });
    const gridMajor = new THREE.LineBasicMaterial({ color: 0x777777 });
    const ruler = new THREE.LineBasicMaterial({ color: 0x48d7ff });

    this.fieldGroup.add(this.line([pyfiiPoint(0, 0, 0), pyfiiPoint(size, 0, 0)], lineMaterial));
    this.fieldGroup.add(this.line([pyfiiPoint(0, 0, 0), pyfiiPoint(0, size, 0)], lineMaterial));
    this.fieldGroup.add(this.line([pyfiiPoint(size, 0, 0), pyfiiPoint(size, size, 0)], lineMaterial));
    this.fieldGroup.add(this.line([pyfiiPoint(0, size, 0), pyfiiPoint(size, size, 0)], lineMaterial));
    this.fieldGroup.add(this.line([pyfiiPoint(-20, -20, 0), pyfiiPoint(size + 20, -20, 0)], axisX));
    this.fieldGroup.add(this.line([pyfiiPoint(-20, -20, 0), pyfiiPoint(-20, size + 20, 0)], axisY));
    this.fieldGroup.add(this.line([pyfiiPoint(-20, -20, 0), pyfiiPoint(-20, -20, HEIGHT_MAX)], axisZ));

    for (let i = 0; i <= size; i += 20) {
      const material = i % 100 === 0 ? gridMajor : gridMinor;
      this.fieldGroup.add(this.line([pyfiiPoint(i, 0, 0), pyfiiPoint(i, size, 0)], material));
      this.fieldGroup.add(this.line([pyfiiPoint(0, i, 0), pyfiiPoint(size, i, 0)], material));
    }

    this.fieldGroup.add(this.line([pyfiiPoint(size + 35, -20, 0), pyfiiPoint(size + 35, -20, HEIGHT_MAX)], ruler));
    for (let z = 0; z <= HEIGHT_MAX; z += 50) {
      this.fieldGroup.add(this.line([pyfiiPoint(size + 25, -20, z), pyfiiPoint(size + 45, -20, z)], ruler));
      const label = makeTextSprite(`${z}`, "#48d7ff");
      label.position.copy(pyfiiPoint(size + 58, -20, z));
      this.fieldGroup.add(label);
    }
    const title = makeTextSprite("z cm", "#48d7ff");
    title.position.copy(pyfiiPoint(size + 62, -20, HEIGHT_MAX + 22));
    this.fieldGroup.add(title);
  }

  private line(points: THREE.Vector3[], material: THREE.LineBasicMaterial): THREE.Mesh {
    return this.cylinderBetween(points[0], points[1], material.color, this.strokeRadius(0.35));
  }

  private strokeRadius(base: number): number {
    return Math.max(0.25, base * this.activeRenderScale);
  }

  private cylinderBetween(
    start: THREE.Vector3,
    end: THREE.Vector3,
    color: THREE.Color,
    radius: number,
    opacity = 1,
  ): THREE.Mesh {
    const material = new THREE.MeshBasicMaterial({
      color,
      transparent: opacity < 1,
      opacity,
    });
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, 1, 8), material);
    this.updateCylinder(mesh, start, end, radius);
    return mesh;
  }

  private updateCylinder(mesh: THREE.Mesh, start: THREE.Vector3, end: THREE.Vector3, radius: number): void {
    const direction = end.clone().sub(start);
    const rawLength = direction.length();
    const length = Math.max(0.001, rawLength);
    const axis = rawLength > 0.001 ? direction.normalize() : new THREE.Vector3(0, 1, 0);
    mesh.geometry.dispose();
    mesh.geometry = new THREE.CylinderGeometry(radius, radius, length, 8);
    mesh.position.copy(start).add(end).multiplyScalar(0.5);
    mesh.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      axis,
    );
  }

  private updateDrones(
    drones: DroneFrame[],
    events: SafetyEvent[],
    timeMs: number,
    device: string,
    selectedDroneId: number | null,
  ): void {
    const seen = new Set<number>();
    const activeSafety = this.activeSafetyDrones(events, timeMs);

    for (const drone of drones) {
      seen.add(drone.id);
      const parts = this.ensureDrone(drone.id, device);
      const baseColor = colorFromRgb(droneRgb(drone.id));
      const ledColor = ledOrDroneColor(drone);
      parts.group.visible = true;
      parts.projectionLine.visible = true;
      parts.shadow.visible = true;
      parts.group.position.copy(pyfiiPoint(drone.xCm, drone.yCm, drone.zCm));
      setDroneAttitude(parts.group.quaternion, drone.acceleration, drone.yawDeg);
      parts.body.visible = !ledIsOn(drone);
      parts.led.visible = ledIsOn(drone);
      materialColor(parts.body.material, baseColor);
      materialColor(parts.led.material, ledColor);
      parts.marker.visible = activeSafety.has(drone.id) || selectedDroneId === drone.id;
      materialColor(parts.marker.material, activeSafety.has(drone.id) ? new THREE.Color(0xff3333) : new THREE.Color(0xfff07a));
      this.updateProjection(parts, drone, baseColor);
    }

    for (const [id, parts] of this.droneParts) {
      if (!seen.has(id)) {
        parts.group.visible = false;
        parts.projectionLine.visible = false;
        parts.shadow.visible = false;
      }
    }
  }

  private updateProjection(parts: DroneRenderParts, drone: DroneFrame, color: THREE.Color): void {
    const start = pyfiiPoint(drone.xCm, drone.yCm, 0);
    const end = pyfiiPoint(drone.xCm, drone.yCm, drone.zCm);
    this.updateCylinder(parts.projectionLine, start, end, this.strokeRadius(0.32));
    materialColor(parts.projectionLine.material, color);
    parts.shadow.position.copy(start);
    materialColor(parts.shadow.material, color);
  }

  private activeSafetyDrones(events: SafetyEvent[], timeMs: number): Set<number> {
    const active = new Set<number>();
    for (const event of events) {
      if (event.category === "action_incomplete" || Math.abs(event.time_ms - timeMs) >= 500) {
        continue;
      }
      if (event.drone_a) active.add(event.drone_a);
      if (event.drone_b) active.add(event.drone_b);
    }
    return active;
  }

  private ensureDrone(id: number, device: string): DroneRenderParts {
    const existing = this.droneParts.get(id);
    if (
      existing
      && existing.device === device
      && Math.abs(existing.renderScale - this.activeRenderScale) <= 0.001
    ) {
      return existing;
    }
    if (existing) {
      this.world.remove(existing.group, existing.projectionLine, existing.shadow);
      this.droneParts.delete(id);
    }

    const spec = droneGeometrySpec(device);
    const motorCoordinate = motorAxisOffset(spec);
    const group = new THREE.Group();
    const droneColor = colorFromRgb(droneRgb(id));
    const strokeScale = this.activeRenderScale;
    const body = new THREE.Mesh(
      new THREE.SphereGeometry(Math.max(1, strokeScale), 12, 8),
      new THREE.MeshBasicMaterial({ color: droneColor }),
    );
    const led = new THREE.Mesh(
      new THREE.SphereGeometry(spec.bodyRadius * strokeScale, 18, 12),
      new THREE.MeshBasicMaterial({ color: droneColor }),
    );
    led.visible = false;

    const arms = [
      this.cylinderBetween(
        new THREE.Vector3(motorCoordinate, 0, motorCoordinate),
        new THREE.Vector3(-motorCoordinate, 0, -motorCoordinate),
        droneColor,
        this.strokeRadius(0.45),
      ),
      this.cylinderBetween(
        new THREE.Vector3(-motorCoordinate, 0, motorCoordinate),
        new THREE.Vector3(motorCoordinate, 0, -motorCoordinate),
        droneColor,
        this.strokeRadius(0.45),
      ),
    ];

    const rotorTube = Math.max(0.6, spec.rotorRadius * 0.12) * strokeScale;
    const rotorGeometry = new THREE.TorusGeometry(spec.rotorRadius, rotorTube, 8, 28);
    rotorGeometry.rotateX(Math.PI / 2);
    for (const [x, z] of [
      [motorCoordinate, motorCoordinate],
      [-motorCoordinate, motorCoordinate],
      [-motorCoordinate, -motorCoordinate],
      [motorCoordinate, -motorCoordinate],
    ]) {
      const rotor = new THREE.Mesh(
        rotorGeometry,
        new THREE.MeshStandardMaterial({ color: droneColor, roughness: 0.35, metalness: 0.08 }),
      );
      rotor.position.set(x, 0, z);
      group.add(rotor);
    }

    const markerGeometry = new THREE.TorusGeometry(spec.motorRadius + spec.rotorRadius + 5, 1.5 * strokeScale, 8, 48);
    markerGeometry.rotateX(Math.PI / 2);
    const marker = new THREE.Mesh(markerGeometry, new THREE.MeshBasicMaterial({ color: 0xff3333 }));
    marker.position.y = 2;
    marker.visible = false;

    const projectionLine = this.cylinderBetween(
      new THREE.Vector3(),
      new THREE.Vector3(0, 0.001, 0),
      droneColor,
      this.strokeRadius(0.32),
      0.48,
    );
    const shadowGeometry = new THREE.TorusGeometry(spec.motorRadius + spec.rotorRadius, 0.9 * strokeScale, 8, 42);
    shadowGeometry.rotateX(Math.PI / 2);
    const shadow = new THREE.Mesh(
      shadowGeometry,
      new THREE.MeshBasicMaterial({ color: droneColor, transparent: true, opacity: 0.32 }),
    );
    shadow.position.y = 0.6;

    group.add(...arms, body, led, marker);
    this.world.add(group, projectionLine, shadow);

    const parts = { device, renderScale: this.activeRenderScale, group, body, led, marker, projectionLine, shadow };
    this.droneParts.set(id, parts);
    return parts;
  }
}
