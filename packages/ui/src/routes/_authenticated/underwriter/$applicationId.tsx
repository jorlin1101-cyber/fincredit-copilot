// This project was developed with assistance from AI tools.

import { useState } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';
import { staffName } from '@/lib/staff-names';
import {
  ChevronRight,
  AlertTriangle,
  CheckCircle2,
  ShieldCheck,
  Scale,
  FileText,
  Gavel,
  Plus,
} from 'lucide-react';
import { useApplication } from '@/hooks/use-applications';
import { useConditions } from '@/hooks/use-conditions';
import { useDecisions } from '@/hooks/use-decisions';
import {
  useRiskAssessment,
  useComplianceResult,
  useDeterministicAssessment,
} from '@/hooks/use-underwriting';
import { useFeatures } from '@/hooks/use-features';
import { formatCurrency, formatDate, formatPercent } from '@/lib/format';
import {
  APPLICATION_STAGE_LABELS,
  LOAN_TYPE_LABELS,
  type ApplicationStage,
} from '@/schemas/enums';
import type { ApplicationResponse } from '@/schemas/applications';
import type { Condition } from '@/schemas/conditions';
import type { DecisionItem } from '@/schemas/decisions';
import { cn } from '@/lib/utils';

// -- Stage-aware action guards ------------------------------------------------

const ASSESSMENT_STAGES = new Set<ApplicationStage>(['underwriting']);
const DECISION_STAGES = new Set<ApplicationStage>([
  'underwriting',
  'conditional_approval',
]);

function stageAllows(
  stage: ApplicationStage | undefined,
  allowed: Set<ApplicationStage>,
): boolean {
  return stage != null && allowed.has(stage);
}

function disabledReason(
  stage: ApplicationStage | undefined,
  allowed: Set<ApplicationStage>,
): string | null {
  if (stageAllows(stage, allowed)) return null;
  const label = stage ? APPLICATION_STAGE_LABELS[stage] : '未知';
  const names = [...allowed].map((s) => APPLICATION_STAGE_LABELS[s]).join('或');
  return `当前处于“${label}”阶段，此操作仅适用于“${names}”阶段。`;
}

const STAGE_BADGE_COLORS: Partial<Record<ApplicationStage, string>> = {
  underwriting: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  conditional_approval:
    'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  clear_to_close:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  closed: 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400',
  denied: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  withdrawn: 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400',
};

export const Route = createFileRoute('/_authenticated/underwriter/$applicationId')({
  component: UnderwriterDetail,
});

// -- Helpers ------------------------------------------------------------------

const SEVERITY_LABELS: Record<string, string> = {
  prior_to_approval: '审批前完成',
  prior_to_docs: '合同文件出具前完成',
  prior_to_closing: '放款签约前完成',
  prior_to_funding: '放款前完成',
};

