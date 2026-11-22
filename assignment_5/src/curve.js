// The /curve page: fitted curve, model comparison, rich/cheap scores, and the backtest.
// All numbers are computed offline by the Python pipeline (curve_page.json in R2);
// this module validates that file and renders it. Charts are drawn in the browser
// from a JSON island so the page stays a single server-rendered response.
import { dateLabel, escapeHtml, isoDate, navCss, siteNav } from './shared.js';

export const CURVE_KEY = 'curve_page.json';
const CUSIP = /^[A-Z0-9]{9}$/;
const finite = value => typeof value === 'number' && Number.isFinite(value);

export function validateCurve(doc) {
  if (!doc || typeof doc !== 'object') throw new Error('Curve data is not an object');
  if (!isoDate(doc.price_date)) throw new Error('Curve data has an invalid price date');
  if (!Array.isArray(doc.models) || !doc.models.length) throw new Error('Curve data has no models');
  const keys = new Set();
  for (const m of doc.models) {
    if (!m || typeof m.key !== 'string' || typeof m.label !== 'string' || keys.has(m.key)) {
      throw new Error('A curve model has a missing or duplicate key');
    }
    keys.add(m.key);
    const c = m.curve || {};
    if (!Array.isArray(c.t) || !c.t.length || !['zero_pct', 'forward_pct'].every(k =>
      Array.isArray(c[k]) && c[k].length === c.t.length && c[k].every(finite)) || !c.t.every(finite)) {
      throw new Error(`Model ${m.key} has an invalid curve`);
    }
    if (!m.metrics || !finite(m.metrics.cv_rmse_bp)) throw new Error(`Model ${m.key} has no metrics`);
  }
  if (!keys.has(doc.selected)) throw new Error('The selected model is not in the curve data');
  if (!Array.isArray(doc.bonds) || !doc.bonds.length) throw new Error('Curve data has no securities');
  const seen = new Set();
  for (const b of doc.bonds) {
    if (!b || !CUSIP.test(b.cusip) || seen.has(b.cusip)) {
      throw new Error('A curve record has a missing or duplicate CUSIP');
    }
    seen.add(b.cusip);
    if (!isoDate(b.maturity) || !['coupon', 'years', 'market_ytm', 'fair_ytm'].every(k => finite(b[k])) ||
        !b.rc || ![...keys].every(k => finite(b.rc[k])) || typeof b.in_fit !== 'boolean') {
      throw new Error(`Invalid curve record for ${b.cusip}`);
    }
  }
  const profile = doc.backtest?.profiles?.[doc.selected];
  if (!profile || !Array.isArray(profile.days) || !profile.days.length ||
      !['cheap_decile_bp', 'rich_decile_bp'].every(k => Array.isArray(profile[k]) &&
        profile[k].length === profile.days.length && profile[k].every(finite))) {
    throw new Error('Curve data has no convergence profile for the selected model');
  }
  if (!Array.isArray(doc.issue_selection?.windows)) throw new Error('Curve data has no issue selection');
  const r = doc.robustness;
  if (r != null) {  // optional: the page omits the section without it
    const fwdOk = f => Array.isArray(f) && f.length === 2 && f.every(finite);
    if (!Array.isArray(r.watch) || !r.watch.every(c => CUSIP.test(c)) ||
        !Array.isArray(r.penalty_sweep) || !r.penalty_sweep.length ||
        !r.penalty_sweep.every(x => ['lambda', 'interleaved_cv_bp', 'blocked_cv_bp'].every(k => finite(x[k])) &&
          fwdOk(x.forward_8_14y_pct)) ||
        !Array.isArray(r.liquidity_specs) ||
        !r.liquidity_specs.every(x => Array.isArray(x.features) && finite(x.cv_bp) && fwdOk(x.forward_8_14y_pct)) ||
        !r.nss_reference || !fwdOk(r.nss_reference.forward_8_14y_pct)) {
      throw new Error('Curve data has invalid robustness checks');
    }
  }
  return doc;
}

// --- Formatting ------------------------------------------------------------

const num = (v, d = 2) => (finite(v) ? v.toFixed(d) : '–');
const signed = (v, d = 2) => (finite(v) ? `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}` : '–');
const tstat = v => (finite(v) ? `<span class="t">t ${signed(v, 1)}</span>` : '<span class="t">t –</span>');
const pval = p => (!finite(p) ? '–' : p < 0.001 ? '&lt;0.001' : p.toFixed(3));
const pct = v => (finite(v) ? `${Math.round(v * 100)}%` : '–');
const usd = v => (finite(v) ? `${v < 0 ? '−' : ''}$${Math.round(Math.abs(v) / 1000).toLocaleString('en-US')}k` : '–');
const liquidityLabel = { 'on-the-run': 'On-the-run', 'first off-the-run': '1st off-the-run',
  'off-the-run': 'Off-the-run', unknown: 'Unknown' };

function jsonIsland(value) {
  // Escape "<" so the data cannot close the script element.
  return JSON.stringify(value).replace(/</g, '\\u003c');
}

// --- Sections --------------------------------------------------------------

function answers(doc, sel, nss) {
  const bt1 = sel.backtest?.['1'] || {};
  const bt20 = sel.backtest?.['20'] || {};
  const prof = doc.backtest.profiles[doc.selected];
  const last = prof.days.length - 1;
  const g = doc.issue_selection.groups || {};
  const nssPaired = nss?.paired;
  return `
    <section class="answers" aria-labelledby="answers-title">
      <h2 id="answers-title" class="visually-hidden">Summary</h2>
      <article>
        <h3>Which curve?</h3>
        <p class="big">${escapeHtml(sel.label)}</p>
        <p>Chosen from six models by nested 10-fold cross-validation: ${num(sel.metrics.cv_rmse_bp)} bp
          out-of-sample yield error${nss ? ` vs ${num(nss.metrics.cv_rmse_bp)} bp for Nelson-Siegel-Svensson
          (Diebold-Mariano p = ${pval(nssPaired?.p_value)}); ${num(sel.metrics.blocked_cv_rmse_bp)} vs
          ${num(nss.metrics.blocked_cv_rmse_bp)} bp with whole maturity ranges held out` : ''}.</p>
      </article>
      <article>
        <h3>How is rich/cheap measured?</h3>
        <p class="big">Leave-one-out yield gap</p>
        <p>Each bond's market yield minus the yield of its own cash flows priced off a curve fitted
          <em>without</em> it. Positive = cheap. On-the-run and first off-the-run issues are excluded from
          the fit and scored out of sample.</p>
      </article>
      <article>
        <h3>Is it really cheap?</h3>
        <p class="big">Persistently, yes</p>
        <p>The cheapest decile averages ${signed(prof.cheap_decile_bp[0])} bp and is still
          ${signed(prof.cheap_decile_bp[last])} bp after ${prof.days[last]} days. The 1-day reversion
          (${signed(bt1.gross_bp)} bp, ${tstat(bt1.gross_t)}) vanishes if you trade a day late
          (${signed(bt1.delayed_gross_bp)} bp): it is quote noise, not a mispricing that closes.</p>
      </article>
      <article>
        <h3>What's the edge?</h3>
        <p class="big">Issue selection, not convergence</p>
        <p>A cheap-vs-rich convergence trade loses ${num(-bt20.net_bp)} bp per position after the bid/ask.
          Buying the cheapest issue in a maturity range instead of an average one picks up
          ${signed(g['5-10y']?.net_pickup_vs_average_bp)} bp (5–10y) and ${signed(g['10-30y']?.net_pickup_vs_average_bp)} bp
          (10–30y) of yield after costs, held for life.</p>
      </article>
    </section>`;
}

