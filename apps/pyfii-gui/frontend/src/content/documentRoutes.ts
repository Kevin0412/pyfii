export type DocumentId =
  | "overview"
  | "guide"
  | "core"
  | "gui"
  | "tutorial"
  | "install"
  | "group-flight"
  | "script-mode"
  | "principle"
  | "light";

export type AppRoute =
  | { page: "home" }
  | { page: "studio" }
  | { page: "document"; documentId: DocumentId };

const routeDocuments: Record<string, DocumentId> = {
  "/docs": "overview",
  "/docs/guide": "guide",
  "/docs/core": "core",
  "/docs/gui": "gui",
  "/docs/tutorial": "tutorial",
  "/docs/tutorial/install": "install",
  "/docs/tutorial/group-flight": "group-flight",
  "/docs/tutorial/script-mode": "script-mode",
  "/docs/tutorial/principle": "principle",
  "/docs/tutorial/light": "light",
};

const pathAliases: Record<string, string> = {
  "/doc": "/docs",
  "/guide": "/docs/guide",
  "/gui": "/studio",
  "/docs/tutorial/programme-challenge": "/docs/tutorial",
  "/docs/tutorial/more": "/docs/tutorial",
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