const SEVERITY_COLORS: Record<string, string> = {
  prior_to_approval: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  prior_to_docs:
    'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  prior_to_closing:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  prior_to_funding: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

const CONDITION_STATUS_COLORS: Record<string, string> = {
  open: 'bg-amber-100 text-amber-700',
  responded: 'bg-blue-100 text-blue-700',
  under_review: 'bg-violet-100 text-violet-700',
  cleared: 'bg-emerald-100 text-emerald-700',
  waived: 'bg-slate-100 text-slate-600',
  escalated: 'bg-red-100 text-red-700',
};

const DECISION_TYPE_LABELS: Record<string, string> = {
  approved: '同意',
  conditional_approval: '有条件同意',
  suspended: '暂缓',
  denied: '拒绝',
};

const CONDITION_STATUS_LABELS: Record<string, string> = {
  open: '待处理',
  responded: '已反馈',
  under_review: '复核中',
  cleared: '已完成',
  waived: '已豁免',
  escalated: '已升级',
};

const COMPLIANCE_STATUS_LABELS: Record<string, string> = {
  PASS: '通过',
  CONDITIONAL_PASS: '有条件通过',
  WARNING: '需关注',
  FAIL: '未通过',
};

const DECISION_TYPE_COLORS: Record<string, string> = {
  approved: 'bg-emerald-100 text-emerald-700',
  conditional_approval: 'bg-amber-100 text-amber-700',
  suspended: 'bg-orange-100 text-orange-700',
  denied: 'bg-red-100 text-red-700',
};

function chatPrefill(message: string, autoSend = true) {
  window.dispatchEvent(
    new CustomEvent('chat-prefill', { detail: { message, autoSend } }),
  );
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

function borrowerName(app: ApplicationResponse): string {
  const primary = app.borrowers?.find((b) => b.is_primary) ?? app.borrowers?.[0];
  if (!primary) return `申请 #${app.id}`;
  return /\p{Script=Han}/u.test(`${primary.first_name}${primary.last_name}`)
    ? `${primary.last_name}${primary.first_name}`
    : `${primary.first_name} ${primary.last_name}`;
}

function localizeConditionDescription(value: string): string {
  const labels: Record<string, string> = {
    'Verify employment with current employer': '核验借款人当前工作及收入情况',
    'Provide most recent two months bank statements': '补充最近两个月的银行流水',
    'USDA property eligibility verification required': '核验县域住房贷款房产资格',
    'Income must not exceed 115% of area median for USDA eligibility':
      '核验家庭收入与贷款方案准入要求',
    'Final title insurance commitment required': '补充最终不动产权属核验材料',
    'Hazard insurance binder with mortgagee clause': '补充含抵押权人信息的房屋保险凭证',
  };
  return labels[value] ?? value;
}

function localizeComplianceRationale(value: string): string {
  return value
    .replace(/PASS/gi, '通过')
    .replace(/FAIL/gi, '未通过')
    .replace(/WARNING/gi, '需关注')
    .replace(/borrower/gi, '借款人')
    .replace(/loan/gi, '贷款')
    .replace(/income/gi, '收入')
    .replace(/document(s)?/gi, '材料')
    .replace(/disclosure(s)?/gi, '信息披露');
}

function recommendationLabel(value: string): string {
  const normalized = value.toLowerCase();
  if (normalized.includes('approve')) return '建议通过';
  if (normalized.includes('deny') || normalized.includes('reject')) return '建议拒绝';
  if (normalized.includes('suspend')) return '建议暂缓并补充核验';
  return value;
}

const ASSESSMENT_SUGGESTION_LABELS: Record<string, string> = {
  READY_FOR_HUMAN_DECISION: '证据与规则校验完成，可进入人工决策',
  NEEDS_SUPPLEMENT: '需要补充材料',
  NEEDS_MANUAL_REVIEW: '存在异常，需要人工复核',
};

const ASSESSMENT_RATING_LABELS: Record<string, string> = {
  Low: '低风险',
  Medium: '中风险',
  High: '高风险',
};

function DeterministicAssessmentCard({
  appId,
  stage,
}: {
  appId: number;
  stage?: ApplicationStage;
}) {
  const [monthlyPayment, setMonthlyPayment] = useState('6500');
  const assessment = useDeterministicAssessment(appId);
  const disabled = !stageAllows(stage, ASSESSMENT_STAGES) || assessment.isPending;
  const result = assessment.data;

  return (
    <CardShell className="border-[#1e3a5f]/20">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <span className="rounded bg-blue-50 px-2 py-0.5 text-xs font-bold text-[#1e3a5f]">
              确定性引擎
            </span>
            <span className="text-xs text-muted-foreground">采用固定公式计算</span>
          </div>
          <h3 className="text-lg font-bold text-foreground">
            负债收入比 / 贷款成数与材料校验
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            输入拟申请贷款的月供，系统按固定公式计算并保留规则版本。
          </p>
        </div>
        <div className="flex items-end gap-2">
          <label className="text-xs text-muted-foreground">
            拟申请月供（元）
            <input
              type="number"
              min="0"
              value={monthlyPayment}
              onChange={(event) => setMonthlyPayment(event.target.value)}
              className="mt-1 block w-32 rounded-lg border border-border bg-transparent px-3 py-2 text-sm text-foreground"
            />
          </label>
          <button
            type="button"
            disabled={disabled || Number(monthlyPayment) < 0}
            onClick={() => assessment.mutate(Number(monthlyPayment))}
            className="rounded-lg bg-[#1e3a5f] px-4 py-2 text-sm font-semibold text-white hover:bg-[#152e42] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {assessment.isPending ? '计算中…' : '执行规则评估'}
          </button>
        </div>
      </div>

      {assessment.isError && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          评估失败，请确认材料已上传且服务可用。
        </p>
      )}

      {!result && !assessment.isError && (
        <div className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-muted-foreground">
          尚未执行。本步骤会计算
          负债收入比（DTI）、贷款成数（LTV），核验身份证、收入证明和银行流水，并输出只供人工参考的风险提示。
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ['DTI', result.dti],
              ['LTV', result.ltv],
            ].map(([label, metric]) => {
              const item = metric as typeof result.dti;
              return (
                <div
                  key={label as string}
                  className="rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-800/50"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-foreground">{label as string}</span>
                    <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-muted-foreground dark:bg-slate-900">
                      {item.rating
                        ? (ASSESSMENT_RATING_LABELS[item.rating] ?? item.rating)
                        : '待计算'}
                    </span>
                  </div>
                  <p className="mt-2 text-3xl font-bold text-[#1e3a5f]">
                    {item.value == null ? '--' : `${item.value.toFixed(2)}%`}
                  </p>
                  <p className="mt-2 break-words text-xs text-muted-foreground">
                    公式：{item.formula}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    规则版本：{item.rule_version}
                  </p>
                </div>
              );
            })}
          </div>
          <div
            className={cn(
              'rounded-lg border p-4',
              result.suggestion === 'READY_FOR_HUMAN_DECISION'
                ? 'border-emerald-200 bg-emerald-50'
                : 'border-amber-200 bg-amber-50',
            )}
          >
            <p className="font-semibold text-foreground">
              {ASSESSMENT_SUGGESTION_LABELS[result.suggestion] ?? result.suggestion}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              材料：{result.documents.provided.length}/
              {result.documents.required.length}；一致性问题：
              {result.consistency_issue_count} 项；人工复核：必须。
            </p>
            {result.documents.missing.length > 0 && (
              <p className="mt-1 text-sm text-amber-800">
                缺失材料：{result.documents.missing.join('、')}
              </p>
            )}
          </div>
        </div>
      )}
    </CardShell>
  );
}

