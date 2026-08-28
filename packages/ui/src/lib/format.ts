// This project was developed with assistance from AI tools.

const currencyFmt = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 0,
});
const currencyPreciseFmt = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const cnyFmt = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 0,
});
const percentFmt = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 2,
});
const dateFmt = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
});
const dateTimeFmt = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});
const zhDateFmt = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
});

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return '--';
  return currencyFmt.format(value);
}

export function formatCurrencyPrecise(value: number | null | undefined): string {
  if (value == null) return '--';
  return currencyPreciseFmt.format(value);
}

export function formatCny(value: number | null | undefined): string {
  if (value == null) return '--';
  return cnyFmt.format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return '--';
  return percentFmt.format(value);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '--';
  return dateFmt.format(new Date(value));
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '--';
  return dateTimeFmt.format(new Date(value));
}

export function formatDateZh(value: string | null | undefined): string {
  if (!value) return '--';
  return zhDateFmt.format(new Date(value));
}

export function formatDays(value: number | null | undefined): string {
  if (value == null) return '--';
  return `${Math.round(value)}天`;
}

export function formatDaysZh(value: number | null | undefined): string {
  if (value == null) return '--';
  return `${Math.round(value)}天`;
}
