// This project was developed with assistance from AI tools.

import { useState, useMemo } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';
import { Shield, ChevronLeft, ChevronRight, Download, ArrowUpDown } from 'lucide-react';
import { useAuditEventsFiltered } from '@/hooks/use-audit';
import type { AuditEventItem } from '@/schemas/audit';
import { cn } from '@/lib/utils';
import { staffName } from '@/lib/staff-names';

export const Route = createFileRoute('/_authenticated/ceo/audit')({
  component: AuditTrailPage,
});

// -- Constants ----------------------------------------------------------------

const TIME_RANGES = [
  { label: '30天', value: 30 },
  { label: '60天', value: 60 },
  { label: '90天', value: 90 },
  { label: '180天', value: 180 },
  { label: '1年', value: 365 },
] as const;

const PAGE_SIZE = 50;

const EVENT_TYPE_BADGE: Record<string, string> = {
  application_created:
    'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  application_updated: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
  application_submitted:
    'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  status_changed:
    'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  stage_transition:
    'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  document_uploaded: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  document_extracted:
    'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400',
  credit_pulled:
    'bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900/30 dark:text-fuchsia-400',
  prequalification_issued:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  risk_assessment_completed:
    'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  compliance_check_completed:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  decision_created:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  decision_made:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  condition_added: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400',
  condition_cleared: 'bg-lime-100 text-lime-700 dark:bg-lime-900/30 dark:text-lime-400',
  disclosure_acknowledged:
    'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  communication_sent: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
  chat_session_started:
    'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  agent_tool_called: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400',
  risk_assessment:
    'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  compliance_check:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
};

const ROLE_BADGE: Record<string, string> = {
  borrower: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  loan_officer:
    'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  underwriter: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  ceo: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  system: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-400',
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  application_created: '创建申请',
  application_updated: '更新申请',
  application_submitted: '提交申请',
  status_changed: '状态变更',
  stage_transition: '阶段变更',
  document_uploaded: '上传材料',
  document_extracted: '识别材料',
  document_status_changed: '材料状态变更',
  credit_pulled: '征信查询',
  prequalification_issued: '完成预审',
  risk_assessment_completed: '完成风险评估',
  compliance_check_completed: '完成合规检查',
  decision_created: '生成审批提案',
  decision_made: '审批决策',
  condition_added: '新增审批条件',
  condition_cleared: '完成审批条件',
  disclosure_acknowledged: '确认信息披露',
  communication_sent: '发送客户通知',
  chat_session_started: '开始智能咨询',
  agent_tool_called: '智能服务调用',
  risk_assessment: '风险评估',
  compliance_check: '合规检查',
};

const ROLE_LABELS: Record<string, string> = {
  prospect: '访客',
  borrower: '借款人',
  loan_officer: '客户经理',
  underwriter: '审批人员',
  ceo: '管理人员',
  system: '系统',
  admin: '管理员',
};

