export type DocumentId =
  | "guide"
  | "core"
  | "gui"
  | "tutorial"
  | "install"
  | "group-flight"
  | "programme-challenge"
  | "script-mode"
  | "principle"
  | "more"
  | "light";

export type AppRoute =
  | { page: "home" }
  | { page: "studio" }
  | { page: "document"; documentId: DocumentId };

const routeDocuments: Record<string, DocumentId> = {
  "/guide": "guide",
  "/docs": "core",
  "/docs/gui": "gui",
  "/tutorial": "tutorial",
  "/tutorial/install": "install",
  "/tutorial/group-flight": "group-flight",
  "/tutorial/programme-challenge": "programme-challenge",
  "/tutorial/script-mode": "script-mode",
  "/tutorial/principle": "principle",
  "/tutorial/more": "more",
  "/tutorial/light": "light",
};

const pathAliases: Record<string, string> = {
  "/doc": "/docs",
  "/gui": "/studio",
};

export function normalizePath(pathname: string): string {
  if (!pathname || pathname === "/") {
    return "/";
  }
  return pathname.replace(/\/+$/, "") || "/";
}

export function canonicalAppPath(pathname: string): string {
  const normalized = normalizePath(pathname);
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
