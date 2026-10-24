let betsData = null;
let roiChart = null;
let pnlSource = 'all';

// Read a color straight from :root in styles.css, so the P&L chart's
// Chart.js canvas stays in sync with the palette without duplicating hex
// values here -- change the variable once, the chart follows.
function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
function hexToRgba(hex, alpha) {
    const h = hex.replace('#', '');
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
}

document.addEventListener('DOMContentLoaded', () => {
    loadBets();
});

async function loadBets() {
    try {
        betsData = await fetchBetsData();
        renderDashboard();
    } catch (error) {
        console.error('Error loading bets:', error);
        document.getElementById('kpiRow').innerHTML = '<div class="calib-note">Error loading data</div>';
    }
}

function renderDashboard() {
    buildKPIs();
    renderCharts();
    renderBetSource();
    renderSelectionsPerformance();
}

// Longest run of consecutive won/lost coupons, most recent first (voids don't break it).
function computeStreak(coupons) {
    const settled = [...coupons].reverse().filter(c => c.status === 'won' || c.status === 'lost');
    if (settled.length === 0) return { count: 0, type: null };
    const type = settled[0].status;
    let count = 0;
    for (const c of settled) {
        if (c.status !== type) break;
        count++;
    }
    return { count, type };
}

function buildKPIs() {
    const s = betsData.summary;
    const roi = (s.roi * 100).toFixed(1);

    const streak = computeStreak(betsData.coupons);
    const streakCls = streak.type === 'won' ? 'pos' : streak.type === 'lost' ? 'neg' : '';
    const streakValue = streak.count > 0 ? `${streak.count}${streak.type === 'won' ? 'W' : 'L'}` : '—';
    const streakNoun = streak.type === 'won'
        ? (streak.count === 1 ? 'win' : 'wins')
        : (streak.count === 1 ? 'loss' : 'losses');
    const streakSub = streak.count > 0 ? `${streak.count} ${streakNoun} in a row (coupons)` : 'no settled coupons yet';

    const selStats = selectionStats(getAllSelections(betsData));
    const selHitCls = selStats.hitRate == null ? '' : (selStats.hitRate >= 0.55 ? 'pos' : selStats.hitRate < 0.45 ? 'neg' : '');

    const bySrc = couponsBySource(betsData.coupons);
    const signed = n => `${n >= 0 ? '+' : ''}${n.toFixed(2)}`;
    const netSourceSub = `real ${signed(bySrc.own.net)} · rec ${signed(bySrc.edge.net)} PLN`;

    const kpis = [
        { label: 'Net Result', info: 'netResult', value: `${s.net_result_pln >= 0 ? '+' : ''}${fmt(s.net_result_pln, 2)} PLN`, cls: s.net_result_pln < 0 ? 'neg' : 'pos', sub: `${fmt(s.total_staked_pln, 2)} PLN staked`, sub2: netSourceSub },
        { label: 'ROI', info: 'roi', value: `${roi >= 0 ? '+' : ''}${roi}%`, cls: roi < 0 ? 'neg' : 'pos', sub: `on ${fmt(s.total_staked_pln, 2)} PLN staked · flat 1u stakes` },
        { label: 'Selection Hit Rate', info: 'selHitRate', value: selStats.hitRate != null ? `${(selStats.hitRate * 100).toFixed(0)}%` : '—', cls: selHitCls, sub: `coupons: ${s.won}W – ${s.lost}L` },
        { label: 'Streak', info: 'streak', value: streakValue, cls: streakCls, sub: streakSub }
    ];

    document.getElementById('kpiRow').innerHTML = kpis.map(k => `
        <div class="kpi ${k.cls}">
            <div class="kpi-label click" onclick="calibInfo('${k.info}')">${k.label}</div>
            <div class="kpi-value ${k.cls}">${k.value}</div>
            <div class="kpi-sub">${k.sub}</div>
            ${k.sub2 ? `<div class="kpi-sub">${k.sub2}</div>` : ''}
        </div>`).join('');
}

function parseISODate(s) {
    const [y, m, d] = s.split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, d));
}
function formatISODate(date) { return date.toISOString().slice(0, 10); }

// One point per calendar day (coupons settled the same day are summed into
// one point, tooltip lists their IDs), plus a synthetic (first day - 1, 0)
// point so the line always starts at zero.
function buildPnlSeries(coupons) {
    const settled = coupons.filter(c => c.status !== 'pending');
    const byDate = {};
    settled.forEach(c => {
        const day = byDate[c.date] = byDate[c.date] || { date: c.date, net: 0, ids: [] };
        day.net += c.net_result_pln;
        day.ids.push(c.id);
    });
    const days = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));

    let cumulative = 0;
    const points = days.map(d => {
        cumulative += d.net;
        return { x: d.date, y: cumulative, dayNet: d.net, ids: d.ids };
    });

    if (points.length > 0) {
        const start = parseISODate(points[0].x);
        start.setUTCDate(start.getUTCDate() - 1);
        points.unshift({ x: formatISODate(start), y: 0, dayNet: 0, ids: [] });
    }
    return points;
}

