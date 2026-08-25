// This project was developed with assistance from AI tools.

/** Shared display labels and badge styles used across borrower and LO views. */

export const DOC_TYPE_LABELS: Record<string, string> = {
  id_card: '身份证',
  income_certificate: '收入证明',
  bank_statement: '银行流水',
  w2: '工资与税务证明',
  pay_stub: '工资单',
  tax_return: '纳税证明',
  drivers_license: '驾驶证',
  passport: '护照',
  property_appraisal: '房产评估报告',
  homeowners_insurance: '房屋保险',
  title_insurance: '产权保险',
  flood_insurance: '洪水保险',
  purchase_agreement: '购房合同',
  gift_letter: '赠与声明',
  other: '其他材料',
};

export const STAGE_BADGE: Record<string, string> = {
  inquiry: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  prequalification: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  application:
    'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300',
  processing:
    'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300',
  underwriting: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  conditional_approval:
    'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  clear_to_close:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  closed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  denied: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  withdrawn: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
};
