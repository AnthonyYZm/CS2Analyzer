import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  BridgeError,
  chooseDemoFiles,
  chooseDirectory,
  clearApiKey,
  generateAiReport,
  onSidecarEvent,
  rpc,
  secretStatus,
  setApiKey,
  testProvider,
} from "./lib/bridge";
import { isValidPlayerIdentifier } from "./lib/playerIdentifier";
import { useUiStore } from "./store";
import { t } from "./i18n";
import type {
  CapabilityStatus,
  CoachingReport,
  DemoItem,
  JobItem,
  MatchItem,
  ProviderSettings,
  ReportListItem,
  Settings,
} from "./types";

type ListResult<T> = { items: T[] };
const PLAYER_DRAFT_KEY = "roundlens:onboarding-player";
const DIRECTORY_DRAFT_KEY = "roundlens:onboarding-directory";

const capabilityLabels: Record<string, string> = {
  core_events: "核心事件",
  shots: "逐发射击",
  utility: "道具",
  positions: "位置",
  view_angles: "视角",
  velocity: "速度",
  usercmd: "输入命令",
  map_radar: "雷达图",
  map_nav: "导航网格",
  visibility: "可见性",
};

function useSettings() {
  return useQuery({ queryKey: ["settings"], queryFn: () => rpc<Settings>("get_settings") });
}

function formatError(error: unknown): string {
  if (error instanceof BridgeError) return `${error.code}: ${error.message}`;
  if (error instanceof Error) return error.message;
  return String(error);
}

function StatusPill({ children, tone = "neutral" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function LoadingState({ label = "正在加载" }: { label?: string }) {
  return <div className="state-card" aria-live="polite"><span className="loader" />{label}</div>;
}

function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="state-card state-error" role="alert">
      <strong>无法完成请求</strong>
      <p>{formatError(error)}</p>
      {retry && <button className="button secondary" onClick={retry}>重试</button>}
    </div>
  );
}

export function DataQualityBadges({ quality }: { quality: Record<string, CapabilityStatus> }) {
  return (
    <div className="quality-list" aria-label="数据能力">
      {Object.entries(quality).map(([name, status]) => (
        <span className={`quality quality-${status}`} key={name}>
          {capabilityLabels[name] ?? name}: {status}
        </span>
      ))}
    </div>
  );
}

function Shell() {
  const locale = useUiStore((state) => state.locale);
  const setLocale = useUiStore((state) => state.setLocale);
  const queryClient = useQueryClient();

  useEffect(() => {
    let disposed = false;
    let cleanup: (() => void) | undefined;
    onSidecarEvent((message) => {
      if (message.event.startsWith("job.") || message.event.startsWith("import.")) {
        void queryClient.invalidateQueries({ queryKey: ["jobs"] });
        if (message.event === "job.completed") {
          void queryClient.invalidateQueries({ queryKey: ["matches"] });
          void queryClient.invalidateQueries({ queryKey: ["demos"] });
        }
      }
    }).then((unlisten) => {
      if (disposed) unlisten(); else cleanup = unlisten;
    }).catch(() => undefined);
    return () => { disposed = true; cleanup?.(); };
  }, [queryClient]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">RL</span><div><strong>RoundLens</strong><small>{t(locale, "local")}</small></div></div>
        <nav aria-label="主导航">
          <NavLink to="/import">{t(locale, "import")}</NavLink>
          <NavLink to="/history">{t(locale, "history")}</NavLink>
          <NavLink to="/reports">{t(locale, "reports")}</NavLink>
          <NavLink to="/trends">{t(locale, "trends")}</NavLink>
          <NavLink to="/settings">{t(locale, "settings")}</NavLink>
        </nav>
        <div className="sidebar-foot">
          <button className="lang-switch" onClick={() => setLocale(locale === "zh-CN" ? "en-US" : "zh-CN")}>
            {locale === "zh-CN" ? "English" : "中文"}
          </button>
          <small>v0.1.0 · Protocol 1</small>
        </div>
      </aside>
      <main className="main"><RoutesContent /></main>
    </div>
  );
}

