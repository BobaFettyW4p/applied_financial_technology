// Treasury price/yield formula: 31 CFR Part 356, Appendix B, section II.D.
// Yields are annual percentages, quoted with semiannual compounding.
function paymentTerms(row) {
  const next = new Date(row.next_coupon_date + 'T00:00:00Z');
  const maturity = new Date(row.maturity + 'T00:00:00Z');
  const months = (maturity.getUTCFullYear() - next.getUTCFullYear()) * 12 +
    maturity.getUTCMonth() - next.getUTCMonth();
  const n = months / 6;
  const fraction = row.days_to_next_coupon / row.coupon_period_days;
  if (!Number.isInteger(n) || n < 0 || !Number.isFinite(n) ||
      !(fraction > 0 && fraction <= 1)) {
    throw new Error('Invalid dates or yield for ' + row.cusip);
  }
  return { n, fraction, coupon: row.coupon / 2 };
}

function priceAtYield({ n, fraction, coupon }, annualYield) {
  if (!(annualYield > -200)) throw new Error('Yield must exceed -200%');
  const halfYearYield = annualYield / 200;
  const exponent = -n * Math.log1p(halfYearYield);
  const principalFactor = Math.exp(exponent);
  // expm1 keeps the annuity accurate when the yield is close to zero.
  const annuity = halfYearYield === 0 ? n : -Math.expm1(exponent) / halfYearYield;
  const value = coupon + coupon * annuity + 100 * principalFactor;
  // Treasury uses simple discounting for the initial partial coupon period.
  return value / (1 + fraction * halfYearYield);
}

export function dirtyPriceAtYield(row, annualYield) {
  return priceAtYield(paymentTerms(row), annualYield);
}

export function yieldToMaturity(row) {
  if (!Number.isFinite(row.dirty_price) || row.dirty_price <= 0 ||
      !Number.isFinite(row.coupon) || row.coupon <= 0) {
    throw new Error('Invalid price or coupon for ' + row.cusip);
  }
  const terms = paymentTerms(row);
  if (terms.n === 0) {
    return ((100 + terms.coupon) / row.dirty_price - 1) * 200 / terms.fraction;
  }
  const price = value => priceAtYield(terms, value);
  let low = -199, high = 100;
  while (price(high) > row.dirty_price && high < 1e6) high *= 2;
  if (price(low) < row.dirty_price || price(high) > row.dirty_price) {
    throw new Error('Could not find a yield for ' + row.cusip);
  }
  let current = 4;
  for (let iteration = 0; iteration < 60; iteration++) {
    const difference = price(current) - row.dirty_price;
    if (Math.abs(difference) < 1e-10) return current;
    if (difference > 0) low = current;
    else high = current;
    // Use the local price slope for a fast step, retaining the bracket as a fallback.
    const slope = (price(current + .0001) - price(current - .0001)) / .0002;
    const next = current - difference / slope;
    current = Number.isFinite(next) && next > low && next < high ? next : (low + high) / 2;
  }
  throw new Error('Yield calculation did not converge for ' + row.cusip);
}

export function maturityBucket(row) {
  const settlement = new Date(row.settlement_date + 'T00:00:00Z');
  const maturity = new Date(row.maturity + 'T00:00:00Z');
  for (const [index, years] of [1, 3, 5, 10, 20].entries()) {
    const boundary = new Date(settlement);
    boundary.setUTCFullYear(settlement.getUTCFullYear() + years);
    if (maturity < boundary) return index;
  }
  return 5;
}

export function withYield(row) {
  return { ...row, ytm: yieldToMaturity(row), maturity_bucket: maturityBucket(row) };
}
