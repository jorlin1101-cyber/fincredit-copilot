// This project was developed with assistance from AI tools.

import { useState } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';
import {
  Activity,
  TrendingDown,
  Users,
  Shield,
  ChevronDown,
  ChevronUp,
  Star,
} from 'lucide-react';
import {
  usePipelineSummary,
  useDenialTrends,
  useLOPerformance,
} from '@/hooks/use-analytics';
import { useAuditEvents } from '@/hooks/use-audit';
import type { PipelineSummary } from '@/schemas/analytics';
import type { DenialTrends } from '@/schemas/analytics';
import type { LOPerformanceSummary } from '@/schemas/analytics';
import type { AuditSearchResponse, AuditEventItem } from '@/schemas/audit';
import { cn } from '@/lib/utils';
import { staffName } from '@/lib/staff-names';
import { COMPANY_NAME } from '@/lib/company';

export const Route = createFileRoute('/_authenticated/ceo/')({
  component: CeoDashboard,
});

// -- Helpers ------------------------------------------------------------------

const DEFAULT_DAYS = 180;

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-slate-200 dark:bg-slate-700',
        className,
      )}
    />
  );
}

function CardShell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-white p-6 shadow-sm dark:bg-slate-900',
        className,
      )}
    >
      {children}
    </div>
  );
}