function setPnlSource(src) {
    pnlSource = src;
    document.querySelectorAll('#pnlSourceToggle .report-tab').forEach(el => {
        el.classList.toggle('active', el.dataset.src === src);
    });
    renderCharts();
}

function renderCharts() {
    const chartBox = document.getElementById('pnlChartBox');
    const noteEl = document.getElementById('pnlNote');
    const plMeta = document.getElementById('plMeta');
    const captionEl = document.getElementById('pnlSourceCaption');

    const bySrc = couponsBySource(betsData.coupons);
    if (captionEl) {
        captionEl.textContent = pnlSource === 'all' ? `${bySrc.own.n} real · ${bySrc.edge.n} recommended` : '';
    }

    // Outcome Split always reflects every coupon regardless of this toggle
    // (a filtered outcome bar on a 2-coupon "Recommended" slice would just
    // show a meaningless 100%-lost bar) -- flag the scope mismatch instead.
    const scopeNoteEl = document.getElementById('outcomeScopeNote');
    if (scopeNoteEl) {
        scopeNoteEl.textContent = pnlSource === 'all' ? '' : 'chart filtered · outcome split shows all coupons';
    }

    const filtered = couponsForSource(betsData.coupons, pnlSource);
    const group = pnlSource === 'real' ? bySrc.own : pnlSource === 'rec' ? bySrc.edge : null;
    const settledCount = group ? group.won + group.lost + group.void : filtered.filter(c => c.status !== 'pending').length;

    // Below 3 settled points a line chart is misleading noise -- show the raw
    // record instead. Only applies to the Real/Recommended subsets; All always
    // has enough history to chart.
    if (pnlSource !== 'all' && settledCount < 3) {
        if (roiChart) { roiChart.destroy(); roiChart = null; }
        chartBox.style.display = 'none';
        noteEl.style.display = '';
        const label = pnlSource === 'real' ? 'Real' : 'Recommended';
        noteEl.textContent = `${label}: ${settledCount} settled coupons · ${group.won}W–${group.lost}L · net ${group.net >= 0 ? '+' : ''}${group.net.toFixed(2)} PLN — too few for a trend line`;
        if (plMeta) { plMeta.textContent = ''; plMeta.className = ''; }
        renderOutcomeBar();
        return;
    }

    chartBox.style.display = '';
    noteEl.style.display = 'none';

    const roiCtx = document.getElementById('roiChart').getContext('2d');
    const points = buildPnlSeries(filtered);

    // Read theme colors from the CSS custom properties in styles.css (:root)
    // instead of hardcoding hex here -- Chart.js draws to canvas so it can't
    // pick up var(--edge) etc. on its own, but this way a palette change only
    // ever needs to happen in one place.
    const edgeColor = cssVar('--edge');
    const posFill = hexToRgba(cssVar('--pos'), 0.12);
    const negFill = hexToRgba(cssVar('--neg'), 0.12);

    if (roiChart) roiChart.destroy();
    roiChart = new Chart(roiCtx, {
        type: 'line',
        data: {
            datasets: [{
                data: points,
                borderColor: edgeColor,
                borderWidth: 2,
                tension: 0.25,
                fill: { target: 'origin', above: posFill, below: negFill },
                pointBackgroundColor: edgeColor,
                pointBorderColor: cssVar('--bg'),
                pointRadius: ctx => (ctx.raw && ctx.raw.ids && ctx.raw.ids.length ? 4 : 0),
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: items => items[0].raw.x,
                        label: item => {
                            const r = item.raw;
                            const lines = [
                                `Daily net: ${r.dayNet >= 0 ? '+' : ''}${r.dayNet.toFixed(2)} PLN`,
                                `Cumulative: ${r.y >= 0 ? '+' : ''}${r.y.toFixed(2)} PLN`
                            ];
                            if (r.ids && r.ids.length) lines.push(`Coupons: ${r.ids.join(', ')}`);
                            return lines;
                        }
                    }
                }
            },
            scales: {
                y: {
                    ticks: { color: '#a8abb3', font: { family: 'JetBrains Mono', size: 10 } },
                    grid: {
                        color: ctx => ctx.tick.value === 0 ? 'rgba(242,240,235,0.3)' : '#1c1e23',
                        lineWidth: ctx => ctx.tick.value === 0 ? 2 : 1
                    }
                },
                x: {
                    type: 'time',
                    time: { unit: 'day', tooltipFormat: 'yyyy-MM-dd', displayFormats: { day: 'MM-dd' } },
                    ticks: { color: '#a8abb3', font: { family: 'JetBrains Mono', size: 10 } },
                    grid: { display: false }
                }
            }
        }
    });

    if (plMeta) {
        const total = points.length ? points[points.length - 1].y : 0;
        plMeta.textContent = `total ${total >= 0 ? '+' : ''}${total.toFixed(2)} PLN`;
        plMeta.className = total >= 0 ? 'pos' : 'neg';
    }

    renderOutcomeBar();
}

