import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataQualityBadges, ReportView } from "./App";
import { BridgeError, unwrapRpcEnvelope } from "./lib/bridge";
import { isValidPlayerIdentifier } from "./lib/playerIdentifier";
import type { CoachingReport } from "./types";

const report: CoachingReport = {
  schema_version: "1.0.0",
  report_summary: { overall_status: "ready", one_sentence_summary: "先处理人数优势后的死亡。", matches_analyzed: 2, rounds_analyzed: 40, data_confidence: 0.82, analysis_scope: "multi_match" },
  priority_issues: [{ issue_id: "ADVANTAGE_GIVEBACK", title: "人数优势后过早送回", category: "decision_making", severity: "high", priority_rank: 1, impact_score: 78, evidence_summary: "10 个样本", why_it_matters: "削弱回合优势。", trend: "重复出现", confidence: 0.8, metric_refs: ["advantage_giveback_rate"], review_round_ids: ["m1:r2"], next_match_rule: "取得人数优势后先确认队友。" }],
  review_rounds: [{ round_id: "m1:r2", review_type: "high_impact_issue", title: "第 2 回合", why_review: "高影响", issue_tags: ["ADVANTAGE_GIVEBACK"], key_event_summary: "tick 1200", review_questions: ["能否等待队友？"], recommended_action: "保持交叉火力" }],
  strengths: [{ strength_id: "OPENING", title: "首次交火稳定", category: "duels", evidence_summary: "20 个样本", trend: "稳定", confidence: 0.8, maintain_rule: "保持准备节奏" }],
  dimension_summaries: Object.fromEntries(["aim", "movement", "duels", "positioning", "teamplay", "utility", "decision_making", "economy_and_objectives"].map((key) => [key, { grade: "B", status: "observed", main_positive: null, main_negative: null, metric_refs: [] }])),
  training_plan: { period: "未来 5-10 场", primary_goals: [{ title: "人数优势", metric_id: "advantage_giveback_rate", current_value: 0.5, target_value: 0.25, behavior_rule: "先确认队友" }], maintenance_goals: [] },
  warnings: [],
};

describe("report UI", () => {
  it("accepts an in-match player name without requiring a SteamID64", () => {
    expect(isValidPlayerIdentifier("AnthonyYZ")).toBe(true);
    expect(isValidPlayerIdentifier("   ")).toBe(false);
  });

  it("surfaces privileged sidecar errors instead of reporting false success", () => {
    expect(() =>
      unwrapRpcEnvelope({
        protocol_version: 1,
        error: { code: "LLM_AUTH_FAILED", message: "API 鉴权失败" },
      }),
    ).toThrow(BridgeError);
  });

  it("puts priority issues before base dimensions", () => {
    render(<ReportView report={report} />);
    expect(screen.getByText("人数优势后过早送回")).toBeInTheDocument();
    expect(screen.getByText("规则影响 78")).toBeInTheDocument();
    expect(screen.getByText("最值得复盘的回合")).toBeInTheDocument();
  });

  it("shows unavailable capabilities as unavailable, not zero", () => {
    render(<DataQualityBadges quality={{ view_angles: "unavailable", visibility: "estimated" }} />);
    expect(screen.getByText("视角: unavailable")).toBeInTheDocument();
    expect(screen.queryByText("视角: 0")).not.toBeInTheDocument();
  });
});
