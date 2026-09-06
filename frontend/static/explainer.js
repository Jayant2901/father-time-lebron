const eby = (id) => document.getElementById(id);
const SVGNS = "http://www.w3.org/2000/svg";

let metricsCache = null;
let lebronId = null;

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

async function resolvePlayerId(name) {
  const results = await fetchJSON(`/players?search=${encodeURIComponent(name)}&limit=1`);
  return results.length ? results[0].player_id : null;
}

async function getMetrics() {
  if (!metricsCache) metricsCache = await fetchJSON("/metrics");
  return metricsCache;
}

function populateMetricSelect(selectId, metrics, defaultKey) {
  const select = eby(selectId);
  select.innerHTML = "";
  for (const m of metrics) {
    const opt = document.createElement("option");
    opt.value = m.key;
    opt.textContent = m.unit ? `${m.display_name} (${m.unit})` : m.display_name;
    select.appendChild(opt);
  }
  if ([...select.options].some((o) => o.value === defaultKey)) {
    select.value = defaultKey;
  }
}

function describeSd(z) {
  if (z == null) return "no comparable data";
  const a = Math.abs(z);
  const dir = z >= 0 ? "better" : "worse";
  if (a < 0.5) return "about typical for this age";
  if (a < 1) return `slightly ${dir} than typical for this age`;
  if (a < 2) return `much ${dir} than typical for this age`;
  return `historically ${dir === "better" ? "rare (great)" : "rare (poor)"} for this age`;
}

function showError(msg, id) {
  const box = eby(id);
  box.textContent = msg;
  box.hidden = false;
}
function clearError(id) {
  eby(id).hidden = true;
}
function setLoading(isLoading, id) {
  eby(id).hidden = !isLoading;
}

function svgEl(tag, attrs) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

// ---- Generic player search (shared by both interactive sections) ----------

async function searchPlayers(query, resultsContainerId, errId, onPick, pickLabel) {
  clearError(errId);
  const container = eby(resultsContainerId);
  container.innerHTML = "";
  if (!query.trim()) return;

  try {
    const results = await fetchJSON(`/players?search=${encodeURIComponent(query)}&limit=12`);
    if (results.length === 0) {
      const p = document.createElement("p");
      p.textContent = "No players found.";
      container.appendChild(p);
      return;
    }
    for (const p of results) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = `${pickLabel} ${p.display_name} (${p.first_season}–${p.last_season})`;
      btn.onclick = () => onPick(p.player_id, p.display_name);
      container.appendChild(btn);
    }
  } catch (err) {
    showError(err.message, errId);
  }
}

// ---- Section 1: single-player line chart -----------------------------------

let soloPlayerId = null;

function describeAgePoint(p) {
  const z = p.z_score != null
    ? `${p.z_score.toFixed(2)} SD (${describeSd(p.z_score)})`
    : "n/a (no baseline at this age)";
  const note = p.low_confidence
    ? `<div class="detail-note">Low-confidence age — small historical sample, interpret cautiously.</div>`
    : "";
  return `
    <div class="detail-row"><span class="detail-label">Age</span><span class="detail-value">${p.age} (Season ${p.season})</span></div>
    <div class="detail-row"><span class="detail-label">Raw value</span><span class="detail-value">${p.value.toFixed(1)}</span></div>
    <div class="detail-row"><span class="detail-label">Percentile</span><span class="detail-value">${p.percentile.toFixed(1)}</span></div>
    <div class="detail-row"><span class="detail-label">Anomaly score</span><span class="detail-value">${z}</span></div>
    ${note}
  `;
}

