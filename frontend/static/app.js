const el = (id) => document.getElementById(id);

let chart = null;
let currentPlayerId = null;
let currentPlayerName = null;

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

function showError(msg) {
  const box = el("error");
  box.textContent = msg;
  box.hidden = false;
}

function clearError() {
  el("error").hidden = true;
}

function setLoading(isLoading) {
  el("loading").hidden = !isLoading;
}

async function loadMetrics() {
  const metrics = await fetchJSON("/metrics");
  const select = el("metric-select");
  select.innerHTML = "";
  for (const m of metrics) {
    const opt = document.createElement("option");
    opt.value = m.key;
    opt.textContent = m.unit ? `${m.display_name} (${m.unit})` : m.display_name;
    select.appendChild(opt);
  }
  if ([...select.options].some((o) => o.value === "PTS")) {
    select.value = "PTS";
  }
}

async function searchPlayers(query) {
  clearError();
  const container = el("search-results");
  container.innerHTML = "";
  if (!query.trim()) return;

  try {
    const results = await fetchJSON(`/players?search=${encodeURIComponent(query)}&limit=12`);
    if (results.length === 0) {
      container.textContent = "No players found.";
      return;
    }
    for (const p of results) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "player-result";
      btn.textContent = `${p.display_name} (${p.first_season}–${p.last_season})`;
      btn.onclick = () => selectPlayer(p.player_id, p.display_name);
      container.appendChild(btn);
    }
  } catch (err) {
    showError(err.message);
  }
}

function renderChart(metricResult) {
  const ctx = el("chart").getContext("2d");
  const points = metricResult.points;

  const labels = points.map((p) => p.age);
  const playerPct = points.map((p) => p.percentile);
  const upper = points.map((p) =>
    p.cohort_mean != null ? Math.min(100, p.cohort_mean + p.cohort_std) : null
  );
  const lower = points.map((p) =>
    p.cohort_mean != null ? Math.max(0, p.cohort_mean - p.cohort_std) : null
  );
  const pointColors = points.map((p) => (p.low_confidence ? "#ff8a3d99" : "#4fd1c5"));
  const pointRadius = points.map((p) => (p.low_confidence ? 3 : 4.5));

  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Baseline +1 SD",
          data: upper,
          borderColor: "rgba(154,165,184,0)",
          pointRadius: 0,
          fill: false,
          tension: 0.3,
          order: 3,
        },
        {
          label: "League baseline range",
          data: lower,
          borderColor: "rgba(154,165,184,0)",
          backgroundColor: "rgba(154,165,184,0.16)",
          pointRadius: 0,
          fill: "-1",
          tension: 0.3,
          order: 3,
        },
        {
          label: metricResult.display_name,
          data: playerPct,
          borderColor: "#4fd1c5",
          backgroundColor: "#4fd1c5",
          pointBackgroundColor: pointColors,
          pointRadius,
          tension: 0.3,
          fill: false,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: "Age", color: "#9aa5b8" }, ticks: { color: "#9aa5b8" }, grid: { color: "#2a3346" } },
        y: {
          title: { display: true, text: "Within-season percentile", color: "#9aa5b8" },
          min: 0,
          max: 100,
          ticks: { color: "#9aa5b8" },
          grid: { color: "#2a3346" },
        },
      },
      plugins: {
        legend: { labels: { color: "#e8ecf4" } },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => {
              if (ctx.datasetIndex !== 2) return "";
              const p = points[ctx.dataIndex];
              const z = p.z_score != null ? `z = ${p.z_score.toFixed(2)}` : "z = n/a (no baseline at this age)";
              const conf = p.low_confidence ? " — low-confidence age (small historical sample)" : "";
              return [`Season ${p.season}`, `Raw value: ${p.value.toFixed(1)}`, z + conf];
            },
          },
        },
      },
    },
  });
}

function renderSummary(player, metricResult) {
  const s = metricResult.summary;
  const container = el("summary");

  if (s.career_anomaly_index == null) {
    container.innerHTML = `<p>${player.display_name} has no qualifying seasons for ${metricResult.display_name} under the current thresholds.</p>`;
    return;
  }

  const dir = s.career_anomaly_index >= 0 ? "above" : "below";
  container.innerHTML = `
    <p><strong>${player.display_name}</strong> — Career Anomaly Index for ${metricResult.display_name}:
      <strong>${s.career_anomaly_index.toFixed(2)} SD</strong> ${dir} the typical aging curve.</p>
    <p>Peak-anomaly age: <strong>${s.peak_anomaly_age}</strong>
      &nbsp;·&nbsp; Seasons in the league-wide top 5%: <strong>${s.top_5_pct_season_count}</strong>
      &nbsp;·&nbsp; Qualifying seasons analyzed: ${s.qualifying_season_count}</p>
  `;
}

async function loadPlayer() {
  if (!currentPlayerId) return;
  clearError();
  setLoading(true);
  try {
    const metric = el("metric-select").value || "PTS";
    const data = await fetchJSON(
      `/players/${encodeURIComponent(currentPlayerId)}/aging-curve?metrics=${encodeURIComponent(metric)}`
    );
    const result = data.results[0];
    el("current-player").textContent = `${data.player.display_name} — ${result.display_name}`;
    renderChart(result);
    renderSummary(data.player, result);
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

function selectPlayer(playerId, displayName) {
  currentPlayerId = playerId;
  currentPlayerName = displayName;
  return loadPlayer();
}

async function init() {
  await loadMetrics();

  el("search-btn").addEventListener("click", () => searchPlayers(el("player-search").value));
  el("player-search").addEventListener("keydown", (e) => {
    if (e.key === "Enter") searchPlayers(el("player-search").value);
  });
  el("metric-select").addEventListener("change", loadPlayer);

  try {
    const results = await fetchJSON("/players?search=lebron james&limit=1");
    if (results.length) {
      await selectPlayer(results[0].player_id, results[0].display_name);
    } else {
      showError("Default player (LeBron James) not found in the cache — try searching for another player.");
    }
  } catch (err) {
    showError("Could not load the default player: " + err.message);
  }
}

document.addEventListener("DOMContentLoaded", init);