function scorecard(doc) {
  const rows = [...doc.models].sort((a, b) => a.metrics.cv_rmse_bp - b.metrics.cv_rmse_bp).map(m => {
    const mt = m.metrics;
    const p = m.paired;
    const verdict = m.key === doc.selected ? '<span class="pill best">Selected</span>'
      : p?.significantly_worse ? '<span class="pill worse">Worse</span>' : '<span class="pill tie">Tied</span>';
    return `
            <tr${m.key === doc.selected ? ' class="selected"' : ''}>
              <th scope="row">${escapeHtml(m.label)}</th>
              <td class="number strong">${num(mt.cv_rmse_bp)}</td>
              <td class="number">${mt.blocked_cv_rmse_bp > 100 ? '&gt;100' : num(mt.blocked_cv_rmse_bp)}${m.paired_blocked ? ` <span class="t">p ${pval(m.paired_blocked.p_value)}</span>` : ''}</td>
              <td class="number">${p ? `${signed(p.rmse_diff_bp)} <span class="t">[${signed(p.rmse_diff_ci95_bp?.[0])}, ${signed(p.rmse_diff_ci95_bp?.[1])}]</span>` : '–'}</td>
              <td class="number">${p ? pval(p.p_value) : '–'}</td>
              <td>${verdict}</td>
              <td class="number">${num(mt.effective_dof, 1)}</td>
              <td class="number">${signed(mt.runs_z, 1)}</td>
              <td class="number">${num(mt.bucket_bias_bp)}</td>
              <td class="number">${num(mt.stability_median_std_bp)}</td>
              <td class="number">${num(mt.wiggles, 0)}</td>
            </tr>`;
  }).join('');
  return `
      <div class="table-scroll compact" tabindex="0" role="region" aria-label="Curve model scorecard">
        <table>
          <caption>Every model is fitted to the same ${doc.fit_count} bonds with the same duration-weighted
            objective and scored the same way. Sorted by cross-validated error.</caption>
          <thead><tr>
            <th scope="col">Model</th>
            <th scope="col" class="number">CV error (bp)</th>
            <th scope="col" class="number">Blocked CV (bp)</th>
            <th scope="col" class="number">Gap to best [95% CI]</th>
            <th scope="col" class="number">p-value</th>
            <th scope="col">Verdict</th>
            <th scope="col" class="number">Effective params</th>
            <th scope="col" class="number">Runs z</th>
            <th scope="col" class="number">Sector bias (bp)</th>
            <th scope="col" class="number">Stability (bp)</th>
            <th scope="col" class="number">Forward wiggles</th>
          </tr></thead>
          <tbody>${rows}
          </tbody>
        </table>
      </div>
      <p class="notes"><strong>CV error</strong>: nested 10-fold cross-validated yield error; each fold re-picks the
        model's own shape parameters or smoothing penalty. <strong>Blocked CV</strong>: the same with whole maturity ranges
        held out, so a curve cannot learn a sector's level from that sector's own bonds (p: Diebold-Mariano vs the selected
        model on those errors). The smoothing and VRP splines choose their penalty this way; the unpenalized splines
        extrapolate wildly across a missing range (&gt;100 bp). <strong>Gap to best / p-value</strong>:
        Diebold-Mariano test on the interleaved-CV errors with a Newey-West variance and a block-bootstrap interval;
        "Worse" needs both.
        <strong>Runs z</strong>: residual clustering by maturity (0 = random; very negative = the curve's shape is wrong).
        <strong>Sector bias</strong>: RMS of average residuals across maturity buckets. <strong>Stability</strong>: median
        bootstrap standard deviation of a bond's score. <strong>Forward wiggles</strong>: turning points in the forward
        curve; the overfit spline ties on accuracy but fails here.</p>`;
}

function backtestTable(doc) {
  const keys = [doc.selected, 'nss'].filter((k, i, a) => a.indexOf(k) === i &&
    doc.models.some(m => m.key === k));
  const rows = keys.flatMap(k => {
    const m = doc.models.find(x => x.key === k);
    return doc.backtest.horizons.map((h, i) => {
      const r = m.backtest?.[String(h)] || {};
      return `
            <tr${i === 0 ? ' class="group-start"' : ''}>
              ${i === 0 ? `<th scope="rowgroup" rowspan="${doc.backtest.horizons.length}">${escapeHtml(m.label)}</th>` : ''}
              <td class="number">${h} day${h > 1 ? 's' : ''}</td>
              <td class="number">${signed(r.fm_slope, 3)} ${tstat(r.fm_t)}</td>
              <td class="number">${signed(r.gross_bp)} ${tstat(r.gross_t)}</td>
              <td class="number strong">${signed(r.delayed_gross_bp)} ${tstat(r.delayed_gross_t)}</td>
              <td class="number">${signed(r.net_bp)} ${tstat(r.net_t)}</td>
              <td class="number">${pct(r.hit_rate)}</td>
            </tr>`;
    });
  }).join('');
  const dropped = doc.backtest.dropped_days?.length
    ? ` ${doc.backtest.dropped_days.map(d => dateLabel(d.date)).join(', ')} excluded: FedInvest had not published end-of-day prices.`
    : '';
  return `
      <div class="table-scroll compact" tabindex="0" role="region" aria-label="Convergence backtest">
        <table>
          <caption>Each day: buy the cheapest 20% and sell the richest 20% of the fit set, equal DV01 per bond,
            hedged with that day's fitted curve. P&amp;L in bp of yield per position.</caption>
          <thead><tr>
            <th scope="col">Model</th>
            <th scope="col" class="number">Hold</th>
            <th scope="col" class="number">Reversion slope</th>
            <th scope="col" class="number">Gross P&amp;L</th>
            <th scope="col" class="number">Gross, entered next day</th>
            <th scope="col" class="number">Net of bid/ask</th>
            <th scope="col" class="number">Hit rate</th>
          </tr></thead>
          <tbody>${rows}
          </tbody>
        </table>
      </div>
      <p class="notes"><strong>Reversion slope</strong>: Fama-MacBeth regression of the change in score on today's score
        (−1 = gap fully closes, 0 = no convergence). <strong>Entered next day</strong>: the same trade bought at the next
        day's prices; mean reversion caused by noise in today's quote disappears, a real mispricing would not.
        <strong>Net</strong>: buys at FedInvest's BUY price and sells at its SELL price on entry and exit. t-statistics use
        Newey-West standard errors because holding windows overlap. ${doc.backtest.days} trading days,
        ${dateLabel(doc.backtest.window[0])} to ${dateLabel(doc.backtest.window[1])}.${dropped}</p>`;
}

function issueTable(doc) {
  const rows = doc.issue_selection.windows.filter(w => w.days).map(w => `
            <tr>
              <th scope="row">${w.from}–${w.to === 30.5 ? 30 : w.to}y</th>
              <td class="number">${num(w.issues, 0)}</td>
              <td class="number">${signed(w.pickup_vs_average_bp)}</td>
              <td class="number strong">${signed(w.net_pickup_vs_average_bp)}</td>
              <td class="number">${signed(w.pickup_vs_richest_bp)}</td>
              <td class="number">${signed(w.net_pickup_vs_newest_bp)}</td>
              <td class="number">${usd(w.pick_discount_usd_per_100mm)}</td>
              <td class="mono">${escapeHtml(w.most_picked?.cusip || '–')} <span class="t">${pct(w.most_picked?.share_of_days)} of days</span></td>
            </tr>`).join('');
  return `
      <div class="table-scroll compact" tabindex="0" role="region" aria-label="Issue selection by maturity">
        <table>
          <caption>Yield pickup from buying the cheapest issue in each maturity range, averaged over the backtest days.</caption>
          <thead><tr>
            <th scope="col">Maturity</th>
            <th scope="col" class="number">Issues</th>
            <th scope="col" class="number">vs average (bp)</th>
            <th scope="col" class="number">Net of cost</th>
            <th scope="col" class="number">vs richest</th>
            <th scope="col" class="number">vs newest, net</th>
            <th scope="col" class="number">Below curve, per $100mm</th>
            <th scope="col">Most often cheapest</th>
          </tr></thead>
          <tbody>${rows}
          </tbody>
        </table>
      </div>
      <p class="notes"><strong>Net of cost</strong> subtracts the difference in FedInvest purchase cost, converted to yield.
        Short maturities look cheapest but lose after costs: the picks are 1997–2000 thirty-year bonds that are cheap because
        they are illiquid. From 5 years out the pickup survives costs and the same issue is usually the pick. Realized
        returns over three months are too noisy to confirm a 1–4 bp/year carry, so this is the predicted yield advantage.
        The 8–10y pick is a recent 10-year note; its pickup is relative to the old bonds around it (see
        <a href="#robust-title">Is the 10-year bend real?</a>).</p>`;
}

