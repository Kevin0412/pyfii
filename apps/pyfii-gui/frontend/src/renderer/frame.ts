import type { DroneFrame, DroneSample, DroneTrack, RenderFrame } from "./types";

function sampleToFrame(trackId: number, sample: DroneSample): DroneFrame {
  return {
    id: trackId,
    timeMs: sample[0],
    xCm: sample[1],
    yCm: sample[2],
    zCm: sample[3],
    yawDeg: sample[4],
    ledRgb: [sample[5], sample[6], sample[7]],
    acceleration: [sample[8], sample[9], sample[10]],
  };
}

function nearestSample(samples: DroneSample[], timeMs: number): DroneSample | null {
  if (samples.length === 0) {
    return null;
  }

  let nearest = samples[0];
  let nearestDelta = Math.abs(nearest[0] - timeMs);

  for (const sample of samples) {
    const delta = Math.abs(sample[0] - timeMs);
    if (delta < nearestDelta) {
      nearest = sample;
      nearestDelta = delta;
    }
    if (sample[0] > timeMs && delta > nearestDelta) {
      break;
    }
  }

  return nearest;
}

export function getFrameAtTime(tracks: DroneTrack[], timeMs: number): RenderFrame {
  const drones: DroneFrame[] = [];

  for (const track of tracks) {
    const sample = nearestSample(track.samples, timeMs);
    if (sample) {
      drones.push(sampleToFrame(track.id, sample));
    }
  }

  return {
    timeMs,
    drones,
  };
}
