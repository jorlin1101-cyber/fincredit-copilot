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

export const DOCUMENT_STATUS_LABELS: Record<string, string> = {
  uploaded: '已上传',
  processing: '解析中',
  processing_complete: '解析完成',
  accepted: '已通过',
  pending_review: '待复核',
  flagged_for_resubmission: '需重新提交',
  rejected: '未通过',
  processing_failed: '解析失败',
};

export const CONDITION_SEVERITY_LABELS: Record<string, string> = {
  prior_to_approval: '审批前完成',
  prior_to_docs: '合同出具前完成',
  prior_to_closing: '签约前完成',
  prior_to_funding: '放款前完成',
};

export const CONDITION_STATUS_LABELS: Record<string, string> = {
  open: '待处理',
  responded: '已回复',
  under_review: '复核中',
  cleared: '已满足',
  waived: '已豁免',
  escalated: '已升级',
};

export const EMPLOYMENT_STATUS_LABELS: Record<string, string> = {
  w2_employee: '企业职员',
  self_employed: '个体经营者',
  retired: '退休',
  unemployed: '待业',
  other: '其他',
};

export const QUALITY_FLAG_LABELS: Record<string, string> = {
  blurry: '图像模糊',
  incomplete: '材料不完整',
  wrong_period: '所属期间不符',
  future_date: '日期异常',
  document_type_mismatch: '材料类型不匹配',
  unsigned: '未签章',
  unsigned_document: '未签章',
  low_confidence: '识别置信度较低',
  low_resolution: '分辨率较低',
  blurry_scan: '扫描件模糊',
  partially_illegible: '部分内容无法辨认',
  outdated_statement: '流水所属期间过早',
  wrong_account_period: '账户流水期间不符',
  missing_pages: '材料页面缺失',
  evidence_not_found: '未找到原文依据',
  page_extraction_failed: '页面解析失败',
  cross_page_document_type_conflict: '跨页材料类型冲突',
  unreadable: '文件无法读取',
};

export const EXTRACTION_FIELD_LABELS: Record<string, string> = {
  full_name: '姓名',
  employee_name: '员工姓名',
  employer_name: '工作单位',
  account_holder_name: '账户户名',
  bank_name: '银行名称',
  statement_period_start: '账单起始日期',
  statement_period_end: '账单结束日期',
  opening_balance: '期初余额',
  ending_balance: '期末余额',
  monthly_gross_income: '税前月收入',
  annual_gross_income: '税前年收入',
  annual_income: '年收入',
  gross_pay: '税前工资',
  ytd_earnings: '本年度累计收入',
  pay_period: '发薪周期',
  institution: '开户机构',
  account_type: '账户类型',
  statement_period: '流水期间',
  issuing_state: '签发地区',
  tax_year: '纳税年度',
  ein: '单位统一社会信用代码',
  filer_name: '纳税人姓名',
  adjusted_gross_income: '年度综合收入',
  filing_status: '申报类型',
  signature_present: '是否签章',
  property_type: '房屋类型',
  condition: '房屋状况',
  employer: '工作单位',
  review_result: '识别结论',
  salary_credit_monthly_average: '月均工资入账',
  id_number: '身份证号',
  address: '地址',
  issue_date: '出具日期',
  valid_until: '有效期至',
  property_address: '房产地址',
  appraised_value: '评估价值',
  policy_number: '保单号',
  coverage_amount: '保险金额',
  effective_date: '生效日期',
  expiration_date: '到期日期',
  wages: '收入金额',
  pay_period_end: '计薪截止日期',
};

const EXTRACTION_VALUE_LABELS: Record<string, string> = {
  'US Department of Veterans Affairs': '成都优抚服务中心（演示）',
  'US Dept. of Veterans Affairs': '成都优抚服务中心（演示）',
  'USAA Federal Savings': '中国邮政储蓄银行成都分行（演示）',
  'USAA Federal Savings Bank': '中国邮政储蓄银行成都分行（演示）',
  Colorado: '四川省',
  Checking: '个人结算账户',
  Savings: '个人储蓄账户',
  'Bi-weekly': '每两周',
  Monthly: '每月',
  Yes: '是',
  No: '否',
};

/** Convert legacy demo values to the Chinese public-demo vocabulary. */
export function formatExtractionValue(
  fieldName: string,
  value: string | null | undefined,
): string {
  if (!value) return '--';
  const exact = EXTRACTION_VALUE_LABELS[value];
  if (exact) return exact;

  if (/^\$[\d,.]+$/.test(value)) return value.replace('$', '¥');

  const isoDate = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (isoDate) {
    return `${isoDate[1]}年${Number(isoDate[2])}月${Number(isoDate[3])}日`;
  }

  const monthYear = /^([A-Za-z]{3}) (\d{4})$/.exec(value);
  if (monthYear && fieldName === 'statement_period') {
    const monthMap: Record<string, number> = {
      Jan: 1,
      Feb: 2,
      Mar: 3,
      Apr: 4,
      May: 5,
      Jun: 6,
      Jul: 7,
      Aug: 8,
      Sep: 9,
      Oct: 10,
      Nov: 11,
      Dec: 12,
    };
    const month = monthMap[monthYear[1]];
    if (month) return `${monthYear[2]}年${month}月`;
  }

  return value;
}

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