function bondTable(doc) {
  const sel = doc.selected;
  const hasNss = doc.models.some(m => m.key === 'nss');
  const rows = [...doc.bonds].sort((a, b) => b.rc[sel] - a.rc[sel]).map(b => {
    const rc = b.rc[sel];
    const p = b.persist;
    return `
            <tr data-years="${b.years}" data-coupon="${b.coupon}" data-maturity="${b.maturity}" data-fit="${b.in_fit ? 'yes' : 'no'}"
                data-ytm="${b.market_ytm}" data-fair="${b.fair_ytm}" data-rc="${rc}" data-nss="${hasNss ? b.rc.nss : ''}"
                data-mean="${p ? p.mean_bp : ''}" data-share="${p ? p.cheap_share : ''}">
              <th scope="row">${escapeHtml(b.cusip)}</th>
              <td class="number">${num(b.coupon, 3)}%</td>
              <td class="maturity"><time datetime="${b.maturity}">${dateLabel(b.maturity)}</time></td>
              <td>${escapeHtml(liquidityLabel[b.liquidity] || b.liquidity)}${b.in_fit ? '' : ' <span class="t">not in fit</span>'}</td>
              <td class="number">${num(b.market_ytm, 3)}%</td>
              <td class="number">${num(b.fair_ytm, 3)}%</td>
              <td class="number strong ${rc > 0 ? 'cheap' : 'rich'}">${signed(rc)}</td>
              ${hasNss ? `<td class="number">${signed(b.rc.nss)}</td>` : ''}
              <td class="number">${p ? signed(p.mean_bp) : '–'}</td>
              <td class="number">${p ? pct(p.cheap_share) : '–'}</td>
            </tr>`;
  }).join('');
  return `
      <form class="filters" id="bond-filters" aria-label="Filter securities" hidden>
        <label>CUSIP<input type="search" name="cusip" placeholder="e.g. 912810" autocomplete="off"></label>
        <label>Signal<select name="signal"><option value="">All</option><option value="cheap">Cheap</option><option value="rich">Rich</option></select></label>
        <label>Fit<select name="fit"><option value="">All</option><option value="yes">In fit</option><option value="no">Excluded (newest issues)</option></select></label>
        <label>Years from<input type="number" name="ymin" step="0.5" min="0"></label>
        <label>Years to<input type="number" name="ymax" step="0.5" min="0"></label>
        <button type="reset">Clear</button>
      </form>
      <p class="count" id="bond-count" aria-live="polite"></p>
      <div class="table-scroll" tabindex="0" role="region" aria-label="Rich/cheap scores, scroll for more securities">
        <table id="bond-table">
          <caption>${doc.bonds.length} notes and bonds, cheapest first. Scores in bp of yield; positive = cheap.</caption>
          <thead><tr>
            <th scope="col" data-sort="text">CUSIP</th>
            <th scope="col" class="number" data-sort="coupon">Coupon</th>
            <th scope="col" data-sort="maturity">Maturity</th>
            <th scope="col" data-sort="fit">Liquidity</th>
            <th scope="col" class="number" data-sort="ytm">Market yield</th>
            <th scope="col" class="number" data-sort="fair">Fair yield</th>
            <th scope="col" class="number" data-sort="rc">Rich/cheap</th>
            ${hasNss ? '<th scope="col" class="number" data-sort="nss">NSS score</th>' : ''}
            <th scope="col" class="number" data-sort="mean">${doc.backtest.days}-day mean</th>
            <th scope="col" class="number" data-sort="share">Days cheap</th>
          </tr></thead>
          <tbody>${rows}
          </tbody>
        </table>
      </div>
      <p class="notes">Yields are semiannual bond-equivalent, from end-of-day dirty prices. <strong>Fair yield</strong> is the
        market yield minus the score. <strong>${doc.backtest.days}-day mean</strong> and <strong>Days cheap</strong> come from
        refitting the curve on every backtest day (securities scored on at least ${doc.backtest.persist_min_days} days).
        The recent 10-year notes score cheap and the old thirty-year bonds maturing around them score rich. The gap between
        the two groups is in every model; which side is "fair" depends on how smooth the curve is assumed to be. See
        <a href="#robust-title">Is the 10-year bend real?</a></p>`;
}