const STAGE_LABELS: Record<string, string> = {
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

const TOOL_LABELS: Record<string, string> = {
  lo_pipeline_summary: '客户经理业务概览查询',
  lo_application_detail: '申请详情查询',
  lo_document_review: '申请材料复核',
  lo_completeness_check: '材料完整性检查',
  kb_search: '政策库查询',
  uw_risk_assessment: '风险评估',
  uw_compliance_check: '合规检查',
};

const DECISION_LABELS: Record<string, string> = {
  approved: '同意',
  conditional_approval: '有条件同意',
  suspended: '暂缓',
  denied: '拒绝',
};

type SortField = 'timestamp' | 'event_type' | 'user_id';
type SortDir = 'asc' | 'desc';

// -- Helpers ------------------------------------------------------------------

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function eventDescription(event: AuditEventItem): string {
  const data = event.event_data;
  const fallback = EVENT_TYPE_LABELS[event.event_type] ?? '其他业务操作';
  if (!data) return fallback;

  // For tool invocations, show the tool name as the primary detail
  if (event.event_type === 'agent_tool_called') {
    const toolName = data.tool_name ?? data.tool;
    if (typeof toolName === 'string')
      return TOOL_LABELS[toolName] ?? '智能业务服务调用';
  }

  if (typeof data.description === 'string')
    return /\p{Script=Han}/u.test(data.description) ? data.description : fallback;
  if (typeof data.message === 'string')
    return /\p{Script=Han}/u.test(data.message) ? data.message : fallback;
  if (typeof data.detail === 'string')
    return /\p{Script=Han}/u.test(data.detail) ? data.detail : fallback;

  if (event.event_type === 'stage_transition' && data.from_stage && data.to_stage) {
    return `办理阶段由“${STAGE_LABELS[String(data.from_stage)] ?? String(data.from_stage)}”变更为“${STAGE_LABELS[String(data.to_stage)] ?? String(data.to_stage)}”`;
  }
  if (event.event_type === 'decision_made' && data.decision) {
    const decision = String(data.decision);
    return `审批结论：${DECISION_LABELS[decision] ?? '已记录'}`;
  }

  return fallback;
}

function truncateId(id: string | number | null | undefined): string {
  if (id == null) return '--';
  const s = String(id);
  if (s.length > 12) return s.slice(0, 8) + '...';
  return s;
}

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

// -- Component ----------------------------------------------------------------

function AuditTrailPage() {
  const [days, setDays] = useState(90);
  const [eventType, setEventType] = useState('');
  const [page, setPage] = useState(0);
  const [sortField, setSortField] = useState<SortField>('timestamp');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const { data, isLoading } = useAuditEventsFiltered(days, eventType, 5000);

  const eventTypes = useMemo(() => {
    if (!data?.events) return [];
    const types = new Set(data.events.map((e) => e.event_type));
    return Array.from(types).sort();
  }, [data]);

  const sortedEvents = useMemo(() => {
    if (!data?.events) return [];
    const events = [...data.events];
    events.sort((a, b) => {
      let cmp = 0;
      if (sortField === 'timestamp') {
        cmp = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
      } else if (sortField === 'event_type') {
        cmp = a.event_type.localeCompare(b.event_type);
      } else if (sortField === 'user_id') {
        cmp = staffName(a.user_id).localeCompare(staffName(b.user_id));
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return events;
  }, [data, sortField, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sortedEvents.length / PAGE_SIZE));
  const pagedEvents = sortedEvents.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir(field === 'timestamp' ? 'desc' : 'asc');
    }
  }

  function handleExport() {
    const params = new URLSearchParams({
      fmt: 'csv',
      days: String(days),
      limit: '5000',
    });
    if (eventType) params.set('event_type', eventType);
    window.open(`/api/audit/export?${params.toString()}`);
  }

  function SortHeader({
    field,
    children,
  }: {
    field: SortField;
    children: React.ReactNode;
  }) {
    const isActive = sortField === field;
    return (
      <button
        onClick={() => toggleSort(field)}
        className="inline-flex items-center gap-1 font-semibold text-muted-foreground hover:text-foreground"
      >
        {children}
        <ArrowUpDown className={cn('h-3 w-3', isActive && 'text-foreground')} />
      </button>
    );
  }

  return (
    <div className="mx-auto max-w-[1280px] p-6 md:p-8">
      {/* Breadcrumb */}
      <nav className="mb-4 text-sm text-muted-foreground">
        <Link to="/ceo" className="hover:text-foreground">
          管理驾驶舱
        </Link>
        <span className="mx-2">/</span>
        <span className="text-foreground">操作记录</span>
      </nav>

      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#1e3a5f]/10">
            <Shield className="h-5 w-5 text-[#1e3a5f]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">操作记录</h1>
            <p className="text-sm text-muted-foreground">
              {data ? `共 ${data.count.toLocaleString()} 条记录` : '加载中…'}
            </p>
          </div>
        </div>
        <button
          onClick={handleExport}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-foreground shadow-sm hover:bg-slate-50 dark:bg-slate-900 dark:hover:bg-slate-800"
        >
          <Download className="h-4 w-4" />
          导出 CSV
        </button>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <div className="inline-flex rounded-lg border border-border bg-white p-1 dark:bg-slate-900">
          {TIME_RANGES.map((range) => (
            <button
              key={range.value}
              onClick={() => {
                setDays(range.value);
                setPage(0);
              }}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                days === range.value
                  ? 'bg-[#1e3a5f] text-white'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {range.label}
            </button>
          ))}
        </div>

        <select
          value={eventType}
          onChange={(e) => {
            setEventType(e.target.value);
            setPage(0);
          }}
          className="rounded-lg border border-border bg-white px-3 py-2 text-sm text-foreground shadow-sm dark:bg-slate-900"
        >
          <option value="">全部操作类型</option>
          {eventTypes.map((type) => (
            <option key={type} value={type}>
              {EVENT_TYPE_LABELS[type] ?? '其他业务操作'}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-border bg-white shadow-sm dark:bg-slate-900">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
                <th className="px-6 py-3 text-left">
                  <SortHeader field="timestamp">时间</SortHeader>
                </th>
                <th className="px-6 py-3 text-left">
                  <SortHeader field="event_type">操作类型</SortHeader>
                </th>
                <th className="px-6 py-3 text-left">
                  <SortHeader field="user_id">操作人</SortHeader>
                </th>
                <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                  角色
                </th>
                <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                  申请编号
                </th>
                <th className="px-6 py-3 text-left font-semibold text-muted-foreground">
                  操作说明
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i} className="border-b border-border">
                    <td className="px-6 py-3">
                      <Skeleton className="h-4 w-36" />
                    </td>
                    <td className="px-6 py-3">
                      <Skeleton className="h-5 w-28 rounded" />
                    </td>
                    <td className="px-6 py-3">
                      <Skeleton className="h-4 w-20" />
                    </td>
                    <td className="px-6 py-3">
                      <Skeleton className="h-5 w-16 rounded" />
                    </td>
                    <td className="px-6 py-3">
                      <Skeleton className="h-4 w-16" />
                    </td>
                    <td className="px-6 py-3">
                      <Skeleton className="h-4 w-48" />
                    </td>
                  </tr>
                ))
              ) : pagedEvents.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-12 text-center text-muted-foreground"
                  >
                    当前筛选条件下暂无操作记录。
                  </td>
                </tr>
              ) : (
                pagedEvents.map((event) => {
                  const badgeClass =
                    EVENT_TYPE_BADGE[event.event_type] ??
                    'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-400';
                  const roleClass =
                    ROLE_BADGE[event.user_role ?? ''] ??
                    'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-400';

                  return (
                    <tr
                      key={event.id}
                      className="border-b border-border hover:bg-slate-50/50 dark:hover:bg-slate-800/30"
                    >
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
                      <td className="px-6 py-3 text-foreground">
                        {event.user_role === 'prospect'
                          ? '访客用户'
                          : staffName(event.user_id)}
                      </td>
                      <td className="px-6 py-3">
                        {event.user_role ? (
                          <span
                            className={cn(
                              'inline-flex items-center rounded px-2 py-0.5 text-xs font-medium',
                              roleClass,
                            )}
                          >
                            {ROLE_LABELS[event.user_role] ?? '其他角色'}
                          </span>
                        ) : (
                          '--'
                        )}
                      </td>
                      <td
                        className="px-6 py-3 text-muted-foreground"
                        title={
                          event.application_id != null
                            ? String(event.application_id)
                            : undefined
                        }
                      >
                        {truncateId(event.application_id)}
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

        {/* Pagination */}
        {sortedEvents.length > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-border bg-slate-50 px-6 py-3 dark:bg-slate-800/50">
            <p className="text-sm text-muted-foreground">
              显示第 {page * PAGE_SIZE + 1}—
              {Math.min((page + 1) * PAGE_SIZE, sortedEvents.length)} 条，共{' '}
              {sortedEvents.length} 条
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="inline-flex items-center rounded-md border border-border bg-white px-2 py-1 text-sm text-foreground shadow-sm hover:bg-slate-50 disabled:opacity-50 dark:bg-slate-900 dark:hover:bg-slate-800"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-sm text-muted-foreground">
                第 {page + 1} / {totalPages} 页
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="inline-flex items-center rounded-md border border-border bg-white px-2 py-1 text-sm text-foreground shadow-sm hover:bg-slate-50 disabled:opacity-50 dark:bg-slate-900 dark:hover:bg-slate-800"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