function renderLineChart({ svgId, faceId, detailId, points, summary, headshotUrl }) {
  const padL = 44, padT = 20, padR = 20, padB = 36, W = 760, H = 320;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const n = points.length;
  const xAt = (i) => (n === 1 ? padL + innerW / 2 : padL + (i / (n - 1)) * innerW);
  const yAt = (v) => padT + ((100 - v) / 100) * innerH;

  const bandTop = points.map((p) => (p.cohort_mean != null ? Math.min(100, p.cohort_mean + p.cohort_std) : null));
  const bandBottom = points.map((p) => (p.cohort_mean != null ? Math.max(0, p.cohort_mean - p.cohort_std) : null));

  const svg = eby(svgId);
  svg.innerHTML = "";
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

  svg.appendChild(svgEl("line", { x1: padL, y1: padT, x2: padL, y2: H - padB, stroke: "var(--color-divider)", "stroke-width": 1 }));
  svg.appendChild(svgEl("line", { x1: padL, y1: H - padB, x2: W - padR, y2: H - padB, stroke: "var(--color-divider)", "stroke-width": 1 }));

  for (const v of [0, 25, 50, 75, 100]) {
    const y = yAt(v);
    const t = svgEl("text", { x: 36, y, "text-anchor": "end", class: "axis-label", dy: 3 });
    t.textContent = String(v);
    svg.appendChild(t);
    svg.appendChild(svgEl("line", { x1: padL, y1: y, x2: W - padR, y2: y, stroke: "var(--color-divider)", "stroke-width": 0.5, "stroke-dasharray": "2,3" }));
  }

  const tickEvery = Math.max(1, Math.round(n / 8));
  for (let i = 0; i < n; i += tickEvery) {
    const t = svgEl("text", { x: xAt(i), y: 298, "text-anchor": "middle", class: "axis-label" });
    t.textContent = String(points[i].age);
    svg.appendChild(t);
  }

  const bandPoints = [
    ...bandTop.map((v, i) => (v != null ? `${xAt(i)},${yAt(v)}` : null)).filter(Boolean),
    ...bandBottom.map((v, i) => (v != null ? `${xAt(i)},${yAt(v)}` : null)).filter(Boolean).reverse(),
  ].join(" ");
  svg.appendChild(svgEl("polygon", { points: bandPoints, fill: "var(--color-accent-100)" }));

  const baselinePoints = points
    .map((p, i) => (p.cohort_mean != null ? `${xAt(i)},${yAt(p.cohort_mean)}` : null))
    .filter(Boolean)
    .join(" ");
  svg.appendChild(svgEl("polyline", { points: baselinePoints, fill: "none", stroke: "var(--color-neutral-500)", "stroke-width": 1.5, "stroke-dasharray": "4,3" }));

  const linePoints = points.map((p, i) => `${xAt(i)},${yAt(p.percentile)}`).join(" ");
  svg.appendChild(svgEl("polyline", { points: linePoints, fill: "none", stroke: "var(--color-accent-2)", "stroke-width": 2.5 }));

  const showDetail = (p) => { eby(detailId).innerHTML = describeAgePoint(p); };

  points.forEach((p, i) => {
    const c = svgEl("circle", {
      cx: xAt(i), cy: yAt(p.percentile), r: p.low_confidence ? 3 : 4,
      fill: "#d6006c", opacity: p.low_confidence ? 0.4 : 1, style: "cursor: pointer;",
    });
    c.addEventListener("mouseenter", () => showDetail(p));
    c.addEventListener("click", () => showDetail(p));
    svg.appendChild(c);
  });

  const lastIdx = n - 1;
  const labelX = Math.max(padL + 30, xAt(lastIdx) - 30);
  const lineLabel = svgEl("text", { x: labelX, y: yAt(points[lastIdx].percentile) - 10, class: "axis-label", fill: "var(--color-accent-2)", "font-weight": 600, "font-size": 12 });
  lineLabel.textContent = "Percentile";
  svg.appendChild(lineLabel);

  if (points[lastIdx].cohort_mean != null) {
    const baseLabel = svgEl("text", { x: labelX, y: yAt(points[lastIdx].cohort_mean) + 16, class: "axis-label", fill: "var(--color-neutral-700)", "font-size": 12 });
    baseLabel.textContent = "League baseline (mean)";
    svg.appendChild(baseLabel);
  }

  // Face slot: place near peak-anomaly age, from the real summary.
  const face = eby(faceId);
  const peakIdx = points.findIndex((p) => p.age === summary.peak_anomaly_age);
  const faceD = 56;
  if (peakIdx >= 0 && headshotUrl) {
    const cx = xAt(peakIdx), cy = yAt(points[peakIdx].percentile) - 30;
    face.style.width = `${faceD}px`;
    face.style.height = `${faceD}px`;
    face.style.left = `${((cx - faceD / 2) / W) * 100}%`;
    face.style.top = `${((cy - faceD / 2) / H) * 100}%`;
    face.style.display = "";
    face.src = headshotUrl;
    face.onerror = () => { face.style.display = "none"; };
  } else {
    face.style.display = "none";
  }

  if (points.length) showDetail(points[points.length - 1]);
}