function robustnessSection(doc) {
  const r = doc.robustness;
  if (!r) return '';
  const names = { '91282CRF0': 'Aug 2036 10y (on-the-run)', '91282CQQ7': 'May 2036 10y',
    '91282CPZ8': 'Feb 2036 10y', '912810FT0': '4.5% Feb 2036 bond', '912810FB9': '6.125% Nov 2027 bond',
    '912810FA1': '6.375% Aug 2027 bond' };
  const watch = r.watch.slice(0, 4);
  const head = watch.map(c => `<th scope="col" class="number">${escapeHtml(names[c] || c)}</th>`).join('');
  const cells = sc => watch.map(c => `<td class="number">${signed(sc?.[c])}</td>`).join('');
  const fwd = f => `${num(f?.[0])}–${num(f?.[1])}%`;
  const lam = v => {
    const [m, e] = v.toExponential(0).split('e');
    return `${m === '1' ? '' : `${m}×`}10<sup>${Number(e) < 0 ? '−' : ''}${Math.abs(Number(e))}</sup>`;
  };
  const short = { premium: 'Coupon premium', old: 'Issued 10+ years ago', age: 'Log age' };
  const shown = r.penalty_sweep.filter((_, i) => i % 2 === 0 || r.penalty_sweep[i].lambda === r.best_lambda_blocked);
  const sweepRows = shown.map(s => {
    const best = s.lambda === r.best_lambda_blocked;
    const inter = s.lambda === r.best_lambda_interleaved;
    return `
            <tr${best ? ' class="selected"' : ''}>
              <th scope="row">${lam(s.lambda)}${best ? ' <span class="pill best">Blocked-CV pick</span>' : inter ? ' <span class="pill tie">Interleaved pick</span>' : ''}</th>
              <td class="number">${num(s.interleaved_cv_bp)}</td>
              <td class="number${best ? ' strong' : ''}">${num(s.blocked_cv_bp)}</td>
              <td class="number">${fwd(s.forward_8_14y_pct)}</td>${cells(s.scores_bp)}
            </tr>`;
  }).join('');
  const n = r.nss_reference;
  const specRows = r.liquidity_specs.map(s => `
            <tr${s.features.length ? '' : ' class="group-start"'}>
              <th scope="row">${s.model === 'nss' ? 'Nelson-Siegel-Svensson' : 'Smoothing spline'}</th>
              <td>${s.features.length ? s.features.map(f => escapeHtml(short[f] || f)).join(' + ') : 'None'}</td>
              <td class="number">${num(s.cv_bp)}</td>
              <td class="number">${s.vs_no_liquidity ? pval(s.vs_no_liquidity.p_value) : '–'}</td>
              <td class="number">${Object.values(s.gammas_bp).map(g => signed(g)).join(', ') || '–'}</td>
              <td class="number">${fwd(s.forward_8_14y_pct)}</td>${cells(s.scores_bp)}
            </tr>`).join('');
  return `
    <section class="block" aria-labelledby="robust-title">
      <h2 id="robust-title">Is the 10-year bend real?</h2>
      <p class="lede">The spline's forward curve swings between about 4.5% and 6.5% from 8 to 14 years, where recent 10-year
        notes sit next to old thirty-year bonds that trade roughly 10 bp richer. Two checks: does the bend survive a test the
        curve cannot pass by learning a sector from its own bonds, and do bond characteristics explain the gap instead?</p>
      <div class="table-scroll compact" tabindex="0" role="region" aria-label="Smoothing penalty sweep">
        <table>
          <caption>Smoothing spline at each penalty. A heavier penalty forces a smoother curve.</caption>
          <thead><tr>
            <th scope="col">Penalty λ</th>
            <th scope="col" class="number">Interleaved CV (bp)</th>
            <th scope="col" class="number">Blocked CV (bp)</th>
            <th scope="col" class="number">Forward 8–14y</th>${head}
          </tr></thead>
          <tbody>${sweepRows}
            <tr class="group-start">
              <th scope="row">Nelson-Siegel-Svensson</th>
              <td class="number">${num(n.interleaved_cv_bp)}</td>
              <td class="number">${num(n.blocked_cv_bp)}</td>
              <td class="number">${fwd(n.forward_8_14y_pct)}</td>${cells(n.scores_bp)}
            </tr>
          </tbody>
        </table>
      </div>
      <p class="notes">Blocked CV holds out whole maturity ranges, so the bend cannot be learned from neighbouring bonds of the
        same sector. It still prefers a curve that keeps most of the bend; curves smooth enough to make the new 10-year notes
        look fair predict the held-out ranges worse, as does Nelson-Siegel-Svensson. Scores in bp, positive = cheap.</p>
      <div class="table-scroll compact" tabindex="0" role="region" aria-label="Liquidity factor specifications" style="margin-top: 16px">
        <table>
          <caption>Adding per-bond liquidity spreads to the fit: yield = curve + γ × characteristic, estimated jointly with the curve.</caption>
          <thead><tr>
            <th scope="col">Model</th>
            <th scope="col">Characteristics</th>
            <th scope="col" class="number">CV error (bp)</th>
            <th scope="col" class="number">p vs none</th>
            <th scope="col" class="number">γ (bp)</th>
            <th scope="col" class="number">Forward 8–14y</th>${head}
          </tr></thead>
          <tbody>${specRows}
          </tbody>
        </table>
      </div>
      <p class="notes">Coupon premium = coupon minus the bond's yield (% points); log age = log(1 + years since issue).
        No characteristic improves out-of-sample accuracy (p-values from Diebold-Mariano tests against the same
        model without it), the coefficients are under 1 bp, and the bend does not move. Every bond maturing from 10 to 15 years
        is an old thirty-year bond, so a vintage effect and the curve's level there cannot be told apart. The roughly 10 bp gap
        between new 10-year notes and those bonds is real in every model; whether the notes are cheap or the old bonds rich
        rests on how smooth the curve is assumed to be, and the data favour the bend.</p>
    </section>`;
}

// --- Page ------------------------------------------------------------------

