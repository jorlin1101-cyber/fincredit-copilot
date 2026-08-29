// This project was developed with assistance from AI tools.

import { describe, expect, it } from 'vitest';
import { formatExtractionValue } from './labels';

describe('formatExtractionValue', () => {
  it('translates legacy upstream organizations and account values', () => {
    expect(formatExtractionValue('employer_name', 'US Department of Veterans Affairs')).toBe(
      '成都优抚服务中心（演示）',
    );
    expect(formatExtractionValue('account_type', 'Checking')).toBe('个人结算账户');
    expect(formatExtractionValue('pay_period', 'Bi-weekly')).toBe('每两周');
  });

  it('formats legacy currency and dates for the Chinese demo', () => {
    expect(formatExtractionValue('gross_pay', '$4,523.08')).toBe('¥4,523.08');
    expect(formatExtractionValue('expiration_date', '2027-11-30')).toBe('2027年11月30日');
    expect(formatExtractionValue('statement_period', 'Jan 2026')).toBe('2026年1月');
  });

  it('keeps already localized values unchanged', () => {
    expect(formatExtractionValue('institution', '成都银行建设路支行（演示）')).toBe(
      '成都银行建设路支行（演示）',
    );
    expect(formatExtractionValue('unknown', null)).toBe('--');
  });
});