function renderSoloSummary(player, metricResult) {
  const s = metricResult.summary;
  const container = eby("solo-summary");
  if (s.career_anomaly_index == null) {
    container.innerHTML = `<p>${player.display_name} has no qualifying seasons for ${metricResult.display_name} under the current thresholds.</p>`;
    return;
  }
  const dir = s.career_anomaly_index >= 0 ? "above" : "below";
  container.innerHTML = `
    <p><strong>${player.display_name}</strong> — Career Anomaly Index for ${metricResult.display_name}:
      <strong>${s.career_anomaly_index.toFixed(2)} SD</strong> ${dir} the typical aging curve
      (${describeSd(s.career_anomaly_index)}).
      Peak-anomaly age: <strong>${s.peak_anomaly_age}</strong>
      · seasons in the league-wide top 5%: <strong>${s.top_5_pct_season_count}</strong>
      · qualifying seasons analyzed: ${s.qualifying_season_count}.</p>
  `;
}

async function loadSoloChart() {
  if (!soloPlayerId) return;
  clearError("solo-error");
  setLoading(true, "solo-loading");
  try {
    const metric = eby("solo-metric-select").value || "PER";
    const data = await fetchJSON(`/players/${encodeURIComponent(soloPlayerId)}/aging-curve?metrics=${encodeURIComponent(metric)}`);
    const result = data.results[0];

    const isDefaultView = soloPlayerId === lebronId && metric === "PER";
    eby("solo-title").textContent = isDefaultView
      ? "LeBron, season by season, never once acting his age"
      : `${data.player.display_name}, season by season, vs. the historical baseline`;

    // Look up a headshot for the face slot via the /compare endpoint (cheapest
    // way to get a headshot_url without a dedicated player-detail endpoint).
    let headshotUrl = null;
    try {
      const cmp = await fetchJSON(`/compare?player_ids=${encodeURIComponent(soloPlayerId)}&metric=${encodeURIComponent(metric)}`);
      headshotUrl = cmp.players[0]?.headshot_url ?? null;
    } catch (_) { /* decorative only */ }

    renderLineChart({
      svgId: "solo-chart-svg",
      faceId: "solo-face",
      detailId: "solo-point-detail",
      points: result.points,
      summary: result.summary,
      headshotUrl,
    });
    renderSoloSummary(data.player, result);
  } catch (err) {
    showError(err.message, "solo-error");
  } finally {
    setLoading(false, "solo-loading");
  }
}

function selectSoloPlayer(playerId) {
  soloPlayerId = playerId;
  return loadSoloChart();
}

// ---- Hero stats (always LeBron/PER, independent of the solo picker) -------

async function loadHeroStats() {
  try {
    const data = await fetchJSON(`/players/${encodeURIComponent(lebronId)}/aging-curve?metrics=PER`);
    const r = data.results[0];
    const zs = r.points.map((p) => p.z_score).filter((z) => z != null);
    if (!zs.length) return;
    eby("hero-sd").textContent = `+${Math.min(...zs).toFixed(1)} to +${Math.max(...zs).toFixed(1)} SD`;
  } catch (_) {
    // Decorative -- a failure here shouldn't block the rest of the page.
  }
}

// ---- Section 2: LeBron vs. the other legends (interactive roster) ---------

let compareRoster = [];

const DEFAULT_COMPARE_NAMES = [
  "LeBron James",
  "Michael Jordan",
  "Kareem Abdul-Jabbar",
  "Kobe Bryant",
  "Tim Duncan",
  "Stephen Curry",
  "Kevin Durant",
];

function shortName(displayName) {
  const parts = displayName.trim().split(/\s+/);
  const suffixes = new Set(["Jr.", "Sr.", "II", "III", "IV", "V"]);
  if (parts.length >= 2 && suffixes.has(parts[parts.length - 1])) {
    return parts.slice(-2).join(" ");
  }
  return parts[parts.length - 1];
}