function renderOutcomeBar() {
    const s = betsData.summary;
    const total = s.coupons || 1;

    const segments = [
        { label: 'Won', count: s.won, color: 'var(--pos)' },
        { label: 'Lost', count: s.lost, color: 'var(--neg)' },
        { label: 'Void', count: s.voided, color: 'var(--void)' },
        { label: 'Pending', count: s.pending, color: 'var(--ink-faint)' }
    ].filter(seg => seg.count > 0);

    document.getElementById('outcomeBar').innerHTML = segments.map(seg => {
        const pct = (seg.count / total) * 100;
        return `<div class="outcome-seg" style="width:${pct}%;background:${seg.color};" title="${seg.label}: ${seg.count} (${pct.toFixed(0)}%)"></div>`;
    }).join('');

    document.getElementById('outcomeLegend').innerHTML = segments.map(seg => {
        const pct = ((seg.count / total) * 100).toFixed(0);
        return `<div class="outcome-legend-item">
            <span class="outcome-dot" style="background:${seg.color};"></span>
            <span class="ol-label">${seg.label}</span>
            <span class="ol-count">${seg.count}</span>
            <span class="ol-pct">${pct}%</span>
        </div>`;
    }).join('');
}

// ===== Selections Performance =====

function renderSelectionsPerformance() {
    const el = document.getElementById('selBody');
    const countEl = document.getElementById('selCount');
    if (!el) return;

    const selections = getAllSelections(betsData);
    const stats = selectionStats(selections);
    if (countEl) countEl.textContent = `${stats.total} legs · ${stats.won + stats.lost} settled`;

    if (stats.total === 0) {
        el.innerHTML = '<div class="calib-note">No selections logged yet.</div>';
        return;
    }

    const oddsBuckets = selectionsByOddsBucket(selections).filter(b => b.n > 0);
    const qualifying = oddsBuckets.filter(b => b.n >= 2 && b.hitRate != null);
    const best = qualifying.length ? qualifying.reduce((a, b) => b.hitRate > a.hitRate ? b : a) : null;
    const worst = qualifying.length ? qualifying.reduce((a, b) => b.hitRate < a.hitRate ? b : a) : null;

    const oddsValues = selections.filter(s => typeof s.odds === 'number');
    const avgOdds = oddsValues.length ? oddsValues.reduce((s, x) => s + x.odds, 0) / oddsValues.length : null;

    const hrCls = stats.hitRate == null ? '' : (stats.hitRate >= 0.55 ? 'pos' : stats.hitRate < 0.45 ? 'neg' : '');
    const cards = [
        { label: 'Selection Hit Rate', info: 'selHitRate', value: stats.hitRate != null ? `${(stats.hitRate * 100).toFixed(0)}%` : '—', cls: hrCls, sub: `${stats.won}W – ${stats.lost}L on legs` },
        { label: 'Avg Leg Odds', info: 'avgOdds', value: avgOdds != null ? avgOdds.toFixed(2) : '—', cls: '', sub: 'across all logged legs' },
        { label: 'Best Bucket', info: 'bestWorst', value: best ? best.label : '—', cls: best ? 'pos' : '', sub: best ? `${(best.hitRate * 100).toFixed(0)}% hit rate (n=${best.n})` : 'not enough data (need n≥2)' },
        { label: 'Worst Bucket', info: 'bestWorst', value: worst ? worst.label : '—', cls: worst ? 'neg' : '', sub: worst ? `${(worst.hitRate * 100).toFixed(0)}% hit rate (n=${worst.n})` : 'not enough data (need n≥2)' }
    ];

    const cardsHTML = `<div class="kpi-row">${cards.map(k => `
        <div class="kpi ${k.cls}">
            <div class="kpi-label click" onclick="calibInfo('${k.info}')">${k.label}</div>
            <div class="kpi-value ${k.cls}">${k.value}</div>
            <div class="kpi-sub">${k.sub}</div>
        </div>`).join('')}</div>`;

    const hrCell = b => b.hitRate == null ? '—' : `<span class="${b.hitRate >= 0.5 ? 'pos' : 'neg'}">${(b.hitRate * 100).toFixed(0)}%</span>`;

    const oddsRows = oddsBuckets.map(b => `
        <tr><td>${b.label}</td><td>${b.n}</td><td>${b.won}–${b.lost}</td><td>${hrCell(b)}</td></tr>`).join('');

    const marketRows = selectionsByMarket(selections).map(m => `
        <tr><td>${m.label}</td><td>${m.n}</td><td>${m.won}–${m.lost}</td><td>${hrCell(m)}</td></tr>`).join('');

    el.innerHTML = `
        ${cardsHTML}
        <div class="perf-tables">
            <div>
                <div class="calib-sub click" onclick="calibInfo('oddsRange')">By odds range</div>
                <table class="calib-table compact">
                    <thead><tr><th>Range</th><th>n</th><th>W–L</th><th>Hit rate</th></tr></thead>
                    <tbody>${oddsRows}</tbody>
                </table>
            </div>
            <div>
                <div class="calib-sub click" onclick="calibInfo('byMarketTbl')">By market</div>
                <table class="calib-table compact">
                    <thead><tr><th>Market</th><th>n</th><th>W–L</th><th>Hit rate</th></tr></thead>
                    <tbody>${marketRows}</tbody>
                </table>
            </div>
        </div>`;
}

