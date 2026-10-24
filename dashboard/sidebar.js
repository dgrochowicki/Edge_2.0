// Shared sidebar markup — avoids duplicating the brand/nav SVGs across
// index.html, dashboard/logs.html and dashboard/signals.html.

const SIDEBAR_ICONS = {
    brand: '<path d="M12.5021 3.31679L5.62356 1.16725C2.88437 0.311249 0.311249 2.88436 1.16725 5.62356L3.31678 12.5021C4.1143 15.0541 7.33676 15.847 9.2274 13.9564L13.9564 9.2274C15.847 7.33676 15.0541 4.1143 12.5021 3.31679Z" fill="currentColor"/>',
    dashboard: '<path d="M0.5 7.57422L0.499999 13C0.5 14.3807 1.61929 15.5 3 15.5L13 15.5L13.2559 15.4873C14.5164 15.3592 15.5 14.2943 15.5 13L15.5 7.57422C15.5 6.79345 15.135 6.05776 14.5137 5.58496L9.51367 1.78027C8.61921 1.09972 7.38079 1.09972 6.48633 1.78027L1.48633 5.58496C0.903726 6.02828 0.546162 6.70266 0.503906 7.42871L0.5 7.57422Z" stroke="currentColor"/>',
    signals: '<circle cx="8" cy="8" r="7.5" stroke="currentColor"/><circle cx="8" cy="8" r="0.5" stroke="currentColor"/><circle cx="8" cy="8" r="4" stroke="currentColor"/>',
    logs: '<path d="M0.5 3L0.5 3.35449C0.5 3.70759 0.576256 4.066 0.711914 4.41406C1.02578 5.21909 1.56641 6.77054 1.56641 8C1.56641 9.22946 1.02578 10.7809 0.711914 11.5859C0.576256 11.934 0.499999 12.2924 0.499999 12.6455L0.499999 13C0.499999 14.3807 1.61929 15.5 3 15.5L13 15.5C14.3807 15.5 15.5 14.3807 15.5 13L15.5 12.6455C15.5 12.2924 15.4237 11.934 15.2881 11.5859C14.9742 10.7809 14.4336 9.22946 14.4336 8C14.4336 6.77054 14.9742 5.21909 15.2881 4.41406C15.4237 4.066 15.5 3.70759 15.5 3.35449L15.5 3C15.5 1.61929 14.3807 0.500001 13 0.500001L3 0.5C1.61929 0.5 0.5 1.61929 0.5 3Z" stroke="currentColor"/>'
};

// index.html lives at repo root; logs/signals.html live under dashboard/
// and so share the same relative links to each other and home.
const SUBPAGE_LINKS = { home: '../index.html', dashboard: '../index.html', logs: 'logs.html', signals: 'signals.html' };
const SIDEBAR_LINKS = {
    dashboard: { home: 'index.html', dashboard: 'index.html', logs: 'dashboard/logs.html', signals: 'dashboard/signals.html' },
    logs: SUBPAGE_LINKS,
    signals: SUBPAGE_LINKS
};

const SIDEBAR_NAV = [
    ['dashboard', 'Dashboard'],
    ['logs', 'Logs'],
    ['signals', 'Signals']
];

function renderSidebar(page) {
    const links = SIDEBAR_LINKS[page];
    const nav = SIDEBAR_NAV.map(([key, title]) => `
        <a href="${links[key]}" class="navlink${page === key ? ' active' : ''}" title="${title}" aria-label="${title}">
            <svg class="nav-icon" width="18" height="18" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">${SIDEBAR_ICONS[key]}</svg>
        </a>`).join('');

    document.getElementById('sidebar-mount').outerHTML = `
<aside class="sidebar">
    <a href="${links.home}" class="brand" title="Edge">
        <svg class="blade-sm" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">${SIDEBAR_ICONS.brand}</svg>
    </a>
    <nav class="sidenav">${nav}
    </nav>
</aside>`;
}