function RoutesContent() {
  return (
    <Routes>
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route path="/import" element={<ImportPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="/reports" element={<ReportsPage />} />
      <Route path="/analysis" element={<CreateAnalysisPage />} />
      <Route path="/report/:analysisId" element={<ReportPage />} />
      <Route path="/report/:analysisId/review/:roundId" element={<ReviewPage />} />
      <Route path="/trends" element={<TrendsPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<Navigate to="/import" replace />} />
    </Routes>
  );
}

function OnboardingGate() {
  const settings = useSettings();
  const location = useLocation();
  if (settings.isLoading) return <div className="gate"><LoadingState label="正在连接本地分析服务" /></div>;
  if (settings.isError) return <div className="gate"><ErrorState error={settings.error} retry={() => void settings.refetch()} /></div>;
  const data = settings.data;
  if (!data) return <div className="gate"><ErrorState error={new Error("本地设置响应为空")} /></div>;
  if (!data.onboarding_complete && location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }
  if (data.onboarding_complete && location.pathname === "/onboarding") {
    return <Navigate to="/import" replace />;
  }
  return <Shell />;
}

export function App() {
  return <OnboardingGate />;
}

function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: React.ReactNode }) {
  return (
    <header className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{actions && <div className="header-actions">{actions}</div>}</header>
  );
}

function OnboardingPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [playerIdentifier, setPlayerIdentifier] = useState(
    () => sessionStorage.getItem(PLAYER_DRAFT_KEY) ?? "",
  );
  const [directory, setDirectory] = useState<string | null>(
    () => sessionStorage.getItem(DIRECTORY_DRAFT_KEY),
  );
  useEffect(() => {
    sessionStorage.setItem(PLAYER_DRAFT_KEY, playerIdentifier);
  }, [playerIdentifier]);
  useEffect(() => {
    if (directory) sessionStorage.setItem(DIRECTORY_DRAFT_KEY, directory);
    else sessionStorage.removeItem(DIRECTORY_DRAFT_KEY);
  }, [directory]);
  const mutation = useMutation({
    mutationFn: () => rpc<Settings>("update_profile", { player_identifier: playerIdentifier.trim(), scan_directories: directory ? [directory] : [], onboarding_complete: true, locale: "zh-CN" }),
    onSuccess: async () => {
      sessionStorage.removeItem(PLAYER_DRAFT_KEY);
      sessionStorage.removeItem(DIRECTORY_DRAFT_KEY);
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      navigate("/import");
    },
  });
  const valid = isValidPlayerIdentifier(playerIdentifier);
  return (
    <div className="onboarding">
      <section className="onboarding-copy"><span className="eyebrow">WELCOME TO ROUNDLENS</span><h1>把对局变成下一场能执行的规则</h1><p>Demo、Tick 和轨迹默认只在本机解析。只有你主动生成 AI 报告时，经过裁剪的结构化摘要才会发送给所配置的服务。</p><div className="privacy-grid"><div><strong>本地优先</strong><span>不上传原始 Demo</span></div><div><strong>证据优先</strong><span>缺失字段不填 0</span></div><div><strong>问题优先</strong><span>规则影响不冒充胜率</span></div></div></section>
      <form className="onboarding-card" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
        <span className="step">首次设置 · 1 / 1</span><h2>建立本人档案</h2>
        <label>对局内玩家 ID/名称<input value={playerIdentifier} onChange={(event) => setPlayerIdentifier(event.target.value)} placeholder="例如 AnthonyYZ；也支持 SteamID64" aria-invalid={playerIdentifier.length > 0 && !valid} /></label>
        <p className="fine-print">解析 Demo 后会优先匹配 SteamID64，否则按记分板中的玩家名称唯一匹配。</p>
        <label>Demo 扫描目录（可跳过）<div className="field-row"><input readOnly value={directory ?? "未选择"} /><button type="button" className="button secondary" onClick={async () => setDirectory(await chooseDirectory())}>选择</button></div></label>
        <p className="fine-print">API 可稍后在设置中配置。API Key 只保存到 Windows Credential Manager。</p>
        {mutation.isError && <ErrorState error={mutation.error} />}
        <button className="button primary wide" disabled={!valid || mutation.isPending}>{mutation.isPending ? "正在保存" : "进入导入中心"}</button>
      </form>
    </div>
  );
}

