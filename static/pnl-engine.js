// PnL chart — data from bridge API, rendering from pnl-curve.js _drawChart
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var S = { period: (PNL_DATA && PNL_DATA.all_sh) ? 'all' : 'quarter', idx: 'sh' };
  var MET = { sh: '上证指数', sz: '深证成指', cy: '创业板指' };
  var PER = { today: '今日', week: '近一周', month: '近一月', quarter: '近三月', year: '近一年', all: '全部记录' };
  function fmt(v) { return (v >= 0 ? '+' : '') + (v != null ? v.toFixed(2) : '0.00') + '%'; }

  // ── chartData from API cache ──
  function cd() {
    var data = (PNL_DATA || {})[S.period + '_' + S.idx] || null;
    if (S.period === 'all' && data) {
      var converted = {};
      for (var k in data) converted[k] = data[k];
      converted.portfolio = twrChain(data.portfolio || []);
      converted.benchmark = twrChain(data.benchmark || []);
      return converted;
    }
    return data;
  }
  function allDaily() { return (PNL_DATA || {})['all_' + S.idx] || null; }
  function meta() { return (PNL_DATA || {}).meta || {}; }

  // ── TWR chain from raw daily returns ──
  function twrChain(raw) {
    var cum = 1.0, result = [];
    for (var i = 0; i < raw.length; i++) {
      cum *= (1 + (raw[i] || 0) / 100);
      result.push(parseFloat(((cum - 1) * 100).toFixed(4)));
    }
    return result;
  }

  // ── calcDD from cumulative array ──
  function calcDD(cum) {
    if (!cum || cum.length < 2) return null;
    // Skip leading nulls
    var s = 0; while (s < cum.length && cum[s] == null) s++;
    if (s >= cum.length - 1) return null;
    var pk = cum[s], pkI = s, worst = { dd: 0, peak: null, trough: null };
    for (var i = s + 1; i < cum.length; i++) {
      if (cum[i] == null) continue;
      if (cum[i] > pk) { pk = cum[i]; pkI = i; }
      var dd = cum[i] - pk;
      if (dd < worst.dd) worst = { dd: Math.round(dd * 100) / 100, peak: { idx: pkI, val: pk }, trough: { idx: i, val: cum[i] } };
    }
    return worst.dd < 0 ? worst : null;
  }

  function calendarPeriodMetrics(period, idx) {
    var all = allDaily();
    if (!all || !all.dates || !all.dates.length) return null;
    var now = new Date();
    var sinceMap = {
      today: now.toISOString().slice(0, 10),
      week: (function () { var d0 = new Date(now); d0.setDate(d0.getDate() - ((d0.getDay() || 7) - 1)); return d0.toISOString().slice(0, 10); })(),
      month: now.toISOString().slice(0, 7) + '-01',
      quarter: new Date(now.getFullYear(), now.getMonth() - 3, 1).toISOString().slice(0, 10),
      year: now.getFullYear() + '-01-01',
      all: all.dates[0],
    };
    var since = sinceMap[period] || all.dates[0];
    var rawP = [], rawB = [];
    for (var i = 0; i < all.dates.length; i++) {
      if (all.dates[i] >= since) {
        rawP.push(all.portfolio[i] || 0);
        rawB.push(all.benchmark[i] || 0);
      }
    }
    if (!rawP.length) return null;
    var cumP = twrChain(rawP), cumB = twrChain(rawB);
    return {
      twr: cumP.length ? cumP[cumP.length - 1] : 0,
      bm: cumB.length ? cumB[cumB.length - 1] : 0,
      dd: calcDD(cumP),
    };
  }

  // ═══════════════ KPI Update ═══════════════
  function updateKPIs() {
    var d = cd();
    var all = allDaily();
    var m = meta();
    if (!d || !$('pnl_asset')) return;

    // ── Row 1: cumulative ──
    var allCum = twrChain(all && all.portfolio ? all.portfolio : []);
    var allBmCum = twrChain(all && all.benchmark ? all.benchmark : []);
    var allTWR = allCum.length ? allCum[allCum.length - 1] : 0;
    var allBM = allBmCum.length ? allBmCum[allBmCum.length - 1] : 0;
    var allDD = calcDD(allCum);
    var allPK = 0; for (var i = 0; i < allCum.length; i++) { if (allCum[i] > allPK) allPK = allCum[i]; }

    // Current asset
    $('pnl_asset').textContent = m.total_asset ? m.total_asset.toLocaleString() : '—';
    $('pnl_asset_sub').textContent = '累计入金 ' + ((m.total_deposit || 200000).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }));

    setKPI('pnl_twr', fmt(allTWR), allTWR >= 0, '累计时间加权收益');
    setKPI('pnl_alpha', fmt(allTWR - allBM), (allTWR - allBM) >= 0, 'TWR − 指数参考');
    setKPI('pnl_maxdd', (allDD ? allDD.dd.toFixed(2) : '0.00') + '%', false, '历史最大');

    // ── Row 2: selected period, matching Live Dashboard semantics ──
    var periodText = PER[S.period] || '今日';
    var p = d.portfolio || [];
    var b = d.benchmark || [];
    var pos = d.position || [];
    var lastI = p.length - 1;
    while (lastI >= 0 && p[lastI] == null) lastI--;
    var lastP = lastI >= 0 ? p[lastI] : 0;
    var lastB = lastI >= 0 && b[lastI] != null ? b[lastI] : 0;
    var validPos = [];
    for (var k = 0; k < pos.length; k++) {
      if (p[k] != null && pos[k] != null && !isNaN(parseFloat(pos[k]))) validPos.push(parseFloat(pos[k]));
    }
    var avgPos = validPos.length ? validPos.reduce(function (a, v) { return a + v; }, 0) / validPos.length : null;
    var lastPos = validPos.length ? validPos[validPos.length - 1] : 0;
    var posVal = S.period === 'today' ? lastPos : avgPos;
    var cal = S.period === 'today' ? null : calendarPeriodMetrics(S.period, S.idx);
    var periodTWR = cal ? cal.twr : lastP;
    var periodBM = cal ? cal.bm : lastB;
    var alpha = periodTWR - periodBM;
    var perDD = cal ? cal.dd : calcDD(p);

    if ($('pnl_pnl_label')) $('pnl_pnl_label').textContent = periodText + '收益';
    setKPI('pnl_pnl', fmt(lastP), lastP >= 0, periodText + ' TWR');

    if ($('pnl_pos_label')) $('pnl_pos_label').textContent = S.period === 'today' ? '今日仓位' : periodText + '平均仓位';
    $('pnl_pos').textContent = posVal == null ? '—' : (S.period === 'today' ? posVal.toFixed(1) : posVal.toFixed(0)) + '%';
    $('pnl_pos').style.color = posVal == null ? '' : (posVal > 80 ? '#DC2626' : posVal > 50 ? '#D97706' : '#059669');
    $('pnl_pos_sub').textContent = S.period === 'today' ? '今日仓位' : validPos.length + ' 个采样';

    $('pnl_period_label').textContent = periodText + ' TWR';
    setKPI('pnl_period_val', fmt(periodTWR), periodTWR >= 0, '相对指数 ' + fmt(alpha));

    if ($('pnl_today_alpha_label')) $('pnl_today_alpha_label').textContent = periodText + ' 相对指数';
    setKPI('pnl_today_alpha', fmt(alpha), alpha >= 0, 'TWR − 指数参考');

    $('pnl_dd_label').textContent = periodText + ' 回撤';
    setKPI('pnl_dd_val', (perDD ? perDD.dd.toFixed(2) : '0.00') + '%', false, S.period === 'today' ? '今日峰谷' : '—');
  }

  function setKPI(id, text, isPos, sub) {
    var el = $(id); if (!el) return;
    el.textContent = text;
    el.style.color = text.indexOf('%') > -1 ? (isPos ? '#DC2626' : '#059669') : '';
    var subEl = $(id + '_sub'); if (subEl) subEl.textContent = sub;
  }

  // ═══════════════ Drawer ═══════════════
  function updateDrawer() {
    var all = allDaily();
    if (!all || !all.dates || !all.dates.length) return;
    var tbody = $('pnl_tbody'), summary = $('pnl_summary');
    if (!tbody || !summary) return;

    var now = new Date();
    var periods = [
      { key: 'today', label: '日', since: new Date(now.getFullYear(), now.getMonth(), now.getDate()) },
      { key: 'week', label: '近一周', since: (function () { var d = new Date(now); d.setDate(d.getDate() - ((d.getDay() || 7) - 1)); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); })() },
      { key: 'month', label: '近一月', since: new Date(now.getFullYear(), now.getMonth(), 1) },
      { key: 'quarter', label: '近三月', since: new Date(now.getFullYear(), now.getMonth() - 3, now.getDate()) },
      { key: 'year', label: '近一年', since: new Date(now.getFullYear(), 0, 1) },
      { key: 'all', label: '全部', since: new Date(0) },
    ];
    var rows = '';
    periods.forEach(function (per) {
      var idxs = [];
      for (var i = 0; i < all.dates.length; i++) { if (new Date(all.dates[i]) >= per.since) idxs.push(i); }
      if (!idxs.length && per.key === 'today') idxs = [all.dates.length - 1];
      var rawP = idxs.map(function (i) { return all.portfolio[i]; });
      var rawB = idxs.map(function (i) { return all.benchmark[i]; });
      var cumP = twrChain(rawP), cumB = twrChain(rawB);
      var twr = cumP.length ? cumP[cumP.length - 1] : 0;
      var bm = cumB.length ? cumB[cumB.length - 1] : 0;
      var dd = calcDD(cumP);
      rows += '<tr><td class="pnl-td-period">' + per.label + '</td>' +
        '<td class="pnl-td-num" style="color:' + (twr >= 0 ? '#DC2626' : '#059669') + '">' + fmt(twr) + '</td>' +
        '<td class="pnl-td-num">' + fmt(bm) + '</td>' +
        '<td class="pnl-td-num" style="color:' + ((twr - bm) >= 0 ? '#DC2626' : '#059669') + '">' + fmt(twr - bm) + '</td>' +
        '<td class="pnl-td-num" style="color:#059669">' + (dd ? dd.dd.toFixed(2) : '0.00') + '%</td></tr>';
    });
    tbody.innerHTML = rows;

    var allCumP = twrChain(all.portfolio), allCumB = twrChain(all.benchmark);
    var allTWR = allCumP.length ? allCumP[allCumP.length - 1] : 0;
    var allBM = allCumB.length ? allCumB[allCumB.length - 1] : 0;
    var allDD2 = calcDD(allCumP);
    var allPK2 = 0; for (var j = 0; j < allCumP.length; j++) { if (allCumP[j] > allPK2) allPK2 = allCumP[j]; }

    summary.innerHTML = '<div class="pnl-sum-cell"><div class="pnl-sum-lbl">累计收益</div><div class="pnl-sum-val" style="color:' + (allTWR >= 0 ? '#DC2626' : '#059669') + '">' + fmt(allTWR) + '</div></div>' +
      '<div class="pnl-sum-cell"><div class="pnl-sum-lbl">指数参考</div><div class="pnl-sum-val" style="color:' + (allBM >= 0 ? '#DC2626' : '#059669') + '">' + fmt(allBM) + '</div></div>' +
      '<div class="pnl-sum-cell"><div class="pnl-sum-lbl">相对指数</div><div class="pnl-sum-val" style="color:' + ((allTWR - allBM) >= 0 ? '#DC2626' : '#059669') + '">' + fmt(allTWR - allBM) + '</div></div>' +
      '<div class="pnl-sum-cell"><div class="pnl-sum-lbl">累计最高</div><div class="pnl-sum-val" style="color:#DC2626">' + fmt(allPK2) + '</div></div>' +
      '<div class="pnl-sum-cell"><div class="pnl-sum-lbl">最大回撤</div><div class="pnl-sum-val" style="color:#059669">' + (allDD2 ? allDD2.dd.toFixed(2) : '0.00') + '%</div></div>';
  }

  // ═══════════════ Draw Chart ═══════════════ 
  // Direct copy from pnl-curve.js _drawChart (lines 544-762)
  function drawChart() {
    var canvas = $('pnl_canvas');
    if (!canvas) return;
    var rect = canvas.getBoundingClientRect();
    var W = rect.width, H = rect.height;
    if (!W || !H) { setTimeout(drawChart, 100); return; }
    var DPR = window.devicePixelRatio || 1;
    canvas.width = W * DPR; canvas.height = H * DPR;
    var ctx = canvas.getContext('2d'); ctx.scale(DPR, DPR);

    var cd_ = cd();
    if (!cd_ || !cd_.labels || !cd_.labels.length) {
      ctx.clearRect(0, 0, W, H); ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#8A8480'; ctx.font = '13px system-ui';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('暂无数据', W / 2, H / 2); return;
    }

    var p = cd_.portfolio, b = cd_.benchmark, pos = cd_.position, labels = cd_.labels || cd_.dates || [];
    // For intraday, labels are time strings; for daily, they're date slices
    var n = p.length;

    // Pad arrays for today: add a pre-market null to avoid connecting 0 to first data
    if (cd_.type === 'intraday' && n > 0) {
      // Already has full slots with nulls between — use as-is
    }
    if (n < 2) { p = [p[0], p[0]]; b = [b[0], b[0]]; labels = [labels[0], labels[0]]; n = 2; }

    var PAD = { t: 24, r: 70, b: 30, l: 62 };
    var cw = W - PAD.l - PAD.r, ch = H - PAD.t - PAD.b;
    if (cw < 50 || ch < 20) return;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, W, H);

    // Scale: pool portfolio + benchmark, skip nulls
    // 前值填充：中间 null 用上一个有效值填（首尾 null 保留）
    function forwardFill(arr) {
      var out = [], last = null, seen = false;
      for (var i2 = 0; i2 < arr.length; i2++) {
        if (arr[i2] != null) { seen = true; last = arr[i2]; out.push(arr[i2]); }
        else if (seen) { out.push(last); }
        else { out.push(null); }
      }
      for (var j2 = out.length - 1; j2 >= 0 && out[j2] === last && arr[j2] == null; j2--) { out[j2] = null; }
      return out;
    }
    var pF = forwardFill(p);
    var bF = forwardFill(b);
    var posF = forwardFill(pos);

    var validP = pF.filter(function (v) { return v != null; });
    var validB = bF.filter(function (v) { return v != null; });
    var allVals = validP.concat(validB);
    if (!allVals.length) allVals = [0, 0];
    var absMax = Math.max(Math.abs(Math.min.apply(null, allVals)), Math.abs(Math.max.apply(null, allVals)));
    var step = absMax < 2 ? 0.5 : absMax < 5 ? 1 : absMax < 10 ? 2 : 5;
    var maxY = Math.ceil(absMax / step) * step, minY = -maxY;

    function yV(v) { return v == null ? null : PAD.t + ch - ((v - minY) / (maxY - minY)) * ch; }
    function xV(i) { return PAD.l + (i / (n - 1)) * cw; }

    // Grid
    ctx.fillStyle = '#8A8480'; ctx.font = '10px "JetBrains Mono", system-ui, sans-serif';
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    var gs = [minY, minY / 2, 0, maxY / 2, maxY];
    for (var gi = 0; gi < gs.length; gi++) {
      var gy = yV(gs[gi]);
      ctx.strokeStyle = gs[gi] === 0 ? '#D1CFC5' : '#F0EEEC';
      ctx.lineWidth = gs[gi] === 0 ? 1.2 : 0.5;
      ctx.beginPath(); ctx.moveTo(PAD.l, gy); ctx.lineTo(W - PAD.r + 8, gy); ctx.stroke();
      ctx.fillText((gs[gi] >= 0 ? '+' : '') + gs[gi].toFixed(1) + '%', PAD.l - 8, gy);
    }

    // X-axis labels
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    var ls = n <= 10 ? 1 : n <= 30 ? Math.ceil(n / 8) : Math.ceil(n / 10);
    for (var xi = 0; xi < n; xi += ls) {
      var lbl = labels[xi];
      if (lbl && lbl.length > 5) lbl = lbl.slice(5);  // date → MM-DD
      ctx.fillText(lbl || '', xV(xi), PAD.t + ch + 6);
    }
    if ((n - 1) % ls > ls / 2) {
      var ll = labels[n - 1]; if (ll && ll.length > 5) ll = ll.slice(5);
      ctx.fillText(ll || '', xV(n - 1), PAD.t + ch + 6);
    }

    var hasBM = b.some(function (v) { return v !== 0; });
    var zy = yV(0);

    // drawSegments — handles null breaks
    function drawSegments(vals, color, width, dash) {
      ctx.beginPath(); var s = false;
      if (dash) ctx.setLineDash(dash);
      for (var i = 0; i < n; i++) {
        var sy = yV(vals[i]);
        if (vals[i] == null || sy == null) { s = false; continue; }
        if (!s) { ctx.moveTo(xV(i), sy); s = true; }
        else ctx.lineTo(xV(i), sy);
      }
      ctx.strokeStyle = color; ctx.lineWidth = width || 2; ctx.stroke(); ctx.setLineDash([]);
    }

    function fillArea(vals, gradTop, gradBot) {
      for (var i = 0; i < n; i++) {
        if (vals[i] == null) continue;
        ctx.beginPath(); ctx.moveTo(xV(i), zy); ctx.lineTo(xV(i), yV(vals[i]));
        var e = i;
        while (e + 1 < n && vals[e + 1] != null) e++;
        for (var j = i + 1; j <= e; j++) ctx.lineTo(xV(j), yV(vals[j]));
        ctx.lineTo(xV(e), zy); ctx.closePath();
        var g = ctx.createLinearGradient(0, PAD.t, 0, PAD.t + ch);
        g.addColorStop(0, gradTop); g.addColorStop(1, gradBot);
        ctx.fillStyle = g; ctx.fill();
        i = e;
      }
    }

    // Position fill (gray area at bottom)
    if (posF && posF.some(function (v) { return v > 0; })) {
      for (var pi = 0; pi < n; pi++) {
        if (posF[pi] == null) continue;
        var ph = PAD.t + ch - (posF[pi] / 100 * ch * 0.3 + PAD.b);
        if (ph < PAD.t + ch * 0.3) ph = PAD.t + ch * 0.3;
        ctx.beginPath(); ctx.moveTo(xV(pi), PAD.t + ch); ctx.lineTo(xV(pi), ph);
        var pe = pi;
        while (pe + 1 < n && posF[pe + 1] != null) pe++;
        for (var pj = pi + 1; pj <= pe; pj++) {
          var pjh = PAD.t + ch - (posF[pj] / 100 * ch * 0.3 + PAD.b);
          if (pjh < PAD.t + ch * 0.3) pjh = PAD.t + ch * 0.3;
          ctx.lineTo(xV(pj), pjh);
        }
        ctx.lineTo(xV(pe), PAD.t + ch); ctx.closePath();
        ctx.fillStyle = 'rgba(0,0,0,0.04)'; ctx.fill();
        pi = pe;
      }
    }

    // Benchmark (drawn first, below portfolio)
    if (hasBM) {
      fillArea(bF, 'rgba(37,99,235,0.08)', 'rgba(37,99,235,0.005)');
      drawSegments(bF, '#2563EB', 2, [6, 3]);
    }

    // Portfolio
    fillArea(pF, 'rgba(220,38,38,0.12)', 'rgba(220,38,38,0.01)');
    drawSegments(pF, '#DC2626', 2.5);

    // End labels
    var li = n - 1; while (li >= 0 && p[li] == null) li--;
    if (li >= 0) {
      ctx.fillStyle = '#DC2626'; ctx.font = '600 12px "JetBrains Mono", system-ui, sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillText(fmt(p[li]), xV(li) + 6, yV(p[li]));
    }
    if (hasBM) {
      var bi = n - 1; while (bi >= 0 && b[bi] == null) bi--;
      if (bi >= 0) {
        ctx.fillStyle = '#2563EB'; ctx.font = '600 12px "JetBrains Mono", system-ui, sans-serif';
        ctx.fillText(fmt(b[bi]), xV(bi) + 6, yV(b[bi]) - 14);
      }
    }

    // Max drawdown
    var ddInfo = calcDD(pF);
    if (ddInfo && ddInfo.peak && ddInfo.trough) {
      var pkX = xV(ddInfo.peak.idx), pkY = yV(ddInfo.peak.val);
      var trX = xV(ddInfo.trough.idx), trY = yV(ddInfo.trough.val);
      ctx.beginPath(); ctx.arc(pkX, pkY, 5, 0, Math.PI * 2); ctx.fillStyle = '#D97706'; ctx.fill();
      ctx.strokeStyle = '#FFF'; ctx.lineWidth = 2; ctx.stroke();
      ctx.beginPath(); ctx.arc(trX, trY, 5, 0, Math.PI * 2); ctx.fillStyle = '#D97706'; ctx.fill();
      ctx.strokeStyle = '#FFF'; ctx.stroke();
      ctx.strokeStyle = 'rgba(217,119,6,0.5)'; ctx.setLineDash([4, 4]); ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(pkX, pkY); ctx.lineTo(trX, pkY); ctx.lineTo(trX, trY); ctx.stroke();
      ctx.setLineDash([]);
      var ddLabel = '最大回撤 ' + ddInfo.dd.toFixed(2) + '%';
      ctx.font = '11px system-ui'; ctx.fillStyle = '#D97706';
      var tw = ctx.measureText(ddLabel).width;
      // 谷底常常就在曲线末端，而末端已经写了一个数值标签；谷底上方又是曲线本身。
      // 放到谷底**下方**（那里是空白），水平方向优先靠左，放不下才靠右。
      var labX = trX - tw - 12;
      if (labX < PAD.l) labX = trX + 12;
      if (labX + tw > W - 8) labX = Math.max(PAD.l, W - 8 - tw);
      var below = trY + 16, fitsBelow = below + 12 <= PAD.t + ch;
      var labY = fitsBelow ? below : trY - 12;
      ctx.textAlign = 'left'; ctx.textBaseline = fitsBelow ? 'top' : 'bottom';
      ctx.fillText(ddLabel, labX, labY);
    }

    canvas._chartData = { portfolio: p, benchmark: b, labels: labels, xV: xV, yV: yV, n: n, PAD: PAD, W: W, H: H, hasBM: hasBM };
  }

  // ── Crosshair ──
  function initCrosshair() {
    var canvas = $('pnl_canvas'); if (!canvas) return;
    var ch = document.createElement('div');
    ch.id = 'pnl_ch'; ch.style.cssText = 'position:absolute;top:0;width:1px;background:rgba(217,119,6,0.5);pointer-events:none;display:none;z-index:2';
    canvas.parentElement.appendChild(ch);
    var tip = document.createElement('div');
    tip.id = 'pnl_tip'; tip.style.cssText = 'position:fixed;z-index:9999;background:#FFF;border:1px solid #E5E2DE;border-radius:8px;padding:8px 12px;font-size:12px;line-height:1.6;color:#2D2926;pointer-events:none;display:none;box-shadow:0 2px 12px rgba(0,0,0,.1);max-width:200px';
    document.body.appendChild(tip);
    canvas.addEventListener('mousemove', function (e) {
      var cd2 = canvas._chartData;
      if (!cd2) { ch.style.display = 'none'; tip.style.display = 'none'; return; }
      var rect = canvas.getBoundingClientRect(), mx = e.clientX - rect.left;
      if (mx < cd2.PAD.l || mx > cd2.W - cd2.PAD.r) { ch.style.display = 'none'; tip.style.display = 'none'; return; }
      var idx = Math.round(((mx - cd2.PAD.l) / (cd2.W - cd2.PAD.l - cd2.PAD.r)) * (cd2.n - 1));
      idx = Math.max(0, Math.min(cd2.n - 1, idx));
      ch.style.left = cd2.xV(idx) + 'px'; ch.style.height = cd2.H + 'px'; ch.style.display = 'block';
      var pv = cd2.portfolio[idx], bv = cd2.benchmark ? cd2.benchmark[idx] : null;
      var h = '<div style="font-weight:600;margin-bottom:3px;font-family:var(--font-mono)">' + cd2.labels[idx] + '</div>';
      h += '<div>收益 <span style="color:' + (pv >= 0 ? '#DC2626' : '#059669') + ';font-weight:600;font-family:var(--font-mono)">' + fmt(pv) + '</span></div>';
      if (cd2.hasBM && bv != null) h += '<div style="font-size:11px;color:#8A8480">' + MET[S.idx] + ' <span style="color:#2563EB;font-family:var(--font-mono)">' + fmt(bv) + '</span></div>';
      tip.innerHTML = h; tip.style.display = 'block';
      tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 210) + 'px';
      tip.style.top = Math.min(e.clientY - 10, window.innerHeight - 100) + 'px';
    });
    canvas.addEventListener('mouseleave', function () { ch.style.display = 'none'; tip.style.display = 'none'; });
  }

  // ── Init ──
  function init() {
    if (typeof PNL_DATA === 'undefined') return;
    if (!$('pnl_asset')) return;
    document.querySelectorAll('.pnl-period').forEach(function (b) {
      b.addEventListener('click', function () {
        document.querySelectorAll('.pnl-period').forEach(function (x) { x.classList.remove('active'); });
        this.classList.add('active'); S.period = this.getAttribute('data-p'); updateKPIs(); drawChart();
      });
    });
    document.querySelectorAll('.pnl-idx-btn').forEach(function (b) {
      b.addEventListener('click', function () {
        document.querySelectorAll('.pnl-idx-btn').forEach(function (x) { x.classList.remove('active'); });
        this.classList.add('active'); S.idx = this.getAttribute('data-idx');
        $('pnl_idx_label').textContent = MET[S.idx]; updateKPIs(); updateDrawer(); drawChart();
      });
    });
    updateDrawer(); updateKPIs(); initCrosshair(); drawChart();
    window.addEventListener('resize', drawChart);
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
