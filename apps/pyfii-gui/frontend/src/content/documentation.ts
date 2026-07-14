import { marked } from "marked";

import aiChoreography from "../../../../../doc/ai_choreography_exploration.md?raw";
import aiGeneratedDistillation from "../../../../../doc/ai_generated_distillation.md?raw";
import cannonDesignLessons from "../../../../../doc/cannon_design_lessons.md?raw";
import choreoAgentLessons from "../../../../../doc/choreo_agent_lessons.md?raw";
import choreoAgentRoadmap from "../../../../../doc/choreo_agent_roadmap.md?raw";
import coreDocs from "../../../../../doc/doc_zh_CN.md?raw";
import deepseekCannonReflection from "../../../../../doc/deepseek_cannon_reflection.md?raw";
import docsOverview from "../../../../../doc/pyfii_docs.md?raw";
import flightLogAnalysis from "../../../../../doc/flight_log_trajectory_analysis.md?raw";
import fwfiiMergePlan from "../../../../../doc/fwfii_merge_plan.md?raw";
import guiDocs from "../../../../../doc/pyfii_gui.md?raw";
import guiGuide from "../../../../../doc/pyfii_gui_guide.md?raw";
import humanChoreography from "../../../../../doc/human_choreography_distillation.md?raw";
import repositoryIndex from "../../../../../doc/INDEX.md?raw";
import aiScriptPatterns from "../../../../../doc/pyfii_script_patterns_ai.md?raw";
import humanScriptPatterns from "../../../../../doc/pyfii_script_patterns_human.md?raw";
import tutorialContents from "../../../../../doc/tutorial/contents.md?raw";
import tutorialGroupFlight from "../../../../../doc/tutorial/group_flight.md?raw";
import tutorialInstall from "../../../../../doc/tutorial/install.md?raw";
import tutorialLight from "../../../../../doc/tutorial/light.md?raw";
import tutorialPrinciple from "../../../../../doc/tutorial/principle.md?raw";
import tutorialScriptMode from "../../../../../doc/tutorial/script_mode.md?raw";
import type { LocaleMode } from "../stores/ui";
import type { DocumentId } from "./documentRoutes";

export type { DocumentId } from "./documentRoutes";

interface DocumentSource {
  title: Record<LocaleMode, string>;
  markdown: string;
  route: string;
  group: "start" | "docs" | "tutorial" | "choreo" | "research";
}

const documents: Record<DocumentId, DocumentSource> = {
  overview: {
    title: { zh: "文档与教程", en: "Docs & Tutorials" },
    markdown: docsOverview,
    route: "/docs",
    group: "start",
  },
  index: {
    title: { zh: "全部文档索引", en: "All Documents" },
    markdown: repositoryIndex,
    route: "/docs/index",
    group: "start",
  },
  guide: {
    title: { zh: "使用引导", en: "Guide" },
    markdown: guiGuide,
    route: "/docs/guide",
    group: "start",
  },
  core: {
    title: { zh: "PyFii 文档", en: "PyFii Docs" },
    markdown: coreDocs,
    route: "/docs/core",
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
    route: "/docs/tutorial",
    group: "tutorial",
  },
  install: {
    title: { zh: "安装", en: "Install" },
    markdown: tutorialInstall,
    route: "/docs/tutorial/install",
    group: "tutorial",
  },
  "group-flight": {
    title: { zh: "编队飞行", en: "Group Flight" },
    markdown: tutorialGroupFlight,
    route: "/docs/tutorial/group-flight",
    group: "tutorial",
  },
  "script-mode": {
    title: { zh: "脚本模式", en: "Script Mode" },
    markdown: tutorialScriptMode,
    route: "/docs/tutorial/script-mode",
    group: "tutorial",
  },
  principle: {
    title: { zh: "内部原理", en: "Internals" },
    markdown: tutorialPrinciple,
    route: "/docs/tutorial/principle",
    group: "tutorial",
  },
  light: {
    title: { zh: "灯光编写", en: "Lighting" },
    markdown: tutorialLight,
    route: "/docs/tutorial/light",
    group: "tutorial",
  },
  "human-choreography": {
    title: { zh: "人类编舞作品蒸馏", en: "Human Choreography" },
    markdown: humanChoreography,
    route: "/docs/choreo/human-choreography",
    group: "choreo",
  },
  "human-script-patterns": {
    title: { zh: "人类作品编码模式", en: "Human Script Patterns" },
    markdown: humanScriptPatterns,
    route: "/docs/choreo/human-script-patterns",
    group: "choreo",
  },
  "choreo-agent-lessons": {
    title: { zh: "编舞 Agent 踩坑记录", en: "Choreo Agent Lessons" },
    markdown: choreoAgentLessons,
    route: "/docs/choreo/agent-lessons",
    group: "choreo",
  },
  "choreo-agent-roadmap": {
    title: { zh: "编舞 Agent 后续计划", en: "Choreo Agent Roadmap" },
    markdown: choreoAgentRoadmap,
    route: "/docs/choreo/agent-roadmap",
    group: "choreo",
  },
  "flight-log-analysis": {
    title: { zh: "真实飞行轨迹分析", en: "Flight Log Analysis" },
    markdown: flightLogAnalysis,
    route: "/docs/research/flight-log-analysis",
    group: "research",
  },
  "fwfii-merge-plan": {
    title: { zh: "fwfii 合并调研", en: "fwfii Merge Plan" },
    markdown: fwfiiMergePlan,
    route: "/docs/research/fwfii-merge-plan",
    group: "research",
  },
  "ai-choreography": {
    title: { zh: "AI 编舞探索", en: "AI Choreography" },
    markdown: aiChoreography,
    route: "/docs/choreo/ai-exploration",
    group: "choreo",
  },
  "ai-generated-distillation": {
    title: { zh: "AI 生成产物蒸馏", en: "AI Output Distillation" },
    markdown: aiGeneratedDistillation,
    route: "/docs/choreo/ai-output-distillation",
    group: "choreo",
  },
  "cannon-design-lessons": {
    title: { zh: "Cannon 设计经验", en: "Cannon Design Lessons" },
    markdown: cannonDesignLessons,
    route: "/docs/choreo/cannon-design-lessons",
    group: "choreo",
  },
  "deepseek-cannon-reflection": {
    title: { zh: "DeepSeek Cannon 反思", en: "DeepSeek Cannon Reflection" },
    markdown: deepseekCannonReflection,
    route: "/docs/choreo/deepseek-cannon-reflection",
    group: "choreo",
  },
  "ai-script-patterns": {
    title: { zh: "AI 编码模式", en: "AI Script Patterns" },
    markdown: aiScriptPatterns,
    route: "/docs/choreo/ai-script-patterns",
    group: "choreo",
  },
};