// -- Risk Assessment card -----------------------------------------------------

const RATING_COLORS: Record<string, { icon: string; bar: string; barWidth: string }> = {
  Low: { icon: 'text-emerald-500', bar: 'bg-emerald-500', barWidth: 'w-1/3' },
  Medium: { icon: 'text-amber-500', bar: 'bg-amber-500', barWidth: 'w-2/3' },
  High: { icon: 'text-red-500', bar: 'bg-red-500', barWidth: 'w-full' },
};

function ratingStyle(rating: string | null | undefined) {
  return (
    RATING_COLORS[rating ?? ''] ?? {
      icon: 'text-slate-300',
      bar: 'bg-slate-300',
      barWidth: 'w-0',
    }
  );
}

function RiskAssessmentCard({
  appId,
  stage,
  predictiveModelEnabled,
}: {
  appId: number;
  stage?: ApplicationStage;
  predictiveModelEnabled: boolean;
}) {
  const { data: assessment, isError } = useRiskAssessment(appId);
  const hasData = assessment && !isError;
  const disabled = !stageAllows(stage, ASSESSMENT_STAGES);
  const tooltip = disabledReason(stage, ASSESSMENT_STAGES);

  const metrics = hasData
    ? [
        {
          label: '征信',
          value:
            assessment.credit_value != null ? String(assessment.credit_value) : '--',
          detail: assessment.credit_rating
            ? `${ASSESSMENT_RATING_LABELS[assessment.credit_rating] ?? assessment.credit_rating}`
            : '暂无数据',
          rating: assessment.credit_rating,
        },
        {
          label: '偿付能力 DTI',
          value: assessment.dti_value != null ? `${assessment.dti_value}%` : '--',
          detail: assessment.dti_rating
            ? `${ASSESSMENT_RATING_LABELS[assessment.dti_rating] ?? assessment.dti_rating}`
            : '暂无数据',
          rating: assessment.dti_rating,
        },
        {
          label: '抵押物 LTV',
          value: assessment.ltv_value != null ? `${assessment.ltv_value}%` : '--',
          detail: assessment.ltv_rating
            ? `${ASSESSMENT_RATING_LABELS[assessment.ltv_rating] ?? assessment.ltv_rating}`
            : '暂无数据',
          rating: assessment.ltv_rating,
        },
      ]
    : [
        { label: '征信', value: '--', detail: '运行后生成风险画像', rating: null },
        {
          label: '偿付能力 DTI',
          value: '--',
          detail: '运行后生成风险画像',
          rating: null,
        },
        {
          label: '抵押物 LTV',
          value: '--',
          detail: '运行后生成风险画像',
          rating: null,
        },
      ];

  return (
    <CardShell>
      <div className="mb-6 flex items-center justify-between">
        <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
          <Scale className="h-5 w-5 text-muted-foreground" />
          补充风险画像
          {hasData && assessment.overall_risk && (
            <span
              className={cn(
                'ml-2 rounded px-2 py-0.5 text-xs font-medium',
                assessment.overall_risk === 'Low' && 'bg-emerald-100 text-emerald-700',
                assessment.overall_risk === 'Medium' && 'bg-amber-100 text-amber-700',
                assessment.overall_risk === 'High' && 'bg-red-100 text-red-700',
              )}
            >
              {ASSESSMENT_RATING_LABELS[assessment.overall_risk] ??
                assessment.overall_risk}
            </span>
          )}
        </h3>
        <button
          onClick={() =>
            chatPrefill(`请为申请 #${appId} 生成补充风险画像，并说明证据来源。`)
          }
          disabled={disabled}
          title={tooltip ?? undefined}
          className="flex items-center gap-1.5 rounded-lg bg-[#1e3a5f] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[#152e42] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {hasData ? '重新运行' : '运行画像'}
        </button>
      </div>
      <div
        className={cn(
          'grid grid-cols-1 gap-4',
          predictiveModelEnabled ? 'sm:grid-cols-4' : 'sm:grid-cols-3',
        )}
      >
        {metrics.map((m) => {
          const style = ratingStyle(m.rating);
          return (
            <div
              key={m.label}
              className="rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-800/50"
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-muted-foreground">
                  {m.label}
                </span>
                <CheckCircle2 className={cn('h-5 w-5', style.icon)} />
              </div>
              <p className="text-2xl font-bold text-foreground">{m.value}</p>
              <p className="mt-1 text-xs text-muted-foreground">{m.detail}</p>
              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    style.bar,
                    style.barWidth,
                  )}
                />
              </div>
            </div>
          );
        })}
        {predictiveModelEnabled &&
          (() => {
            const hasResult = hasData && assessment.predictive_model_result;
            const isApproved =
              hasResult &&
              assessment.predictive_model_result!.toLowerCase().includes('approved');
            return (
              <div className="rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-800/50">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-semibold text-muted-foreground">
                    模型辅助结果
                  </span>
                  <CheckCircle2
                    className={cn(
                      'h-5 w-5',
                      hasResult
                        ? isApproved
                          ? 'text-emerald-500'
                          : 'text-red-500'
                        : 'text-slate-300',
                    )}
                  />
                </div>
                <p className="text-2xl font-bold text-foreground">
                  {hasResult ? (isApproved ? '建议通过' : '建议复核') : '--'}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {hasResult
                    ? '仅供人工审批参考'
                    : hasData
                      ? '暂无模型结果'
                      : '运行风险画像后生成'}
                </p>
                <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all',
                      hasResult
                        ? isApproved
                          ? 'bg-emerald-500 w-full'
                          : 'bg-red-500 w-full'
                        : 'w-0',
                    )}
                  />
                </div>
              </div>
            );
          })()}
      </div>
      {hasData && assessment.warnings && assessment.warnings.length > 0 && (
        <div className="mt-4 space-y-1">
          {assessment.warnings.map((w, i) => (
            <p
              key={i}
              className="flex items-start gap-2 text-xs text-amber-700 dark:text-amber-400"
            >
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
              {w}
            </p>
          ))}
        </div>
      )}
    </CardShell>
  );
}

