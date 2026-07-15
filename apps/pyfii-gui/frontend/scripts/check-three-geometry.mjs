import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import ts from "typescript";

const sourceUrl = new URL("../src/renderer/three/geometry.ts", import.meta.url);
const source = await readFile(sourceUrl, "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const geometry = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

assert.equal(geometry.wrapHorizontalAngle(181), -179);
assert.equal(geometry.wrapHorizontalAngle(-181), 179);
assert.equal(geometry.wrapHorizontalAngle(540), -180);

const viewport1x = geometry.logicalViewportSize(1200, 600, 1);
const viewport4x = geometry.logicalViewportSize(4800, 2400, 4);
assert.deepEqual(viewport4x, viewport1x, "SSAA must not change the logical 3D viewport");
assert.equal(
  geometry.perspectiveFovDegrees(viewport4x.height, 450),
  geometry.perspectiveFovDegrees(viewport1x.height, 450),
  "1x and 4x SSAA must keep the same perspective composition",
);

const rendererSource = await readFile(
  new URL("../src/renderer/three/PyfiiThreeRenderer.ts", import.meta.url),
  "utf8",
);
assert.doesNotMatch(rendererSource, /activeRenderScale|settings\.renderScale|strokeScale/);
assert.doesNotMatch(
  rendererSource,
  /perspectiveFovDegrees\((?:this\.)?(?:height|backingHeight)/,
  "perspective FOV must not use backing-buffer height",
);

for (const device of ["F400", "F600"]) {
  const spec = geometry.droneGeometrySpec(device);
  const axisOffset = geometry.motorAxisOffset(spec);
  assert.ok(Math.abs(Math.hypot(axisOffset, axisOffset) - spec.motorRadius) < 1e-12);
  assert.ok(
    Math.abs(2 * axisOffset - 2 * spec.rotorRadius) < 0.4,
    `${device} adjacent rotor circles should remain tangent like the core model`,
  );
}

console.log("3D geometry and SSAA separation checks passed.");