const markdownRoutes: Record<string, string> = {
  "INDEX.md": "/docs/index",
  "ai_choreography_exploration.md": "/docs/choreo/ai-exploration",
  "ai_generated_distillation.md": "/docs/choreo/ai-output-distillation",
  "cannon_design_lessons.md": "/docs/choreo/cannon-design-lessons",
  "choreo_agent_lessons.md": "/docs/choreo/agent-lessons",
  "choreo_agent_roadmap.md": "/docs/choreo/agent-roadmap",
  "deepseek_cannon_reflection.md": "/docs/choreo/deepseek-cannon-reflection",
  "flight_log_trajectory_analysis.md": "/docs/research/flight-log-analysis",
  "fwfii_merge_plan.md": "/docs/research/fwfii-merge-plan",
  "human_choreography_distillation.md": "/docs/choreo/human-choreography",
  "pyfii_script_patterns_ai.md": "/docs/choreo/ai-script-patterns",
  "pyfii_script_patterns_human.md": "/docs/choreo/human-script-patterns",
  "pyfii_docs.md": "/docs",
  "pyfii_gui.md": "/docs/gui",
  "pyfii_gui_guide.md": "/docs/guide",
  "doc_zh_CN.md": "/docs/core",
  "contents.md": "/docs/tutorial",
  "install.md": "/docs/tutorial/install",
  "group_flight.md": "/docs/tutorial/group-flight",
  "script_mode.md": "/docs/tutorial/script-mode",
  "principle.md": "/docs/tutorial/principle",
  "light.md": "/docs/tutorial/light",
};

const documentAssets = Object.fromEntries(
  Object.entries(
    import.meta.glob("../../../../../doc/images/*", {
      eager: true,
      query: "?url",
      import: "default",
    }) as Record<string, string>,
  ).map(([path, url]) => [`images/${path.split("/").pop()}`, url]),
);

const repositoryLinks: Record<string, string> = {
  "../tools/flight_log_analysis.py":
    "https://github.com/Kevin0412/pyfii/blob/pyfii-dev/tools/flight_log_analysis.py",
  "../src/pyfii/read.py":
    "https://github.com/Kevin0412/pyfii/blob/pyfii-dev/src/pyfii/read.py",
  "images/": "https://github.com/Kevin0412/pyfii/tree/pyfii-dev/doc/images",
};

function rewriteMarkdownLinks(markdown: string): string {
  return markdown.replace(/\]\(([^)#]+)(#[^)]+)?\)/g, (match, path: string, anchor = "") => {
    const filename = path.split("/").pop() || "";
    const target = markdownRoutes[filename] || documentAssets[path] || repositoryLinks[path];
    return target ? `](${target}${anchor})` : match;
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
