export type DocumentId =
  | "overview"
  | "index"
  | "guide"
  | "core"
  | "gui"
  | "tutorial"
  | "install"
  | "group-flight"
  | "script-mode"
  | "principle"
  | "light"
  | "human-choreography"
  | "human-script-patterns"
  | "choreo-agent-lessons"
  | "choreo-agent-roadmap"
  | "flight-log-analysis"
  | "fwfii-merge-plan"
  | "ai-choreography"
  | "ai-generated-distillation"
  | "cannon-design-lessons"
  | "deepseek-cannon-reflection"
  | "ai-script-patterns";

export type AppRoute =
  | { page: "home" }
  | { page: "studio" }
  | { page: "document"; documentId: DocumentId };

const routeDocuments: Record<string, DocumentId> = {
  "/docs": "overview",
  "/docs/index": "index",
  "/docs/guide": "guide",
  "/docs/core": "core",
  "/docs/gui": "gui",
  "/docs/tutorial": "tutorial",
  "/docs/tutorial/install": "install",
  "/docs/tutorial/group-flight": "group-flight",
  "/docs/tutorial/script-mode": "script-mode",
  "/docs/tutorial/principle": "principle",
  "/docs/tutorial/light": "light",
  "/docs/choreo/human-choreography": "human-choreography",
  "/docs/choreo/human-script-patterns": "human-script-patterns",
  "/docs/choreo/agent-lessons": "choreo-agent-lessons",
  "/docs/choreo/agent-roadmap": "choreo-agent-roadmap",
  "/docs/choreo/ai-exploration": "ai-choreography",
  "/docs/choreo/ai-output-distillation": "ai-generated-distillation",
  "/docs/choreo/cannon-design-lessons": "cannon-design-lessons",
  "/docs/choreo/deepseek-cannon-reflection": "deepseek-cannon-reflection",
  "/docs/choreo/ai-script-patterns": "ai-script-patterns",
  "/docs/research/flight-log-analysis": "flight-log-analysis",
  "/docs/research/fwfii-merge-plan": "fwfii-merge-plan",
};

const pathAliases: Record<string, string> = {
  "/doc": "/docs",
  "/guide": "/docs/guide",
  "/gui": "/studio",
  "/docs/tutorial/programme-challenge": "/docs/tutorial",
  "/docs/tutorial/more": "/docs/tutorial",
  "/docs/research/human-choreography": "/docs/choreo/human-choreography",
  "/docs/research/human-script-patterns": "/docs/choreo/human-script-patterns",
  "/docs/research/choreo-agent-lessons": "/docs/choreo/agent-lessons",
  "/docs/research/choreo-agent-roadmap": "/docs/choreo/agent-roadmap",
  "/docs/archive/ai-choreography": "/docs/choreo/ai-exploration",
  "/docs/archive/ai-generated-distillation": "/docs/choreo/ai-output-distillation",
  "/docs/archive/cannon-design-lessons": "/docs/choreo/cannon-design-lessons",
  "/docs/archive/deepseek-cannon-reflection": "/docs/choreo/deepseek-cannon-reflection",
  "/docs/archive/ai-script-patterns": "/docs/choreo/ai-script-patterns",
};

export function normalizePath(pathname: string): string {
  if (!pathname || pathname === "/") {
    return "/";
  }
  return pathname.replace(/\/+$/, "") || "/";
}

export function canonicalAppPath(pathname: string): string {
  const normalized = normalizePath(pathname);
  if (normalized === "/tutorial" || normalized.startsWith("/tutorial/")) {
    return pathAliases[`/docs${normalized}`] ?? `/docs${normalized}`;
  }
  return pathAliases[normalized] ?? normalized;
}

export function appRouteFromPath(pathname: string): AppRoute {
  const path = canonicalAppPath(pathname);
  if (path === "/studio") {
    return { page: "studio" };
  }
  const documentId = routeDocuments[path];
  if (documentId) {
    return { page: "document", documentId };
  }
  return { page: "home" };
}

export function legacyPathFromHash(hash: string): string | null {
  if (!hash.startsWith("#/")) {
    return null;
  }
  const path = canonicalAppPath(hash.slice(1));
  return isAppPath(path) ? path : null;
}

export function isAppPath(pathname: string): boolean {
  const path = canonicalAppPath(pathname);
  return path === "/" || path === "/studio" || path in routeDocuments;
}
