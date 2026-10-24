// Shared across index.html and dashboard/logs.html: pure coupon/selection
// aggregation helpers, the info modal, and the coupon-detail modal. Load
// this script before any page-specific script that calls into it.
// Coupons only -- predictions stay in the Edge archive (zlecenie A4).

function fmt(n, d = 2) { return Number(n).toFixed(d); }

// `report` paths on historical coupons point at files in the archived Edge
// repo (zlecenie A2), so links go to GitHub rather than a local page.
const EDGE_ARCHIVE_BLOB = 'https://github.com/dgrochowicki/Edge/blob/main/';
function reportHref(report) { return EDGE_ARCHIVE_BLOB + report; }

// ===== Selection-level metrics engine =====
// Pure functions, no DOM/rendering side effects. All aggregation is
// computed live from betsData; nothing here hardcodes a count.

// Flattens every coupon selection into one list.
function getAllSelections(betsData) {
    const selections = [];
    (betsData.coupons || []).forEach(c => {
        (c.selections || []).forEach(s => {
            selections.push({
                couponId: c.id,
                couponDate: c.date,
                couponStatus: c.status,
                match: s.match,
                market: s.market,
                pick: s.pick,
                odds: s.odds,
                result: s.result,
                notes: s.notes
            });
        });
    });
    return selections;
}

function selectionStats(selections) {
    const total = selections.length;
    const won = selections.filter(s => s.result === 'won').length;
    const lost = selections.filter(s => s.result === 'lost').length;
    const voided = selections.filter(s => s.result === 'void').length;
    const decided = won + lost;
    return { total, won, lost, void: voided, hitRate: decided > 0 ? won / decided : null };
}

const ODDS_BUCKETS = [
    { label: '< 1.30', min: 1, max: 1.30 },
    { label: '1.30–1.59', min: 1.30, max: 1.60 },
    { label: '1.60–1.99', min: 1.60, max: 2.00 },
    { label: '≥ 2.00', min: 2.00, max: Infinity }
];

function selectionsByOddsBucket(selections) {
    return ODDS_BUCKETS.map(b => {
        const inBucket = selections.filter(s => typeof s.odds === 'number' && s.odds >= b.min && s.odds < b.max);
        const stats = selectionStats(inBucket);
        const avgOdds = inBucket.length ? inBucket.reduce((sum, s) => sum + s.odds, 0) / inBucket.length : null;
        return { label: b.label, n: stats.total, won: stats.won, lost: stats.lost, hitRate: stats.hitRate, avgOdds };
    });
}

function groupSelectionsBy(selections, keyFn) {
    const groups = {};
    selections.forEach(s => {
        const key = keyFn(s);
        (groups[key] = groups[key] || []).push(s);
    });
    return Object.keys(groups).map(key => {
        const stats = selectionStats(groups[key]);
        return { label: key, n: stats.total, won: stats.won, lost: stats.lost, hitRate: stats.hitRate };
    });
}

function selectionsByMarket(selections) { return groupSelectionsBy(selections, s => s.market || 'unknown'); }

// Totals (stake/net/W-L-void-pending) for one already-filtered coupon list.
// Shared by couponsBySource's per-group buckets and any page that needs a
// plain summary over a coupon subset (e.g. logs.js's summary bar).
function aggregateCoupons(coupons) {
    const won = coupons.filter(c => c.status === 'won').length;
    const lost = coupons.filter(c => c.status === 'lost').length;
    const void_ = coupons.filter(c => c.status === 'void').length;
    const pending = coupons.filter(c => c.status === 'pending').length;
    const staked = coupons.reduce((s, c) => s + (c.stake_pln || 0), 0);
    const net = coupons.reduce((s, c) => s + (c.net_result_pln || 0), 0);
    return {
        n: coupons.length, won, lost, void: void_, pending, staked, net,
        roi: staked > 0 ? net / staked : null,
        hitRate: (won + lost) > 0 ? won / (won + lost) : null
    };
}

