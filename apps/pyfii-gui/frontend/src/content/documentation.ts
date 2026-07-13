import { marked } from "marked";

import coreDocs from "../../../../../doc/doc_zh_CN.md?raw";
import guiDocs from "../../../../../doc/pyfii_gui.md?raw";
import guiGuide from "../../../../../doc/pyfii_gui_guide.md?raw";
import tutorialContents from "../../../../../doc/tutorial/contents.md?raw";
import tutorialGroupFlight from "../../../../../doc/tutorial/group_flight.md?raw";
import tutorialInstall from "../../../../../doc/tutorial/install.md?raw";
import tutorialLight from "../../../../../doc/tutorial/light.md?raw";
import tutorialMore from "../../../../../doc/tutorial/more.md?raw";
import tutorialPrinciple from "../../../../../doc/tutorial/principle.md?raw";
import tutorialProgrammeChallenge from "../../../../../doc/tutorial/programme_challenge.md?raw";
import tutorialScriptMode from "../../../../../doc/tutorial/script_mode.md?raw";
import type { LocaleMode } from "../stores/ui";
import type { DocumentId } from "./documentRoutes";

export type { DocumentId } from "./documentRoutes";

interface DocumentSource {
  title: Record<LocaleMode, string>;
  markdown: string;
  route: string;
  group: "start" | "docs" | "tutorial";
}

const documents: Record<DocumentId, DocumentSource> = {
  guide: {
    title: { zh: "使用引导", en: "Guide" },
    markdown: guiGuide,
    route: "/guide",
    group: "start",
  },
  core: {
    title: { zh: "PyFii 文档", en: "PyFii Docs" },
    markdown: coreDocs,
    route: "/docs",
    group: "docs",
  },
  gui: {
    title: { zh: "GUI 架构与部署", en: "GUI Architecture" },
    markdown: guiDocs,
    route: "/docs/gui",
    group: "docs",
  },
  tutorial: {
    title: { zh: "教程目录", en: "Tutorials" },
    markdown: tutorialContents,
    route: "/tutorial",
    group: "tutorial",
  },
  install: {
    title: { zh: "安装", en: "Install" },
    markdown: tutorialInstall,
    route: "/tutorial/install",
    group: "tutorial",
  },
  "group-flight": {
    title: { zh: "编队飞行", en: "Group Flight" },
    markdown: tutorialGroupFlight,
    route: "/tutorial/group-flight",
    group: "tutorial",
  },
  "programme-challenge": {
    title: { zh: "编程挑战", en: "Programming Challenge" },
    markdown: tutorialProgrammeChallenge,
    route: "/tutorial/programme-challenge",
    group: "tutorial",
  },
  "script-mode": {
    title: { zh: "脚本模式", en: "Script Mode" },
    markdown: tutorialScriptMode,
    route: "/tutorial/script-mode",
    group: "tutorial",
  },
  principle: {
    title: { zh: "内部原理", en: "Internals" },
    markdown: tutorialPrinciple,
    route: "/tutorial/principle",
    group: "tutorial",
  },
  more: {
    title: { zh: "进阶用法", en: "Advanced Usage" },
    markdown: tutorialMore,
    route: "/tutorial/more",
    group: "tutorial",
  },
  light: {
    title: { zh: "灯光编写", en: "Lighting" },
    markdown: tutorialLight,
    route: "/tutorial/light",
    group: "tutorial",
  },
};

const markdownRoutes: Record<string, string> = {
  "pyfii_gui.md": "/docs/gui",
  "pyfii_gui_guide.md": "/guide",
  "doc_zh_CN.md": "/docs",
  "contents.md": "/tutorial",
  "install.md": "/tutorial/install",
  "group_flight.md": "/tutorial/group-flight",
  "programme_challenge.md": "/tutorial/programme-challenge",
  "script_mode.md": "/tutorial/script-mode",
  "principle.md": "/tutorial/principle",
  "more.md": "/tutorial/more",
  "light.md": "/tutorial/light",
};

function rewriteMarkdownLinks(markdown: string): string {
  return markdown.replace(/\]\(([^)]+\.md)(#[^)]+)?\)/g, (match, path: string) => {
    const filename = path.split("/").pop() || "";
    const route = markdownRoutes[filename];
    return route ? `](${route})` : match;
  });
}

export function documentSource(id: DocumentId): DocumentSource {
  return documents[id];
}

export function documentHtml(id: DocumentId): string {
  return marked.parse(rewriteMarkdownLinks(documents[id].markdown), {
    async: false,
    gfm: true,
  }) as string;
}

export function documentNavigation(): Array<{ id: DocumentId; source: DocumentSource }> {
  return (Object.keys(documents) as DocumentId[]).map((id) => ({ id, source: documents[id] }));
}