function computeDomain(values, padFrac, minPad) {
  const clean = values.filter((v) => v != null && !Number.isNaN(v));
  if (!clean.length) return [0, 100];
  const min = Math.min(...clean), max = Math.max(...clean);
  const pad = Math.max((max - min) * padFrac, minPad);
  return [min - pad, max + pad];
}

// Text labels default to sitting just above each bubble. When bubbles are
// close together (e.g. two players a percentile point apart), that puts
// their labels on a collision course -- nudge later ones further up until
// they clear anything already placed.
const LABEL_H = 13;

// Approximate the label as a centered rect and test against a circle
// (another player's bubble) using closest-point distance.
function rectHitsCircle(labelX, labelY, labelW, cx, cy, r) {
  const closestX = Math.max(labelX - labelW / 2, Math.min(cx, labelX + labelW / 2));
  const closestY = Math.max(labelY - LABEL_H / 2, Math.min(cy, labelY + LABEL_H / 2));
  const dx = cx - closestX, dy = cy - closestY;
  return dx * dx + dy * dy < r * r;
}

function resolveLabelPositions(items) {
  const placed = [];
  const ordered = [...items].sort((a, b) => a.x - b.x);
  for (const item of ordered) {
    let y = item.baseY;
    let guard = 0;
    const collides = (testY) =>
      placed.some((p) => Math.abs(p.x - item.x) < (p.width / 2 + item.width / 2 + 6) && Math.abs(p.y - testY) < LABEL_H) ||
      items.some((other) => other !== item && rectHitsCircle(item.x, testY, item.width, other.x, other.y, other.r));
    while (guard++ < 20 && collides(y)) {
      y -= 6;
    }
    item.labelY = y;
    placed.push({ x: item.x, y, width: item.width });
  }
}

function describeComparePlayer(p) {
  if (p.avg_percentile == null) {
    return `
      <div class="detail-row"><span class="detail-label">Player</span><span class="detail-value">${p.display_name}</span></div>
      <div class="detail-note">No qualifying seasons for this metric.</div>
    `;
  }
  const outlier = p.career_anomaly_index != null
    ? `${p.career_anomaly_index.toFixed(2)} SD (${describeSd(p.career_anomaly_index)})`
    : "n/a";
  return `
    <div class="detail-row"><span class="detail-label">Player</span><span class="detail-value">${p.display_name}</span></div>
    <div class="detail-row"><span class="detail-label">Longevity</span><span class="detail-value">${p.qualifying_season_count} qualifying seasons</span></div>
    <div class="detail-row"><span class="detail-label">Career-avg percentile</span><span class="detail-value">${p.avg_percentile.toFixed(1)}</span></div>
    <div class="detail-row"><span class="detail-label">Outlier magnitude</span><span class="detail-value">${outlier}</span></div>
  `;
}

