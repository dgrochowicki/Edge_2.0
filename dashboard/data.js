// Shared bets.json fetch — used by dashboard.js and logs.js.
const GITHUB_RAW_URL = 'https://raw.githubusercontent.com/dgrochowicki/Edge_2.0/main/data/bets.json';

function isLocalEnv() {
    return ['localhost', '127.0.0.1'].includes(location.hostname) || location.protocol === 'file:';
}

async function fetchBetsData() {
    if (isLocalEnv()) {
        // index.html lives at repo root; logs.html lives under dashboard/.
        const path = location.pathname.includes('/dashboard/') ? '../data/bets.json' : 'data/bets.json';
        try {
            const response = await fetch(path);
            return await response.json();
        } catch (err) {
            console.warn('Local bets.json fetch failed, falling back to GitHub raw:', err);
        }
    }
    const response = await fetch(GITHUB_RAW_URL);
    return response.json();
}
