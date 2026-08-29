// This project was developed with assistance from AI tools.

import { useState, type FormEvent } from 'react';
import {
  Banknote,
  CalendarDays,
  ExternalLink,
  Landmark,
  Percent,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';
import { useCalculator } from '@/hooks/use-calculator';
import { useChatContext } from '@/contexts/chat-context';
import { Label } from '@/components/atoms/label/label';
import { formatCny } from '@/lib/format';
import type { AffordabilityRequest } from '@/schemas/affordability';

interface FormState {
  gross_monthly_income: string;
  monthly_debts: string;
  monthly_property_fee: string;
  down_payment: string;
  interest_rate: string;
  loan_term_years: string;
}

const INITIAL_FORM: FormState = {
  gross_monthly_income: '20000',
  monthly_debts: '2000',
  monthly_property_fee: '300',
  down_payment: '300000',
  interest_rate: '3.5',
  loan_term_years: '30',
};

const POLICY_SOURCES = [
  {
    title: '全国最低首付比例政策',
    detail: '商业性个人住房贷款最低首付比例全国下限为 15%，地方和银行可因城施策。',
    source: '中国人民银行、国家金融监督管理总局（2024-09-24）',
    href: 'https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html?docId=1180751&generaltype=1',
  },
  {
    title: '5 年期以上 LPR',
    detail:
      '2026 年 8 月 20 日公布值为 3.5%，仅作本页默认参考，不等于银行实际房贷报价。',
    source: '全国银行间同业拆借中心（2026-08-20）',
    href: 'https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html',
  },
  {
    title: '偿债能力审慎口径',
    detail: '住房支出收入比不高于 50%，全部债务支出收入比不高于 55%。',
    source: '中国银监会《商业银行房地产贷款风险管理指引》',
    href: 'https://www.pbc.gov.cn/eportal/fileDir/history_file/files/att_11620_1.pdf',
  },
  {
    title: '成都市商转公规则',
    detail: '成都商转公贷款月还款额不得高于家庭月收入的 50%，贷款期限最长 30 年。',
    source: '成都市政务服务网（2025-11-04）',
    href: 'https://cds.sczwfw.gov.cn/art/2025/11/4/art_15398_300321.html',
  },
];

function NumberInputField({
  id,
  label,
  value,
  onChange,
  placeholder,
  icon: Icon,
  required,
  suffix,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  icon: LucideIcon;
  required?: boolean;
  suffix?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="text-sm font-medium text-foreground">
        {label}
        {required && (
          <span className="ml-1 text-destructive" aria-hidden="true">
            *
          </span>
        )}
      </Label>
      <div className="relative">
        <span
          className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-muted-foreground"
          aria-hidden="true"
        >
          <Icon className="h-4 w-4" />
        </span>
        <input
          id={id}
          type="number"
          min={0}
          step="any"
          required={required}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`flex h-11 w-full rounded-lg border border-input bg-slate-50 py-2 pl-9 ${suffix ? 'pr-16' : 'pr-3'} text-sm ring-offset-background transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-slate-800`}
          aria-label={label}
        />
        {suffix && (
          <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-muted-foreground">
            {suffix}
          </span>
        )}
      </div>
    </div>
  );
}

