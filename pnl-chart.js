// pnl-chart.js — 门户静态收益曲线图 (Canvas 2D, 零依赖)
// 数据来自 index.html 中嵌入的 PNL_DATA (sync_pnl_data.py 同步)

(function () {
  'use strict';

  var COLORS = {
    bg: '#FFFFFF',
    grid: '#F0EEEC',
    zero: '#D1CFC5',
    text: '#2D2926',
    text2: '#5C5652',
    text3: '#8A8480',
    red: '#DC2626',
    green: '#059669',
    accent: '#D97706',
    accentBg: 'rgba(217,119,6,0.08)',
    fillTop: 'rgba(220,38,38,0.12)',
    fillBot: 'rgba(220,38,38,0.01)',
  };

  var state = {
    period: 'all', // today | week | month | quarter | year | all
    drawerOpen: false,
  };

  // ── Period helpers ──
  function dateKey(d) { return d.date || d; }
  function parseDate(s) { var p = s.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }

  function filterByPeriod(daily) {
    if (!daily || !daily.length) return [];
    var now = new Date();
    var since = null;
    switch (state.period) {
      case 'today': since = new Date(now.getFullYear(), now.getMonth(), now.getDate()); break;
      case 'week':
        var d = new Date(now);
        d.setDate(d.getDate() - ((d.getDay() || 7) - 1));
        since = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        break;
      case 'month': since = new Date(now.getFullYear(), now.getMonth(), 1); break;
      case 'quarter':
        var m = now.getMonth() - 3;
        since = new Date(now.getFullYear(), m < 0 ? m + 12 : m, now.getDate());
        break;
      case 'year': since = new Date(now.getFullYear(), 0, 1); break;
      default: since = null;
    }
    if (!since) return daily.slice();
    return daily.filter(function (d) { return parseDate(dateKey(d)) >= since; });
  }

  // TWR chain: daily pnl_pct → cumulative portfolio %
  function buildPortfolio(daily) {
    var cum = 1.0;
    return daily.map(function (d) { cum *= (1 + (d.pnl_pct || 0) / 100); return parseFloat(((cum - 1) * 100).toFixed(4)); });
  }

  // ── Max drawdown ──
  function calcDD(portfolio) {
    if (!portfolio || portfolio.length < 2) return null;
    var bestPeak = { idx: 0, val: portfolio[0] };
    var worst = { dd: 0, peak: null, trough: null };
    for (var i = 1; i < portfolio.length; i++) {
      if (portfolio[i] > bestPeak.val) bestPeak = { idx: i, val: portfolio[i] };
      var dd = portfolio[i] - bestPeak.val;
      if (dd < worst.dd) worst = { dd: Math.round(dd * 100) / 100, peak: { idx: bestPeak.idx, val: bestPeak.val }, trough: { idx: i, val: portfolio[i] } };
    }
    return worst.dd < 0 ? worst : null;
  }

  // ── Draw chart ──
  function drawChart() {
    var canvas = document.getElementById('pnl-canvas');
    if (!canvas) return;
    var rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    var W = rect.width, H = rect.height;
    var DPR = window.devicePixelRatio || 1;
    canvas.width = W * DPR;
    canvas.height = H * DPR;
    var ctx = canvas.getContext('2d');
    ctx.scale(DPR, DPR);

    var daily = filterByPeriod(window.PNL_DAILY || []);
    if (daily.length < 2) {
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = COLORS.bg;
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = COLORS.text3;
      ctx.font = '13px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('暂无数据', W / 2, H / 2);
      return;
    }
    var portfolio = buildPortfolio(daily);
    var dates = daily.map(function (d) { return d.date; });
    var ddInfo = calcDD(portfolio);
    var n = portfolio.length;

    var PAD = { t: 24, r: 70, b: 34, l: 62 };
    var cw = W - PAD.l - PAD.r;
    var ch = H - PAD.t - PAD.b;
    if (cw < 50 || ch < 20) return;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, W, H);

    var absMax = Math.max(Math.abs(Math.min.apply(null, portfolio)), Math.abs(Math.max.apply(null, portfolio)));
    var step = absMax < 2 ? 0.5 : absMax < 5 ? 1 : absMax < 10 ? 2 : 5;
    var maxY = Math.ceil(absMax / step) * step;
    var minY = -maxY;

    function yVal(v) { return PAD.t + ch - ((v - minY) / (maxY - minY)) * ch; }
    function xVal(i) { return PAD.l + (i / (n - 1)) * cw; }

    // Grid lines
    ctx.fillStyle = COLORS.text3;
    ctx.font = '10px system-ui';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    var gridSteps = [minY, minY / 2, 0, maxY / 2, maxY];
    for (var gi = 0; gi < gridSteps.length; gi++) {
      var gy = yVal(gridSteps[gi]);
      ctx.strokeStyle = gridSteps[gi] === 0 ? COLORS.zero : COLORS.grid;
      ctx.lineWidth = gridSteps[gi] === 0 ? 1.2 : 0.5;
      ctx.beginPath();
      ctx.moveTo(PAD.l, gy);
      ctx.lineTo(W - PAD.r + 8, gy);
      ctx.stroke();
      ctx.fillText((gridSteps[gi] >= 0 ? '+' : '') + gridSteps[gi].toFixed(1) + '%', PAD.l - 8, gy);
    }

    // X-axis labels
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    var labelStep = n <= 10 ? 1 : n <= 30 ? Math.ceil(n / 8) : Math.ceil(n / 10);
    for (var xi = 0; xi < n; xi += labelStep) {
      ctx.fillText(dates[xi].slice(5), xVal(xi), PAD.t + ch + 6);
    }
    // last label
    if ((n - 1) % labelStep > labelStep / 2) {
      ctx.fillText(dates[n - 1].slice(5), xVal(n - 1), PAD.t + ch + 6);
    }

    // Area fill
    var zy = yVal(0);
    for (var si = 0; si < n; si++) {
      if (portfolio[si] == null) continue;
      ctx.beginPath();
      ctx.moveTo(xVal(si), zy);
      ctx.lineTo(xVal(si), yVal(portfolio[si]));
      var se = si;
      while (se + 1 < n && portfolio[se + 1] != null) se++;
      for (var j = si + 1; j <= se; j++) ctx.lineTo(xVal(j), yVal(portfolio[j]));
      ctx.lineTo(xVal(se), zy);
      ctx.closePath();
      var grad = ctx.createLinearGradient(0, PAD.t, 0, PAD.t + ch);
      grad.addColorStop(0, COLORS.fillTop);
      grad.addColorStop(1, COLORS.fillBot);
      ctx.fillStyle = grad;
      ctx.fill();
      si = se;
    }

    // Portfolio line
    ctx.beginPath();
    var started = false;
    for (var i = 0; i < n; i++) {
      if (portfolio[i] == null) { started = false; continue; }
      if (!started) { ctx.moveTo(xVal(i), yVal(portfolio[i])); started = true; }
      else ctx.lineTo(xVal(i), yVal(portfolio[i]));
    }
    ctx.strokeStyle = COLORS.red;
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // End label
    var lastI = n - 1;
    while (lastI >= 0 && portfolio[lastI] == null) lastI--;
    if (lastI >= 0) {
      var lx = xVal(lastI), ly = yVal(portfolio[lastI]);
      ctx.fillStyle = COLORS.red;
      ctx.font = '600 12px system-ui';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText((portfolio[lastI] >= 0 ? '+' : '') + portfolio[lastI].toFixed(2) + '%', lx + 6, ly);
    }

    // Max drawdown
    if (ddInfo && ddInfo.peak && ddInfo.trough) {
      var peakX = xVal(ddInfo.peak.idx), peakY = yVal(ddInfo.peak.val);
      var troughX = xVal(ddInfo.trough.idx), troughY = yVal(ddInfo.trough.val);

      // Peak dot
      ctx.beginPath();
      ctx.arc(peakX, peakY, 5, 0, Math.PI * 2);
      ctx.fillStyle = COLORS.accent;
      ctx.fill();
      ctx.strokeStyle = '#FFF';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Trough dot
      ctx.beginPath();
      ctx.arc(troughX, troughY, 5, 0, Math.PI * 2);
      ctx.fillStyle = COLORS.accent;
      ctx.fill();
      ctx.strokeStyle = '#FFF';
      ctx.lineWidth = 2;
      ctx.stroke();

      // L-shaped dashed line
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.strokeStyle = 'rgba(217,119,6,0.5)';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(peakX, peakY);
      ctx.lineTo(troughX, peakY);
      ctx.lineTo(troughX, troughY);
      ctx.stroke();
      ctx.setLineDash([]);

      var ddText = '最大回撤 ' + ddInfo.dd.toFixed(2) + '%';
      ctx.font = '11px system-ui';
      var ddTX = troughX + 8;
      var ddTY = troughY;
      var tm = ctx.measureText(ddText);
      if (ddTX + tm.width > W - 10) ddTX = troughX - tm.width - 8;
      ctx.fillStyle = COLORS.accent;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(ddText, ddTX, ddTY);
    }

    // Store for crosshair
    canvas._chartData = { portfolio: portfolio, dates: dates, xVal: xVal, yVal: yVal, n: n, PAD: PAD, W: W, H: H };
  }

  // ── Crosshair + tooltip ──
  function initCrosshair() {
    var canvas = document.getElementById('pnl-canvas');
    if (!canvas) return;
    var wrap = canvas.parentElement;
    var ch = document.createElement('div');
    ch.id = 'pnl-crosshair';
    ch.style.cssText = 'position:absolute;top:0;width:1px;background:#D97706;opacity:0.6;pointer-events:none;display:none;z-index:2';
    wrap.appendChild(ch);
    var tip = document.createElement('div');
    tip.id = 'pnl-tooltip';
    tip.style.cssText =
      'position:fixed;z-index:9999;background:#FFF;border:1px solid #E5E2DE;border-radius:8px;padding:8px 12px;font-size:12px;line-height:1.6;color:#2D2926;pointer-events:none;display:none;box-shadow:0 2px 12px rgba(0,0,0,.1)';
    document.body.appendChild(tip);

    canvas.addEventListener('mousemove', function (e) {
      var cd = canvas._chartData;
      if (!cd) { ch.style.display = 'none'; tip.style.display = 'none'; return; }
      var rect = canvas.getBoundingClientRect();
      var mx = e.clientX - rect.left;
      if (mx < cd.PAD.l || mx > cd.W - cd.PAD.r) { ch.style.display = 'none'; tip.style.display = 'none'; return; }
      var idx = Math.round(((mx - cd.PAD.l) / (cd.W - cd.PAD.l - cd.PAD.r)) * (cd.n - 1));
      idx = Math.max(0, Math.min(cd.n - 1, idx));
      var cx = cd.xVal(idx);
      ch.style.left = cx + 'px';
      ch.style.height = (cd.H) + 'px';
      ch.style.display = 'block';

      var v = cd.portfolio[idx];
      var date = cd.dates[idx];
      tip.innerHTML =
        '<div style="font-weight:600;margin-bottom:2px">' + date + '</div>' +
        '<div>收益 <span style="color:' + (v >= 0 ? COLORS.red : COLORS.green) + ';font-weight:600">' + (v >= 0 ? '+' : '') + v.toFixed(2) + '%</span></div>';
      tip.style.display = 'block';
      tip.style.left = (e.clientX + 14) + 'px';
      tip.style.top = (e.clientY - 10) + 'px';
    });
    canvas.addEventListener('mouseleave', function () { ch.style.display = 'none'; tip.style.display = 'none'; });
  }

  // ── Update KPI cards ──
  function updateKPI() {
    var daily = window.PNL_DAILY || [];
    var meta = window.PNL_META || {};
    var totalDeposit = meta.total_deposit || 200000;

    // 当前资产
    var lastTotal = daily.length ? daily[daily.length - 1].total : 0;
    document.getElementById('pnl-k-asset').textContent = lastTotal ? lastTotal.toLocaleString() : '—';
    document.getElementById('pnl-k-asset-sub').textContent = '累计入金 ' + totalDeposit.toLocaleString();

    // TWR 累计
    var cumP = 1;
    var pk = 0, maxDD = 0;
    for (var i = 0; i < daily.length; i++) {
      cumP *= (1 + (daily[i].pnl_pct || 0) / 100);
      var rp = (cumP - 1) * 100;
      if (rp > pk) pk = rp;
      if (rp - pk < maxDD) maxDD = rp - pk;
    }
    var twr = (cumP - 1) * 100;
    var el = document.getElementById('pnl-k-twr');
    el.textContent = (twr >= 0 ? '+' : '') + twr.toFixed(2) + '%';
    el.style.color = twr >= 0 ? COLORS.red : COLORS.green;

    // 年内最高
    document.getElementById('pnl-k-high').textContent = (pk >= 0 ? '+' : '') + pk.toFixed(2) + '%';
    document.getElementById('pnl-k-high').style.color = pk >= 0 ? COLORS.red : COLORS.green;

    // 年内最低回撤
    document.getElementById('pnl-k-dd').textContent = maxDD.toFixed(2) + '%';
    document.getElementById('pnl-k-dd').style.color = COLORS.green;

    // Period KPI
    updatePeriodKPI(daily);
  }

  function updatePeriodKPI(daily) {
    var filtered = filterByPeriod(daily);
    var port = buildPortfolio(filtered);
    var lastV = port.length ? port[port.length - 1] : 0;
    var el = document.getElementById('pnl-k-period');
    el.textContent = (lastV >= 0 ? '+' : '') + lastV.toFixed(2) + '%';
    el.style.color = lastV >= 0 ? COLORS.red : COLORS.green;

    var dd = calcDD(port);
    document.getElementById('pnl-k-pdd').textContent = (dd ? dd.dd : '0.00') + '%';
    document.getElementById('pnl-k-pdd').style.color = COLORS.green;

    // Period label
    var labels = { today: '今日', week: '本周', month: '本月', quarter: '近三月', year: '今年', all: '累计' };
    document.getElementById('pnl-k-period-label').textContent = (labels[state.period] || state.period) + ' TWR';
  }

  // ── Drawer ──
  function updateDrawer() {
    var daily = window.PNL_DAILY || [];
    if (!daily.length) return;
    var now = new Date();
    var periods = [
      { key: 'today', label: '日', since: new Date(now.getFullYear(), now.getMonth(), now.getDate()) },
      { key: 'week', label: '近一周', since: new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() || 7) - 1)) },
      { key: 'month', label: '近一月', since: new Date(now.getFullYear(), now.getMonth(), 1) },
      { key: 'quarter', label: '近三月', since: new Date(now.getFullYear(), now.getMonth() - 3, now.getDate()) },
      { key: 'year', label: '近一年', since: new Date(now.getFullYear(), 0, 1) },
    ];
    var tbody = document.getElementById('pnl-drawer-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    var allP = buildPortfolio(daily);
    var allDD = calcDD(allP);
    var cumAll = 1;
    daily.forEach(function (d) { cumAll *= (1 + (d.pnl_pct || 0) / 100); });

    periods.forEach(function (per) {
      var fd = daily.filter(function (d) { return parseDate(d.date) >= per.since; });
      var p = buildPortfolio(fd);
      var lastV = p.length ? p[p.length - 1] : 0;
      var dd = calcDD(p);
      var row = '<tr>' +
        '<td class="pnl-td-period">' + per.label + '</td>' +
        '<td class="pnl-td-num" style="color:' + (lastV >= 0 ? COLORS.red : COLORS.green) + '">' + (lastV >= 0 ? '+' : '') + lastV.toFixed(2) + '%</td>' +
        '<td class="pnl-td-num">—</td>' +
        '<td class="pnl-td-num">—</td>' +
        '<td class="pnl-td-num" style="color:' + COLORS.green + '">' + (dd ? dd.dd.toFixed(2) : '0.00') + '%</td>' +
        '</tr>';
      tbody.innerHTML += row;
    });

    // 累计 row
    var cumRow = '<tr class="pnl-cum-row"><td class="pnl-td-period">累计</td>' +
      '<td class="pnl-td-num pnl-td-bold" style="color:' + ((cumAll - 1) * 100 >= 0 ? COLORS.red : COLORS.green) + '">' + ((cumAll - 1) * 100 >= 0 ? '+' : '') + ((cumAll - 1) * 100).toFixed(2) + '%</td>' +
      '<td class="pnl-td-num pnl-td-bold">—</td>' +
      '<td class="pnl-td-num pnl-td-bold">—</td>' +
      '<td class="pnl-td-num pnl-td-bold" style="color:' + COLORS.green + '">' + (allDD ? allDD.dd.toFixed(2) : '0.00') + '%</td></tr>';
    tbody.innerHTML += cumRow;
  }

  // ── Init ──
  function init() {
    if (!window.PNL_DATA) return;
    // Flatten data
    window.PNL_DAILY = window.PNL_DATA.daily || [];
    window.PNL_META = window.PNL_DATA.meta || {};

    // Build DOM (target element must exist in HTML)
    var container = document.getElementById('pnl-section');
    if (!container) return;
    var parts = document.getElementById('pnl-meta-parts');
    if (parts) {
      var ts = window.PNL_META.updated || window.PNL_META.last_updated || '';
      parts.textContent = '数据截止 ' + ts.slice(0, 10);
    }
    if (document.getElementById('pnl-meta-deposit')) {
      document.getElementById('pnl-meta-deposit').textContent = '累计入金 ¥' + (window.PNL_META.total_deposit || 200000).toLocaleString();
    }

    // Period tab click handlers
    document.querySelectorAll('.pnl-pill').forEach(function (btn) {
      btn.addEventListener('click', function () {
        document.querySelectorAll('.pnl-pill').forEach(function (b) { b.classList.remove('active'); });
        this.classList.add('active');
        state.period = this.dataset.p;
        updateKPI();
        drawChart();
      });
    });

    // Drawer toggle
    var drawerBtn = document.getElementById('pnl-drawer-btn');
    var drawer = document.getElementById('pnl-drawer');
    if (drawerBtn && drawer) {
      drawerBtn.addEventListener('click', function () {
        state.drawerOpen = !state.drawerOpen;
        drawer.classList.toggle('pnl-drawer-open', state.drawerOpen);
        drawerBtn.classList.toggle('pnl-drawer-btn-open', state.drawerOpen);
        drawerBtn.textContent = state.drawerOpen ? '收起损益明细' : '查看损益明细';
      });
    }

    updateDrawer();
    updateKPI();
    initCrosshair();
    drawChart();

    window.addEventListener('resize', drawChart);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
