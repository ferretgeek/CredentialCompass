(() => {
  'use strict';

  const THEMES = {
    sky: { label: '天青', color: '#287f87', themeColor: '#f3f7f6' },
    jade: { label: '青玉', color: '#5f7f55', themeColor: '#f3f7f2' },
    sunset: { label: '夕照', color: '#b3674c', themeColor: '#faf5f1' },
    graphite: { label: '深灰', color: '#79b9bd', themeColor: '#17191d' },
  };
  const THEME_KEY = 'credential_compass_theme';
  const POLL_IDLE = 4000;
  const POLL_RUNNING = 850;

  let accessToken = '';
  let bootstrap = null;
  let state = null;
  let revealAccounts = false;
  let activeFilter = 'all';
  let searchTerm = '';
  let selected = new Set();
  let pollTimer = null;
  let pendingAction = null;

  const byId = (id) => document.getElementById(id);

  function applyTheme(theme) {
    const next = Object.hasOwn(THEMES, theme) ? theme : 'sky';
    const meta = THEMES[next];
    document.documentElement.dataset.theme = next;
    byId('themeLabel').textContent = meta.label;
    byId('themeSwatch').style.background = meta.color;
    document.querySelector('meta[name="theme-color"]').setAttribute('content', meta.themeColor);
    localStorage.setItem(THEME_KEY, next);
    document.querySelectorAll('[data-theme-option]').forEach((button) => {
      button.setAttribute('aria-current', button.dataset.themeOption === next ? 'true' : 'false');
    });
  }

  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const fallback = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'graphite' : 'sky';
    applyTheme(saved || fallback);
  }

  function toggleThemeMenu(force) {
    const menu = byId('themeMenu');
    const trigger = byId('themeTrigger');
    const open = typeof force === 'boolean' ? force : menu.hidden;
    menu.hidden = !open;
    trigger.setAttribute('aria-expanded', String(open));
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set('Authorization', `Bearer ${accessToken}`);
    if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    const response = await fetch(path, { ...options, headers, cache: 'no-store' });
    let payload = {};
    try { payload = await response.json(); } catch (_) { payload = {}; }
    if (!response.ok) {
      const error = new Error(payload?.error?.message || `Request failed (${response.status})`);
      error.status = response.status;
      error.code = payload?.error?.code || 'request_failed';
      throw error;
    }
    return payload;
  }

  function toast(message, tone = 'neutral') {
    const element = document.createElement('div');
    element.className = `toast ${tone}`;
    element.textContent = message;
    byId('toastRegion').appendChild(element);
    window.setTimeout(() => element.remove(), 4200);
  }

  function setConnection(connected) {
    const pill = byId('connectionPill');
    pill.className = `connection-pill ${connected ? 'connected' : 'failed'}`;
    pill.querySelector('span').textContent = connected ? '管理边界已连接' : '管理边界未连接';
  }

  function formatPercent(value) {
    if (value === null || value === undefined || value === '') return '—';
    return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1).replace('.0', '')}%` : '—';
  }

  function formatReset(value) {
    if (!value) return '未提供';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value).slice(0, 28);
    return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date);
  }

  function phaseLabel(phase) {
    return {
      idle: '等待开始', inventory: '整理凭证目录', probing: '观察健康信号', cancelling: '正在收束',
      cancelled: '已停止', complete: '盘点完成', error: '需要检查配置',
    }[phase] || '等待开始';
  }

  function visibleItems() {
    const items = Array.isArray(state?.items) ? state.items : [];
    return items.filter((item) => {
      if (activeFilter === 'healthy' && item.category !== 'healthy') return false;
      if (activeFilter === 'attention' && !['bad', 'warn'].includes(item.tone)) return false;
      if (activeFilter === 'disabled' && !item.disabled) return false;
      if (searchTerm && !String(item.account || '').toLowerCase().includes(searchTerm)) return false;
      return true;
    });
  }

  function quotaCell(item) {
    const wrapper = document.createElement('div');
    wrapper.className = 'quota-cell';
    const meta = document.createElement('div');
    meta.className = 'quota-meta';
    const plan = document.createElement('span');
    plan.textContent = item.quota?.plan ? item.quota.plan.toUpperCase() : '—';
    const percent = document.createElement('span');
    percent.textContent = formatPercent(item.quota?.used_percent);
    meta.append(plan, percent);
    const bar = document.createElement('div');
    bar.className = 'quota-bar';
    const fill = document.createElement('i');
    fill.style.width = `${Math.max(0, Math.min(100, Number(item.quota?.used_percent) || 0))}%`;
    bar.appendChild(fill);
    wrapper.append(meta, bar);
    return wrapper;
  }

  function renderRows() {
    const body = byId('resultBody');
    body.replaceChildren();
    const items = visibleItems();
    byId('emptyState').hidden = items.length > 0;
    for (const item of items) {
      const row = document.createElement('tr');
      const selectCell = document.createElement('td');
      selectCell.className = 'select-cell';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'row-check';
      checkbox.checked = selected.has(item.handle);
      checkbox.setAttribute('aria-label', `选择 ${item.account}`);
      checkbox.addEventListener('change', () => {
        checkbox.checked ? selected.add(item.handle) : selected.delete(item.handle);
        renderSelection();
      });
      selectCell.appendChild(checkbox);

      const accountCell = document.createElement('td');
      const account = document.createElement('div');
      account.className = 'account-cell';
      const strong = document.createElement('strong');
      strong.textContent = item.account;
      const small = document.createElement('small');
      small.textContent = item.disabled ? '当前不参与探测' : '由服务端生成匿名句柄';
      account.append(strong, small);
      accountCell.appendChild(account);

      const statusCell = document.createElement('td');
      const badge = document.createElement('span');
      badge.className = `status-badge ${item.tone || 'neutral'}`;
      badge.textContent = item.label || '状态待确认';
      statusCell.appendChild(badge);

      const quota = document.createElement('td');
      quota.appendChild(quotaCell(item));

      const reset = document.createElement('td');
      reset.className = 'reset-cell';
      reset.textContent = formatReset(item.quota?.resets_at);
      row.append(selectCell, accountCell, statusCell, quota, reset);
      body.appendChild(row);
    }
  }

  function renderSelection() {
    const validHandles = new Set((state?.items || []).map((item) => item.handle));
    selected = new Set([...selected].filter((item) => validHandles.has(item)));
    byId('selectedCount').textContent = String(selected.size);
    byId('selectionBar').hidden = selected.size === 0;
    const writable = Boolean(bootstrap?.status_changes);
    byId('enableSelected').disabled = !writable;
    byId('disableSelected').disabled = !writable;
  }

  function renderEvents() {
    const list = byId('eventList');
    list.replaceChildren();
    const events = Array.isArray(state?.events) ? state.events.slice().reverse() : [];
    if (!events.length) {
      const empty = document.createElement('li');
      empty.className = 'empty-event';
      empty.append(document.createElement('i'));
      const text = document.createElement('span');
      text.textContent = '等待第一项经过脱敏的事件';
      empty.appendChild(text);
      list.appendChild(empty);
      return;
    }
    for (const event of events.slice(0, 5)) {
      const item = document.createElement('li');
      item.className = event.tone || 'neutral';
      const time = document.createElement('time');
      time.textContent = event.time || '—';
      const dot = document.createElement('i');
      const message = document.createElement('span');
      message.textContent = event.message || '事件已完成';
      item.append(time, dot, message);
      list.appendChild(item);
    }
  }

  function renderState() {
    if (!state) return;
    const summary = state.summary || {};
    byId('metricTotal').textContent = String(summary.total ?? 0);
    byId('metricHealthy').textContent = String(summary.healthy ?? 0);
    byId('metricAttention').textContent = String(summary.attention ?? 0);
    byId('metricQuota').textContent = formatPercent(summary.average_used_percent);
    byId('countAll').textContent = String(summary.total ?? 0);
    byId('countHealthy').textContent = String(summary.healthy ?? 0);
    byId('countAttention').textContent = String(summary.attention ?? 0);
    byId('countDisabled').textContent = String(summary.disabled ?? 0);
    byId('scanPhase').textContent = phaseLabel(state.phase);
    byId('scanPercent').textContent = `${Number(state.percent || 0).toFixed(0)}%`;
    byId('scanProgress').style.width = `${Math.max(0, Math.min(100, Number(state.percent) || 0))}%`;
    byId('scanCaption').textContent = state.running
      ? `已完成 ${state.completed}/${state.total}，用时 ${state.elapsed_seconds.toFixed(1)} 秒`
      : (state.error || '凭证不会离开服务器内存。');
    byId('scanStatusDot').className = `status-dot ${state.running ? 'running' : ''}`;
    byId('scanStart').disabled = state.running;
    byId('scanCancel').disabled = !state.running;
    renderRows();
    renderSelection();
    renderEvents();
  }

  async function refreshState() {
    window.clearTimeout(pollTimer);
    try {
      state = await api(`/api/state?reveal=${revealAccounts ? '1' : '0'}`);
      renderState();
      if (state.error) toast(state.error, 'bad');
    } catch (error) {
      if (error.status === 401) {
        accessToken = '';
        byId('appShell').hidden = true;
        byId('accessError').textContent = '访问令牌已失效，请重新输入。';
        byId('accessDialog').showModal();
        return;
      }
      toast('暂时无法刷新航图', 'bad');
    }
    pollTimer = window.setTimeout(refreshState, state?.running ? POLL_RUNNING : POLL_IDLE);
  }

  async function openApp(token) {
    accessToken = token;
    bootstrap = await api('/api/bootstrap');
    state = await api('/api/state?reveal=0');
    byId('versionLabel').textContent = `v${bootstrap.version}`;
    byId('probeLabel').textContent = bootstrap.live_probe ? '兼容探测开启' : '静态盘点';
    byId('modeLabel').textContent = bootstrap.demo ? 'SYNTHETIC DEMO · 合成演示' : 'PRIVATE OBSERVATORY · 私密观察站';
    byId('modeBadge').textContent = bootstrap.demo ? '保留示例数据' : '本地边界';
    byId('scanConcurrency').value = String(bootstrap.default_concurrency || 4);
    byId('scanLimit').max = String(bootstrap.max_accounts || 1000);
    byId('appShell').hidden = false;
    byId('accessDialog').close();
    renderState();
    refreshState();
    try { setConnection((await api('/api/connection')).connected); } catch (_) { setConnection(false); }
  }

  async function startScan() {
    const concurrency = Number.parseInt(byId('scanConcurrency').value, 10);
    const limit = Number.parseInt(byId('scanLimit').value, 10);
    try {
      await api('/api/scan', { method: 'POST', body: JSON.stringify({ concurrency, limit }) });
      toast('巡航已经开始', 'good');
      await refreshState();
    } catch (error) { toast(error.message, 'bad'); }
  }

  async function cancelScan() {
    try {
      await api('/api/scan/cancel', { method: 'POST', body: '{}' });
      toast('正在安全停止');
      await refreshState();
    } catch (error) { toast(error.message, 'bad'); }
  }

  function requestStatusChange(action) {
    if (!selected.size) return;
    const count = selected.size;
    const phrase = `${action.toUpperCase()} ${count}`;
    pendingAction = { action, handles: [...selected], phrase };
    byId('confirmTitle').textContent = action === 'disable' ? `安全停用 ${count} 枚凭证` : `恢复启用 ${count} 枚凭证`;
    byId('confirmCopy').textContent = action === 'disable'
      ? '停用是可逆操作。完成后请重新盘点，确认凭证池仍符合预期。'
      : '恢复后凭证会重新参与服务；建议随即执行一次低并发盘点。';
    byId('confirmHint').textContent = `请输入：${phrase}`;
    byId('confirmInput').value = '';
    byId('confirmDialog').showModal();
    byId('confirmInput').focus();
  }

  async function submitStatusChange() {
    if (!pendingAction) return;
    const action = pendingAction;
    if (byId('confirmInput').value !== action.phrase) {
      byId('confirmHint').textContent = `短语不一致，请输入：${action.phrase}`;
      return;
    }
    try {
      const result = await api('/api/credentials/status', {
        method: 'POST',
        body: JSON.stringify({ action: action.action, handles: action.handles, confirmation: action.phrase }),
      });
      toast(`完成 ${result.changed}/${result.matched} 项状态变更`, result.failed ? 'bad' : 'good');
      selected.clear();
      byId('confirmDialog').close();
      await refreshState();
    } catch (error) { byId('confirmHint').textContent = error.message; }
  }

  function bindEvents() {
    byId('themeTrigger').addEventListener('click', () => toggleThemeMenu());
    document.querySelectorAll('[data-theme-option]').forEach((button) => button.addEventListener('click', () => {
      applyTheme(button.dataset.themeOption);
      toggleThemeMenu(false);
    }));
    document.addEventListener('click', (event) => {
      if (!event.target.closest('.theme-control')) toggleThemeMenu(false);
    });
    byId('tokenReveal').addEventListener('click', () => {
      const input = byId('accessToken');
      const reveal = input.type === 'password';
      input.type = reveal ? 'text' : 'password';
      byId('tokenReveal').setAttribute('aria-pressed', String(reveal));
    });
    byId('accessForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      byId('accessError').textContent = '';
      const token = byId('accessToken').value;
      try {
        await openApp(token);
        byId('accessToken').value = '';
      } catch (error) {
        accessToken = '';
        byId('accessError').textContent = error.status === 401 ? '访问令牌不正确。' : '暂时无法进入，请检查本地服务。';
      }
    });
    byId('privacyToggle').addEventListener('click', async () => {
      revealAccounts = !revealAccounts;
      byId('privacyToggle').setAttribute('aria-pressed', String(revealAccounts));
      byId('privacyToggle').querySelector('span').textContent = revealAccounts ? '已揭开' : '隐私帘';
      await refreshState();
    });
    byId('scanStart').addEventListener('click', startScan);
    byId('scanCancel').addEventListener('click', cancelScan);
    byId('searchInput').addEventListener('input', (event) => { searchTerm = event.target.value.trim().toLowerCase(); renderRows(); });
    document.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => {
      activeFilter = button.dataset.filter;
      document.querySelectorAll('[data-filter]').forEach((item) => item.classList.toggle('active', item === button));
      renderRows();
    }));
    byId('clearSelection').addEventListener('click', () => { selected.clear(); renderRows(); renderSelection(); });
    byId('disableSelected').addEventListener('click', () => requestStatusChange('disable'));
    byId('enableSelected').addEventListener('click', () => requestStatusChange('enable'));
    byId('confirmForm').addEventListener('submit', (event) => {
      if (event.submitter?.value === 'cancel') return;
      event.preventDefault();
      submitStatusChange();
    });
  }

  initTheme();
  bindEvents();
  byId('accessDialog').showModal();
})();
