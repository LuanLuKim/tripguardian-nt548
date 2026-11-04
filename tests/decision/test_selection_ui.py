"""Render selection components through the track's Vite server, without model calls."""

import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASE = os.environ.get('SELECTION_UI_URL', 'http://127.0.0.1:5186')
RAW = '0x317116dda7eb76c3:0x653f7aed2c2bff4e'


@pytest.fixture
def page():
    try:
        urlopen(BASE, timeout=3).close()
    except (OSError, URLError):
        pytest.skip('Start the web-a Vite server on :5186 for component browser tests')
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(ROOT / '.cache/ms-playwright/chromium-1169/chrome-linux/chrome'))
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('pageerror', lambda error: print('BROWSER ERROR', error))
        # Use real components; replace only the app entrypoint and network-backed providers.
        page.route('**/src/main.tsx*', lambda r: r.fulfill(content_type='text/javascript', body=''))
        page.route('**/src/user/pd/decision.tsx*', lambda r: r.fulfill(content_type='text/javascript', body='export const useDecision = () => window.selectionContext'))
        page.goto(BASE + '/app/explore')
        yield page
        browser.close()


def render(page, status='partial', preview='failed', chosen=True, saved=False):
    page.evaluate("""async ({status, preview, chosen, saved, raw}) => {
      const React = (await import('/node_modules/.vite/deps/react.js')).default;
      const {createRoot} = (await import('/node_modules/.vite/deps/react-dom_client.js')).default;
      const {SelectedBar} = await import('/src/user/ui/SelectedBar.tsx');
      const {PlaceCard} = await import('/src/user/ui/PlaceCard.tsx');
      const {setUi} = await import('/src/user/store.ts');
      for (const css of ['tokens', 'base', 'shell', 'tags', 'screens', 'explore', 'bar']) await import(`/src/user/css/${css}.css`);
      document.documentElement.classList.add('tg-scaled');
      document.getElementById('root').className = 'tg tg-app';
      setUi({saved: saved ? [raw] : []});
      const card = {id: raw, name: 'Đồi Chè Cầu Đất', chosen, status: 'main', location: {minutes: null}, confidence: {level: 'unknown', reason: ''}, why: [], failed: [], unverified: [], tradeoffs: [], warnings: [], checks: [], fit: {}};
      window.selectionContext = {
        view: {selected: [raw, 'place-2', 'place-3', 'place-4', 'place-5', 'unloaded-place'], locked: [], groups: [{cards: [card, ...['Hồ Xuân Hương', 'Dinh Bảo Đại', 'Thiền Viện Trúc Lâm', 'Đường Hầm Điêu Khắc'].map((name, i) => ({...card, id: `place-${i + 2}`, name}))]}], unverified: {cards: []},
          feasibility: {status, known_days: true, totals: {places: 6, visit: 500, travel: 120, available: 600},
            conflicts: [{id: 'far_areas', title: '3 khu cách xa cho 2 ngày', places: [raw], fixes: []}],
            warnings: ['Bạn đã chọn hơi nhiều nơi', 'Bỏ ' + raw]}},
        preview: {status: preview}, busy: false, diff: null, error: null,
        act: async () => true, toPlan: async () => true
      };
      createRoot(document.getElementById('root')).render(React.createElement(React.Fragment, null,
        React.createElement(SelectedBar), React.createElement('main', {className: 'tg-grid', style: {padding: '24px', paddingBottom: '120px'}}, window.selectionContext.view.groups[0].cards.map(c => React.createElement(PlaceCard, {key: c.id, c, onDrop: () => {}, cmp: false, onCmp: () => {}})))));
    }""", {'status': status, 'preview': preview, 'chosen': chosen, 'saved': saved, 'raw': RAW})
    page.get_by_role('region', name='Đã chọn', exact=True).wait_for()


@pytest.mark.parametrize('status,preview', [('partial', 'failed'), ('infeasible', 'blocked')])
def test_selection_does_not_nudge_or_claim_a_failed_plan_is_ready(page, status, preview):
    render(page, status, preview)
    bar = page.get_by_role('region', name='Đã chọn', exact=True)
    assert 'is-attention' not in bar.get_attribute('class')
    assert 'is-blocked' not in bar.get_attribute('class')
    assert 'Đi kịp' not in bar.inner_text()
    assert 'sẵn sàng' not in bar.inner_text()
    assert page.get_by_role('button', name='Lập lịch', exact=True).is_enabled()
    page.locator('.tg-bar__main').click()
    text = page.inner_text('body')
    assert 'hơi nhiều' not in text
    assert 'khu cách xa' not in text
    assert RAW not in text
    assert 'Đồi Chè Cầu Đất' in page.get_by_role('dialog').inner_text()
    if os.environ.get('SELECTION_UI_SHOTS'):
        shots = ROOT / '.superpowers/sdd/2026-11-03-prod-e2e/web-a/shots'
        shots.mkdir(exist_ok=True)
        page.screenshot(path=str(shots / f'{status}-selected-panel.png'), full_page=True)
        page.get_by_role('button', name='Thu gọn', exact=True).click()
        page.screenshot(path=str(shots / f'{status}-selection.png'), full_page=True)


@pytest.mark.parametrize('chosen', [False, True])
def test_save_is_distinct_from_select_and_does_not_deny_existing_selection(page, chosen):
    render(page, chosen=chosen, saved=True)
    save = page.locator('.tg-pc__save').first
    assert 'xem lại' in save.inner_text().lower()
    assert 'xem lại' in save.get_attribute('aria-label').lower()
    if chosen:
        assert 'chưa' not in save.get_attribute('title')
    else:
        assert page.get_by_role('button', name='Thêm vào chuyến', exact=True).first.is_visible()
