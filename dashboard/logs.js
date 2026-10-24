let betsData = null;
let logsSource = 'all';

document.addEventListener('DOMContentLoaded', () => {
    loadBets();
    setupModalHandlers();
});

async function loadBets() {
    try {
        betsData = await fetchBetsData();
        renderLogs();

        const params = new URLSearchParams(window.location.search);
        const openId = params.get('open');
        if (openId && betsData.coupons.some(c => c.id === openId)) {
            showDetails(openId);
        }
    } catch (error) {
        console.error('Error loading bets:', error);
        document.getElementById('tableBody').innerHTML = '<tr><td colspan="9">Error loading data</td></tr>';
    }
}

function setSource(src) {
    logsSource = src;
    document.querySelectorAll('#sourceToggle .report-tab').forEach(el => {
        el.classList.toggle('active', el.dataset.src === src);
    });
    renderLogs();
}

function renderLogs() {
    renderSummaryRow();
    renderTable();
}

function renderSummaryRow() {
    const filtered = couponsForSource(betsData.coupons, logsSource);
    const bySrc = couponsBySource(filtered);
    const totals = aggregateCoupons(filtered);
    const roiPct = totals.roi != null ? (totals.roi * 100).toFixed(1) : '0.0';

    const kpis = [
        {
            label: 'Coupons', value: `${totals.n}`,
            sub: `${bySrc.own.n} real · ${bySrc.edge.n} rec`, cls: ''
        },
        {
            label: 'Record', value: `${totals.won}W – ${totals.lost}L – ${totals.pending}P`,
            sub: totals.void > 0 ? `${totals.void} void` : 'no voids', cls: ''
        },
        {
            label: 'Net', value: `${totals.net >= 0 ? '+' : ''}${totals.net.toFixed(2)} PLN`,
            sub: `${totals.staked.toFixed(2)} PLN staked`, cls: totals.net >= 0 ? 'pos' : 'neg'
        },
        {
            label: 'ROI', value: `${roiPct >= 0 ? '+' : ''}${roiPct}%`,
            sub: 'flat 1u stakes', cls: roiPct < 0 ? 'neg' : 'pos'
        }
    ];

    document.getElementById('logsSummaryRow').innerHTML = kpis.map(k => `
        <div class="kpi ${k.cls}">
            <div class="kpi-label">${k.label}</div>
            <div class="kpi-value ${k.cls}">${k.value}</div>
            <div class="kpi-sub">${k.sub}</div>
        </div>`).join('');
}

function sourceTag(c) {
    if (isUserBet(c.source)) return '<span class="source-tag">real</span>';
    if (isRecommendation(c.source)) return '<span class="source-tag rec">rec</span>';
    return '<span class="source-tag">—</span>';
}

function renderTable() {
    const tbody = document.getElementById('tableBody');
    const filtered = [...couponsForSource(betsData.coupons, logsSource)].reverse();

    tbody.innerHTML = filtered.map(c => {
        const legs = (c.selections || []).length;
        const type = c.type === 'single' ? 'single' : `acca · ${legs}`;
        const returnCls = c.gross_return_pln > c.stake_pln ? 'pos' : c.gross_return_pln === 0 ? 'neg' : '';
        return `<tr onclick="showDetails('${c.id}')">
            <td>${c.id}</td>
            <td>${c.date}</td>
            <td>${type}</td>
            <td>${sourceTag(c)}</td>
            <td class="num">${fmt(c.stake_pln)}</td>
            <td class="num">${c.combined_odds}</td>
            <td class="num ${returnCls}">${fmt(c.gross_return_pln)}</td>
            <td><span class="tag ${c.status}">${c.status}</span></td>
            <td class="view-link">VIEW &rarr;</td>
        </tr>`;
    }).join('');

    document.getElementById('couponCount').textContent = `${filtered.length} total`;
}
