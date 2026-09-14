// This project was developed with assistance from AI tools.

import type {
  AffordabilityRequest,
  AffordabilityResponse,
} from '@/schemas/affordability';

const HOUSING_EXPENSE_RATIO_LIMIT = 0.5;
const TOTAL_DEBT_RATIO_LIMIT = 0.55;
const MINIMUM_DOWN_PAYMENT_RATIO = 0.15;

function round(value: number, digits = 2): number {
  const factor = 10 ** digits;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

function monthlyPayment(
  principal: number,
  annualRate: number,
  termMonths: number,
): number {
  if (principal <= 0 || termMonths <= 0) return 0;

  const monthlyRate = annualRate / 100 / 12;
  if (monthlyRate <= 0) return principal / termMonths;

  const compound = (1 + monthlyRate) ** termMonths;
  return principal * ((monthlyRate * compound) / (compound - 1));
}

function validateRequest(req: AffordabilityRequest): void {
  const monthlyPropertyFee = req.monthly_property_fee ?? 0;
  const interestRate = req.interest_rate ?? 3.5;
  const loanTermYears = req.loan_term_years ?? 30;
  const values = [
    req.gross_annual_income,
    req.monthly_debts,
    monthlyPropertyFee,
    req.down_payment,
    interestRate,
    loanTermYears,
  ];

  if (
    values.some((value) => !Number.isFinite(value)) ||
    req.gross_annual_income <= 0 ||
    req.monthly_debts < 0 ||
    monthlyPropertyFee < 0 ||
    req.down_payment < 0 ||
    interestRate < 0 ||
    interestRate > 15 ||
    !Number.isInteger(loanTermYears) ||
    loanTermYears < 10 ||
    loanTermYears > 40
  ) {
    throw new Error('测算输入无效');
  }
}

/**
 * Keep the public calculator usable while the free API service is waking up.
 * This mirrors the API's deterministic equal-payment calculation.
 */
export function calculateAffordabilityLocally(
  req: AffordabilityRequest,
): AffordabilityResponse {
  validateRequest(req);

  const monthlyPropertyFee = req.monthly_property_fee ?? 0;
  const interestRate = req.interest_rate ?? 3.5;
  const loanTermYears = req.loan_term_years ?? 30;
  const grossMonthlyIncome = req.gross_annual_income / 12;
  const housingPaymentCap =
    grossMonthlyIncome * HOUSING_EXPENSE_RATIO_LIMIT - monthlyPropertyFee;
  const totalDebtPaymentCap =
    grossMonthlyIncome * TOTAL_DEBT_RATIO_LIMIT -
    monthlyPropertyFee -
    req.monthly_debts;
  const maxHousingPayment = Math.max(
    0,
    Math.min(housingPaymentCap, totalDebtPaymentCap),
  );

  if (maxHousingPayment <= 0) {
    const existingDti =
      ((req.monthly_debts + monthlyPropertyFee) / grossMonthlyIncome) * 100;
    return {
      max_loan_amount: 0,
      estimated_monthly_payment: 0,
      estimated_purchase_price: 0,
      dti_ratio: round(existingDti, 1),
      housing_expense_ratio: round((monthlyPropertyFee / grossMonthlyIncome) * 100, 1),
      ltv_ratio: 0,
      down_payment_ratio: 0,
      housing_payment_cap: round(Math.max(0, housingPaymentCap)),
      total_debt_payment_cap: round(Math.max(0, totalDebtPaymentCap)),
      binding_constraint: 'repayment_capacity',
      minimum_down_payment_ratio: MINIMUM_DOWN_PAYMENT_RATIO * 100,
      dti_warning:
        '现有月债务与物业费已达到审慎偿债能力上限，当前输入下不建议新增住房贷款。',
      pmi_warning: null,
    };
  }

  const monthlyRate = interestRate / 100 / 12;
  const numberOfPayments = loanTermYears * 12;
  const paymentPerYuan =
    monthlyRate > 0
      ? (monthlyRate * (1 + monthlyRate) ** numberOfPayments) /
        ((1 + monthlyRate) ** numberOfPayments - 1)
      : 1 / numberOfPayments;
  const repaymentCapacityLoan = maxHousingPayment / paymentPerYuan;
  const repaymentCapacityPrice = repaymentCapacityLoan + req.down_payment;
  const downPaymentCapacityPrice =
    req.down_payment > 0 ? req.down_payment / MINIMUM_DOWN_PAYMENT_RATIO : 0;
  const estimatedPurchasePrice = Math.min(
    repaymentCapacityPrice,
    downPaymentCapacityPrice,
  );
  const maxLoanAmount = Math.max(0, estimatedPurchasePrice - req.down_payment);
  const estimatedMonthlyPayment = monthlyPayment(
    maxLoanAmount,
    interestRate,
    numberOfPayments,
  );
  const housingMonthlyObligations = estimatedMonthlyPayment + monthlyPropertyFee;
  const totalMonthlyObligations = housingMonthlyObligations + req.monthly_debts;

  return {
    max_loan_amount: round(maxLoanAmount),
    estimated_monthly_payment: round(estimatedMonthlyPayment),
    estimated_purchase_price: round(estimatedPurchasePrice),
    dti_ratio: round((totalMonthlyObligations / grossMonthlyIncome) * 100, 1),
    housing_expense_ratio: round(
      (housingMonthlyObligations / grossMonthlyIncome) * 100,
      1,
    ),
    ltv_ratio:
      estimatedPurchasePrice > 0
        ? round((maxLoanAmount / estimatedPurchasePrice) * 100, 1)
        : 0,
    down_payment_ratio:
      estimatedPurchasePrice > 0
        ? round((req.down_payment / estimatedPurchasePrice) * 100, 1)
        : 0,
    housing_payment_cap: round(Math.max(0, housingPaymentCap)),
    total_debt_payment_cap: round(Math.max(0, totalDebtPaymentCap)),
    binding_constraint:
      downPaymentCapacityPrice <= repaymentCapacityPrice
        ? 'down_payment'
        : 'repayment_capacity',
    minimum_down_payment_ratio: MINIMUM_DOWN_PAYMENT_RATIO * 100,
    dti_warning:
      req.down_payment <= 0
        ? '首付款为 0，未达到商业性个人住房贷款最低首付比例要求。'
        : null,
    pmi_warning: null,
  };
}