function CardHeader({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div className="mb-4 flex items-center gap-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#1e3a5f]/10">
        <Icon className="h-4 w-4 text-[#1e3a5f]" />
      </div>
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
    </div>
  );
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

const DENIAL_REASON_LABELS: Record<string, string> = {
  'High DTI ratio': '负债收入比偏高',
  'Credit score below minimum': '征信评分未达到准入要求',
  'Insufficient income documentation': '收入证明材料不足',
  'Appraisal shortfall': '房产评估价值不足',
};

function denialReasonLabel(reason: string): string {
  if (DENIAL_REASON_LABELS[reason]) return DENIAL_REASON_LABELS[reason];
  return /\p{Script=Han}/u.test(reason) ? reason : '其他授信政策或风险原因';
}

function safeBusinessText(value: string, fallback: string): string {
  return /\p{Script=Han}/u.test(value) ? value : fallback;
}

const DECISION_LABELS: Record<string, string> = {
  approved: '同意',
  conditional_approval: '有条件同意',
  suspended: '暂缓',
  denied: '拒绝',
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  application_created: '创建申请',
  application_updated: '更新申请',
  stage_transition: '阶段变更',
  document_uploaded: '上传材料',
  document_status_changed: '材料状态变更',
  decision_made: '审批决策',
  compliance_check: '合规检查',
  risk_assessment: '风险评估',
  condition_added: '新增审批条件',
  condition_cleared: '完成审批条件',
  agent_tool_called: '智能服务调用',
};

const ROLE_LABELS: Record<string, string> = {
  borrower: '借款人',
  loan_officer: '客户经理',
  underwriter: '审批人员',
  ceo: '管理人员',
  admin: '管理员',
};

const STAGE_NAME_LABELS: Record<string, string> = {
  inquiry: '咨询',
  prequalification: '预审',
  application: '申请中',
  processing: '材料处理中',
  underwriting: '授信审批',
  conditional_approval: '有条件通过',
  clear_to_close: '具备放款条件',
  closed: '已结案',
  denied: '未通过',
  withdrawn: '已撤回',
};

// -- Cards --------------------------------------------------------------------

function PipelineOverviewCard({ data }: { data: PipelineSummary }) {
  const maxCount = Math.max(...data.by_stage.map((s) => s.count), 1);

  const STAGE_LABELS: Record<string, string> = {
    prospect: '意向咨询',
    inquiry: '咨询',
    pre_qualification: '预审',
    prequalification: '预审',
    application: '申请中',
    processing: '材料处理中',
    underwriting: '授信审批',
    conditional_approval: '有条件通过',
    clear_to_close: '具备放款条件',
    closed: '已结案',
    denied: '未通过',
    withdrawn: '已撤回',
  };

  return (
    <CardShell>
      <CardHeader icon={Activity} title="业务申请概览" />
      <div className="space-y-3">
        {data.by_stage.map((stage) => (
          <div key={stage.stage}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {STAGE_LABELS[stage.stage] ?? stage.stage}
              </span>
              <span className="font-medium text-foreground">{stage.count}</span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-slate-100 dark:bg-slate-800">
              <div
                className="h-2.5 rounded-full bg-[#1e3a5f]"
                style={{ width: `${(stage.count / maxCount) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-6 grid grid-cols-3 gap-4 border-t border-border pt-4">
        <div>
          <p className="text-xs text-muted-foreground">申请转化率</p>
          <p className="text-lg font-bold text-foreground">
            {data.pull_through_rate.toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">平均结案时长</p>
          <p className="text-lg font-bold text-foreground">
            {data.avg_days_to_close != null
              ? `${data.avg_days_to_close.toFixed(1)}天`
              : '--'}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">当前申请数</p>
          <p className="text-lg font-bold text-foreground">{data.total_applications}</p>
        </div>
      </div>
    </CardShell>
  );
}

function PipelineOverviewSkeleton() {
  return (
    <CardShell>
      <CardHeader icon={Activity} title="业务申请概览" />
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i}>
            <div className="mb-1 flex justify-between">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-8" />
            </div>
            <Skeleton className="h-2.5 w-full" />
          </div>
        ))}
      </div>
      <div className="mt-6 grid grid-cols-3 gap-4 border-t border-border pt-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="mb-1 h-3 w-20" />
            <Skeleton className="h-6 w-12" />
          </div>
        ))}
      </div>
    </CardShell>
  );
}

function DenialAnalysisCard({ data }: { data: DenialTrends }) {
  const maxRate = Math.max(...data.trend.map((t) => t.denial_rate), 1);
  const maxReasonPct = Math.max(...data.top_reasons.map((r) => r.percentage), 1);

  return (
    <CardShell>
      <CardHeader icon={TrendingDown} title="未通过申请分析" />

      {/* Avg rate badge */}
      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm text-muted-foreground">总体未通过率</span>
        <span
          className={cn(
            'rounded-full px-2.5 py-0.5 text-sm font-bold',
            data.overall_denial_rate > 15
              ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
              : data.overall_denial_rate > 10
                ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
          )}
        >
          {data.overall_denial_rate.toFixed(1)}%
        </span>
      </div>

      {/* Bar chart (pure CSS) */}
      {data.trend.length > 0 && (
        <div className="mb-4">
          <div className="flex items-end gap-1" style={{ height: 100 }}>
            {data.trend.map((point) => (
              <div
                key={point.period}
                className="group relative flex h-full flex-1 items-end"
              >
                <div
                  className="w-full rounded-t bg-[#1e3a5f] transition-colors hover:bg-[#152e42]"
                  style={{
                    height: `${(point.denial_rate / maxRate) * 100}%`,
                    minHeight: 4,
                  }}
                  title={`${point.period}: ${point.denial_rate.toFixed(1)}%`}
                />
              </div>
            ))}
          </div>
          <div className="mt-1 flex gap-1">
            {data.trend.map((point) => (
              <div
                key={point.period}
                className="flex-1 text-center text-[10px] text-muted-foreground truncate"
              >
                {point.period}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top reasons */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-muted-foreground">
          主要未通过原因
        </h3>
        <div className="space-y-2">
          {data.top_reasons.slice(0, 3).map((reason) => (
            <div key={reason.reason}>
              <div className="mb-0.5 flex items-center justify-between text-sm">
                <span className="truncate text-foreground">
                  {denialReasonLabel(reason.reason)}
                </span>
                <span className="ml-2 shrink-0 text-muted-foreground">
                  {reason.percentage.toFixed(1)}%
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-slate-100 dark:bg-slate-800">
                <div
                  className="h-1.5 rounded-full bg-red-400 dark:bg-red-500"
                  style={{ width: `${(reason.percentage / maxReasonPct) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </CardShell>
  );
}

function DenialAnalysisSkeleton() {
  return (
    <CardShell>
      <CardHeader icon={TrendingDown} title="未通过申请分析" />
      <div className="mb-4 flex items-center gap-2">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-6 w-14 rounded-full" />
      </div>
      <div className="mb-4 flex items-end gap-1" style={{ height: 100 }}>
        {[40, 65, 30, 80, 55, 45].map((h, i) => (
          <div key={i} className="flex-1" style={{ height: `${h}%` }}>
            <Skeleton className="h-full w-full" />
          </div>
        ))}
      </div>
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="mb-1 h-4 w-3/4" />
            <Skeleton className="h-1.5 w-full" />
          </div>
        ))}
      </div>
    </CardShell>
  );
}

function LOPerformanceCard({ data }: { data: LOPerformanceSummary }) {
  const lowestDenialRate = Math.min(...data.loan_officers.map((lo) => lo.denial_rate));

  return (
    <CardShell className="overflow-hidden p-0">
      <div className="p-6 pb-0">
        <CardHeader icon={Users} title="客户经理业务表现" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
              <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                客户经理
              </th>
              <th className="px-6 py-3 text-right font-semibold text-muted-foreground">
                在办申请
              </th>
              <th className="px-6 py-3 text-right font-semibold text-muted-foreground">
                已结案
              </th>
              <th className="px-6 py-3 text-right font-semibold text-muted-foreground">
                未通过率
              </th>
            </tr>
          </thead>
          <tbody>
            {data.loan_officers.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-muted-foreground">
                  暂无客户经理业务数据。
                </td>
              </tr>
            ) : (
              data.loan_officers.map((lo) => {
                const isTopPerformer =
                  lo.denial_rate === lowestDenialRate && data.loan_officers.length > 1;
                const rateColor =
                  lo.denial_rate > 15
                    ? 'text-red-600 dark:text-red-400'
                    : lo.denial_rate > 10
                      ? 'text-amber-600 dark:text-amber-400'
                      : 'text-emerald-600 dark:text-emerald-400';
                const name = lo.lo_name ?? staffName(lo.lo_id);

                return (
                  <tr
                    key={lo.lo_id}
                    className={cn(
                      'border-b border-border',
                      isTopPerformer && 'bg-emerald-50/50 dark:bg-emerald-900/10',
                    )}
                  >
                    <td className="px-6 py-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#1e3a5f] text-xs font-bold text-white">
                          {initials(name)}
                        </div>
                        <span className="font-medium text-foreground">
                          {name}
                          {isTopPerformer && (
                            <Star className="ml-1 inline h-3.5 w-3.5 text-amber-500" />
                          )}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-3 text-right text-foreground">
                      {lo.active_count}
                    </td>
                    <td className="px-6 py-3 text-right text-foreground">
                      {lo.closed_count}
                    </td>
                    <td className={cn('px-6 py-3 text-right font-bold', rateColor)}>
                      {lo.denial_rate.toFixed(1)}%
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </CardShell>
  );
}

function LOPerformanceSkeleton() {
  return (
    <CardShell className="overflow-hidden p-0">
      <div className="p-6 pb-0">
        <CardHeader icon={Users} title="客户经理业务表现" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
              <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                客户经理
              </th>
              <th className="px-6 py-3 text-right font-semibold text-muted-foreground">
                在办申请
              </th>
              <th className="px-6 py-3 text-right font-semibold text-muted-foreground">
                已结案
              </th>
              <th className="px-6 py-3 text-right font-semibold text-muted-foreground">
                未通过率
              </th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 3 }).map((_, i) => (
              <tr key={i} className="border-b border-border">
                <td className="px-6 py-3">
                  <Skeleton className="h-5 w-32" />
                </td>
                <td className="px-6 py-3">
                  <Skeleton className="ml-auto h-5 w-8" />
                </td>
                <td className="px-6 py-3">
                  <Skeleton className="ml-auto h-5 w-8" />
                </td>
                <td className="px-6 py-3">
                  <Skeleton className="ml-auto h-5 w-12" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </CardShell>
  );
}

const EVENT_TYPE_BADGE: Record<string, string> = {
  application_created:
    'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  application_updated: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
  stage_transition:
    'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  document_uploaded: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  decision_made:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  compliance_check:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  risk_assessment:
    'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  condition_added: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400',
  condition_cleared: 'bg-lime-100 text-lime-700 dark:bg-lime-900/30 dark:text-lime-400',
};

function eventDescription(event: AuditEventItem): string {
  const data = event.event_data;
  if (!data) return EVENT_TYPE_LABELS[event.event_type] ?? event.event_type;

  const fallback = EVENT_TYPE_LABELS[event.event_type] ?? '其他业务操作';
  if (typeof data.description === 'string')
    return safeBusinessText(data.description, fallback);
  if (typeof data.message === 'string') return safeBusinessText(data.message, fallback);
  if (typeof data.detail === 'string') return safeBusinessText(data.detail, fallback);

  // Build a description from known fields
  if (event.event_type === 'stage_transition' && data.from_stage && data.to_stage) {
    return `办理阶段由“${STAGE_NAME_LABELS[String(data.from_stage)] ?? String(data.from_stage)}”变更为“${STAGE_NAME_LABELS[String(data.to_stage)] ?? String(data.to_stage)}”`;
  }
  if (event.event_type === 'decision_made' && data.decision) {
    const decision = String(data.decision);
    return `审批结论：${DECISION_LABELS[decision] ?? safeBusinessText(decision, '已记录')}`;
  }

  return fallback;
}

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function AuditEventsCard({ data }: { data: AuditSearchResponse }) {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <CardShell className="overflow-hidden p-0">
      <div className="flex items-center justify-between p-6 pb-0">
        <CardHeader icon={Shield} title="最近操作记录" />
        <button
          onClick={() => setIsExpanded((v) => !v)}
          className="rounded-md p-1 text-muted-foreground hover:bg-slate-100 hover:text-foreground dark:hover:bg-slate-800"
        >
          {isExpanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>
      </div>
      {isExpanded && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
                  <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                    时间
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                    操作类型
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                    操作角色
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                    说明
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.events.length === 0 ? (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-6 py-8 text-center text-muted-foreground"
                    >
                      暂无操作记录。
                    </td>
                  </tr>
                ) : (
                  data.events.map((event) => {
                    const badgeClass =
                      EVENT_TYPE_BADGE[event.event_type] ??
                      'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-400';
                    return (
                      <tr key={event.id} className="border-b border-border">
                        <td className="whitespace-nowrap px-6 py-3 text-muted-foreground">
                          {formatTimestamp(event.timestamp)}
                        </td>
                        <td className="px-6 py-3">
                          <span
                            className={cn(
                              'inline-flex items-center rounded px-2 py-0.5 text-xs font-medium',
                              badgeClass,
                            )}
                          >
                            {EVENT_TYPE_LABELS[event.event_type] ?? '其他业务操作'}
                          </span>
                        </td>
                        <td className="px-6 py-3 text-muted-foreground">
                          {event.user_role
                            ? (ROLE_LABELS[event.user_role] ?? '其他角色')
                            : (event.user_id ?? '--')}
                        </td>
                        <td
                          className="max-w-[300px] truncate px-6 py-3 text-foreground"
                          title={eventDescription(event)}
                        >
                          {eventDescription(event)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <div className="border-t border-border bg-slate-50 px-6 py-3 text-xs text-muted-foreground dark:bg-slate-800/50">
            <Link
              to="/ceo/audit"
              className="text-[#1e3a5f] hover:underline dark:text-sky-400"
            >
              查看全部操作记录
            </Link>
          </div>
        </>
      )}
    </CardShell>
  );
}

function AuditEventsSkeleton() {
  return (
    <CardShell className="overflow-hidden p-0">
      <div className="p-6 pb-0">
        <CardHeader icon={Shield} title="最近操作记录" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
              <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                时间
              </th>
              <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                操作类型
              </th>
              <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                操作角色
              </th>
              <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                说明
              </th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="border-b border-border">
                <td className="px-6 py-3">
                  <Skeleton className="h-4 w-28" />
                </td>
                <td className="px-6 py-3">
                  <Skeleton className="h-5 w-24 rounded" />
                </td>
                <td className="px-6 py-3">
                  <Skeleton className="h-4 w-16" />
                </td>
                <td className="px-6 py-3">
                  <Skeleton className="h-4 w-48" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </CardShell>
  );
}

// -- Main component -----------------------------------------------------------

function CeoDashboard() {
  const pipeline = usePipelineSummary(DEFAULT_DAYS);
  const denials = useDenialTrends(DEFAULT_DAYS);
  const loPerformance = useLOPerformance(DEFAULT_DAYS);
  const auditEvents = useAuditEvents(5);

  return (
    <div className="mx-auto max-w-[1280px] p-6 md:p-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">管理驾驶舱</h1>
        <p className="text-sm text-muted-foreground">
          {COMPANY_NAME} · 住房贷款业务运行概览
        </p>
      </div>

      {/* 2-col grid */}
      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {pipeline.isLoading ? (
          <PipelineOverviewSkeleton />
        ) : pipeline.data ? (
          <PipelineOverviewCard data={pipeline.data} />
        ) : null}
        {denials.isLoading ? (
          <DenialAnalysisSkeleton />
        ) : denials.data ? (
          <DenialAnalysisCard data={denials.data} />
        ) : null}
      </div>

      {/* LO Performance - full width */}
      <div className="mb-6">
        {loPerformance.isLoading ? (
          <LOPerformanceSkeleton />
        ) : loPerformance.data ? (
          <LOPerformanceCard data={loPerformance.data} />
        ) : null}
      </div>

      {/* Audit events - full width */}
      {auditEvents.isLoading ? (
        <AuditEventsSkeleton />
      ) : auditEvents.data ? (
        <AuditEventsCard data={auditEvents.data} />
      ) : null}
    </div>
  );
}