export function AffordabilityForm() {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const { mutate, data: results, isPending, isError } = useCalculator();
  const { openChat } = useChatContext();

  function setField(field: keyof FormState) {
    return (val: string) => setForm((prev) => ({ ...prev, [field]: val }));
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const req: AffordabilityRequest = {
      gross_annual_income: parseFloat(form.gross_monthly_income) * 12,
      monthly_debts: parseFloat(form.monthly_debts),
      monthly_property_fee: parseFloat(form.monthly_property_fee),
      down_payment: parseFloat(form.down_payment),
      loan_term_years: parseFloat(form.loan_term_years),
    };

    if (form.interest_rate) {
      req.interest_rate = parseFloat(form.interest_rate);
    }

    mutate(req);
  }

  const hasResults = !!results;

  return (
    <section id="calculator" className="w-full py-16 lg:py-24">
      <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="mb-12 flex flex-col items-center gap-3 text-center">
          <span className="text-xs font-semibold uppercase tracking-widest text-[#cc0000]">
            商业住房贷款购房预算测算
          </span>
          <h2 className="font-display text-3xl font-bold text-foreground sm:text-4xl">
            以家庭偿债能力测算购房预算
          </h2>
          <p className="max-w-2xl text-base text-muted-foreground">
            人民币口径 · 全国通用监管政策 + 成都市地方规则
          </p>
        </div>

        {/* Calculator card */}
        <div className="overflow-hidden rounded-2xl border border-border shadow-lg">
          <div className="flex flex-col lg:flex-row">
            {/* Left: form */}
            <div className="flex-1 p-6 lg:w-3/5 lg:p-10">
              <form onSubmit={handleSubmit} aria-label="购房预算测算表单">
                <div className="mb-5 rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-blue-900 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-200">
                  下列金额仅为可编辑的演示输入，不代表官方平均水平。测算按等额本息方式进行。
                </div>
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  <NumberInputField
                    id="gross_monthly_income"
                    label="家庭税前月收入"
                    value={form.gross_monthly_income}
                    onChange={setField('gross_monthly_income')}
                    placeholder="20,000"
                    icon={Banknote}
                    suffix="元/月"
                    required
                  />
                  <NumberInputField
                    id="monthly_debts"
                    label="其他债务月均偿付额"
                    value={form.monthly_debts}
                    onChange={setField('monthly_debts')}
                    placeholder="2,000"
                    icon={Landmark}
                    suffix="元/月"
                    required
                  />
                  <NumberInputField
                    id="monthly_property_fee"
                    label="月物业管理费"
                    value={form.monthly_property_fee}
                    onChange={setField('monthly_property_fee')}
                    placeholder="300"
                    icon={Banknote}
                    suffix="元/月"
                    required
                  />
                  <NumberInputField
                    id="down_payment"
                    label="可用首付款"
                    value={form.down_payment}
                    onChange={setField('down_payment')}
                    placeholder="300,000"
                    icon={Banknote}
                    suffix="元"
                    required
                  />
                  <NumberInputField
                    id="interest_rate"
                    label="年利率参考值"
                    value={form.interest_rate}
                    onChange={setField('interest_rate')}
                    placeholder="3.5"
                    icon={Percent}
                    suffix="%"
                    required
                  />
                  <NumberInputField
                    id="loan_term_years"
                    label="贷款期限"
                    value={form.loan_term_years}
                    onChange={setField('loan_term_years')}
                    placeholder="30"
                    icon={CalendarDays}
                    suffix="年"
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={isPending}
                  className="mt-6 flex h-11 w-full items-center justify-center rounded-lg bg-[#1e3a5f] px-6 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#2b5a8f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1e3a5f] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                  aria-busy={isPending}
                >
                  {isPending ? '正在测算…' : '开始测算'}
                </button>

                {isError && (
                  <p role="alert" className="mt-3 text-center text-sm text-destructive">
                    暂时无法完成测算，请检查输入后重试。
                  </p>
                )}

                <button
                  type="button"
                  onClick={() => openChat()}
                  className="mt-4 w-full cursor-pointer text-center text-sm text-[#1e3a5f] underline decoration-[#1e3a5f]/30 underline-offset-2 transition-colors hover:text-[#2b5a8f] hover:decoration-[#2b5a8f]/50 dark:text-blue-300 dark:decoration-blue-300/30 dark:hover:text-blue-200"
                >
                  已有意向住房？咨询小融
                </button>
              </form>
            </div>

            {/* Right: results */}
            <div className="flex flex-col justify-center gap-6 bg-slate-50 p-6 dark:bg-slate-800 lg:w-2/5 lg:p-10">
              <div className="flex flex-col gap-4">
                {hasResults &&
                results.dti_warning &&
                results.estimated_monthly_payment <= 0 ? (
                  <div className="rounded-xl border border-amber-300 bg-amber-50 p-6 dark:border-amber-700 dark:bg-amber-950/30">
                    <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">
                      当前偿债空间不足
                    </p>
                    <p className="mt-2 text-sm leading-relaxed text-amber-700 dark:text-amber-400">
                      {results.dti_warning}
                    </p>
                    <p className="mt-3 text-xs text-amber-600 dark:text-amber-500">
                      可调整其他月债务、首付款或家庭月收入后重新测算。
                    </p>
                  </div>
                ) : (
                  <>
                    {/* Budget result */}
                    <div className="rounded-xl border border-border bg-white p-5 dark:bg-card">
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        参考购房总价上限
                      </p>
                      {isPending ? (
                        <p className="font-display text-3xl font-bold text-muted-foreground animate-pulse">
                          测算中…
                        </p>
                      ) : hasResults ? (
                        <p
                          data-testid="estimated-home-budget"
                          className="font-display text-3xl font-bold text-[#1e3a5f] dark:text-blue-300"
                        >
                          {formatCny(results.estimated_purchase_price)}
                        </p>
                      ) : (
                        <p className="font-display text-3xl font-bold text-muted-foreground">
                          --
                        </p>
                      )}
                    </div>

                    {/* Monthly payment result */}
                    <div className="rounded-xl border border-border bg-white p-5 dark:bg-card">
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        预计等额本息月供
                      </p>
                      {isPending ? (
                        <p className="font-display text-3xl font-bold text-muted-foreground animate-pulse">
                          测算中…
                        </p>
                      ) : hasResults ? (
                        <p
                          data-testid="estimated-monthly-payment"
                          className="font-display text-3xl font-bold text-emerald-600 dark:text-emerald-400"
                        >
                          {formatCny(results.estimated_monthly_payment)}
                          <span className="ml-1 text-base font-normal text-muted-foreground">
                            /月
                          </span>
                        </p>
                      ) : (
                        <p className="font-display text-3xl font-bold text-muted-foreground">
                          --
                        </p>
                      )}
                    </div>

                    {hasResults && (
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-xl border border-border bg-white p-4 dark:bg-card">
                          <p className="text-xs text-muted-foreground">
                            最高参考贷款额
                          </p>
                          <p className="mt-1 text-lg font-bold text-foreground">
                            {formatCny(results.max_loan_amount)}
                          </p>
                        </div>
                        <div className="rounded-xl border border-border bg-white p-4 dark:bg-card">
                          <p className="text-xs text-muted-foreground">
                            LTV / 总债务收入比
                          </p>
                          <p className="mt-1 text-lg font-bold text-foreground">
                            {results.ltv_ratio}% / {results.dti_ratio}%
                          </p>
                        </div>
                      </div>
                    )}

                    {hasResults && results.estimated_monthly_payment > 0 && (
                      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs leading-5 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
                        <div className="flex items-start gap-2">
                          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
                          <span>
                            当前主要约束：
                            {results.binding_constraint === 'down_payment'
                              ? `首付款（测算首付比例 ${results.down_payment_ratio}%）`
                              : '家庭偿债能力'}
                            ；住房支出收入比 {results.housing_expense_ratio}
                            %，总债务收入比 {results.dti_ratio}%。
                          </span>
                        </div>
                      </div>
                    )}

                    {/* DTI warning (non-blocking) */}
                    {hasResults && results.dti_warning && (
                      <p
                        role="alert"
                        className="text-xs text-amber-600 dark:text-amber-400"
                      >
                        {results.dti_warning}
                      </p>
                    )}
                  </>
                )}
              </div>

              <p className="text-xs leading-5 text-muted-foreground">
                本结果仅作贷前辅助测算，不构成授信审批或贷款承诺。实际首付比例、利率、额度和期限以当地政策、银行审查及合同为准。
              </p>
            </div>
          </div>
        </div>

        <div className="mt-8 rounded-2xl border border-border bg-white p-6 dark:bg-card lg:p-8">
          <div className="mb-5">
            <h3 className="font-display text-xl font-bold text-foreground">
              测算依据与官方来源
            </h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              政策核验日期：2026-08-26。LPR
              会定期更新，地方规则和银行审查标准也可能调整。
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {POLICY_SOURCES.map((item) => (
              <a
                key={item.href}
                href={item.href}
                target="_blank"
                rel="noreferrer"
                className="group rounded-xl border border-border p-4 transition-colors hover:border-[#1e3a5f]/40 hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-foreground">{item.title}</p>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">
                      {item.detail}
                    </p>
                    <p className="mt-2 text-xs text-[#1e3a5f] dark:text-blue-300">
                      {item.source}
                    </p>
                  </div>
                  <ExternalLink className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-colors group-hover:text-[#1e3a5f]" />
                </div>
              </a>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
