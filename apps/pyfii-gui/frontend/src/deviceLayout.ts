export type DeviceClass = "desktop" | "phone" | "tablet";
export type DeviceOrientation = "portrait" | "landscape";

interface DeviceSignals {
  userAgent: string;
  maxTouchPoints: number;
  screenWidth: number;
  screenHeight: number;
}

/**
 * Classify the physical device instead of treating every narrow desktop window
 * as a phone. The 600px short-edge boundary follows common phone/tablet screen
 * sizes; iPadOS needs a touch check because it can identify itself as macOS.
 */
export function classifyDevice(signals: DeviceSignals): DeviceClass {
  const { userAgent } = signals;
  const isIpad = /iPad/i.test(userAgent)
    || (/Macintosh/i.test(userAgent) && signals.maxTouchPoints > 1);
  const isPortablePlatform = isIpad
    || /Android|iPhone|iPod|Windows Phone|IEMobile|Opera Mini|Tablet|PlayBook|Silk|Mobile/i.test(userAgent);

  if (!isPortablePlatform) return "desktop";
  if (isIpad || /Tablet|PlayBook|Silk/i.test(userAgent)) return "tablet";

  const shortEdge = Math.min(signals.screenWidth, signals.screenHeight);
  return shortEdge >= 600 ? "tablet" : "phone";
}

export function currentDeviceClass(): DeviceClass {
  return classifyDevice({
    userAgent: navigator.userAgent,
    maxTouchPoints: navigator.maxTouchPoints,
    screenWidth: window.screen.width,
    screenHeight: window.screen.height,
  });
}

export function currentOrientation(): DeviceOrientation {
  return window.innerWidth > window.innerHeight ? "landscape" : "portrait";
}

export function updateDeviceLayout(): void {
  document.body.dataset.device = currentDeviceClass();
  document.body.dataset.orientation = currentOrientation();
}