function renderBubbleChart(players) {
  const bx0 = 50, by0 = 20, bx1 = 610, by1 = 310;
  const W = 640, H = 380;

  const plottable = players.filter((p) => p.avg_percentile != null);
  const [domXMin, domXMax] = computeDomain(plottable.map((p) => p.qualifying_season_count), 0.15, 1);
  const [domYMin, domYMax] = computeDomain(plottable.map((p) => p.avg_percentile), 0.15, 3);
  const [sdMin, sdMax] = computeDomain(plottable.map((p) => p.career_anomaly_index), 0, 0);

  const radiusFor = (sd) => {
    if (sd == null) return 14;
    if (sdMax === sdMin) return 22;
    return 14 + ((sd - sdMin) / (sdMax - sdMin)) * 22; // 14-36px, scaled to this roster's spread
  };

  const svg = eby("bubble-chart-svg");
  svg.innerHTML = "";
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.appendChild(svgEl("line", { x1: bx0, y1: by0, x2: bx0, y2: by1, stroke: "var(--color-divider)", "stroke-width": 1 }));
  svg.appendChild(svgEl("line", { x1: bx0, y1: by1, x2: bx1, y2: by1, stroke: "var(--color-divider)", "stroke-width": 1 }));

  const xLabel = svgEl("text", { x: (bx0 + bx1) / 2, y: 345, "text-anchor": "middle", class: "axis-label" });
  xLabel.textContent = "Elite qualifying seasons (longevity) →";
  svg.appendChild(xLabel);
  const yLabel = svgEl("text", { x: 20, y: 165, "text-anchor": "middle", class: "axis-label", transform: "rotate(-90 20 165)" });
  yLabel.textContent = "Avg. percentile vs. peers →";
  svg.appendChild(yLabel);

  const facesContainer = eby("bubble-faces");
  facesContainer.innerHTML = "";

  const showDetail = (p) => { eby("compare-point-detail").innerHTML = describeComparePlayer(p); };

  const items = plottable.map((p) => {
    const x = bx0 + ((p.qualifying_season_count - domXMin) / (domXMax - domXMin)) * (bx1 - bx0);
    const y = by1 - ((p.avg_percentile - domYMin) / (domYMax - domYMin)) * (by1 - by0);
    const r = radiusFor(p.career_anomaly_index);
    const label = shortName(p.display_name);
    return { p, x, y, r, label, baseY: y - r - 8, width: label.length * 6.5 };
  });
  resolveLabelPositions(items);

  const isLebron = (p) => p.player_id === lebronId;

  items.forEach(({ p, x, y, r, label, labelY }) => {
    const fill = isLebron(p) ? "var(--color-accent-2-200)" : "var(--color-accent-100)";
    const stroke = isLebron(p) ? "var(--color-accent-2)" : "var(--color-accent-500)";

    const circle = svgEl("circle", { cx: x, cy: y, r, fill, opacity: 0.85, stroke, "stroke-width": 1.5, style: "cursor: pointer;" });
    circle.addEventListener("mouseenter", () => showDetail(p));
    circle.addEventListener("click", () => showDetail(p));
    svg.appendChild(circle);

    const text = svgEl("text", { x, y: labelY, "text-anchor": "middle", "font-size": 12, "font-weight": isLebron(p) ? 600 : 400, fill: "var(--color-text)" });
    text.textContent = label;
    svg.appendChild(text);

    const faceD = r * 1.5;
    if (p.headshot_url) {
      const img = document.createElement("img");
      img.className = "face-slot";
      img.alt = p.display_name;
      img.src = p.headshot_url;
      img.style.width = `${(faceD / W) * 100}%`;
      img.style.height = `${(faceD / H) * 100}%`;
      img.style.left = `${((x - faceD / 2) / W) * 100}%`;
      img.style.top = `${((y - faceD / 2) / H) * 100}%`;
      img.style.border = `2px solid ${stroke}`;
      img.onerror = () => { img.style.display = "none"; };
      img.addEventListener("mouseenter", () => showDetail(p));
      img.addEventListener("click", () => showDetail(p));
      facesContainer.appendChild(img);
    }
  });

  const defaultPlayer = plottable.find((p) => isLebron(p)) || plottable[0];
  if (defaultPlayer) showDetail(defaultPlayer);
}

function renderCompareRoster() {
  const container = eby("compare-roster");
  container.innerHTML = "";
  for (const p of compareRoster) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = p.display_name;
    const x = document.createElement("button");
    x.type = "button";
    x.textContent = "×";
    x.title = `Remove ${p.display_name}`;
    x.onclick = () => removeFromComparison(p.player_id);
    chip.appendChild(x);
    container.appendChild(chip);
  }
}

async function loadCompare() {
  clearError("compare-error");
  if (compareRoster.length === 0) {
    eby("bubble-chart-svg").innerHTML = "";
    eby("bubble-faces").innerHTML = "";
    return;
  }
  setLoading(true, "compare-loading");
  try {
    const metric = eby("compare-metric-select").value || "PER";
    const idsParam = compareRoster.map((p) => encodeURIComponent(p.player_id)).join(",");
    const data = await fetchJSON(`/compare?player_ids=${idsParam}&metric=${encodeURIComponent(metric)}`);
    renderBubbleChart(data.players);
  } catch (err) {
    showError(err.message, "compare-error");
  } finally {
    setLoading(false, "compare-loading");
  }
}

