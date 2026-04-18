/* ── 1. Search tabs ──────────────────────────────────────────────────── */

/*
 * Configuration for each search type tab on the home page.
 * Each entry defines what placeholder text and hint to show, and how to
 * build the destination URL when the user submits the form.
 */
const TAB_CONFIG = {
    ip: {
        placeholder: '8.8.8.8  or  2001:4860::',
        hint:        'Geolocate an IP address (IPv4 or IPv6)',
        route:       q => '/ip/' + encodeURIComponent(q),
    },
    asn: {
        placeholder: 'AS15169  or  15169',
        hint:        'Look up an autonomous system and its network prefixes',
        route:       q => '/asn/' + encodeURIComponent(q.replace(/^as/i, '')),
    },
    cidr: {
        placeholder: '192.168.0.0/24  or  2001:db8::/32',
        hint:        'Inspect a network prefix — addresses, mask, hosts',
        route:       q => '/cidr/' + encodeURIComponent(q),
    },
    country: {
        placeholder: 'US  or  United States',
        hint:        "Browse all IP ranges registered in a country",
        route:       q => '/country-search?q=' + encodeURIComponent(q),
    },
    'multi-country': {
        placeholder: 'US, DE, FR',
        hint:        'Find autonomous systems that span all listed countries',
        route:       q => '/multi-country?q=' + encodeURIComponent(q),
    },
    org: {
        placeholder: 'Cloudflare  or  Amazon',
        hint:        'Search by organization name across all ASes',
        route:       q => '/search?q=' + encodeURIComponent(q),
    },
};

/* Track the active tab type so the form submit handler knows where to route. */
let activeTabType = 'ip';

/*
 * Called when a tab button is clicked.
 * Updates the active styling, placeholder text, and hint text.
 */
function setTab(type) {
    activeTabType = type;

    /* Update button states */
    document.querySelectorAll('.search-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.type === type);
    });

    /* Update input placeholder and hint text */
    const config = TAB_CONFIG[type];
    if (!config) return;

    const input = document.getElementById('main-search');
    const hint  = document.getElementById('search-hint');

    if (input) input.placeholder = config.placeholder;
    if (hint)  hint.textContent  = config.hint;

    if (input) input.focus();
}

/*
 * Called when the search form is submitted.
 * Reads the active tab to determine the destination URL.
 */
function goSearch(e) {
    e.preventDefault();
    const input = document.getElementById('main-search');
    if (!input) return;
    const q = input.value.trim();
    if (!q) return;

    const config = TAB_CONFIG[activeTabType];
    if (config) window.location.href = config.route(q);
}


/* ── 2. Navigation utility ───────────────────────────────────────────── */

/*
 * Goes back in browser history if there is history to go back to,
 * otherwise falls back to the home page.
 */
function goBack() {
    if (window.history.length > 1) {
        window.history.back();
    } else {
        window.location.href = '/';
    }
}


/* ── 3. Page initialisation ──────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', function () {

    /* Set the initial placeholder and hint for the first tab on the home page. */
    const firstTab = document.querySelector('.search-tab.active');
    if (firstTab) {
        setTab(firstTab.dataset.type || 'ip');
    }

    /* Auto-focus the main search input if one exists on this page. */
    const mainSearch = document.getElementById('main-search');
    if (mainSearch) mainSearch.focus();

});