// ===== Bet Source =====
// Splits real-money coupons by how the bet came about (Edge's own BET call
// vs. the user's own judgement), so the two can eventually be compared once
// there's a meaningful sample -- see the small-sample note below.

function renderBetSource() {
    const el = document.getElementById('sourceBody');
    const countEl = document.getElementById('sourceCount');
    if (!el) return;

    const coupons = betsData.coupons || [];
    const by = couponsBySource(coupons);
    const total = by.edge.n + by.own.n + by.unknown.n;

    if (countEl) {
        countEl.textContent = `${total} coupons · ${by.edge.n} Edge / ${by.own.n} own`
            + (by.unknown.n > 0 ? ` · ${by.unknown.n} unknown` : '');
    }

    if (total === 0) {
        el.innerHTML = '<div class="calib-note">No coupons logged yet.</div>';
        return;
    }

    const fmtSigned = n => `${n >= 0 ? '+' : ''}${n.toFixed(2)} PLN`;

    const sourceCard = (label, infoKey, g, emptyNote) => {
        if (g.n === 0) {
            return `
                <div class="kpi">
                    <div class="kpi-label click" onclick="calibInfo('${infoKey}')">${label}</div>
                    <div class="kpi-value">—</div>
                    <div class="kpi-sub">${emptyNote}</div>
                </div>`;
        }
        const hitPct = g.hitRate != null ? `${(g.hitRate * 100).toFixed(0)}%` : '—';
        const roiPct = g.roi != null ? `${g.roi >= 0 ? '+' : ''}${(g.roi * 100).toFixed(0)}%` : '—';
        return `
            <div class="kpi">
                <div class="kpi-label click" onclick="calibInfo('${infoKey}')">${label}</div>
                <div class="kpi-value ${g.net >= 0 ? 'pos' : 'neg'}">${fmtSigned(g.net)}</div>
                <div class="kpi-sub">${g.won}W – ${g.lost}L · hit rate ${hitPct}</div>
                <div class="kpi-sub">ROI ${roiPct} · staked ${g.staked.toFixed(2)} PLN</div>
            </div>`;
    };

    // Edge (historical recommendations, closed group) vs Own. `unknown` only
    // surfaces once it has entries.
    const edgeCard = sourceCard('Edge (historyczne rekomendacje)', 'sourceEdge', by.edge, 'no coupons from Edge recommendations');
    const ownCard = sourceCard('Own bets', 'sourceOwn', by.own, 'no coupons from own bets yet');
    const hasUnknown = by.unknown.n > 0;
    const unknownCard = hasUnknown ? `
        <div class="kpi">
            <div class="kpi-label">Unsourced</div>
            <div class="kpi-value ${by.unknown.net >= 0 ? 'pos' : 'neg'}">${fmtSigned(by.unknown.net)}</div>
            <div class="kpi-sub">missing source field</div>
        </div>` : '';

    const sampleN = by.edge.n + by.own.n;
    const smallSampleNote = sampleN < 20
        ? '<div class="calib-note" style="margin-top:8px;">Sample too small for conclusions — this panel collects data, it does not compare performance yet.</div>'
        : '';

    el.innerHTML = `
        <div class="kpi-row ${hasUnknown ? 'cols-3' : 'cols-2'}">${edgeCard}${ownCard}${unknownCard}</div>
        <div class="calib-note" style="margin-top:14px;">Edge ${fmtSigned(by.edge.net)} (${by.edge.n} coupons) · Own ${fmtSigned(by.own.net)} (${by.own.n} coupons)</div>
        ${smallSampleNote}`;
}