// -- Compliance Checks card ---------------------------------------------------

const STATUS_BADGE: Record<string, string> = {
  PASS: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  CONDITIONAL_PASS:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  WARNING: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  FAIL: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

function ComplianceChecksCard({
  appId,
  stage,
}: {
  appId: number;
  stage?: ApplicationStage;
}) {
  const { data: result, isError } = useComplianceResult(appId);
  const hasData = result && !isError;
  const disabled = !stageAllows(stage, ASSESSMENT_STAGES);
  const tooltip = disabledReason(stage, ASSESSMENT_STAGES);

  const checks = [
    { key: 'ecoa' as const, name: '贷款申请与消费者权益审查', icon: Scale },
    { key: 'atr_qm' as const, name: '还款能力与收入负债核验', icon: ShieldCheck },
    { key: 'trid' as const, name: '合同与信息披露时点检查', icon: FileText },
  ];

  return (
    <CardShell>
      <div className="mb-4 flex items-center justify-between">
        <h4 className="text-sm font-bold uppercase tracking-wider text-foreground">
          合规检查
          {hasData && result.overall_status && (
            <span
              className={cn(
                'ml-2 rounded px-2 py-0.5 text-xs font-medium',
                STATUS_BADGE[result.overall_status] ?? 'bg-slate-100 text-slate-600',
              )}
            >
              {COMPLIANCE_STATUS_LABELS[result.overall_status] ?? result.overall_status}
            </span>
          )}
        </h4>
        <button
          onClick={() =>
            chatPrefill(
              `请对申请 #${appId} 运行合规检查，并检索全国通用监管政策与成都市地方规则。`,
            )
          }
          disabled={disabled}
          title={tooltip ?? undefined}
          className="flex items-center gap-1.5 rounded-lg bg-[#1e3a5f] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[#152e42] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {hasData ? '重新检查' : '运行检查'}
        </button>
      </div>
      <div className="space-y-2">
        {checks.map((check) => {
          const Icon = check.icon;
          const status = hasData
            ? (result[`${check.key}_status`] as string | null)
            : null;
          const rationale = hasData
            ? (result[`${check.key}_rationale`] as string | null)
            : null;
          return (
            <div
              key={check.key}
              className="rounded border border-border bg-white p-3 dark:bg-slate-800"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="rounded bg-slate-100 p-1 dark:bg-slate-700">
                    <Icon className="h-4 w-4 text-slate-500" />
                  </div>
                  <span className="text-sm font-medium text-foreground">
                    {check.name}
                  </span>
                </div>
                {status ? (
                  <span
                    className={cn(
                      'rounded px-2 py-0.5 text-xs font-medium',
                      STATUS_BADGE[status] ?? 'bg-slate-100 text-slate-600',
                    )}
                  >
                    {COMPLIANCE_STATUS_LABELS[status] ?? status}
                  </span>
                ) : (
                  <span className="text-xs text-muted-foreground">待检查</span>
                )}
              </div>
              {rationale && (
                <p className="mt-1.5 pl-10 text-xs text-muted-foreground">
                  {localizeComplianceRationale(rationale)}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </CardShell>
  );
}

// -- Conditions card ----------------------------------------------------------

function ConditionsCard({ appId, stage }: { appId: number; stage?: ApplicationStage }) {
  const { data: conditions, isLoading } = useConditions(appId);
  const items = conditions?.data ?? [];
  const openCount = items.filter(
    (c) => c.status === 'open' || c.status === 'responded' || c.status === 'escalated',
  ).length;
  const disabled = !stageAllows(stage, DECISION_STAGES);
  const tooltip = disabledReason(stage, DECISION_STAGES);

  if (isLoading) {
    return (
      <CardShell>
        <Skeleton className="mb-4 h-5 w-40" />
        <Skeleton className="mb-2 h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </CardShell>
    );
  }

  return (
    <CardShell>
      <div className="mb-4 flex items-center justify-between">
        <h4 className="text-sm font-bold uppercase tracking-wider text-foreground">
          审批条件 {openCount > 0 && `（${openCount} 项待处理）`}
        </h4>
        <button
          onClick={() => chatPrefill(`请为申请 #${appId} 新增一项审批条件。`)}
          disabled={disabled}
          title={tooltip ?? undefined}
          className="flex items-center gap-1.5 rounded-lg bg-[#1e3a5f] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[#152e42] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Plus className="h-3.5 w-3.5" />
          新增审批条件
        </button>
      </div>
      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-6 text-muted-foreground">
          <CheckCircle2 className="h-6 w-6 text-emerald-500" />
          <p className="text-sm">暂无审批条件。</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((cond: Condition) => (
            <li
              key={cond.id}
              className="flex gap-3 rounded border border-border bg-slate-50 p-3 text-sm dark:bg-slate-800/50"
            >
              <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-foreground">
                  {localizeConditionDescription(cond.description)}
                </p>
                {cond.response_text && (
                  <p className="mt-0.5 text-xs text-muted-foreground italic">
                    反馈：{cond.response_text}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 items-start gap-2">
                {cond.status && (
                  <span
                    className={cn(
                      'rounded px-2 py-0.5 text-xs font-medium',
                      CONDITION_STATUS_COLORS[cond.status] ??
                        'bg-slate-100 text-slate-600',
                    )}
                  >
                    {CONDITION_STATUS_LABELS[cond.status] ?? cond.status}
                  </span>
                )}
                {cond.severity && (
                  <span
                    className={cn(
                      'rounded px-2 py-0.5 text-xs font-semibold',
                      SEVERITY_COLORS[cond.severity] ?? 'bg-slate-100 text-slate-600',
                    )}
                  >
                    {SEVERITY_LABELS[cond.severity] ?? cond.severity}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </CardShell>
  );
}

// -- Preliminary Recommendation banner ----------------------------------------

function RecommendationBanner({ appId }: { appId: number }) {
  const { data: assessment, isError } = useRiskAssessment(appId);
  const hasData = assessment && !isError;

  if (!hasData) {
    return (
      <div className="rounded-r-lg border-l-4 border-amber-500 bg-amber-50 p-4 dark:bg-amber-900/10">
        <p className="mb-1 text-xs font-bold uppercase tracking-wider text-amber-700 dark:text-amber-500">
          系统初步提示
        </p>
        <p className="text-sm text-amber-800/80 dark:text-amber-300/80">
          请先执行上方规则评估。系统提示仅作辅助，最终结论须由审批人员确认。
        </p>
      </div>
    );
  }

  const rec = assessment.recommendation;
  const hasRec = rec != null;

  // Color by recommendation outcome, fallback to risk level
  const isApprove = rec?.toLowerCase().includes('approve');
  const isDeny = rec?.toLowerCase().includes('deny');
  const isSuspend = rec?.toLowerCase().includes('suspend');

  let borderColor: string, bgColor: string, titleColor: string, textColor: string;
  if (hasRec) {
    if (isDeny) {
      borderColor = 'border-red-500';
      bgColor = 'bg-red-50 dark:bg-red-900/10';
      titleColor = 'text-red-700 dark:text-red-500';
      textColor = 'text-red-800/80 dark:text-red-300/80';
    } else if (isSuspend) {
      borderColor = 'border-orange-500';
      bgColor = 'bg-orange-50 dark:bg-orange-900/10';
      titleColor = 'text-orange-700 dark:text-orange-500';
      textColor = 'text-orange-800/80 dark:text-orange-300/80';
    } else if (isApprove) {
      borderColor = 'border-emerald-500';
      bgColor = 'bg-emerald-50 dark:bg-emerald-900/10';
      titleColor = 'text-emerald-700 dark:text-emerald-500';
      textColor = 'text-emerald-800/80 dark:text-emerald-300/80';
    } else {
      borderColor = 'border-amber-500';
      bgColor = 'bg-amber-50 dark:bg-amber-900/10';
      titleColor = 'text-amber-700 dark:text-amber-500';
      textColor = 'text-amber-800/80 dark:text-amber-300/80';
    }
  } else {
    // No recommendation yet -- show risk level colors
    const risk = assessment.overall_risk;
    borderColor =
      risk === 'Low'
        ? 'border-emerald-500'
        : risk === 'Medium'
          ? 'border-amber-500'
          : 'border-red-500';
    bgColor =
      risk === 'Low'
        ? 'bg-emerald-50 dark:bg-emerald-900/10'
        : risk === 'Medium'
          ? 'bg-amber-50 dark:bg-amber-900/10'
          : 'bg-red-50 dark:bg-red-900/10';
    titleColor =
      risk === 'Low'
        ? 'text-emerald-700 dark:text-emerald-500'
        : risk === 'Medium'
          ? 'text-amber-700 dark:text-amber-500'
          : 'text-red-700 dark:text-red-500';
    textColor =
      risk === 'Low'
        ? 'text-emerald-800/80 dark:text-emerald-300/80'
        : risk === 'Medium'
          ? 'text-amber-800/80 dark:text-amber-300/80'
          : 'text-red-800/80 dark:text-red-300/80';
  }

  return (
    <div className={cn('rounded-r-lg border-l-4 p-4', borderColor, bgColor)}>
      <p className={cn('mb-1 text-xs font-bold uppercase tracking-wider', titleColor)}>
        {hasRec
          ? `辅助建议：${recommendationLabel(rec)}`
          : `风险画像：${ASSESSMENT_RATING_LABELS[assessment.overall_risk ?? ''] ?? assessment.overall_risk}`}
      </p>
      {hasRec &&
        assessment.recommendation_rationale &&
        assessment.recommendation_rationale.length > 0 && (
          <ul className={cn('mt-1 space-y-0.5 text-sm', textColor)}>
            {assessment.recommendation_rationale.map((r, i) => (
              <li key={i}>- {r}</li>
            ))}
          </ul>
        )}
      {hasRec &&
        assessment.recommendation_conditions &&
        assessment.recommendation_conditions.length > 0 && (
          <div className={cn('mt-2 text-sm', textColor)}>
            <span className="font-medium">建议条件：</span>
            <ul className="mt-0.5 space-y-0.5">
              {assessment.recommendation_conditions.map((c, i) => (
                <li key={i}>
                  {i + 1}. {c}
                </li>
              ))}
            </ul>
          </div>
        )}
      {!hasRec && (
        <p className={cn('text-sm', textColor)}>重新运行风险画像以生成辅助建议。</p>
      )}
    </div>
  );
}

// -- Decision panel -----------------------------------------------------------

function DecisionPanel({ appId, stage }: { appId: number; stage?: ApplicationStage }) {
  const [decision, setDecision] = useState<string>('');
  const [rationale, setRationale] = useState('');
  const stageDisabled = !stageAllows(stage, DECISION_STAGES);
  const tooltip = disabledReason(stage, DECISION_STAGES);

  const options = [
    { value: 'approved', label: '同意' },
    { value: 'conditional_approval', label: '有条件同意' },
    { value: 'suspended', label: '暂缓' },
    { value: 'denied', label: '拒绝' },
  ];

  const canSubmit = !stageDisabled && decision !== '' && rationale.trim().length > 0;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const label = options.find((o) => o.value === decision)?.label ?? decision;
    const msg = `为申请 #${appId} 发起人工决策提案：${label}。理由：${rationale.trim()}。请先返回待确认提案，不要直接写入最终结论。`;
    chatPrefill(msg);
  };

  return (
    <CardShell className="shadow-lg">
      <h3 className="mb-4 text-lg font-bold text-foreground flex items-center gap-2">
        <Gavel className="h-5 w-5 text-muted-foreground" />
        人工审批决策
      </h3>
      {stageDisabled && tooltip && (
        <p className="mb-4 rounded-lg border border-border bg-slate-50 px-3 py-2 text-xs text-muted-foreground dark:bg-slate-800/50">
          {tooltip}
        </p>
      )}
      <fieldset disabled={stageDisabled} className={cn(stageDisabled && 'opacity-50')}>
        <div className="mb-6 space-y-3">
          {options.map((opt) => {
            const isSelected = decision === opt.value;
            return (
              <label
                key={opt.value}
                className={cn(
                  'flex items-center gap-3 rounded-lg border p-3 transition-colors',
                  stageDisabled ? 'cursor-not-allowed border-border' : 'cursor-pointer',
                  !stageDisabled && isSelected
                    ? 'border-[#1e3a5f]/50 bg-[#1e3a5f]/5 ring-1 ring-[#1e3a5f]'
                    : !stageDisabled
                      ? 'border-border hover:bg-slate-50 dark:hover:bg-slate-800'
                      : '',
                )}
              >
                <input
                  type="radio"
                  name="decision"
                  value={opt.value}
                  checked={isSelected}
                  onChange={() => setDecision(opt.value)}
                  className="h-4 w-4 text-[#1e3a5f] focus:ring-[#1e3a5f]"
                />
                <span
                  className={cn(
                    'text-sm font-medium',
                    isSelected ? 'font-bold text-[#1e3a5f]' : 'text-foreground',
                  )}
                >
                  {opt.label}
                </span>
              </label>
            );
          })}
        </div>
        <div className="mb-4">
          <label className="mb-2 block text-sm font-medium text-foreground">
            决策理由 / 备注
          </label>
          <textarea
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            placeholder="请输入可审计的决策理由…"
            rows={4}
            className="w-full resize-none rounded-lg border border-border bg-transparent p-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/30"
          />
        </div>
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#1e3a5f] py-3 font-bold text-white shadow-md transition-colors hover:bg-[#152e42] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Gavel className="h-4 w-4" />
          生成待确认提案
        </button>
      </fieldset>
    </CardShell>
  );
}

// -- Application Summary mini-card --------------------------------------------

function AppSummaryCard({ app }: { app: ApplicationResponse }) {
  const loanType = app.loan_type ? LOAN_TYPE_LABELS[app.loan_type] : '--';
  const ltv =
    app.loan_amount && app.property_value
      ? formatPercent(app.loan_amount / app.property_value)
      : '--';

  return (
    <CardShell>
      <h4 className="mb-3 text-sm font-bold text-foreground flex items-center gap-2">
        <FileText className="h-4 w-4 text-muted-foreground" />
        申请摘要
      </h4>
      <div className="space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">贷款类型</span>
          <span className="font-medium text-foreground">{loanType}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">贷款金额</span>
          <span className="font-medium text-foreground">
            {formatCurrency(app.loan_amount)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">房产价值</span>
          <span className="font-medium text-foreground">
            {formatCurrency(app.property_value)}
          </span>
        </div>
        <div className="flex justify-between border-t border-border pt-2">
          <span className="text-muted-foreground">贷款成数（LTV）</span>
          <span className="font-bold text-foreground">{ltv}</span>
        </div>
      </div>
    </CardShell>
  );
}

// -- Compliance KB search card ------------------------------------------------

const KB_TOPICS = [
  {
    label: '全国个人贷款管理',
    query:
      '检索全国通用监管政策中关于个人贷款受理、调查、审查和贷后管理的要求，并给出可点击引用。',
  },
  {
    label: '全国最低首付比例',
    query: '检索全国商业性个人住房贷款最低首付款比例政策，说明生效时间并给出引用。',
  },
  {
    label: '成都公积金贷款',
    query: '检索截至 2026-08-25 有效的成都市住房公积金贷款地方规则，并区分适用条件。',
  },
  {
    label: '商转公规则',
    query: '检索成都市商业性个人住房贷款转住房公积金贷款规则，并给出政策版本和引用。',
  },
  {
    label: '历史政策冲突',
    query:
      '对比成都住房套数认定历史规则与当前规则；若旧政策已失效，请明确提示不可作为当前结论。',
  },
  {
    label: '材料与收入一致性',
    query:
      '检索融安住房金融内部演示规则中关于收入证明和银行流水一致性核验的要求，并标注为内部演示规则。',
  },
] as const;

function ComplianceKBCard() {
  return (
    <CardShell>
      <h4 className="mb-3 text-sm font-bold text-foreground">政策库</h4>
      <p className="mb-3 text-xs text-muted-foreground">
        查询全国通用监管政策与成都市地方规则，并查看政策来源、适用范围和生效日期。
      </p>
      <div className="grid grid-cols-2 gap-2">
        {KB_TOPICS.map((topic) => (
          <button
            key={topic.label}
            onClick={() => chatPrefill(topic.query)}
            className="rounded-full border border-border px-3 py-1 text-xs text-foreground transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            {topic.label}
          </button>
        ))}
      </div>
    </CardShell>
  );
}

// -- Past decisions card ------------------------------------------------------

function PastDecisions({ appId }: { appId: number }) {
  const { data, isLoading } = useDecisions(appId);
  const decisions = data?.data ?? [];

  if (isLoading) return null;
  if (decisions.length === 0) return null;

  return (
    <CardShell>
      <h4 className="mb-3 text-sm font-bold text-foreground">历史人工决策</h4>
      <div className="space-y-2">
        {decisions.map((d: DecisionItem) => (
          <div key={d.id} className="rounded border border-border p-3 text-sm">
            <div className="flex items-center justify-between">
              <span
                className={cn(
                  'rounded px-2 py-0.5 text-xs font-medium',
                  DECISION_TYPE_COLORS[d.decision_type] ??
                    'bg-slate-100 text-slate-600',
                )}
              >
                {DECISION_TYPE_LABELS[d.decision_type] ?? d.decision_type}
              </span>
              <span className="text-xs text-muted-foreground">
                {formatDate(d.created_at)}
              </span>
            </div>
            {d.rationale && (
              <p className="mt-1.5 text-xs text-muted-foreground">{d.rationale}</p>
            )}
            {d.decided_by && (
              <p className="mt-1 text-xs text-muted-foreground italic">
                决策人：{staffName(d.decided_by)}
              </p>
            )}
          </div>
        ))}
      </div>
    </CardShell>
  );
}

// -- Main component -----------------------------------------------------------

function UnderwriterDetail() {
  const { applicationId } = Route.useParams();
  const appId = Number(applicationId);

  const { data: app, isLoading: appLoading } = useApplication(appId);
  const { data: features } = useFeatures();

  if (appLoading) {
    return (
      <div className="mx-auto max-w-[1280px] p-6 md:p-8">
        <Skeleton className="mb-4 h-5 w-48" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-8 space-y-6">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
          <div className="lg:col-span-4 space-y-6">
            <Skeleton className="h-80 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (!app) {
    return (
      <div className="mx-auto max-w-[1280px] p-6 md:p-8">
        <CardShell className="flex flex-col items-center gap-3 py-12">
          <AlertTriangle className="h-8 w-8 text-amber-500" />
          <p className="font-medium text-foreground">未找到该申请</p>
          <Link to="/underwriter" className="text-sm text-[#1e3a5f] hover:underline">
            返回审批队列
          </Link>
        </CardShell>
      </div>
    );
  }

  const name = borrowerName(app);
  const stage = app.stage as ApplicationStage | undefined;
  const stageBadgeColor = stage
    ? (STAGE_BADGE_COLORS[stage] ??
      'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400')
    : '';

  return (
    <div className="mx-auto max-w-[1280px] p-6 md:p-8">
      {/* Breadcrumb */}
      <nav className="mb-4 flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link to="/underwriter" className="transition-colors hover:text-foreground">
          审批队列
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="font-medium text-foreground">
          {name} — #{app.id}
        </span>
        {stage && (
          <span
            className={cn(
              'ml-2 rounded-full px-2.5 py-0.5 text-xs font-semibold',
              stageBadgeColor,
            )}
          >
            {APPLICATION_STAGE_LABELS[stage]}
          </span>
        )}
      </nav>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
        {/* Left column */}
        <div className="flex flex-col gap-6 lg:col-span-8">
          <DeterministicAssessmentCard appId={appId} stage={stage} />
          <RiskAssessmentCard
            appId={appId}
            stage={stage}
            predictiveModelEnabled={features?.predictive_model ?? false}
          />
          <RecommendationBanner appId={appId} />
          <ComplianceChecksCard appId={appId} stage={stage} />
          <ConditionsCard appId={appId} stage={stage} />
        </div>

        {/* Right column (sticky) */}
        <div className="flex flex-col gap-6 lg:col-span-4 lg:sticky lg:top-[80px]">
          <DecisionPanel appId={appId} stage={stage} />
          <AppSummaryCard app={app} />
          <ComplianceKBCard />
          <PastDecisions appId={appId} />
        </div>
      </div>
    </div>
  );
}
