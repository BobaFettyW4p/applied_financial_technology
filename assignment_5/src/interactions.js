// Runs in the browser. All views use the same records and fixed settlement date.
export const browserScript = String.raw`(() => {
  const prices = JSON.parse(document.getElementById('price-data').textContent);
  const byCusip = new Map(prices.map(row => [row.cusip, row]));
  const body = document.querySelector('tbody');
  const tableRows = [...body.rows];
  const form = document.getElementById('filters');
  const count = document.getElementById('count');
  const heads = [...document.querySelectorAll('thead th')];
  const tooltip = document.getElementById('chart-tooltip');
  const tableScroll = document.querySelector('.table-scroll');
  const number = new Intl.NumberFormat('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 6 });
  const rate = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 });
  const date = value => new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
  }).format(new Date(value + 'T00:00:00Z'));
  const timestamp = value => Date.parse(value + 'T00:00:00Z');
  let visible = prices;
  let selected = prices[0].cusip;
  const colors = { clean: '#527ba1', dirty: '#246947', short: '#527ba1', medium: '#287b72', long: '#996149' };

  form.hidden = false;
  document.getElementById('visuals').hidden = false;
  form.addEventListener('submit', event => event.preventDefault());

  function select(cusip, revealRow = false) {
    selected = cusip;
    const row = byCusip.get(cusip);
    for (const element of tableRows) {
      const active = element.dataset.cusip === cusip;
      element.classList.toggle('selected', active);
      element.querySelector('.security-select').setAttribute('aria-pressed', String(active));
      if (active && revealRow) {
        // Scroll inside the table without pulling the page away from the chart.
        tableScroll.scrollTop = element.offsetTop - tableScroll.clientHeight / 2;
      }
    }
    document.querySelectorAll('.chart-point').forEach(point => {
      const active = point.dataset.cusip === cusip;
      point.classList.toggle('selected', active);
      point.setAttribute('aria-pressed', String(active));
      if (active) point.parentNode.append(point);
    });
    const text = (id, value) => { document.getElementById(id).textContent = value; };
    text('selected-cusip', row.cusip);
    text('selected-details', row.security_type + ' · ' + rate.format(row.coupon) + '% coupon · Matures ' + date(row.maturity) + ' · YTM ' + row.ytm.toFixed(3) + '%');
    text('previous-date', date(row.previous_coupon_date));
    text('settlement-date', date(row.settlement_date));
    text('next-date', date(row.next_coupon_date));
    text('elapsed-days', row.days_accrued + ' days elapsed');
    text('remaining-days', row.days_to_next_coupon + ' days remaining');
    const progress = row.days_accrued / row.coupon_period_days * 100;
    document.getElementById('timeline-fill').style.width = progress + '%';
    document.getElementById('settlement-marker').style.left = progress + '%';
    const markerLabel = document.querySelector('.marker-label');
    markerLabel.style.left = progress > 80 ? 'auto' : progress < 20 ? '0' : '50%';
    markerLabel.style.right = progress > 80 ? '0' : 'auto';
    markerLabel.style.transform = progress > 80 || progress < 20 ? 'none' : 'translateX(-50%)';
    document.getElementById('coupon-timeline').setAttribute('aria-label',
      row.days_accrued + ' of ' + row.coupon_period_days + ' days elapsed between ' +
      date(row.previous_coupon_date) + ' and ' + date(row.next_coupon_date));
    text('period-fraction', row.days_accrued + ' / ' + row.coupon_period_days + ' days');
    text('half-coupon', '$' + number.format(row.coupon_per_half_year));
    text('accrued-formula', '$' + number.format(row.coupon_per_half_year) + ' × ' +
      row.days_accrued + ' / ' + row.coupon_period_days + ' = $' + number.format(row.accrued_interest));
    text('dirty-formula', '$' + number.format(row.clean_price) + ' + $' +
      number.format(row.accrued_interest) + ' = $' + number.format(row.dirty_price));
  }

  for (const element of tableRows) {
    const cell = element.cells[0];
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'security-select';
    button.textContent = cell.textContent;
    button.setAttribute('aria-label', 'Explore ' + cell.textContent);
    cell.replaceChildren(button);
    element.addEventListener('click', () => {
      select(element.dataset.cusip);
      document.getElementById('timeline-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  function maturityColor(row) {
    const years = (timestamp(row.maturity) - timestamp(row.settlement_date)) / (365.25 * 86400000);
    return years < 2 ? colors.short : years <= 10 ? colors.medium : colors.long;
  }

  function showTooltip(event, row) {
    tooltip.replaceChildren();
    const title = document.createElement('strong');
    title.textContent = row.cusip + ' · ' + row.security_type;
    const details = document.createElement('div');
    details.textContent = rate.format(row.coupon) + '% coupon · Matures ' + date(row.maturity);
    const values = document.createElement('div');
    values.textContent = 'Clean $' + number.format(row.clean_price) + ' · Accrued $' +
      number.format(row.accrued_interest) + ' · Dirty $' + number.format(row.dirty_price);
    const yieldText = document.createElement('div');
    yieldText.textContent = 'YTM ' + row.ytm.toFixed(3) + '%';
    tooltip.append(title, details, values, yieldText);
    tooltip.hidden = false;
    const box = event.currentTarget.getBoundingClientRect();
    const x = event.clientX || box.left;
    const y = event.clientY || box.bottom;
    tooltip.style.left = Math.max(8, Math.min(x + 12, window.innerWidth - tooltip.offsetWidth - 8)) + 'px';
    tooltip.style.top = Math.max(8, Math.min(y + 16, window.innerHeight - tooltip.offsetHeight - 8)) + 'px';
  }

  function hideTooltip() { tooltip.hidden = true; }

  function drawChart(id, kind) {
    const svg = document.getElementById(id);
    const ns = 'http://www.w3.org/2000/svg';
    svg.replaceChildren();
    const make = (name, attributes, parent = svg, text) => {
      const node = document.createElementNS(ns, name);
      for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
      if (text !== undefined) node.textContent = text;
      parent.append(node);
      return node;
    };
    const title = make('title', {}, svg, kind === 'accrual' ? 'Coupon rate and accrued interest' : 'Coupon rate and clean price');
    title.id = id + '-title';
    svg.setAttribute('aria-labelledby', title.id);
    const width = 560, height = 340;
    const left = 62, right = 20, top = 24, bottom = 60;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    if (!visible.length) {
      make('text', { x: width / 2, y: height / 2, 'text-anchor': 'middle', class: 'chart-empty' }, svg,
        'No securities match these filters.');
      return;
    }
    const values = visible.map(row => row.coupon);
    let xmin = Math.min(...values), xmax = Math.max(...values);
    const xpad = Math.max((xmax - xmin) * .05, .125);
    xmin -= xpad; xmax += xpad;
    xmin = Math.max(0, xmin);
    const tickStep = range => {
      const unit = 10 ** Math.floor(Math.log10(Math.max(range / 4, .01)));
      return [1, 2, 5, 10].find(step => step * unit >= range / 4) * unit;
    };
    let ymin = kind === 'accrual' ? 0 : Math.min(100, ...visible.map(row => row.clean_price));
    let ymax = kind === 'accrual' ? Math.max(.5, ...visible.map(row => row.accrued_interest)) : Math.max(100, ...visible.map(row => row.clean_price));
    const ystep = tickStep(Math.max(ymax - ymin, kind === 'accrual' ? .5 : 2));
    ymin = Math.floor(ymin / ystep) * ystep;
    ymax = Math.ceil(ymax / ystep) * ystep;
    if (ymax === ymin) { ymin -= ystep; ymax += ystep; }
    const xstep = tickStep(xmax - xmin);
    if (kind !== 'prices') {
      xmin = Math.max(0, Math.floor(xmin / xstep) * xstep);
      xmax = Math.ceil(xmax / xstep) * xstep;
    }
    const x = value => left + (value - xmin) / (xmax - xmin) * plotWidth;
    const y = value => top + (ymax - value) / (ymax - ymin) * plotHeight;
    for (let value = ymin; value <= ymax + ystep / 2; value += ystep) {
      make('line', { x1: left, x2: width - right, y1: y(value), y2: y(value), class: 'grid-line' });
      make('text', { x: left - 9, y: y(value) + 4, 'text-anchor': 'end', class: 'axis-tick' }, svg,
        '$' + value.toFixed(ystep < 1 ? 1 : 0));
    }
    for (let value = xmin; value <= xmax + xstep / 2; value += xstep) {
      make('text', { x: x(value), y: height - bottom + 22, 'text-anchor': 'middle', class: 'axis-tick' }, svg,
        rate.format(value) + '%');
    }
    if (kind !== 'accrual') {
    make('line', { x1: left, x2: width - right, y1: y(100), y2: y(100), class: 'par-line' });
    make('text', { x: width - right, y: y(100) - 6, 'text-anchor': 'end', class: 'axis-tick' }, svg, '$100 face value');
    }
    make('text', { x: left + plotWidth / 2, y: height - 10, 'text-anchor': 'middle', class: 'axis-label' }, svg,
      'Annual coupon rate');
    make('text', { transform: 'translate(15,' + (top + plotHeight / 2) + ') rotate(-90)', 'text-anchor': 'middle', class: 'axis-label' }, svg,
      kind === 'accrual' ? 'Accrued interest per $100 face value' : 'Clean price per $100 face value');

    // Draw the selected security last so it remains visible in dense clusters.
    const ordered = [...visible].sort((a, b) => Number(a.cusip === selected) - Number(b.cusip === selected));
    for (const row of ordered) {
      const group = make('g', {
        class: 'chart-point' + (row.cusip === selected ? ' selected' : ''),
        'data-cusip': row.cusip, role: 'button', tabindex: '0',
        'aria-pressed': String(row.cusip === selected),
        'aria-label': row.cusip + ', ' + rate.format(row.coupon) + '% coupon, maturity ' + date(row.maturity) +
          ', clean price ' + number.format(row.clean_price) + ', dirty price ' + number.format(row.dirty_price),
      });
      const px = x(row.coupon);
      const progress = row.days_accrued / row.coupon_period_days;
      const color = kind === 'accrual' ? 'hsl(145, 32%, ' + (82 - progress * 52) + '%)' : maturityColor(row);
      make('circle', { cx: px, cy: y(kind === 'accrual' ? row.accrued_interest : row.clean_price), r: 4, fill: color, class: 'dot' }, group);
      group.addEventListener('pointerenter', event => showTooltip(event, row));
      group.addEventListener('pointermove', event => showTooltip(event, row));
      group.addEventListener('pointerleave', hideTooltip);
      group.addEventListener('focus', event => showTooltip(event, row));
      group.addEventListener('blur', hideTooltip);
      group.addEventListener('click', () => { select(row.cusip, true); hideTooltip(); });
      group.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault(); select(row.cusip, true); hideTooltip();
        }
      });
    }
  }

  function svgHelpers(id, titleText) {
    const svg = document.getElementById(id);
    svg.replaceChildren();
    const make = (tag, attributes, parent = svg, text) => {
      const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
      Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
      if (text !== undefined) node.textContent = text;
      parent.append(node);
      return node;
    };
    make('title', {}, svg, titleText);
    if (!visible.length) make('text', { x: 530, y: 150, 'text-anchor': 'middle', class: 'chart-empty' }, svg, 'No securities match these filters.');
    return { svg, make };
  }

  function drawYields() {
    const { svg, make } = svgHelpers('yield-chart', 'Median yield to maturity by remaining maturity, with the middle 50 percent of yields');
    if (!visible.length) return;
    const buckets = [
      { label: '<1 year', from: 0, to: 1 }, { label: '1–<3 years', from: 1, to: 3 },
      { label: '3–<5 years', from: 3, to: 5 }, { label: '5–<10 years', from: 5, to: 10 },
      { label: '10–<20 years', from: 10, to: 20 }, { label: '20+ years', from: 20, to: null },
    ];
    const quantile = (values, fraction) => {
      const position = (values.length - 1) * fraction;
      const low = Math.floor(position), high = Math.ceil(position);
      return values[low] + (values[high] - values[low]) * (position - low);
    };
    const summaries = buckets.map((bucket, index) => {
      const values = visible.filter(row => row.maturity_bucket === index).map(row => row.ytm).sort((a,b) => a-b);
      return { ...bucket, index, count: values.length,
        median: values.length ? quantile(values, .5) : null,
        low: values.length ? quantile(values, .25) : null,
        high: values.length ? quantile(values, .75) : null };
    });
    const nonempty = summaries.filter(bucket => bucket.count);
    const minimum = Math.min(...nonempty.map(bucket => bucket.low)) - .15;
    const maximum = Math.max(...nonempty.map(bucket => bucket.high)) + .15;
    const step = Math.max(.25, Math.ceil((maximum - minimum) / 5 * 4) / 4);
    const ymin = Math.floor(minimum / step) * step;
    const ymax = Math.ceil((maximum + .1) / step) * step;
    const left = 70, right = 30, top = 30, height = 250;
    const plotWidth = 1060 - left - right;
    const y = value => top + (ymax - value) / (ymax - ymin) * height;
    for (let value = ymin; value <= ymax + step / 2; value += step) {
      make('line', { x1: left, x2: 1060-right, y1: y(value), y2: y(value), class: 'grid-line' });
      make('text', { x: left-12, y: y(value)+4, 'text-anchor': 'end', class: 'axis-tick' }, svg, value.toFixed(2) + '%');
    }
    const yearDate = years => {
      const result = new Date(prices[0].settlement_date + 'T00:00:00Z');
      result.setUTCFullYear(result.getUTCFullYear() + years);
      return result;
    };
    summaries.forEach(bucket => {
      const px = left + plotWidth * (bucket.index + .5) / buckets.length;
      const group = make('g', { class: 'yield-bucket', 'data-bucket': bucket.index, 'data-count': bucket.count,
        role: 'button', tabindex: 0, 'aria-label': bucket.label + ': ' + bucket.count + ' securities' +
          (bucket.count ? ', median YTM ' + bucket.median.toFixed(3) + '%' : ', no data') });
      make('rect', { x: px-60, y: top, width: 120, height, fill: 'transparent' }, group);
      if (bucket.count) {
        group.setAttribute('data-median', bucket.median);
        group.setAttribute('data-low', bucket.low);
        group.setAttribute('data-high', bucket.high);
        make('line', { x1: px, x2: px, y1: y(bucket.low), y2: y(bucket.high), stroke: '#678b74', 'stroke-width': 5 }, group);
        for (const end of [bucket.low, bucket.high]) make('line', { x1: px-12, x2: px+12, y1: y(end), y2: y(end), stroke: '#678b74', 'stroke-width': 2 }, group);
        make('circle', { cx: px, cy: y(bucket.median), r: 7, fill: '#246947', stroke: '#fff', 'stroke-width': 2 }, group);
        make('text', { x: px, y: y(bucket.high)-15, 'text-anchor': 'middle', class: 'bar-label' }, group, bucket.median.toFixed(2) + '%');
      } else {
        make('text', { x: px, y: top+height/2, 'text-anchor': 'middle', class: 'axis-tick' }, group, 'No data');
      }
      make('text', { x: px, y: 307, 'text-anchor': 'middle', class: 'axis-label' }, group, bucket.label);
      make('text', { x: px, y: 327, 'text-anchor': 'middle', class: 'axis-tick' }, group, 'n = ' + bucket.count);
      const show = event => {
        if (!bucket.count) return;
        tooltip.textContent = bucket.label + ' · ' + bucket.count + ' securities · Median YTM ' + bucket.median.toFixed(3) +
          '% · Middle 50%: ' + bucket.low.toFixed(3) + '%–' + bucket.high.toFixed(3) + '%';
        tooltip.hidden = false;
        const box = group.getBoundingClientRect();
        tooltip.style.left = Math.max(8, Math.min(event.clientX || box.left, window.innerWidth-tooltip.offsetWidth-8)) + 'px';
        tooltip.style.top = Math.max(8, Math.min(event.clientY || box.top, window.innerHeight-tooltip.offsetHeight-8)) + 'px';
      };
      const filterBucket = () => {
        if (!bucket.count) return;
        form.elements.mfrom.value = yearDate(bucket.from).toISOString().slice(0,10);
        if (bucket.to === null) form.elements.mto.value = '';
        else {
          const end = yearDate(bucket.to);
          end.setUTCDate(end.getUTCDate()-1);
          form.elements.mto.value = end.toISOString().slice(0,10);
        }
        apply();
      };
      group.addEventListener('pointerenter', show);
      group.addEventListener('pointermove', show);
      group.addEventListener('pointerleave', hideTooltip);
      group.addEventListener('focus', show);
      group.addEventListener('blur', hideTooltip);
      group.addEventListener('click', filterBucket);
      group.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); filterBucket(); }
      });
    });
    make('text', { x: left + plotWidth / 2, y: 355, 'text-anchor': 'middle', class: 'axis-label' }, svg, 'Time remaining from settlement to maturity');
    make('text', { transform: 'translate(17,155) rotate(-90)', 'text-anchor': 'middle', class: 'axis-label' }, svg, 'Annual yield to maturity');
  }

  function drawMaturities() {
    const { svg, make } = svgHelpers('maturity-chart', 'Number of notes and bonds by maturity year');
    if (!visible.length) return;
    const first = Math.min(...visible.map(row => Number(row.maturity.slice(0, 4))));
    const last = Math.max(...visible.map(row => Number(row.maturity.slice(0, 4))));
    const years = Array.from({ length: last - first + 1 }, (_, index) => first + index);
    const counts = new Map(years.map(year => [year, { Note: 0, Bond: 0 }]));
    visible.forEach(row => counts.get(Number(row.maturity.slice(0, 4)))[row.security_type]++);
    const max = Math.max(...[...counts.values()].map(value => value.Note + value.Bond));
    const ymax = Math.max(4, Math.ceil(max / 4) * 4);
    const left = 55, top = 25, height = 220, plotWidth = 980;
    for (let i = 0; i <= 4; i++) {
      const y = top + height - height * i / 4;
      make('line', { x1: left, x2: left + plotWidth, y1: y, y2: y, class: 'grid-line' });
      make('text', { x: left - 10, y: y + 4, 'text-anchor': 'end', class: 'axis-tick' }, svg, String(Math.round(ymax * i / 4)));
    }
    const slot = plotWidth / years.length;
    years.forEach((year, index) => {
      const countsForYear = counts.get(year), total = countsForYear.Note + countsForYear.Bond;
      const px = left + index * slot + slot * .15;
      const group = make('g', { class: 'year-bar', 'data-year': year, role: 'button', tabindex: 0,
        'aria-label': year + ': ' + countsForYear.Note + ' notes, ' + countsForYear.Bond + ' bonds. Filter to this year.' });
      let y = top + height;
      for (const [type, color] of [['Note', colors.short], ['Bond', colors.dirty]]) {
        const barHeight = countsForYear[type] / ymax * height;
        y -= barHeight;
        make('rect', { x: px, y, width: slot * .7, height: barHeight, fill: color }, group);
      }
      make('title', {}, group, year + ': ' + total + ' securities (' + countsForYear.Note + ' notes, ' + countsForYear.Bond + ' bonds)');
      if (total) make('text', { x: px + slot * .35, y: y - 7, 'text-anchor': 'middle', class: 'axis-tick' }, group, total);
      if (years.length < 15 || index % 2 === 0) make('text', { x: px + slot * .35, y: top + height + 20, 'text-anchor': 'middle', class: 'axis-tick' }, group, year);
      const filterYear = () => {
        form.elements.mfrom.value = year + '-01-01';
        form.elements.mto.value = year + '-12-31';
        apply();
      };
      group.addEventListener('click', filterYear);
      group.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); filterYear(); }
      });
    });
    make('text', { x: left + plotWidth / 2, y: 300, 'text-anchor': 'middle', class: 'axis-label' }, svg, 'Maturity year');
    make('text', { transform: 'translate(14,135) rotate(-90)', 'text-anchor': 'middle', class: 'axis-label' }, svg, 'Number of securities');
  }

  function apply() {
    hideTooltip();
    const filters = Object.fromEntries(new FormData(form));
    const query = (filters.cusip || '').trim().toUpperCase();
    visible = prices.filter(row => (!query || row.cusip.includes(query)) &&
      (!filters.type || row.security_type === filters.type) &&
      (!filters.cmin || row.coupon >= Number(filters.cmin)) &&
      (!filters.cmax || row.coupon <= Number(filters.cmax)) &&
      (!filters.mfrom || row.maturity >= filters.mfrom) &&
      (!filters.mto || row.maturity <= filters.mto));
    const included = new Set(visible.map(row => row.cusip));
    tableRows.forEach(row => { row.hidden = !included.has(row.dataset.cusip); });
    count.textContent = 'Showing ' + visible.length + ' of ' + prices.length + ' securities';
    const timeline = document.getElementById('timeline-card');
    timeline.hidden = !visible.length;
    if (visible.length && !included.has(selected)) selected = visible[0].cusip;
    drawYields();
    drawChart('coupon-chart', 'coupons');
    drawChart('accrual-chart', 'accrual');
    drawMaturities();
    if (visible.length) select(selected);
    document.querySelector('caption').textContent = visible.length + ' securities. Click a CUSIP to explore its coupon period.';
  }

  const keys = [['text'], ['num', 'coupon'], ['text', 'maturity'], ['num', 'clean'], ['num', 'accrued'], ['num', 'dirty']];
  heads[2].setAttribute('aria-sort', 'ascending');
  heads.forEach((heading, index) => {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'sort'; button.textContent = heading.textContent;
    heading.replaceChildren(button);
    button.addEventListener('click', () => {
      const direction = heading.getAttribute('aria-sort') === 'ascending' ? -1 : 1;
      heads.forEach(head => head.removeAttribute('aria-sort'));
      heading.setAttribute('aria-sort', direction === 1 ? 'ascending' : 'descending');
      const [kind, key] = keys[index];
      const value = row => index === 0 ? row.dataset.cusip : row.dataset[key];
      tableRows.sort((a, b) => direction * (kind === 'num' ? value(a) - value(b) : value(a).localeCompare(value(b))) ||
        a.dataset.cusip.localeCompare(b.dataset.cusip));
      body.append(...tableRows);
    });
  });
  form.addEventListener('input', apply);
  form.addEventListener('change', apply);
  form.addEventListener('reset', () => setTimeout(apply));
  document.addEventListener('keydown', event => { if (event.key === 'Escape') hideTooltip(); });
  window.addEventListener('scroll', hideTooltip, true);
  apply();
})();`;
