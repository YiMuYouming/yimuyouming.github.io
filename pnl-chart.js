// pnl-chart.js — 门户静态收益曲线 (Canvas 2D, 零依赖)
// 数据来源: index.html 内嵌的 PNL_DATA (sync_pnl_data.py 同步)
(function () {
  'use strict';

  // ── DOM refs (populated in safeGet) ──
  var $ = function (id) { return document.getElementById(id); };

  // ── Colors ──
  var C = {
    bg: '#FFFFFF', grid: '#F0EEEC', zero: '#D1CFC5', text: '#2D2926',
    text2: '#5C5652', text3: '#8A8480', red: '#DC2626', green: '#059669',
    accent: '#D97706', blue: '#2563EB', purple: '#7C3AED',
    fillTop: 'rgba(220,38,38,0.12)', fillBot: 'rgba(220,38,38,0.01)',
    bmFillTop: 'rgba(37,99,235,0.08)', bmFillBot: 'rgba(37,99,235,0.005)',
  };

  // ── State ──
  var S = { period: 'all', idx: 'sh' };

  // ── Date helpers ──
  function pDate(s) { var p = s.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }

  function filterByPeriod(daily) {
    if (!daily || !daily.length) return [];
    var now = new Date(), since = null;
    switch (S.period) {
      case 'week': case 'month': case 'quarter': case 'year': case 'today':
        if (S.period === 'today') { since = new Date(now.getFullYear(), now.getMonth(), now.getDate()); break; }
        if (S.period === 'week') { var d = new Date(now); d.setDate(d.getDate() - ((d.getDay() || 7) - 1)); since = new Date(d.getFullYear(), d.getMonth(), d.getDate()); break; }
        if (S.period === 'month') { since = new Date(now.getFullYear(), now.getMonth(), 1); break; }
        if (S.period === 'quarter') { var m = now.getMonth() - 3; since = new Date(now.getFullYear(), m < 0 ? m + 12 : m, now.getDate()); break; }
        if (S.period === 'year') { since = new Date(now.getFullYear(), 0, 1); break; }
        since = null;
      default:
        return daily.slice();
    }
    return daily.filter(function (d) { return pDate(d.date) >= since; });
  }

  // ── TWR chain: daily pnl_pct → cumulative portfolio % ──
  function buildReturns(daily, key) {
    key = key || 'pnl_pct';
    var cum = 1.0;
    return daily.map(function (d) {
      cum *= (1 + ((d[key] || 0)) / 100);
      return parseFloat(((cum - 1) * 100).toFixed(4));
    });
  }

  // ── Max drawdown ──
  function calcDD(portfolio) {
    if (!portfolio || portfolio.length < 2) return null;
    var bestPeak = { idx: 0, val: portfolio[0] }, worst = { dd: 0, peak: null, trough: null };
    for (var i = 1; i < portfolio.length; i++) {
      if (portfolio[i] > bestPeak.val) bestPeak = { idx: i, val: portfolio[i] };
      var dd = portfolio[i] - bestPeak.val;
      if (dd < worst.dd) worst = { dd: Math.round(dd * 100) / 100, peak: { idx: bestPeak.idx, val: bestPeak.val }, trough: { idx: i, val: portfolio[i] } };
    }
    return worst.dd < 0 ? worst : null;
  }

  // ── Benchmark label helpers ──
  var BM_KEYS = { sh: 'sh_pct', sz: 'sz_pct', cy: 'cy_pct' };
  var BM_LABELS = { sh: '上证指数', sz: '深证成指', cy: '创业板指' };

  function hasBenchmark(daily) {
    var key = BM_KEYS[S.idx];
    for (var i = 0; i < daily.length; i++) { if (daily[i][key] !== 0) return true; }
    return false;
  }

  // ══════════════════════ Draw chart ══════════════════════
  function drawChart() {
    var canvas = $('pnl-canvas');
    if (!canvas) return;
    var rect = canvas.getBoundingClientRect();
    var W = rect.width, H = rect.height;
    if (!W || !H) { setTimeout(drawChart, 100); return; }
    var DPR = window.devicePixelRatio || 1;
    canvas.width = W * DPR; canvas.height = H * DPR;
    var ctx = canvas.getContext('2d');
    ctx.scale(DPR, DPR);

    // Build data
    var daily = filterByPeriod(window.PNL_DAILY || []);
    var portfolio = buildReturns(daily, 'pnl_pct');
    var benchmark = buildReturns(daily, BM_KEYS[S.idx]);
    var dates = daily.map(function (d) { return d.date; });
    var ddInfo = calcDD(portfolio);
    var n = portfolio.length;

    var PAD = { t: 24, r: 70, b: 34, l: 62 };
    var cw = W - PAD.l - PAD.r, ch = H - PAD.t - PAD.b;
    if (cw < 50 || ch < 20) return;

    // Clear
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, W, H);

    if (n < 2) {
      ctx.fillStyle = C.text3; ctx.font = '13px system-ui';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('暂无数据', W / 2, H / 2);
      return;
    }

    function yV(v) { return v == null ? null : PAD.t + ch - ((v - minY) / (maxY - minY)) * ch; }
    function xV(i) { return PAD.l + (i / (n - 1)) * cw; }

    // Scale
    var allVals = portfolio.concat(benchmark).filter(function (v) { return v != null; });
    if (!allVals.length) allVals = [0, 0];
    var absMax = Math.max(Math.abs(Math.min.apply(null, allVals)), Math.abs(Math.max.apply(null, allVals)));
    var step = absMax < 2 ? 0.5 : absMax < 5 ? 1 : absMax < 10 ? 2 : 5;
    var maxY = Math.ceil(absMax / step) * step, minY = -maxY;

    // ── Grid ──
    ctx.fillStyle = C.text3; ctx.font = '10px system-ui';
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    var gridVals = [minY, minY / 2, 0, maxY / 2, maxY];
    for (var gi = 0; gi < gridVals.length; gi++) {
      var gy = yV(gridVals[gi]);
      ctx.strokeStyle = gridVals[gi] === 0 ? C.zero : C.grid;
      ctx.lineWidth = gridVals[gi] === 0 ? 1.2 : 0.5;
      ctx.beginPath(); ctx.moveTo(PAD.l, gy); ctx.lineTo(W - PAD.r + 8, gy); ctx.stroke();
      ctx.fillText((gridVals[gi] >= 0 ? '+' : '') + gridVals[gi].toFixed(1) + '%', PAD.l - 8, gy);
    }

    // ── X-axis labels ──
    ctx.fillStyle = C.text3; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    var labelStep = n <= 10 ? 1 : n <= 30 ? Math.ceil(n / 8) : Math.ceil(n / 10);
    for (var xi = 0; xi < n; xi += labelStep) { ctx.fillText(dates[xi].slice(5), xV(xi), PAD.t + ch + 6); }
    if ((n - 1) % labelStep > labelStep / 2) { ctx.fillText(dates[n - 1].slice(5), xV(n - 1), PAD.t + ch + 6); }

    // ── Benchmark: area fill + dashed line ──
    if (hasBenchmark(daily)) {
      var zyB = yV(0);
      for (var bi = 0; bi < n; bi++) {
        if (benchmark[bi] == null) continue;
        ctx.beginPath(); ctx.moveTo(xV(bi), zyB); ctx.lineTo(xV(bi), yV(benchmark[bi]));
        var be = bi;
        while (be + 1 < n && benchmark[be + 1] != null) be++;
        for (var bj = bi + 1; bj <= be; bj++) ctx.lineTo(xV(bj), yV(benchmark[bj]));
        ctx.lineTo(xV(be), zyB); ctx.closePath();
        var bgrad = ctx.createLinearGradient(0, PAD.t, 0, PAD.t + ch);
        bgrad.addColorStop(0, C.bmFillTop); bgrad.addColorStop(1, C.bmFillBot);
        ctx.fillStyle = bgrad; ctx.fill();
        bi = be;
      }
      ctx.beginPath(); var bs = false;
      for (var bk = 0; bk < n; bk++) {
        if (benchmark[bk] == null) { bs = false; continue; }
        if (!bs) { ctx.moveTo(xV(bk), yV(benchmark[bk])); bs = true; }
        else ctx.lineTo(xV(bk), yV(benchmark[bk]));
      }
      ctx.strokeStyle = C.blue; ctx.lineWidth = 2; ctx.setLineDash([6, 3]); ctx.stroke(); ctx.setLineDash([]);
      // End label
      var blI = n - 1;
      while (blI >= 0 && benchmark[blI] == null) blI--;
      if (blI >= 0) {
        ctx.fillStyle = C.blue; ctx.font = '600 12px system-ui'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
        ctx.fillText((benchmark[blI] >= 0 ? '+' : '') + benchmark[blI].toFixed(2) + '%', xV(blI) + 6, yV(benchmark[blI]) - 14);
      }
    }

    // ── Portfolio: area fill ──
    var zyP = yV(0);
    for (var si = 0; si < n; si++) {
      if (portfolio[si] == null) continue;
      ctx.beginPath(); ctx.moveTo(xV(si), zyP); ctx.lineTo(xV(si), yV(portfolio[si]));
      var se = si;
      while (se + 1 < n && portfolio[se + 1] != null) se++;
      for (var sj = si + 1; sj <= se; sj++) ctx.lineTo(xV(sj), yV(portfolio[sj]));
      ctx.lineTo(xV(se), zyP); ctx.closePath();
      var pgrad = ctx.createLinearGradient(0, PAD.t, 0, PAD.t + ch);
      pgrad.addColorStop(0, C.fillTop); pgrad.addColorStop(1, C.fillBot);
      ctx.fillStyle = pgrad; ctx.fill();
      si = se;
    }

    // ── Portfolio line ──
    ctx.beginPath(); var ps = false; ctx.setLineDash([]);
    for (var pi = 0; pi < n; pi++) {
      if (portfolio[pi] == null) { ps = false; continue; }
      if (!ps) { ctx.moveTo(xV(pi), yV(portfolio[pi])); ps = true; }
      else ctx.lineTo(xV(pi), yV(portfolio[pi]));
    }
    ctx.strokeStyle = C.red; ctx.lineWidth = 2.5; ctx.stroke();

    // ── Portfolio end label ──
    var plI = n - 1;
    while (plI >= 0 && portfolio[plI] == null) plI--;
    if (plI >= 0) {
      ctx.fillStyle = C.red; ctx.font = '600 12px system-ui'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillText((portfolio[plI] >= 0 ? '+' : '') + portfolio[plI].toFixed(2) + '%', xV(plI) + 6, yV(portfolio[plI]));
    }

    // ── Max drawdown ──
    if (ddInfo && ddInfo.peak && ddInfo.trough) {
      var pkX = xV(ddInfo.peak.idx), pkY = yV(ddInfo.peak.val);
      var trX = xV(ddInfo.trough.idx), trY = yV(ddInfo.trough.val);
      // Peak dot
      ctx.beginPath(); ctx.arc(pkX, pkY, 5, 0, Math.PI * 2); ctx.fillStyle = C.accent; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = '#FFF'; ctx.stroke();
      // Trough dot
      ctx.beginPath(); ctx.arc(trX, trY, 5, 0, Math.PI * 2); ctx.fillStyle = C.accent; ctx.fill();
      ctx.strokeStyle = '#FFF'; ctx.stroke();
      // L-shaped dashed
      ctx.strokeStyle = 'rgba(217,119,6,0.5)'; ctx.setLineDash([4, 4]); ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(pkX, pkY); ctx.lineTo(trX, pkY); ctx.lineTo(trX, trY); ctx.stroke();
      ctx.setLineDash([]);
      // DD label
      var ddLabel = '最大回撤 ' + ddInfo.dd.toFixed(2) + '%';
      ctx.font = '11px system-ui'; ctx.fillStyle = C.accent;
      var labX = trX + 8, labY = trY;
      var tw = ctx.measureText(ddLabel).width;
      if (labX + tw > W - 10) labX = trX - tw - 8;
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillText(ddLabel, labX, labY);
    }

    // Store for crosshair
    canvas._chartData = { portfolio: portfolio, benchmark: benchmark, dates: dates, xV: xV, yV: yV, n: n, PAD: PAD, W: W, H: H, hasBM: hasBenchmark(daily) };
  }

  // ── Crosshair + tooltip ──
  function initCrosshair() {
    var canvas = $('pnl-canvas');
    if (!canvas) return;
    var wrap = canvas.parentElement;
    var ch = document.createElement('div');
    ch.id = 'pnl-ch'; ch.style.cssText = 'position:absolute;top:0;width:1px;background:rgba(217,119,6,0.5);pointer-events:none;display:none;z-index:2';
    wrap.appendChild(ch);
    var tip = document.createElement('div');
    tip.id = 'pnl-tip'; tip.style.cssText = 'position:fixed;z-index:9999;background:#FFF;border:1px solid #E5E2DE;border-radius:8px;padding:8px 12px;font-size:12px;line-height:1.6;color:#2D2926;pointer-events:none;display:none;box-shadow:0 2px 12px rgba(0,0,0,.1);max-width:200px';
    document.body.appendChild(tip);

    canvas.addEventListener('mousemove', function (e) {
      var cd = canvas._chartData;
      if (!cd) { ch.style.display = 'none'; tip.style.display = 'none'; return; }
      var rect = canvas.getBoundingClientRect();
      var mx = e.clientX - rect.left;
      if (mx < cd.PAD.l || mx > cd.W - cd.PAD.r) { ch.style.display = 'none'; tip.style.display = 'none'; return; }
      var idx = Math.round(((mx - cd.PAD.l) / (cd.W - cd.PAD.l - cd.PAD.r)) * (cd.n - 1));
      idx = Math.max(0, Math.min(cd.n - 1, idx));
      var cx = cd.xV(idx);
      ch.style.left = cx + 'px'; ch.style.height = cd.H + 'px'; ch.style.display = 'block';
      var pv = cd.portfolio[idx], bv = cd.benchmark ? cd.benchmark[idx] : null;
      var html = '<div style="font-weight:600;margin-bottom:3px">' + cd.dates[idx] + '</div>';
      html += '<div>收益 <span style="color:' + (pv >= 0 ? C.red : C.green) + ';font-weight:600">' + (pv >= 0 ? '+' : '') + pv.toFixed(2) + '%</span></div>';
      if (cd.hasBM && bv != null) {
        html += '<div style="font-size:11px;color:' + C.text3 + '">基准 <span style="color:' + C.blue + '">' + (bv >= 0 ? '+' : '') + bv.toFixed(2) + '%</span></div>';
      }
      tip.innerHTML = html; tip.style.display = 'block';
      tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 210) + 'px';
      tip.style.top = Math.min(e.clientY - 10, window.innerHeight - 100) + 'px';
    });
    canvas.addEventListener('mouseleave', function () { ch.style.display = 'none'; tip.style.display = 'none'; });
  }

  // ── Update KPI cards ──
  function updateKPIs() {
    var daily = window.PNL_DAILY || [];
    var meta = window.PNL_META || {};
    if (!daily.length) return;

    // Current asset
    var lastTotal = daily[daily.length - 1].total || 0;
    var elA = $('pnl-k-asset'); if (elA) elA.textContent = lastTotal ? lastTotal.toLocaleString() : '—';
    var elAS = $('pnl-k-asset-sub'); if (elAS) elAS.textContent = '累计入金 ' + (meta.total_deposit || 200000).toLocaleString();

    // TWR cumulative
    var p = buildReturns(daily, 'pnl_pct');
    var twr = p[p.length - 1];
    var elT = $('pnl-k-twr'); if (elT) { elT.textContent = (twr >= 0 ? '+' : '') + twr.toFixed(2) + '%'; elT.style.color = twr >= 0 ? C.red : C.green; }

    // All-time high
    var pk = 0;
    for (var i = 0; i < p.length; i++) { if (p[i] > pk) pk = p[i]; }
    var elH = $('pnl-k-high'); if (elH) { elH.textContent = (pk >= 0 ? '+' : '') + pk.toFixed(2) + '%'; elH.style.color = C.red; }

    // Max drawdown (all-time)
    var dd = calcDD(p);
    var elD = $('pnl-k-dd'); if (elD) { elD.textContent = (dd ? dd.dd.toFixed(2) : '0.00') + '%'; elD.style.color = C.green; }

    // Period TWR
    var fd = filterByPeriod(daily);
    var fp = buildReturns(fd, 'pnl_pct');
    var fv = fp.length ? fp[fp.length - 1] : 0;
    var elP = $('pnl-k-period'); if (elP) { elP.textContent = (fv >= 0 ? '+' : '') + fv.toFixed(2) + '%'; elP.style.color = fv >= 0 ? C.red : C.green; }
    var pdd = calcDD(fp);
    var elPd = $('pnl-k-pdd'); if (elPd) elPd.textContent = (pdd ? pdd.dd.toFixed(2) : '0.00') + '%';

    // Benchmark cumulative
    var bp = buildReturns(daily, BM_KEYS[S.idx]);
    var btwr = bp[bp.length - 1];
    var elB = $('pnl-k-bm-twr'); if (elB) { elB.textContent = (btwr >= 0 ? '+' : '') + btwr.toFixed(2) + '%'; elB.style.color = btwr >= 0 ? C.red : C.green; }
    var elAlpha = $('pnl-k-alpha'); if (elAlpha) { elAlpha.textContent = (twr - btwr >= 0 ? '+' : '') + (twr - btwr).toFixed(2) + '%'; elAlpha.style.color = (twr - btwr) >= 0 ? C.red : C.green; }

    // Benchmark label
    var elBL = $('pnl-k-bm-label'); if (elBL) elBL.textContent = BM_LABELS[S.idx];
    var elPL = $('pnl-k-period-label');
    var labels = { week: '本周', month: '本月', quarter: '近三月', year: '今年', all: '累计' };
    if (elPL) elPL.textContent = (labels[S.period] || S.period) + ' TWR';
  }

  // ── Drawer ──
  function updateDrawer() {
    var daily = window.PNL_DAILY || [];
    if (!daily.length) return;
    var tbody = $('pnl-drawer-tbody');
    if (!tbody) return;
    var now = new Date();
    var periods = [
      { key: 'week', label: '近一周', since: (function () { var d = new Date(now); d.setDate(d.getDate() - ((d.getDay() || 7) - 1)); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); })() },
      { key: 'month', label: '近一月', since: new Date(now.getFullYear(), now.getMonth(), 1) },
      { key: 'quarter', label: '近三月', since: (function () { var m = now.getMonth() - 3; return new Date(now.getFullYear(), m < 0 ? m + 12 : m, now.getDate()); })() },
      { key: 'year', label: '近一年', since: new Date(now.getFullYear(), 0, 1) },
    ];
    tbody.innerHTML = '';

    var fullP = buildReturns(daily, 'pnl_pct');
    var fullDD = calcDD(fullP);

    periods.forEach(function (per) {
      var fd = daily.filter(function (d) { return pDate(d.date) >= per.since; });
      var pp = buildReturns(fd, 'pnl_pct');
      var pv = pp.length ? pp[pp.length - 1] : 0;
      var pdd = calcDD(pp);
      var bp = buildReturns(fd, BM_KEYS[S.idx]);
      var bv = bp.length ? bp[bp.length - 1] : 0;
      var alpha = pv - bv;
      var row = '<tr><td style="font-weight:600">' + per.label + '</td>' +
        '<td style="text-align:right;color:' + (pv >= 0 ? C.red : C.green) + ';font-variant-numeric:tabular-nums">' + (pv >= 0 ? '+' : '') + pv.toFixed(2) + '%</td>' +
        '<td style="text-align:right;font-variant-numeric:tabular-nums">' + (bv >= 0 ? '+' : '') + bv.toFixed(2) + '%</td>' +
        '<td style="text-align:right;color:' + (alpha >= 0 ? C.red : C.green) + ';font-variant-numeric:tabular-nums">' + (alpha >= 0 ? '+' : '') + alpha.toFixed(2) + '%</td>' +
        '<td style="text-align:right;color:' + C.green + ';font-variant-numeric:tabular-nums">' + (pdd ? pdd.dd.toFixed(2) : '0.00') + '%</td></tr>';
      tbody.innerHTML += row;
    });

    // Cumulative row
    var bmP = buildReturns(daily, BM_KEYS[S.idx]);
    var cumTWR = fullP[fullP.length - 1], cumBM = bmP[bmP.length - 1], cumAlpha = cumTWR - cumBM;
    var cumRow = '<tr style="font-weight:600;border-top:2px solid #E5E2DE;background:#F5F2EE">' +
      '<td>累计</td>' +
      '<td style="text-align:right;color:' + (cumTWR >= 0 ? C.red : C.green) + ';font-variant-numeric:tabular-nums">' + (cumTWR >= 0 ? '+' : '') + cumTWR.toFixed(2) + '%</td>' +
      '<td style="text-align:right;font-variant-numeric:tabular-nums">' + (cumBM >= 0 ? '+' : '') + cumBM.toFixed(2) + '%</td>' +
      '<td style="text-align:right;color:' + (cumAlpha >= 0 ? C.red : C.green) + ';font-variant-numeric:tabular-nums">' + (cumAlpha >= 0 ? '+' : '') + cumAlpha.toFixed(2) + '%</td>' +
      '<td style="text-align:right;color:' + C.green + ';font-variant-numeric:tabular-nums">' + (fullDD ? fullDD.dd.toFixed(2) : '0.00') + '%</td></tr>';
    tbody.innerHTML += cumRow;
  }

  // ── Init ──
  function init() {
    if (typeof window.PNL_DATA === 'undefined') { console.warn('PNL_DATA not loaded'); return; }
    if (!$('pnl-section')) { console.warn('pnl-section not found'); return; }

    window.PNL_DAILY = window.PNL_DATA.daily || [];
    window.PNL_META = window.PNL_DATA.meta || {};

    // Meta text
    var ts = window.PNL_META.updated || window.PNL_META.last_updated || '';
    var elPar = $('pnl-meta-parts'); if (elPar) elPar.textContent = '数据截止 ' + ts.slice(0, 10);
    var elDep = $('pnl-meta-deposit'); if (elDep) elDep.textContent = '累计入金 ¥' + (window.PNL_META.total_deposit || 200000).toLocaleString();
    var elBML = $('bm-label'); if (elBML) elBML.textContent = '上证指数';

    // Period tab clicks
    var pills = document.querySelectorAll('.pnl-pill[data-p]');
    pills.forEach(function (btn) {
      btn.addEventListener('click', function () {
        pills.forEach(function (b) { b.classList.remove('active'); });
        this.classList.add('active');
        S.period = this.getAttribute('data-p');
        updateKPIs();
        drawChart();
      });
    });

    // Index button clicks
    var idxBtns = document.querySelectorAll('.pnl-idx-pill');
    idxBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        idxBtns.forEach(function (b) { b.classList.remove('active'); });
        this.classList.add('active');
        S.idx = this.getAttribute('data-idx');
        var elBML2 = $('bm-label'); if (elBML2) elBML2.textContent = BM_LABELS[S.idx];
        updateKPIs();
        updateDrawer();
        drawChart();
      });
    });

    // Drawer toggle
    var drawerBtn = $('pnl-drawer-btn');
    var drawer = $('pnl-drawer');
    if (drawerBtn && drawer) {
      drawerBtn.addEventListener('click', function () {
        S.drawerOpen = !S.drawerOpen;
        drawer.classList.toggle('pnl-drawer-open', S.drawerOpen);
        drawerBtn.classList.toggle('pnl-drawer-btn-open', S.drawerOpen);
        drawerBtn.innerHTML = S.drawerOpen ? '收起损益明细 ▲' : '查看损益明细 ▼';
      });
    }

    updateDrawer();
    updateKPIs();
    initCrosshair();
    drawChart();
    window.addEventListener('resize', drawChart);
  }

  // ── Bootstrap ──
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