export function renderCurvePage(doc, nonce = '') {
  const sel = doc.models.find(m => m.key === doc.selected);
  const nss = doc.models.find(m => m.key === 'nss');
  const chartData = {
    selected: doc.selected,
    models: doc.models.map(m => ({ key: m.key, label: m.label, curve: m.curve })),
    bonds: doc.bonds.map(b => ({ cusip: b.cusip, coupon: b.coupon, maturity: b.maturity, years: b.years,
      liquidity: b.liquidity, fit: b.in_fit, rc: b.rc, market_ytm: b.market_ytm })),
    profile: doc.backtest.profiles[doc.selected],
  };
  const options = (current) => doc.models.map(m =>
    `<option value="${escapeHtml(m.key)}"${m.key === current ? ' selected' : ''}>${escapeHtml(m.label)}</option>`).join('');
  const compareDefault = nss && nss.key !== doc.selected ? 'nss' : doc.models.find(m => m.key !== doc.selected)?.key;

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Fitted Treasury zero curve, model comparison, and rich/cheap analysis for ${doc.price_date}.">
  <title>Treasury curve &amp; rich/cheap</title>
  <style>
    :root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #202c38; background: #f5f4ef; font-synthesis: none;
      --surface: #ffffff; --line: #dce0d8; --grid: #e8ebe5; --muted: #66736c; --secondary: #53616b;
      --accent: #205840; --series-1: #2a78d6; --series-2: #eb6834; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    main { max-width: 1180px; padding: 40px 28px 32px; margin: auto; }
    ${navCss}
    .eyebrow { font-size: 12px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; color: #577263; }
    h1 { font-family: Georgia, "Times New Roman", serif; font-size: clamp(34px, 5vw, 50px);
      font-weight: 400; letter-spacing: -.035em; margin: 12px 0 16px; }
    .intro { max-width: 720px; font-size: 16px; line-height: 1.7; color: var(--secondary); margin: 0; }
    .visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    .answers { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; margin: 32px 0 8px; }
    .answers article { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 18px 20px; }
    .answers h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin: 0 0 10px; }
    .answers .big { font-family: Georgia, serif; font-size: 21px; margin: 0 0 10px; color: #202c38; }
    .answers p { font-size: 13px; line-height: 1.6; color: var(--secondary); margin: 0; }
    section.block { margin-top: 52px; }
    h2 { font-family: Georgia, serif; font-weight: 400; font-size: 26px; letter-spacing: -.02em; margin: 0 0 8px; }
    .lede { font-size: 14px; line-height: 1.7; color: var(--secondary); max-width: 760px; margin: 0 0 18px; }
    .panel { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 16px 18px 10px; margin-bottom: 14px; }
    .panel-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: end; gap: 10px 20px; margin-bottom: 6px; }
    .panel-head h3 { font-size: 14px; margin: 0; }
    .panel-head p { font-size: 12px; color: var(--muted); margin: 4px 0 0; }
    .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; }
    .controls label, .filters label { display: grid; gap: 4px; font-size: 12px; color: var(--muted); }
    select, input { font: inherit; font-size: 13px; padding: 6px 8px; color: inherit;
      border: 1px solid #c9d1c6; border-radius: 6px; background: #fff; }
    .seg { display: inline-flex; border: 1px solid #c9d1c6; border-radius: 6px; overflow: hidden; }
    .seg[hidden] { display: none; }
    .seg button { all: unset; font-size: 13px; padding: 6px 12px; cursor: pointer; color: var(--secondary); }
    .seg button[aria-pressed=true] { background: #e9eee7; color: #202c38; font-weight: 600; }
    .seg button:focus-visible { outline: 3px solid #547c60; outline-offset: -3px; }
    .legend { display: flex; flex-wrap: wrap; gap: 6px 18px; list-style: none; padding: 0; margin: 8px 0 0; font-size: 12px; color: var(--secondary); }
    .legend li { display: inline-flex; align-items: center; gap: 7px; }
    .key-line { width: 16px; height: 2px; border-radius: 1px; display: inline-block; }
    .key-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
    .key-ring { width: 9px; height: 9px; border-radius: 50%; display: inline-block; border: 2px solid var(--series-1); }
    .chart { position: relative; }
    .chart svg { display: block; width: 100%; height: auto; overflow: visible; }
    .chart text { font-size: 11px; fill: var(--muted); }
    .chart .label { font-size: 12px; fill: var(--secondary); }
    .tip { position: absolute; pointer-events: none; background: #fff; border: 1px solid var(--line); border-radius: 6px;
      box-shadow: 0 4px 14px rgba(32, 44, 56, .12); padding: 8px 10px; font-size: 12px; line-height: 1.5; min-width: 150px;
      color: var(--secondary); white-space: nowrap; z-index: 2; }
    .tip strong { color: #202c38; font-variant-numeric: tabular-nums; }
    .tip .row { display: flex; align-items: center; gap: 8px; }
    .grid-2 { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 14px; align-items: start; }
    .table-scroll { max-height: 65vh; overflow: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }
    .table-scroll.compact { max-height: none; }
    table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; }
    caption { text-align: left; padding: 12px 16px; font-size: 12px; color: var(--muted); }
    thead th { position: sticky; top: 0; background: #e9eee7; font-size: 12px; white-space: nowrap; z-index: 1;
      border-top: 1px solid var(--line); border-bottom: 1px solid #d3dcd2; }
    th, td { text-align: left; padding: 11px 14px; }
    tbody th, tbody td { border-bottom: 1px solid #edf0ea; white-space: nowrap; }
    tbody tr:last-child > * { border-bottom: 0; }
    tbody tr:hover { background: #f7f9f4; }
    tr.selected { background: #f1f6ef; }
    tr.group-start > * { border-top: 2px solid #dfe5dc; }
    tbody th[scope=rowgroup] { vertical-align: top; font-weight: 600; }
    #bond-table tbody th, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 500; }
    .number { text-align: right; font-variant-numeric: tabular-nums; }
    .strong { font-weight: 600; color: #202c38; }
    .t { color: #8a958e; font-size: 11px; font-weight: 400; margin-left: 4px; }
    .pill { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px; }
    .pill.best { background: #dcebdf; color: #205840; }
    .pill.worse { background: #f6e3dc; color: #8a3518; }
    .pill.tie { background: #eceee9; color: #53616b; }
    .filters { display: flex; flex-wrap: wrap; gap: 12px 16px; align-items: end; margin: 0 0 12px; }
    .filters input { width: 120px; }
    .filters input[type=search] { width: 150px; }
    .filters button { font: inherit; font-size: 13px; padding: 6px 12px; border: 1px solid #c9d1c6; border-radius: 6px; background: #fff; cursor: pointer; }
    .count { font-size: 12px; color: var(--muted); margin: 0 0 10px; }
    th .sort { all: unset; cursor: pointer; display: inline-flex; gap: 6px; align-items: center; }
    th .sort:focus-visible { outline: 3px solid #547c60; outline-offset: 2px; }
    th .sort::after { content: "\\2195"; color: #9aa89f; font-size: 11px; }
    th[aria-sort=ascending] .sort::after { content: "\\2191"; color: var(--accent); }
    th[aria-sort=descending] .sort::after { content: "\\2193"; color: var(--accent); }
    .notes { font-size: 12px; line-height: 1.75; color: #657169; margin: 12px 0 0; max-width: 980px; }
    footer { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px 24px;
      padding-top: 24px; margin-top: 44px; border-top: 1px solid var(--line); font-size: 12px; color: #657169; }
    a { color: var(--accent); text-underline-offset: 3px; }
    a:focus-visible, .table-scroll:focus-visible { outline: 3px solid #547c60; outline-offset: 4px; }
    @media (max-width: 860px) { .grid-2 { grid-template-columns: 1fr; } }
    @media (max-width: 600px) {
      main { padding: 28px 16px; }
      th, td { padding: 10px; }
      .panel { padding: 12px 10px 6px; }
    }
  </style>
</head>
<body>
  <main>
    ${siteNav('/curve')}
    <header>
      <div class="eyebrow">U.S. Treasury · Curve &amp; relative value</div>
      <h1>Which Treasuries are rich or cheap?</h1>
      <p class="intro">We fit a zero-coupon curve to ${doc.fit_count} off-the-run notes and bonds priced on
        <time datetime="${doc.price_date}">${dateLabel(doc.price_date)}</time>, score every security against it, and then test
        the scores on ${doc.backtest.days} days of history to see what they are worth.</p>
    </header>
    ${answers(doc, sel, nss)}

    <section class="block" aria-labelledby="curve-title">
      <h2 id="curve-title">The curve</h2>
      <p class="lede">Every note and bond against the fitted curve, coloured by how far it sits from it. Hover a dot for the
        security and its score under the selected and the comparison model. The zero and forward views compare the curves
        themselves: zero rates are close for every model, while the forward curve shows Nelson-Siegel-Svensson too stiff to
        follow the curve's shape and the overfit spline wiggling.</p>
      <div class="panel">
        <div class="panel-head">
          <div><h3 id="curve-chart-title">Par curve and every security</h3><p id="curve-chart-sub">Semiannual yield, %</p></div>
          <div class="controls" id="curve-controls" hidden>
            <div class="seg" role="group" aria-label="Curve shown" id="curve-kind">
              <button type="button" data-kind="par" aria-pressed="true">Par + bonds</button>
              <button type="button" data-kind="zero_pct" aria-pressed="false">Zero</button>
              <button type="button" data-kind="forward_pct" aria-pressed="false">Forward</button>
            </div>
            <div class="seg" role="group" aria-label="Bond yields shown" id="yield-mode">
              <button type="button" data-mode="adjusted" aria-pressed="true">Coupon-adjusted</button>
              <button type="button" data-mode="market" aria-pressed="false">Market yields</button>
            </div>
            <label>Compare with<select id="compare-model">${options(compareDefault)}</select></label>
          </div>
        </div>
        <ul class="legend" id="curve-legend"></ul>
        <div class="chart" id="curve-chart" role="img" aria-labelledby="curve-chart-title"></div>
      </div>
    </section>

    <section class="block" aria-labelledby="models-title">
      <h2 id="models-title">Why this model</h2>
      <p class="lede">Six candidates from too stiff to too flexible. The best rich/cheap curve is not the one with the lowest
        in-sample error: a curve flexible enough to fit every bond absorbs the mispricing it is meant to find.</p>
      ${scorecard(doc)}
    </section>

    <section class="block" aria-labelledby="rc-title">
      <h2 id="rc-title">Rich/cheap scores</h2>
      <p class="lede">Each dot is a security's leave-one-out yield gap to the curve. Switch to Nelson-Siegel-Svensson to see
        its errors run in same-sign waves by maturity: those are the curve's errors, not the bonds'.</p>
      <div class="panel">
        <div class="panel-head">
          <div><h3 id="rc-chart-title">Score by maturity</h3><p>bp of yield · above zero = cheap, below = rich</p></div>
          <div class="controls" id="rc-controls" hidden>
            <label>Model<select id="rc-model">${options(doc.selected)}</select></label>
          </div>
        </div>
        <ul class="legend">
          <li><span class="key-dot" style="background: var(--series-1)"></span>In the fit (scored leave-one-out)</li>
          <li><span class="key-ring"></span>On-the-run or first off-the-run (scored out of sample)</li>
        </ul>
        <div class="chart" id="rc-chart" role="img" aria-labelledby="rc-chart-title"></div>
      </div>
    </section>

    ${robustnessSection(doc)}

    <section class="block" aria-labelledby="proof-title">
      <h2 id="proof-title">Is cheap actually cheap?</h2>
      <p class="lede">If a cheap score were a mispricing, it would close. Instead, the cheapest and richest deciles give back a
        sliver on day one and then hold their level for weeks: the cheapness is persistent and structural.</p>
      <div class="panel">
        <div class="panel-head">
          <div><h3 id="conv-chart-title">Score of today's cheapest and richest 10%, over the next ${chartData.profile.days.at(-1)} trading days</h3>
            <p>${escapeHtml(sel.label)} · mean over ${chartData.profile.formation_days} formation days · bp</p></div>
        </div>
        <ul class="legend">
          <li><span class="key-line" style="background: var(--series-1)"></span>Cheapest 10% today</li>
          <li><span class="key-line" style="background: var(--series-2)"></span>Richest 10% today</li>
        </ul>
        <div class="chart" id="conv-chart" role="img" aria-labelledby="conv-chart-title"></div>
      </div>
      ${backtestTable(doc)}
    </section>

    <section class="block" aria-labelledby="edge-title">
      <h2 id="edge-title">The edge: which issue to buy</h2>
      <p class="lede">Convergence trading loses to the bid/ask. A buyer who pays the spread anyway can still pick the cheapest
        issue in the maturity range they need, and keep the extra yield for as long as they hold it.</p>
      ${issueTable(doc)}
    </section>

    <section class="block" aria-labelledby="bonds-title">
      <h2 id="bonds-title">Every security</h2>
      ${bondTable(doc)}
    </section>

    <footer>
      <span>Sources: FedInvest end-of-day prices and Treasury security terms. Analysis: curve_models.py,
        signal_backtest.py, issue_selection.py.</span>
      <a href="/api/curve" download="curve_page.json">Download curve data (JSON)</a>
    </footer>
  </main>
  <script type="application/json" id="curve-data">${jsonIsland(chartData)}</script>
  <script nonce="${nonce}">${CLIENT_SCRIPT}</script>
</body>
</html>`;
}

// --- Browser script (charts, toggles, table sorting) -------------------------
// Kept as plain ES2020 in a string so the page needs no build step.
const CLIENT_SCRIPT = `
(() => {
  const data = JSON.parse(document.getElementById('curve-data').textContent);
  const NS = 'http://www.w3.org/2000/svg';
  const W = 960, M = { l: 56, r: 24, t: 16, b: 44 };
  const css = getComputedStyle(document.documentElement);
  const C1 = css.getPropertyValue('--series-1').trim(), C2 = css.getPropertyValue('--series-2').trim();
  const SURFACE = '#ffffff', GRID = '#e8ebe5', ZERO = '#b9c2bb';
  const byKey = Object.fromEntries(data.models.map(m => [m.key, m]));
  const fmt = (v, d = 2) => (v > 0 ? '+' : v < 0 ? '\\u2212' : '') + Math.abs(v).toFixed(d);

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.append(e);
    return e;
  }
  function ticks(lo, hi, n) {
    const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(s => s * mag).find(s => s >= raw);
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }
  // Axes, grid and scales for one chart; returns helpers for marks.
  function frame(box, o) {
    box.textContent = '';
    const H = o.height || 380;
    const svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, 'aria-hidden': 'true' }, box);
    const x = v => M.l + (v - o.x[0]) / (o.x[1] - o.x[0]) * (W - M.l - M.r);
    const y = v => H - M.b - (v - o.y[0]) / (o.y[1] - o.y[0]) * (H - M.t - M.b);
    const g = el('g', {}, svg);
    for (const v of ticks(o.y[0], o.y[1], 5)) {
      el('line', { x1: M.l, x2: W - M.r, y1: y(v), y2: y(v), stroke: GRID, 'stroke-width': 1 }, g);
      el('text', { x: M.l - 8, y: y(v) + 4, 'text-anchor': 'end' }, g).textContent = o.yFmt(v);
    }
    for (const v of o.xTicks) {
      el('text', { x: x(v), y: H - M.b + 18, 'text-anchor': 'middle' }, g).textContent = o.xFmt(v);
    }
    el('text', { x: (M.l + W - M.r) / 2, y: H - 6, 'text-anchor': 'middle', class: 'label' }, g).textContent = o.xLabel;
    if (o.zero) el('line', { x1: M.l, x2: W - M.r, y1: y(0), y2: y(0), stroke: ZERO, 'stroke-width': 1 }, g);
    const tip = document.createElement('div');
    tip.className = 'tip'; tip.hidden = true; box.append(tip);
    const toData = ev => {
      const r = svg.getBoundingClientRect(), s = r.width / W;
      return { px: (ev.clientX - r.left) / s, py: (ev.clientY - r.top) / s, s, r };
    };
    const showTip = (rows, title, px, py, s) => {
      tip.textContent = '';
      const t = document.createElement('div'); t.textContent = title; tip.append(t);
      for (const [color, label, value, shape] of rows) {
        const row = document.createElement('div'); row.className = 'row';
        const k = document.createElement('span');
        k.className = shape === 'dot' ? 'key-dot' : 'key-line'; k.style.background = color;
        const v = document.createElement('strong'); v.textContent = value;
        const l = document.createElement('span'); l.textContent = label;
        row.append(k, v, l); tip.append(row);
      }
      tip.hidden = false;
      const bw = box.clientWidth, tw = tip.offsetWidth;
      let left = px * s + 14; if (left + tw > bw) left = px * s - tw - 14;
      tip.style.left = Math.max(0, left) + 'px'; tip.style.top = Math.max(0, py * s - 20) + 'px';
    };
    const hideTip = () => { tip.hidden = true; };
    return { svg, x, y, H, toData, showTip, hideTip };
  }
  function path(points, f) {
    return points.map((p, i) => (i ? 'L' : 'M') + f.x(p[0]).toFixed(1) + ',' + f.y(p[1]).toFixed(1)).join('');
  }
  // Vertical crosshair snapping to the nearest x in xs; rows(i) lists every series.
  function crosshair(f, xs, rows, title) {
    const line = el('line', { y1: M.t, y2: f.H - M.b, stroke: '#9aa89f', 'stroke-width': 1, visibility: 'hidden' }, f.svg);
    const dots = [];
    const hit = el('rect', { x: M.l, y: M.t, width: W - M.l - M.r, height: f.H - M.t - M.b, fill: 'transparent' }, f.svg);
    hit.addEventListener('pointermove', ev => {
      const { px, s } = f.toData(ev);
      let i = 0, best = Infinity;
      xs.forEach((v, j) => { const d = Math.abs(f.x(v) - px); if (d < best) { best = d; i = j; } });
      const X = f.x(xs[i]);
      line.setAttribute('x1', X); line.setAttribute('x2', X); line.setAttribute('visibility', 'visible');
      dots.forEach(d => d.remove()); dots.length = 0;
      const rs = rows(i);
      for (const r of rs) {
        dots.push(el('circle', { cx: X, cy: f.y(r.value), r: 4, fill: r.color, stroke: SURFACE, 'stroke-width': 2 }, f.svg));
      }
      f.showTip(rs.map(r => [r.color, r.label, r.text, 'line']), title(i), X, Math.min(...rs.map(r => f.y(r.value))), s);
    });
    hit.addEventListener('pointerleave', () => {
      line.setAttribute('visibility', 'hidden'); dots.forEach(d => d.remove()); f.hideTip();
    });
  }

  // 1. Curve chart ----------------------------------------------------------
  // "Par + bonds" plots every security against the fitted par curve. Each dot
  // sits at its coupon-adjusted yield (par curve at its maturity + its score),
  // so its distance from the line is exactly the score; "Market yields" shows
  // the raw yields instead, where the coupon effect moves low-coupon bonds.
  const curveBox = document.getElementById('curve-chart');
  const compareSel = document.getElementById('compare-model');
  const yieldSeg = document.getElementById('yield-mode');
  const INK = '#202c38', GRAYLINE = '#8a958e';
  const BINS = [[-Infinity, -3, '#c23a39', 'Rich by 3 bp or more'], [-3, -1, '#ec7f7e', 'Rich 1–3 bp'],
    [-1, 1, '#aeb2ad', 'Within 1 bp'], [1, 3, '#5598e7', 'Cheap 1–3 bp'], [3, Infinity, '#1c5cab', 'Cheap by 3 bp or more']];
  const binColor = v => BINS.find(b => v >= b[0] && v < b[1])[2];
  let kind = 'par', yieldMode = 'adjusted';
  // Par yield (semiannual, %) on the curve's 0.25y grid, from the zero curve:
  // a bond paying c/2 every half year to T, priced at 100 clean.
  function parCurve(m) {
    const z = new Map(m.curve.t.map((x, i) => [x.toFixed(2), m.curve.zero_pct[i] / 100]));
    const d = x => (x <= 1e-9 ? 1 : Math.exp(-z.get(x.toFixed(2)) * x));
    return m.curve.t.filter(T => T >= 0.5).map(T => {
      let S = 0, t1 = T;
      for (let x = T; x > 1e-9; x = +(x - 0.5).toFixed(2)) { S += d(x); t1 = x; }
      return [T, 2 * (1 - d(T)) / (S - (1 - 2 * t1)) * 100];
    });
  }
  const parCache = {};
  const par = m => (parCache[m.key] = parCache[m.key] || parCurve(m));
  function interp(pts, x) {
    if (x <= pts[0][0]) return pts[0][1];
    for (let i = 1; i < pts.length; i++) {
      if (x <= pts[i][0]) {
        const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0);
      }
    }
    return pts[pts.length - 1][1];
  }
  function legendItems(items) {
    const legend = document.getElementById('curve-legend');
    legend.textContent = '';
    for (const [cls, color, text, hollow] of items) {
      const li = document.createElement('li'), k = document.createElement('span');
      k.className = cls;
      if (hollow) { k.style.border = '2px solid ' + color; k.style.background = 'transparent'; }
      else k.style.background = color;
      li.append(k, document.createTextNode(text));
      legend.append(li);
    }
  }
  function drawCurve() {
    const a = byKey[data.selected], b = byKey[compareSel.value];
    const other = b && b !== a ? b : null;
    yieldSeg.hidden = kind !== 'par';
    if (kind === 'par') return drawPar(a, other);
    const series = [{ m: a, color: C1 }].concat(other ? [{ m: other, color: C2 }] : []);
    const t = a.curve.t;
    const vals = series.flatMap(s => s.m.curve[kind].filter((_, i) => t[i] >= 0.5));
    const lo = Math.floor(Math.min(...vals) * 4) / 4, hi = Math.ceil(Math.max(...vals) * 4) / 4;
    const f = frame(curveBox, { x: [0, 30], y: [lo, hi], xTicks: [0, 2, 5, 7, 10, 15, 20, 25, 30],
      xFmt: v => v + 'y', yFmt: v => v.toFixed(2) + '%', xLabel: 'Years to maturity' });
    for (const s of series) {
      const pts = s.m.curve.t.map((x, i) => [x, s.m.curve[kind][i]]).filter(p => p[0] >= 0.5);
      el('path', { d: path(pts, f), fill: 'none', stroke: s.color, 'stroke-width': 2,
        'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, f.svg);
    }
    const idx = t.map((x, i) => i).filter(i => t[i] >= 0.5);
    crosshair(f, idx.map(i => t[i]), j => series.map(s => ({ color: s.color, label: s.m.label,
      value: s.m.curve[kind][idx[j]], text: s.m.curve[kind][idx[j]].toFixed(3) + '%' })),
      j => t[idx[j]].toFixed(2) + ' years');
    legendItems(series.map(s => ['key-line', s.color, s.m.label + (s.m.key === data.selected ? ' (selected)' : '')]));
    document.getElementById('curve-chart-title').textContent =
      kind === 'zero_pct' ? 'Fitted zero curve' : 'Instantaneous forward curve';
    document.getElementById('curve-chart-sub').textContent = 'Continuously compounded, % per year';
  }
  function drawPar(a, other) {
    const pa = par(a), po = other ? par(other) : null;
    const key = data.selected;
    const pts = data.bonds.map(bd => {
      const y = yieldMode === 'adjusted' ? interp(pa, bd.years) + bd.rc[key] / 100 : bd.market_ytm;
      return { bd, y };
    });
    const vals = pts.map(p => p.y).concat(pa.map(p => p[1]), po ? po.map(p => p[1]) : []);
    const lo = Math.floor(Math.min(...vals) * 4) / 4, hi = Math.ceil(Math.max(...vals) * 4) / 4;
    const f = frame(curveBox, { x: [0, 30], y: [lo, hi], height: 420, xTicks: [0, 2, 5, 7, 10, 15, 20, 25, 30],
      xFmt: v => v + 'y', yFmt: v => v.toFixed(2) + '%', xLabel: 'Years to maturity' });
    if (po) el('path', { d: path(po, f), fill: 'none', stroke: GRAYLINE, 'stroke-width': 2,
      'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, f.svg);
    el('path', { d: path(pa, f), fill: 'none', stroke: INK, 'stroke-width': 2,
      'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, f.svg);
    // Draw near-zero scores first so the cheap and rich dots sit on top.
    const placed = pts.map(p => ({ ...p, X: f.x(p.bd.years), Y: f.y(p.y), v: p.bd.rc[key] }))
      .sort((p, q) => Math.abs(p.v) - Math.abs(q.v));
    for (const p of placed) {
      const c = binColor(p.v);
      el('circle', p.bd.fit
        ? { cx: p.X, cy: p.Y, r: 4, fill: c, stroke: SURFACE, 'stroke-width': 2 }
        : { cx: p.X, cy: p.Y, r: 4, fill: SURFACE, stroke: c, 'stroke-width': 2 }, f.svg);
    }
    const ring = el('circle', { r: 7, fill: 'none', stroke: INK, 'stroke-width': 1.5, visibility: 'hidden' }, f.svg);
    const hit = el('rect', { x: 0, y: 0, width: W, height: f.H, fill: 'transparent' }, f.svg);
    hit.addEventListener('pointermove', ev => {
      const { px, py, s } = f.toData(ev);
      let best = null, d2 = 24 * 24 / (s * s);
      for (const p of placed) { const d = (p.X - px) ** 2 + (p.Y - py) ** 2; if (d < d2) { d2 = d; best = p; } }
      if (!best) { ring.setAttribute('visibility', 'hidden'); f.hideTip(); return; }
      ring.setAttribute('cx', best.X); ring.setAttribute('cy', best.Y); ring.setAttribute('visibility', 'visible');
      const bd = best.bd, v = best.v;
      const rows = [[binColor(v), v > 0 ? 'bp cheap, ' + a.label : v < 0 ? 'bp rich, ' + a.label : 'bp, ' + a.label, fmt(v), 'dot'],
        [INK, 'market yield', bd.market_ytm.toFixed(3) + '%', 'line'],
        [INK, 'par curve at ' + bd.years.toFixed(2) + 'y', interp(pa, bd.years).toFixed(3) + '%', 'line']];
      if (other) rows.push([GRAYLINE, 'bp, ' + other.label, fmt(bd.rc[other.key]), 'line']);
      f.showTip(rows, bd.cusip + ' · ' + bd.coupon.toFixed(3) + '% · ' + bd.maturity +
        (bd.fit ? '' : ' · ' + bd.liquidity + ', not in fit'), best.X, best.Y, s);
    });
    hit.addEventListener('pointerleave', () => { ring.setAttribute('visibility', 'hidden'); f.hideTip(); });
    legendItems([['key-line', INK, a.label + ' par curve (selected)']]
      .concat(other ? [['key-line', GRAYLINE, other.label + ' par curve']] : [])
      .concat(BINS.map(b => ['key-dot', b[2], b[3]]))
      .concat([['key-dot', '#5f6b66', 'Hollow: newest issues, not in the fit', true]]));
    document.getElementById('curve-chart-title').textContent = 'Par curve and every security';
    document.getElementById('curve-chart-sub').textContent = yieldMode === 'adjusted'
      ? 'Semiannual yield, % · dots at coupon-adjusted yield: distance from the line = rich/cheap score'
      : 'Semiannual yield, % · dots at market yield: low-coupon bonds sit above the line from the coupon effect alone';
  }
  document.querySelectorAll('#curve-kind button').forEach(btn => btn.addEventListener('click', () => {
    kind = btn.dataset.kind;
    document.querySelectorAll('#curve-kind button').forEach(b => b.setAttribute('aria-pressed', String(b === btn)));
    drawCurve();
  }));
  document.querySelectorAll('#yield-mode button').forEach(btn => btn.addEventListener('click', () => {
    yieldMode = btn.dataset.mode;
    document.querySelectorAll('#yield-mode button').forEach(b => b.setAttribute('aria-pressed', String(b === btn)));
    drawCurve();
  }));
  compareSel.addEventListener('change', drawCurve);
  document.getElementById('curve-controls').hidden = false;
  drawCurve();

  // 2. Rich/cheap scatter ---------------------------------------------------
  const rcBox = document.getElementById('rc-chart');
  const rcSel = document.getElementById('rc-model');
  const all = data.bonds.flatMap(b => data.models.map(m => b.rc[m.key]));
  const rcLo = Math.floor(Math.min(...all) / 2) * 2, rcHi = Math.ceil(Math.max(...all) / 2) * 2;
  function drawScatter() {
    const key = rcSel.value;
    const f = frame(rcBox, { x: [0, 30], y: [rcLo, rcHi], height: 400, zero: true,
      xTicks: [0, 2, 5, 7, 10, 15, 20, 25, 30], xFmt: v => v + 'y', yFmt: v => fmt(v, 0),
      xLabel: 'Years to maturity' });
    const pts = data.bonds.map(b => ({ b, X: f.x(b.years), Y: f.y(b.rc[key]) }));
    for (const p of pts) {
      el('circle', p.b.fit
        ? { cx: p.X, cy: p.Y, r: 4, fill: C1, stroke: SURFACE, 'stroke-width': 2 }
        : { cx: p.X, cy: p.Y, r: 4, fill: SURFACE, stroke: C1, 'stroke-width': 2 }, f.svg);
    }
    const ring = el('circle', { r: 7, fill: 'none', stroke: '#202c38', 'stroke-width': 1.5, visibility: 'hidden' }, f.svg);
    const hit = el('rect', { x: 0, y: 0, width: W, height: f.H, fill: 'transparent' }, f.svg);
    hit.addEventListener('pointermove', ev => {
      const { px, py, s } = f.toData(ev);
      let best = null, d2 = 24 * 24 / (s * s);
      for (const p of pts) { const d = (p.X - px) ** 2 + (p.Y - py) ** 2; if (d < d2) { d2 = d; best = p; } }
      if (!best) { ring.setAttribute('visibility', 'hidden'); f.hideTip(); return; }
      ring.setAttribute('cx', best.X); ring.setAttribute('cy', best.Y); ring.setAttribute('visibility', 'visible');
      const b = best.b, v = b.rc[key];
      f.showTip([[C1, v > 0 ? 'bp cheap' : 'bp rich', fmt(v), 'dot']],
        b.cusip + ' · ' + b.coupon.toFixed(3) + '% · ' + b.maturity + (b.fit ? '' : ' · ' + b.liquidity), best.X, best.Y, s);
    });
    hit.addEventListener('pointerleave', () => { ring.setAttribute('visibility', 'hidden'); f.hideTip(); });
  }
  rcSel.addEventListener('change', drawScatter);
  document.getElementById('rc-controls').hidden = false;
  drawScatter();

  // 3. Convergence ----------------------------------------------------------
  const pr = data.profile;
  const cv = pr.cheap_decile_bp.concat(pr.rich_decile_bp);
  const cLo = Math.floor(Math.min(...cv, 0)), cHi = Math.ceil(Math.max(...cv, 0));
  const last = pr.days[pr.days.length - 1];
  const fc = frame(document.getElementById('conv-chart'), { x: [0, last], y: [cLo, cHi], height: 320, zero: true,
    xTicks: pr.days.filter(d => d % 5 === 0), xFmt: v => 'day ' + v, yFmt: v => fmt(v, 0),
    xLabel: 'Trading days after the scores are measured' });
  [[pr.cheap_decile_bp, C1, 'Cheapest 10%'], [pr.rich_decile_bp, C2, 'Richest 10%']].forEach(([ys, color, name]) => {
    el('path', { d: path(pr.days.map((d, i) => [d, ys[i]]), fc), fill: 'none', stroke: color, 'stroke-width': 2,
      'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, fc.svg);
    el('circle', { cx: fc.x(last), cy: fc.y(ys[ys.length - 1]), r: 4, fill: color, stroke: SURFACE, 'stroke-width': 2 }, fc.svg);
    const end = ys[ys.length - 1];
    el('text', { x: fc.x(last) - 4, y: fc.y(end) + (end > 0 ? 22 : -12), 'text-anchor': 'end', class: 'label' },
      fc.svg).textContent = name + ': ' + fmt(ys[0]) + ' on day 0, ' + fmt(end) + ' bp on day ' + last;
  });
  crosshair(fc, pr.days, i => [
    { color: C1, label: 'cheapest 10%', value: pr.cheap_decile_bp[i], text: fmt(pr.cheap_decile_bp[i]) + ' bp' },
    { color: C2, label: 'richest 10%', value: pr.rich_decile_bp[i], text: fmt(pr.rich_decile_bp[i]) + ' bp' },
  ], i => 'Day ' + pr.days[i]);

  // 4. Securities table: filter and sort -----------------------------------
  const table = document.getElementById('bond-table');
  const body = table.tBodies[0], rows = [...body.rows];
  const form = document.getElementById('bond-filters'), count = document.getElementById('bond-count');
  function apply() {
    const f = Object.fromEntries(new FormData(form));
    const q = (f.cusip || '').trim().toUpperCase();
    let shown = 0;
    for (const r of rows) {
      const d = r.dataset, yrs = Number(d.years), rc = Number(d.rc);
      const ok = (!q || r.cells[0].textContent.includes(q)) &&
        (!f.signal || (f.signal === 'cheap' ? rc > 0 : rc <= 0)) && (!f.fit || d.fit === f.fit) &&
        (f.ymin === '' || f.ymin === undefined || yrs >= Number(f.ymin)) &&
        (f.ymax === '' || f.ymax === undefined || yrs <= Number(f.ymax));
      r.hidden = !ok; if (ok) shown++;
    }
    count.textContent = 'Showing ' + shown + ' of ' + rows.length + ' securities';
  }
  const heads = [...table.tHead.rows[0].cells];
  heads.forEach((th, i) => {
    const key = th.dataset.sort;
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'sort'; b.textContent = th.textContent;
    th.textContent = ''; th.append(b);
    b.addEventListener('click', () => {
      const dir = th.getAttribute('aria-sort') === 'descending' ? 1 : -1;
      heads.forEach(h => h.removeAttribute('aria-sort'));
      th.setAttribute('aria-sort', dir === 1 ? 'ascending' : 'descending');
      const val = r => key === 'text' ? r.cells[0].textContent : r.dataset[key];
      const numeric = !['text', 'maturity', 'fit'].includes(key);
      rows.sort((a, c) => {
        const va = val(a), vc = val(c);
        if (numeric) {
          if (va === '' || vc === '') return (va === '') - (vc === '');
          return dir * (Number(va) - Number(vc));
        }
        return dir * va.localeCompare(vc);
      });
      body.append(...rows);
    });
  });
  form.hidden = false;
  form.addEventListener('input', apply);
  form.addEventListener('reset', () => setTimeout(apply));
  apply();
})();
`;
