/**
 * Standard es-ES formatters for currency (EUR), numbers, dates and percentages.
 * Spanish locale profile: comma for decimals, dot for thousands, EUR symbol, DD/MM/YYYY dates.
 */

const LOCALE = "es-ES";

export function formatCurrencyEUR(amount: number | string): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(num)) return "0,00 €";
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency: "EUR",
    useGrouping: true,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

/** An amount in the currency it was quoted in (a supplier's own currency), never shown with the euro sign. */
export function formatCurrency(amount: number | string, currency: string): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat(LOCALE, { style: "currency", currency, useGrouping: true, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(isNaN(num) ? 0 : num);
}

export function formatNumber(value: number | string, decimals: number = 0): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "0";
  return new Intl.NumberFormat(LOCALE, {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num);
}

export function formatDate(dateInput: string | Date): string {
  const d = typeof dateInput === "string" ? new Date(dateInput) : dateInput;
  if (isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat(LOCALE, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(d);
}

export function formatPercent(value: number | string, decimals: number = 1): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "0 %";
  return new Intl.NumberFormat(LOCALE, {
    style: "percent",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num);
}

export function formatDateTime(input: string | Date): string {
  const d = typeof input === "string" ? new Date(input) : input;
  return new Intl.DateTimeFormat(LOCALE, { dateStyle: "short", timeStyle: "short", timeZone: "Europe/Madrid" }).format(d);
}