// Source classification. `source` on a coupon is either 'user_bet' or one
// of the historical Edge recommendation sources ('official_recommendation',
// 'recommendation_<agent>'). The agent split is not shown in Edge 2.0 --
// all of them count as "Edge (historyczne rekomendacje)". Every place that
// reads coupon.source goes through these -- no raw string comparisons elsewhere.
function isRecommendation(source) {
    return source === 'official_recommendation' || (typeof source === 'string' && source.startsWith('recommendation'));
}
function isUserBet(source) { return source === 'user_bet'; }
function sourceGroup(source) {
    if (isRecommendation(source)) return 'edge';
    if (isUserBet(source)) return 'own';
    return 'unknown';
}
// Human-readable source, for the modal and anywhere else showing it raw --
// never render the source string itself (it has underscores).
function sourceLabel(source) {
    if (isUserBet(source)) return 'own bet';
    if (isRecommendation(source)) return 'Edge rec (historical)';
    return source || '—';
}

// Splits coupons by how the bet came about: a historical Edge recommendation
// vs. a bet the user placed on their own judgement. Coupons with a missing
// or unrecognized `source` are kept as their own "unknown" group rather
// than dropped, so every coupon is still accounted for somewhere.
function couponsBySource(coupons) {
    const buckets = { edge: [], own: [], unknown: [] };
    (coupons || []).forEach(c => buckets[sourceGroup(c.source)].push(c));

    return { edge: aggregateCoupons(buckets.edge), own: aggregateCoupons(buckets.own), unknown: aggregateCoupons(buckets.unknown) };
}

// Which coupons pass the current All/Real/Recommended filter -- shared by
// dashboard.js's P&L chart and logs.js's coupon table.
function couponsForSource(coupons, src) {
    if (src === 'all') return coupons;
    const test = src === 'real' ? isUserBet : isRecommendation;
    return (coupons || []).filter(c => test(c.source));
}

// Info-modal texts for the KPI/section labels (click a label to open).
const CALIB_INFO = {
    selHitRate: ['Selection Hit Rate', 'Jaki procent pojedynczych typów (nóg) trafiasz. Liczone po nogach, nie po całych kuponach: kupon z 3 zdarzeń to 3 osobne nogi. Void nie liczy się do mianownika. To surowa trafność — mówi, jak często masz rację, ale NIE czy zarabiasz (do tego trzeba value i kursów).'],
    avgOdds: ['Avg Leg Odds', 'Średni kurs Twoich pojedynczych typów. Niski (bliżej 1.00) = grasz głównie faworytów. Wysoki = częściej sięgasz po niepewniaki. Sam w sobie nic nie ocenia — służy do czytania tabeli „wg zakresu kursu" obok: gdzie faktycznie masz wyczucie.'],
    bestWorst: ['Best / Worst Bucket', 'Automatyczne wskazanie przedziału kursu z najwyższą i najniższą trafnością (przy min. 2 zakładach). Skrót z tabeli obok: od razu widzisz swój najmocniejszy i najsłabszy rodzaj zakładu.'],
    oddsRange: ['Wg zakresu kursu', 'Twoje trafienia rozbite na przedziały kursu. Kluczowa diagnoza: może faworytów (kurs <1.30) trafiasz w 80%, ale niepewniaki (kurs ≥2.00) tylko w 30%. Pokazuje, w którym typie zakładów masz oko, a gdzie zgadujesz.'],
    byMarketTbl: ['Wg rynku', 'Trafienia w podziale na typ zakładu: zwycięzca meczu (moneyline), liczba map (over/under), handicap. Na razie prawie wszystko to moneyline, więc tabela ma jeden wiersz — rozrośnie się, gdy zaczniesz grać różne rynki.'],
    sourceEdge: ['Edge (historyczne rekomendacje)', 'Kupony zagrane zgodnie z rekomendacją z raportu starego Edge (v1–v3, lipiec–październik 2026) — metoda oznaczyła zakład jako BET i został on faktycznie postawiony. Grupa zamknięta: nowe kupony z rekomendacji nie powstają.'],
    sourceOwn: ['Own bets', 'Zakłady zagrane z własnej decyzji, niezależnie od tego, co mówił raport — także na mecze oznaczone jako PASS. Ta grupa mierzy Twoje własne typowanie. Rozdzielenie obu grup pozwoli po czasie zobaczyć, które decyzje wychodzą lepiej — ale dopiero przy sensownej liczbie kuponów, nie po kilku.'],
    netResult: ['Net Result', 'Suma wygranych minus suma przegranych, po wszystkich kuponach. Realny wynik w PLN przy stawkach faktycznie postawionych — to liczba, która ostatecznie się liczy, niezależnie od tego, jak wyglądały poszczególne zakłady po drodze.'],
    roi: ['ROI', 'Net Result podzielony przez sumę stawek. Pokazuje zwrot względem tego, ile realnie zaryzykowano — dwa identyczne Net Result przy różnych stawkach dają bardzo różne ROI. Liczone przy stałych stawkach 1u, więc porównanie między kuponami jest uczciwe.'],
    streak: ['Streak', 'Najdłuższa aktualna seria wygranych albo przegranych kuponów pod rząd, licząc od najnowszego. Void nie przerywa serii. To ciekawostka o formie, nie sygnał — krótkie serie w małej próbce są w dużej mierze losowe.']
};