function addToComparison(playerId, displayName) {
  if (compareRoster.some((p) => p.player_id === playerId)) return;
  compareRoster.push({ player_id: playerId, display_name: displayName });
  renderCompareRoster();
  loadCompare();
}

function removeFromComparison(playerId) {
  compareRoster = compareRoster.filter((p) => p.player_id !== playerId);
  renderCompareRoster();
  loadCompare();
}

async function initCompareDefaults() {
  await Promise.all(
    DEFAULT_COMPARE_NAMES.map(async (name) => {
      try {
        const results = await fetchJSON(`/players?search=${encodeURIComponent(name)}&limit=1`);
        if (results.length) {
          compareRoster.push({ player_id: results[0].player_id, display_name: results[0].display_name });
        }
      } catch (_) {
        // A curated name failing to resolve is non-fatal -- skip it.
      }
    })
  );
  renderCompareRoster();
  await loadCompare();
}

// ---- Confidence bars --------------------------------------------------

async function renderConfidenceBars() {
  const data = await fetchJSON("/baseline?metric=PER");
  const buckets = [
    { range: "Ages 19–21", min: 19, max: 21 },
    { range: "Ages 22–30", min: 22, max: 30 },
    { range: "Ages 31–36", min: 31, max: 36 },
    { range: "Ages 37–40", min: 37, max: 40 },
  ];
  for (const b of buckets) {
    b.n = data.points.filter((p) => p.age >= b.min && p.age <= b.max).reduce((sum, p) => sum + p.n, 0);
  }
  const maxN = Math.max(...buckets.map((b) => b.n));

  const container = eby("confidence-bars");
  container.innerHTML = "";
  for (const b of buckets) {
    const pct = Math.max(6, (b.n / maxN) * 100);
    const isFull = b.min >= 22 && b.max <= 30;
    const isMid = b.min >= 31 && b.max <= 36;
    const fill = isFull || isMid ? "var(--color-accent)" : "var(--color-neutral-400)";
    const col = document.createElement("div");
    col.style.cssText = "flex:1; display:flex; flex-direction:column; align-items:center; gap:10px; height:100%; justify-content:flex-end;";
    col.innerHTML = `
      <div style="font-size:12px; font-weight:600;">${b.n.toLocaleString()} seasons</div>
      <div style="width:60%; border-radius:1px 1px 0 0; height:${pct}%; background:${fill};"></div>
      <div style="font-size:11px; opacity:0.7; text-align:center;">${b.range}</div>
    `;
    container.appendChild(col);
  }
}

// ---- Wiring -----------------------------------------------------------

async function init() {
  try {
    const metrics = await getMetrics();
    populateMetricSelect("solo-metric-select", metrics, "PER");
    populateMetricSelect("compare-metric-select", metrics, "PER");

    lebronId = await resolvePlayerId("LeBron James");

    eby("solo-search-btn").addEventListener("click", () =>
      searchPlayers(eby("solo-search").value, "solo-search-results", "solo-error", (id) => selectSoloPlayer(id), "View")
    );
    eby("solo-search").addEventListener("keydown", (e) => {
      if (e.key === "Enter") searchPlayers(eby("solo-search").value, "solo-search-results", "solo-error", (id) => selectSoloPlayer(id), "View");
    });
    eby("solo-metric-select").addEventListener("change", loadSoloChart);

    eby("compare-search-btn").addEventListener("click", () =>
      searchPlayers(eby("compare-search").value, "compare-search-results", "compare-error", addToComparison, "+")
    );
    eby("compare-search").addEventListener("keydown", (e) => {
      if (e.key === "Enter") searchPlayers(eby("compare-search").value, "compare-search-results", "compare-error", addToComparison, "+");
    });
    eby("compare-metric-select").addEventListener("change", loadCompare);

    await Promise.all([
      loadHeroStats(),
      selectSoloPlayer(lebronId),
      initCompareDefaults(),
      renderConfidenceBars(),
    ]);
  } catch (err) {
    console.error("Explainer page failed to load live data:", err);
  }
}

document.addEventListener("DOMContentLoaded", init);
