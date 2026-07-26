import type { Locale } from "./types";

const messages = {
  "zh-CN": {
    import: "导入中心",
    history: "历史分析",
    reports: "报告中心",
    trends: "趋势与训练",
    settings: "设置",
    local: "本地处理",
    empty: "暂无可展示数据",
    retry: "重试",
    loading: "正在加载",
  },
  "en-US": {
    import: "Import",
    history: "History",
    reports: "Reports",
    trends: "Trends & Training",
    settings: "Settings",
    local: "Processed locally",
    empty: "Nothing to show yet",
    retry: "Retry",
    loading: "Loading",
  },
} as const;

export function t(locale: Locale, key: keyof (typeof messages)["zh-CN"]): string {
  return messages[locale][key];
}