function calibInfo(key) {
    const info = CALIB_INFO[key];
    if (!info) return;
    let ov = document.getElementById('calibModal');
    if (!ov) {
        ov = document.createElement('div');
        ov.id = 'calibModal';
        ov.className = 'calib-modal-overlay';
        ov.innerHTML = '<div class="calib-modal"><div class="calib-modal-head"><span id="calibModalTitle"></span><button class="calib-modal-x" onclick="document.getElementById(\'calibModal\').style.display=\'none\'">&times;</button></div><div id="calibModalBody"></div></div>';
        ov.addEventListener('click', e => { if (e.target === ov) ov.style.display = 'none'; });
        document.body.appendChild(ov);
    }
    document.getElementById('calibModalTitle').textContent = info[0];
    document.getElementById('calibModalBody').textContent = info[1];
    ov.style.display = 'flex';
}

// ===== Coupon detail modal =====

function showDetails(couponId) {
    const c = betsData.coupons.find(x => x.id === couponId);
    if (!c) return;

    document.getElementById('modalTitle').textContent = `${c.id} · ${c.date}`;

    let selectionsHTML = '';
    if (c.selections && Array.isArray(c.selections)) {
        selectionsHTML = c.selections.map(s => `
            <div class="selection">
                <div class="m">${s.match}</div>
                <div class="d">${s.market} — ${s.pick} @ ${s.odds}${s.final_score ? ` — ${s.final_score}` : ''} —
                    <span class="tag ${s.result}" style="padding:1px 5px;">${s.result}</span>
                </div>
                ${s.notes ? `<div class="note">${s.notes}</div>` : ''}
            </div>`).join('');
    }

    const reviewHTML = c.review ? `
        <div class="review-title">Review</div>
        <div class="review-box">
            <div class="kv"><span class="k">Decision quality</span><span class="v">${c.review.decision_quality}</span></div>
            <div style="margin-top:8px;"><span class="k">Lesson —</span> <span class="v">${c.review.main_lesson}</span></div>
        </div>` : '';

    document.getElementById('modalBody').innerHTML = `
        <div class="kv"><span class="k">Type</span><span class="v">${c.type}</span></div>
        <div class="kv"><span class="k">Source</span><span class="v">${sourceLabel(c.source)}</span></div>
        <div class="kv"><span class="k">Stake</span><span class="v">${fmt(c.stake_pln)} PLN</span></div>
        <div class="kv"><span class="k">Combined odds</span><span class="v">${c.combined_odds}</span></div>
        <div class="kv"><span class="k">Potential return</span><span class="v">${fmt(c.potential_return_pln, 2)} PLN</span></div>
        <div class="kv"><span class="k">Net result</span><span class="v">${fmt(c.net_result_pln, 2)} PLN</span></div>
        <div class="selections-title">Selections</div>
        ${selectionsHTML}
        ${reviewHTML}
        ${c.report ? `<div style="margin-top:16px;">
            <a href="${reportHref(c.report)}" target="_blank" rel="noopener" style="font-family:var(--font-mono);font-size:11px;color:var(--edge);text-decoration:none;">Raport w archiwum Edge →</a>
        </div>` : ''}
    `;

    document.getElementById('modal').style.display = 'flex';
}

function setupModalHandlers() {
    const modal = document.getElementById('modal');
    const closeBtn = document.getElementById('closeModal');

    closeBtn.onclick = () => { modal.style.display = 'none'; };
    modal.addEventListener('click', (event) => {
        if (event.target === modal) modal.style.display = 'none';
    });

    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        modal.style.display = 'none';
        const calibModal = document.getElementById('calibModal');
        if (calibModal) calibModal.style.display = 'none';
    });
}
