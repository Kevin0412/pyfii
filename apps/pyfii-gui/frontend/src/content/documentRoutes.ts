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

export function documentFromHash(hash: string): DocumentId | null {
  const route = hash.startsWith("#") ? hash.slice(1) : hash;
  return routeDocuments[route || "/"] ?? null;
}
