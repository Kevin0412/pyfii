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

for (const device of ["F400", "F600"]) {
  const spec = geometry.droneGeometrySpec(device);
  const axisOffset = geometry.motorAxisOffset(spec);
  assert.ok(Math.abs(Math.hypot(axisOffset, axisOffset) - spec.motorRadius) < 1e-12);
  assert.ok(
    Math.abs(2 * axisOffset - 2 * spec.rotorRadius) < 0.4,
    `${device} adjacent rotor circles should remain tangent like the core model`,
  );
}

console.log("3D angle wrapping and motor geometry checks passed.");