function ImportPage() {
  const queryClient = useQueryClient();
  const demos = useQuery({ queryKey: ["demos"], queryFn: () => rpc<ListResult<DemoItem>>("list_demos") });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => rpc<ListResult<JobItem>>("list_jobs"), refetchInterval: 1500 });
  const importMutation = useMutation({
    mutationFn: async (paths: string[]) => rpc<ListResult<unknown>>("import_demos", { paths }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["demos"] }),
  });
  const parseMutation = useMutation({
    mutationFn: (demoId: string) => rpc<{ job_id: string }>("parse_demo", { demo_id: demoId }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const choose = async () => { const paths = await chooseDemoFiles(); if (paths.length) importMutation.mutate(paths); };
  const drop = (event: React.DragEvent) => {
    event.preventDefault();
    const paths = Array.from(event.dataTransfer.files).map((file) => (file as File & { path?: string }).path).filter((path): path is string => Boolean(path));
    if (paths.length) importMutation.mutate(paths);
  };
  const jobItems = jobs.data?.items ?? [];
  const demoItems = demos.data?.items ?? [];
  return (
    <div className="page">
      <PageHeader eyebrow="IMPORT" title="导入与解析" description="批量选择 Demo，先进行流式哈希与去重，再按队列逐场解析。" actions={<button className="button secondary" onClick={() => void demos.refetch()}>刷新</button>} />
      <section className="drop-zone" onDragOver={(event) => event.preventDefault()} onDrop={drop} tabIndex={0} aria-label="Demo 拖放区">
        <div className="drop-icon">.DEM</div><h2>拖入一个或多个 Demo</h2><p>不会复制或删除源文件。大文件哈希进度会显示在任务列表。</p><button className="button primary" onClick={() => void choose()}>选择 Demo 文件</button>
      </section>
      {importMutation.isError && <ErrorState error={importMutation.error} />}
      <div className="section-grid">
        <section><div className="section-title"><div><span className="eyebrow">QUEUE</span><h2>解析任务</h2></div></div>{jobs.isLoading ? <LoadingState /> : jobs.isError ? <ErrorState error={jobs.error} /> : jobItems.length === 0 ? <EmptyState text="还没有解析任务" /> : <div className="job-list">{jobItems.slice(0, 8).map((job) => <div className="job" key={job.job_id}><div><strong>{job.type}</strong><span>{job.stage}</span></div><div className="progress"><i style={{ width: `${job.progress}%` }} /></div><span>{job.progress}%</span>{job.error_message && <small className="danger">{job.error_code}: {job.error_message}</small>}</div>)}</div>}</section>
        <section><div className="section-title"><div><span className="eyebrow">FILES</span><h2>已导入文件</h2></div></div>{demos.isLoading ? <LoadingState /> : demos.isError ? <ErrorState error={demos.error} /> : demoItems.length === 0 ? <EmptyState text="选择 Demo 后会显示在这里" /> : <div className="file-list">{demoItems.map((demo) => <article key={demo.demo_id}><div className="file-main"><strong>{demo.filename}</strong><span>{(demo.size_bytes / 1024 / 1024).toFixed(1)} MB · {demo.sha256.slice(0, 10)}…</span></div><StatusPill tone={demo.exists ? "good" : "warning"}>{demo.status}</StatusPill><button className="button compact" disabled={!demo.exists || parseMutation.isPending} onClick={() => parseMutation.mutate(demo.demo_id)}>解析</button></article>)}</div>}</section>
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) { return <div className="empty"><strong>{text}</strong><span>完成前置步骤后，这里会自动更新。</span></div>; }

function HistoryPage() {
  const matches = useQuery({ queryKey: ["matches"], queryFn: () => rpc<ListResult<MatchItem>>("list_matches") });
  const selected = useUiStore((state) => state.selectedMatches);
  const toggle = useUiStore((state) => state.toggleMatch);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const remove = useMutation({ mutationFn: (id: string) => rpc("delete_match_data", { match_id: id }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["matches"] }) });
  const matchItems = matches.data?.items ?? [];
  return (
    <div className="page"><PageHeader eyebrow="HISTORY" title="历史分析中心" description="按对局内玩家 ID/名称匹配本人，并检查数据质量与源文件状态。" actions={<button className="button primary" disabled={!selected.length} onClick={() => navigate("/analysis")}>分析已选 {selected.length} 场</button>} />
      {matches.isLoading ? <LoadingState /> : matches.isError ? <ErrorState error={matches.error} retry={() => void matches.refetch()} /> : matchItems.length === 0 ? <EmptyState text="还没有已解析比赛" /> : <div className="match-grid">{matchItems.map((match) => <article className={`match-card ${selected.includes(match.match_id) ? "selected" : ""}`} key={match.match_id}><label className="match-select"><input type="checkbox" checked={selected.includes(match.match_id)} onChange={() => toggle(match.match_id)} /><span>加入分析</span></label><div className="match-map"><span>{match.map_name}</span><StatusPill tone={match.player_match_status === "matched" ? (match.source_exists ? "good" : "warning") : "danger"}>{match.player_match_status === "matched" ? (match.source_exists ? "源文件可用" : "源文件丢失") : "未匹配本人"}</StatusPill></div><strong className="score">{match.round_wins ?? "—"} <small>/ {match.rounds}</small></strong><div className="match-stats"><span>K/D <strong>{match.kd?.toFixed(2) ?? "—"}</strong></span><span>ADR <strong>{match.adr?.toFixed(1) ?? "—"}</strong></span><span>解析 <strong>{match.parse_status}</strong></span></div><DataQualityBadges quality={match.quality} /><div className="card-actions"><button className="button compact danger-outline" onClick={() => { if (window.confirm("只删除 RoundLens 解析数据，绝不会删除源 Demo。继续？")) remove.mutate(match.match_id); }}>删除解析</button></div></article>)}</div>}
    </div>
  );
}

function ReportsPage() {
  const navigate = useNavigate();
  const reports = useQuery({
    queryKey: ["analyses"],
    queryFn: () => rpc<ListResult<ReportListItem>>("list_analyses"),
  });
  const items = reports.data?.items ?? [];
  return (
    <div className="page">
      <PageHeader
        eyebrow="REPORT LIBRARY"
        title="报告中心"
        description="本地报告与 AI 教练报告都保存在这里，可随时手动打开。"
        actions={
          <button className="button secondary" onClick={() => void reports.refetch()}>
            刷新
          </button>
        }
      />
      {reports.isLoading ? (
        <LoadingState label="正在读取报告列表" />
      ) : reports.isError ? (
        <ErrorState error={reports.error} retry={() => void reports.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState text="还没有生成报告" />
      ) : (
        <div className="match-grid">
          {items.map((item) => (
            <article className="match-card" key={item.analysis_id}>
              <div className="match-map">
                <span>{item.report_kind === "ai" ? "AI 教练报告" : "本地确定性报告"}</span>
                <StatusPill
                  tone={!item.report_available ? "danger" : item.source_changed ? "warning" : "good"}
                >
                  {!item.report_available ? "文件缺失" : item.source_changed ? "源数据已变化" : "可打开"}
                </StatusPill>
              </div>
              <p className="fine-print">
                {item.one_sentence_summary ?? "报告摘要不可用"}
              </p>
              <div className="match-stats">
                <span>比赛<strong>{item.match_count}</strong></span>
                <span>回合<strong>{item.rounds_analyzed ?? "—"}</strong></span>
                <span>置信度<strong>{item.data_confidence === null ? "—" : `${Math.round(item.data_confidence * 100)}%`}</strong></span>
              </div>
              <p className="fine-print">{new Date(item.created_at).toLocaleString()}</p>
              <div className="card-actions">
                <button
                  className="button primary compact"
                  disabled={!item.report_available}
                  onClick={() => navigate(`/report/${item.analysis_id}`)}
                >
                  手动打开报告
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function CreateAnalysisPage() {
  const selected = useUiStore((state) => state.selectedMatches);
  const clear = useUiStore((state) => state.clearMatches);
  const matches = useQuery({ queryKey: ["matches"], queryFn: () => rpc<ListResult<MatchItem>>("list_matches") });
  const settings = useSettings();
  const keyStatus = useQuery({ queryKey: ["api-key-configured"], queryFn: secretStatus });
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: async (mode: "local" | "ai") => {
      const local = await rpc<{ analysis_id: string; report: CoachingReport }>(
        "create_analysis",
        { match_ids: selected },
      );
      if (mode === "local") return { ...local, aiError: null };
      try {
        const generated = await generateAiReport<CoachingReport>(local.analysis_id);
        return { ...generated, aiError: null };
      } catch (error) {
        return { ...local, aiError: formatError(error) };
      }
    },
    onSuccess: (data) => {
      clear();
      navigate(`/report/${data.analysis_id}`, {
        state: { report: data.report, aiError: data.aiError },
      });
    },
  });
  const chosen = matches.data?.items.filter((match) => selected.includes(match.match_id)) ?? [];
  const aiConfigured = Boolean(settings.data?.provider && keyStatus.data);
  if (!selected.length) return <Navigate to="/history" replace />;
  return (
    <div className="page">
      <PageHeader eyebrow="CREATE ANALYSIS" title="确认分析范围" description="报告只聚合已选择比赛；地图站位不会跨地图直接合并。" />
      <div className="analysis-layout">
        <section className="panel">
          <h2>已选比赛</h2>
          {chosen.map((match) => (
            <div className="selected-row" key={match.match_id}>
              <strong>{match.map_name}</strong>
              <span>{match.rounds} 回合 · {match.parse_status}</span>
            </div>
          ))}
        </section>
        <section className="panel accent">
          <span className="eyebrow">REPORT MODE</span>
          <h2>选择报告生成方式</h2>
          <p>两种方式都会先在本机计算指标、问题、优势和复盘回合。</p>
          <div className="button-row report-actions">
            <button
              className="button secondary wide"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate("local")}
            >
              {mutation.isPending && mutation.variables === "local"
                ? "正在生成本地报告"
                : "生成本地报告"}
            </button>
            <button
              className="button primary wide"
              disabled={mutation.isPending || !aiConfigured}
              onClick={() => mutation.mutate("ai")}
            >
              {mutation.isPending && mutation.variables === "ai"
                ? "正在生成完整报告"
                : "生成完整 AI 报告"}
            </button>
          </div>
          <p className="fine-print">
            完整报告仅发送脱敏后的聚合指标，不发送 Demo、原始 Tick 或轨迹。
            {!aiConfigured && " 请先在设置中保存 API 服务和 Key。"}
          </p>
          {!aiConfigured && (
            <button className="button compact" onClick={() => navigate("/settings")}>
              前往配置 AI
            </button>
          )}
          {mutation.isError && <ErrorState error={mutation.error} />}
        </section>
      </div>
    </div>
  );
}

function ReportPage() {
  const { analysisId = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const navigationState = location.state as {
    report?: CoachingReport;
    aiError?: string | null;
  } | null;
  const initial = navigationState?.report;
  const [generationWarning, setGenerationWarning] = useState<string | null>(
    navigationState?.aiError ?? null,
  );
  const reportQuery = useQuery({ queryKey: ["analysis", analysisId], queryFn: () => rpc<{ report: CoachingReport }>("get_analysis", { analysis_id: analysisId }), initialData: initial ? { report: initial } : undefined });
  const aiMutation = useMutation({
    mutationFn: () => generateAiReport<CoachingReport>(analysisId),
    onSuccess: async () => {
      setGenerationWarning(null);
      await reportQuery.refetch();
    },
  });
  if (reportQuery.isLoading) return <LoadingState label="正在读取报告" />;
  if (reportQuery.isError) return <ErrorState error={reportQuery.error} retry={() => void reportQuery.refetch()} />;
  if (!reportQuery.data) return <ErrorState error={new Error("报告响应为空")} />;
  return <ReportView report={reportQuery.data.report} onReview={(roundId) => navigate(`review/${encodeURIComponent(roundId)}`)} aiAction={<><button className="button secondary" onClick={() => navigate("/reports")}>报告中心</button><button className="button secondary" disabled={aiMutation.isPending} onClick={() => aiMutation.mutate()}>{aiMutation.isPending ? "AI 正在组织报告" : "生成 AI 教练报告"}</button></>} aiError={aiMutation.error ?? (generationWarning ? new Error(generationWarning) : null)} />;
}

export function ReportView({ report, onReview = () => undefined, aiAction, aiError }: { report: CoachingReport; onReview?: (id: string) => void; aiAction?: React.ReactNode; aiError?: unknown }) {
  return <div className="page report-page"><PageHeader eyebrow="COACHING REPORT" title="问题优先报告" description={report.report_summary.one_sentence_summary} actions={aiAction} />{aiError !== undefined && aiError !== null && <ErrorState error={aiError} />}<div className="report-meta"><span>{report.report_summary.matches_analyzed} 场比赛</span><span>{report.report_summary.rounds_analyzed} 回合</span><span>数据置信度 {(report.report_summary.data_confidence * 100).toFixed(0)}%</span><span>Schema {report.schema_version}</span></div>{report.warnings.length > 0 && <div className="warning-box">{report.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}
    <section className="report-section"><div className="section-title"><div><span className="eyebrow">PRIORITY ISSUES</span><h2>最影响复盘优先级的问题</h2></div></div>{report.priority_issues.length === 0 ? <EmptyState text="当前样本未触发高置信度问题" /> : <div className="issue-list">{report.priority_issues.map((issue) => <article className={`issue issue-${issue.severity}`} key={issue.issue_id}><span className="rank">0{issue.priority_rank}</span><div><div className="issue-head"><h3>{issue.title}</h3><StatusPill tone={issue.severity === "high" ? "danger" : "warning"}>规则影响 {issue.impact_score}</StatusPill></div><p>{issue.evidence_summary} {issue.why_it_matters}</p><div className="metric-refs">{issue.metric_refs.map((metric) => <code key={metric}>{metric}</code>)}</div><div className="next-rule"><span>下一场规则</span><strong>{issue.next_match_rule}</strong></div></div></article>)}</div>}</section>
    <section className="report-section"><div className="section-title"><div><span className="eyebrow">REVIEW ROUNDS</span><h2>最值得复盘的回合</h2></div></div>{report.review_rounds.length === 0 ? <EmptyState text="没有证据充足的复盘回合" /> : <div className="review-grid">{report.review_rounds.map((round) => <button className="review-card" key={round.round_id} onClick={() => onReview(round.round_id)}><span>{round.review_type}</span><h3>{round.title}</h3><p>{round.key_event_summary}</p><strong>打开事件时间线</strong></button>)}</div>}</section>
    <div className="two-column"><section className="report-section"><div className="section-title"><div><span className="eyebrow">STRENGTHS</span><h2>应继续保持</h2></div></div>{report.strengths.length === 0 ? <EmptyState text="优势稳定性样本不足" /> : report.strengths.map((strength) => <article className="strength" key={strength.strength_id}><h3>{strength.title}</h3><p>{strength.evidence_summary}</p><strong>{strength.maintain_rule}</strong></article>)}</section><section className="report-section"><div className="section-title"><div><span className="eyebrow">TRAINING</span><h2>{report.training_plan.period}</h2></div></div>{report.training_plan.primary_goals.map((goal) => <article className="goal" key={goal.metric_id}><h3>{goal.title}</h3><p>{goal.metric_id}: {goal.current_value?.toFixed(2) ?? "—"} → {goal.target_value?.toFixed(2) ?? "保持"}</p><strong>{goal.behavior_rule}</strong></article>)}</section></div>
    <section className="report-section"><div className="section-title"><div><span className="eyebrow">DIMENSIONS</span><h2>能力维度</h2></div></div><div className="dimensions">{Object.entries(report.dimension_summaries).map(([name, dimension]) => <article key={name}><span>{name.replaceAll("_", " ")}</span><strong>{dimension.grade}</strong><small>{dimension.main_negative ?? dimension.main_positive ?? "样本有限"}</small></article>)}</div></section>
  </div>;
}

function ReviewPage() {
  const { analysisId = "", roundId = "" } = useParams();
  const query = useQuery({ queryKey: ["analysis", analysisId], queryFn: () => rpc<{ report: CoachingReport }>("get_analysis", { analysis_id: analysisId }) });
  const decoded = decodeURIComponent(roundId);
  if (query.isLoading) return <LoadingState />;
  if (query.isError) return <ErrorState error={query.error} />;
  if (!query.data) return <ErrorState error={new Error("报告响应为空")} />;
  const round = query.data.report.review_rounds.find((item) => item.round_id === decoded);
  if (!round) return <ErrorState error={new Error("报告中不存在该复盘回合")} />;
  return <div className="page"><PageHeader eyebrow="ROUND REVIEW" title={round.title} description={round.why_review} /><div className="review-layout"><section className="map-fallback"><span className="eyebrow">2D SNAPSHOT</span><div className="radar-placeholder"><i /><p>地图资源不可用时显示文本时间线，不绘制错误地图。</p></div></section><section className="panel"><h2>关键事件</h2><div className="timeline"><div><i /><strong>{round.key_event_summary}</strong><span>{round.issue_tags.join(" · ")}</span></div></div><h2>复盘问题</h2>{round.review_questions.map((question) => <p key={question}>{question}</p>)}<div className="next-rule"><span>推荐替代行动</span><strong>{round.recommended_action}</strong></div></section></div></div>;
}

function TrendsPage() { return <div className="page"><PageHeader eyebrow="TRENDS" title="趋势与训练" description="趋势只在多场有效样本中计算；单场观察不会标记为长期改善或恶化。" /><EmptyState text="生成多场报告后显示趋势" /></div>; }

function SettingsPage() {
  const settings = useSettings();
  if (settings.isLoading) return <LoadingState />;
  if (settings.isError) return <ErrorState error={settings.error} />;
  if (!settings.data) return <ErrorState error={new Error("设置响应为空")} />;
  return <SettingsForm initial={settings.data} />;
}

function SettingsForm({ initial }: { initial: Settings }) {
  const queryClient = useQueryClient();
  const [playerIdentifier, setPlayerIdentifier] = useState(initial.player_identifier ?? "");
  const [apiKey, setKey] = useState("");
  const [configured, setConfigured] = useState(false);
  const [provider, setProvider] = useState<ProviderSettings>(initial.provider ?? { base_url: "https://api.openai.com/v1", model: "gpt-4.1-mini", temperature: 0.2, max_tokens: 3000, timeout_seconds: 60, output_mode: "structured_output" });
  useEffect(() => { void secretStatus().then(setConfigured).catch(() => setConfigured(false)); }, []);
  const saveProfile = useMutation({ mutationFn: () => rpc("update_profile", { player_identifier: playerIdentifier.trim(), locale: initial.locale, scan_directories: initial.scan_directories, onboarding_complete: true }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["settings"] }) });
  const saveProvider = useMutation({ mutationFn: async () => { await rpc("update_provider", { ...provider }); if (apiKey) { await setApiKey(apiKey); setKey(""); setConfigured(true); } }, onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["settings"] }) });
  const connection = useMutation({ mutationFn: () => testProvider() });
  return <div className="page"><PageHeader eyebrow="SETTINGS" title="设置与隐私" description="非敏感设置写入本地数据库；API Key 只进入 Windows Credential Manager。" /><div className="settings-grid"><form className="panel" onSubmit={(event) => { event.preventDefault(); if (isValidPlayerIdentifier(playerIdentifier)) saveProfile.mutate(); }}><h2>本人档案</h2><label>对局内玩家 ID/名称<input value={playerIdentifier} onChange={(event) => setPlayerIdentifier(event.target.value)} placeholder="记分板中的玩家名称或 SteamID64" /></label><label>数据目录<input readOnly value={initial.data_dir} /></label><button className="button primary" disabled={!isValidPlayerIdentifier(playerIdentifier) || saveProfile.isPending}>保存档案</button>{saveProfile.isError && <ErrorState error={saveProfile.error} />}</form><form className="panel" onSubmit={(event) => { event.preventDefault(); saveProvider.mutate(); }}><div className="settings-head"><h2>OpenAI-compatible API</h2><StatusPill tone={configured ? "good" : "neutral"}>{configured ? "Key 已配置" : "未配置"}</StatusPill></div><label>Base URL<input value={provider.base_url} onChange={(event) => setProvider({ ...provider, base_url: event.target.value })} /></label><label>模型<input value={provider.model} onChange={(event) => setProvider({ ...provider, model: event.target.value })} /></label><label>输出模式<select value={provider.output_mode} onChange={(event) => setProvider({ ...provider, output_mode: event.target.value as ProviderSettings["output_mode"] })}><option value="structured_output">JSON Schema</option><option value="json_mode">JSON Mode</option><option value="plain_json_prompt">严格 JSON 提示</option></select></label><label>API Key<input type="password" autoComplete="new-password" value={apiKey} onChange={(event) => setKey(event.target.value)} placeholder={configured ? "留空则不更改" : "仅保存到 Credential Manager"} /></label><div className="button-row"><button className="button primary">保存 API 设置</button><button type="button" className="button secondary" onClick={() => connection.mutate()}>测试连接</button><button type="button" className="button danger-outline" onClick={async () => { await clearApiKey(); setConfigured(false); }}>清除 Key</button></div><p className="fine-print">测试连接可能产生极少量 API 消耗。React 无法读取已保存的 Key。</p>{connection.isSuccess && <p className="success">连接成功</p>}{connection.isError && <ErrorState error={connection.error} />}</form></div></div>;
}
