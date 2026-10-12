/* ══════════════════════════════════════════════════════════════
   BD Route Planner — app.js
   ══════════════════════════════════════════════════════════════ */

const API = "";   // same origin

// ── State ──────────────────────────────────────────────────────
const state = {
  graphData:      null,
  source:         null,   // { id, lat, lon }
  dest:           null,
  clickMode:      "source",  // "source" | "dest" | "view" | "block"
  algorithm:      "astar",
  scenario:       "normal",
  weights:        { distance: 1.0, traffic: 1.0, condition: 1.0, safety: 1.0 },
  animSpeed:      3,
  animTimer:      null,
  charts:         {},
  manualBlocks:   new Map(),  // edgeKey -> { u, v, k, polyline }
};

// ── Map setup ──────────────────────────────────────────────────
const map = L.map("map", {
  center:    [23.7461, 90.3742],
  zoom:      15,
  zoomControl: true,
});

// OpenStreetMap tile layer — free, no API key required
L.tileLayer(
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    subdomains: "abc",
    maxZoom: 19,
  }
).addTo(map);

// ── Leaflet layer groups ───────────────────────────────────────
const layers = {
  edges:    L.layerGroup().addTo(map),
  nodes:    L.layerGroup().addTo(map),
  explored: L.layerGroup().addTo(map),
  path:     L.layerGroup().addTo(map),
  markers:  L.layerGroup().addTo(map),
};

// ── DOM refs ───────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const dom = {
  statusText:  $("status-text"),
  statusSpinner: $("status-spinner"),
  gNodes:      $("g-nodes"),
  gEdges:      $("g-edges"),
  sourceLabel: $("source-label"),
  destLabel:   $("dest-label"),
  sourcePill:  $("source-pill"),
  destPill:    $("dest-pill"),
  runBtn:      $("run-btn"),
  runAllBtn:   $("run-all-btn"),
  clearBtn:    $("clear-btn"),
  clearPathBtn: $("clear-path-btn"),
  algoDesc:    $("algo-desc"),
  resultsPanel: $("results-panel"),
  closeResultsBtn: $("close-results-btn"),
  singleView:  $("single-result-view"),
  compareView: $("compare-view"),
  compareTbody: $("compare-tbody"),
  animSpeed:   $("anim-speed"),
  manualBlockCount: $("manual-block-count"),
  clearManualBlocksBtn: $("clear-manual-blocks-btn"),
  // stat cards
  sAlgo:       $("s-algo"),
  sDist:       $("s-dist"),
  sCost:       $("s-cost"),
  sNodes:      $("s-nodes"),
  sRuntime:    $("s-runtime"),
};

// ── Algorithm descriptions ──────────────────────────────────────
const ALGO_INFO = {
  bfs:        { label: "BFS",        costSensitive: false,
    desc: "<strong>BFS</strong> — Breadth-First Search. Finds fewest <em>hops</em>. <span class='warn-badge'>🚫 Ignores traffic/condition/safety costs.</span> Only blocked roads (condition=4) affect it. Scenarios with flooded/damaged roads will NOT change this path." },
  dfs:        { label: "DFS",        costSensitive: false,
    desc: "<strong>DFS</strong> — Depth-First Search. Dives deep first, not optimal. <span class='warn-badge'>🚫 Ignores all costs.</span> Only condition=4 blocked roads matter. Good baseline to compare against." },
  ucs:        { label: "UCS",        costSensitive: true,
    desc: "<strong>UCS</strong> — Uniform Cost Search (Dijkstra). <span class='good-badge'>✅ Fully cost-sensitive.</span> Finds true minimum-cost path. Raise Traffic/Condition/Safety weights to see it reroute around bad roads." },
  ids:        { label: "IDS",        costSensitive: false,
    desc: "<strong>IDS</strong> — Iterative Deepening Search. Minimum hops, like BFS. <span class='warn-badge'>🚫 Ignores costs.</span> Only condition=4 (blocked) roads affect the path. Shows very high node expansion count." },
  best_first: { label: "Best-First", costSensitive: true,
    desc: "<strong>Best-First</strong> — Greedy, guided by straight-line distance h(n). <span class='good-badge'>✅ Respects blocked edges.</span> Fast but not cost-optimal — ignores traffic/condition beyond blocking." },
  astar:      { label: "A★",         costSensitive: true,
    desc: "<strong>A★</strong> — <span class='good-badge'>✅ Fully cost-sensitive & optimal.</span> Uses f(n)=g(n)+h(n). Raise sliders to see it reroute: high Condition weight → avoids flooded roads; high Traffic → avoids congestion." },
};

// ── Color helpers ──────────────────────────────────────────────
function edgeColor(edge) {
  if (edge.condition === 4) return "#cc0000";   // blocked   — dark red
  if (edge.condition === 3) return "#1a56db";   // flooded   — dark blue
  if (edge.condition === 2) return "#d97706";   // damaged   — dark amber
  // color by traffic
  if (edge.traffic === 3)   return "#dc2626";   // high      — red
  if (edge.traffic === 2)   return "#ca8a04";   // medium    — dark yellow
  return "#16a34a";                             // low / good — dark green
}

function edgeWeight(edge) {
  const hw = edge.highway || "";
  if (["trunk","primary"].includes(hw))        return 4;
  if (["secondary","tertiary"].includes(hw))   return 3;
  return 2;
}

// ── Set status ─────────────────────────────────────────────────
function setStatus(msg, loading = false) {
  dom.statusText.textContent   = msg;
  dom.statusSpinner.style.display = loading ? "block" : "none";
}

// ── Update run buttons ──────────────────────────────────────────
function updateRunButtons() {
  const ready = state.source && state.dest;
  dom.runBtn.disabled    = !ready;
  dom.runAllBtn.disabled = !ready;
}

// ── Draw graph ─────────────────────────────────────────────────
function drawGraph(data) {
  layers.edges.clearLayers();
  layers.nodes.clearLayers();
  state.manualBlocks.clear();
  updateBlockCounter();

  const nodeMap = {};
  data.nodes.forEach(n => { nodeMap[n.id] = n; });

  // Draw edges
  data.edges.forEach(e => {
    const src = nodeMap[e.source];
    const tgt = nodeMap[e.target];
    if (!src || !tgt) return;

    const line = L.polyline(
      [[src.lat, src.lon], [tgt.lat, tgt.lon]],
      {
        color:     edgeColor(e),
        weight:    edgeWeight(e),
        opacity:   e.condition === 4 ? 0.95 : 0.80,
        dashArray: e.condition === 4 ? "6,4" : null,
      }
    );
    // Tooltip
    line.bindTooltip(
      `<div style="font-family:monospace;font-size:11px">
        <b>${e.name || e.highway}</b><br>
        Length: ${(e.length/1000).toFixed(2)} km<br>
        Traffic: ${ ["","Low","Medium","High"][e.traffic] }<br>
        Condition: ${ ["","Good","Damaged","Flooded","Blocked"][e.condition] }<br>
        Safety: ${ ["","Low Risk","Med Risk","High Risk"][e.safety] }
       </div>`,
      { sticky: true, className: "map-tooltip" }
    );

    // Edge click → block/unblock in block mode
    line.on("click", (ev) => {
      if (state.clickMode !== "block") return;
      L.DomEvent.stopPropagation(ev);
      toggleEdgeBlock(e, line);
    });

    // Thicken edge on hover in block mode for easy clicking
    line.on("mouseover", () => {
      if (state.clickMode !== "block") return;
      line.setStyle({ weight: edgeWeight(e) + 3, opacity: 1 });
    });
    line.on("mouseout", () => {
      if (state.clickMode !== "block") return;
      const edgeKey = `${e.source}-${e.target}-${e.key}`;
      const isBlocked = state.manualBlocks.has(edgeKey);
      line.setStyle({
        weight:    isBlocked ? edgeWeight(e) + 2 : edgeWeight(e),
        opacity:   isBlocked ? 0.95 : 0.80,
        color:     isBlocked ? "#cc0000" : edgeColor(e),
        dashArray: isBlocked ? "8,5" : (e.condition === 4 ? "6,4" : null),
      });
    });

    layers.edges.addLayer(line);
  });

  // Draw nodes as clickable circles
  data.nodes.forEach(n => {
    const circle = L.circleMarker([n.lat, n.lon], {
      radius:      5,
      fillColor:   "rgba(100,116,139,0.7)",
      color:       "rgba(255,255,255,0.15)",
      weight:      1,
      fillOpacity: 1,
    });
    circle.bindTooltip(
      `<span style="font-family:monospace;font-size:10px">Node ${n.id.slice(-6)}</span>`,
      { sticky: true }
    );
    circle.on("click", () => handleNodeClick(n));
    layers.nodes.addLayer(circle);
  });

  // Info
  dom.gNodes.textContent = data.stats.num_nodes;
  dom.gEdges.textContent = data.stats.num_edges;
}

// ── Node click handler ─────────────────────────────────────────
function handleNodeClick(node) {
  if (state.clickMode === "source") {
    state.source = node;
    dom.sourceLabel.textContent = `Node ${node.id.slice(-6)} (${node.lat.toFixed(4)}, ${node.lon.toFixed(4)})`;
    dom.sourcePill.classList.add("set");
    placeMarker("source", node);
  } else if (state.clickMode === "dest") {
    state.dest = node;
    dom.destLabel.textContent = `Node ${node.id.slice(-6)} (${node.lat.toFixed(4)}, ${node.lon.toFixed(4)})`;
    dom.destPill.classList.add("set");
    placeMarker("dest", node);
  }
  updateRunButtons();
}

// Map click → nearest node
map.on("click", async e => {
  if (state.clickMode === "view") return;
  setStatus("Finding nearest node…", true);
  try {
    const res  = await fetch(`${API}/api/nearest-node`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ lat: e.latlng.lat, lon: e.latlng.lng }),
    });
    const node = await res.json();
    node.id    = node.node_id;
    handleNodeClick(node);
    setStatus(`Node selected (${node.dist_m.toFixed(0)} m away)`);
    // Auto-advance mode: source → dest → view
    if (state.clickMode === "source") {
      document.querySelectorAll(".mode-tab").forEach(b => b.classList.remove("active"));
      document.querySelector(".mode-tab[data-mode='dest']").classList.add("active");
      state.clickMode = "dest";
    } else if (state.clickMode === "dest") {
      document.querySelectorAll(".mode-tab").forEach(b => b.classList.remove("active"));
      document.querySelector(".mode-tab[data-mode='view']").classList.add("active");
      state.clickMode = "view";
      map.getContainer().style.cursor = "default";
    }
  } catch (err) {
    setStatus("Error: " + err.message);
  }
});

// ── Place source / dest marker ────────────────────────────────
const markerOpts = {
  source: { color: "#00ff88", label: "S" },
  dest:   { color: "#ff3a6e", label: "D" },
};
const markerRefs = {};

function placeMarker(type, node) {
  if (markerRefs[type]) layers.markers.removeLayer(markerRefs[type]);

  const { color, label } = markerOpts[type];
  const icon = L.divIcon({
    className: "",
    iconSize:  [28, 28],
    iconAnchor:[14, 14],
    html: `<div style="
      width:28px;height:28px;border-radius:50%;
      background:${color};border:3px solid white;
      display:flex;align-items:center;justify-content:center;
      font-weight:800;font-size:12px;color:#000;
      box-shadow:0 0 16px ${color},0 2px 8px rgba(0,0,0,0.5);
      font-family:'Outfit',sans-serif;
    ">${label}</div>`,
  });

  const m = L.marker([node.lat, node.lon], { icon, zIndexOffset: 1000 });
  layers.markers.addLayer(m);
  markerRefs[type] = m;
}

// ── Clear route ───────────────────────────────────────────────
dom.clearBtn.addEventListener("click", () => {
  state.source = null;
  state.dest   = null;
  dom.sourceLabel.textContent = "Click map → source";
  dom.destLabel.textContent   = "Click map → destination";
  dom.sourcePill.classList.remove("set");
  dom.destPill.classList.remove("set");
  layers.markers.clearLayers();
  layers.explored.clearLayers();
  layers.path.clearLayers();
  updateRunButtons();
  hideResults();
  if (state.animTimer) { clearInterval(state.animTimer); state.animTimer = null; }
});

// ── Manual block toggle ────────────────────────────────────────
async function toggleEdgeBlock(edge, polyline) {
  const edgeKey   = `${edge.source}-${edge.target}-${edge.key}`;
  const isBlocked = state.manualBlocks.has(edgeKey);
  const action    = isBlocked ? "unblock" : "block";

  try {
    const res = await fetch(`${API}/api/block-edge`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: edge.source,
        target: edge.target,
        key:    edge.key ?? 0,
        action,
      }),
    });
    const data = await res.json();
    if (data.error) { setStatus("Block error: " + data.error); return; }

    if (action === "block") {
      // Redraw as blocked — thick dashed red
      polyline.setStyle({ color: "#cc0000", weight: edgeWeight(edge) + 2,
                          opacity: 0.95, dashArray: "8,5" });
      state.manualBlocks.set(edgeKey, { edge, polyline });
      setStatus(`🚧 Road blocked (${data.manual_blocks} manual block${data.manual_blocks !== 1 ? "s" : ""})`);
    } else {
      // Restore original style
      polyline.setStyle({ color: edgeColor(edge), weight: edgeWeight(edge),
                          opacity: 0.80, dashArray: edge.condition === 4 ? "6,4" : null });
      state.manualBlocks.delete(edgeKey);
      setStatus(`✅ Road unblocked (${data.manual_blocks} manual block${data.manual_blocks !== 1 ? "s" : ""} remaining)`);
    }
    updateBlockCounter();
  } catch (err) {
    setStatus("Block error: " + err.message);
  }
}

function updateBlockCounter() {
  const count = state.manualBlocks.size;
  dom.manualBlockCount.textContent = count;
  dom.clearManualBlocksBtn.disabled = count === 0;
}

// ── Clear all manual blocks ────────────────────────────────────
dom.clearManualBlocksBtn.addEventListener("click", async () => {
  if (state.manualBlocks.size === 0) return;
  try {
    const res  = await fetch(`${API}/api/unblock-all-manual`, {
      method: "POST", headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    // Restore visual style of all manually blocked edges
    state.manualBlocks.forEach(({ edge, polyline }) => {
      polyline.setStyle({ color: edgeColor(edge), weight: edgeWeight(edge),
                          opacity: 0.80, dashArray: null });
    });
    state.manualBlocks.clear();
    updateBlockCounter();
    setStatus(`✅ Cleared ${data.cleared} manual block${data.cleared !== 1 ? "s" : ""}`);
  } catch (err) {
    setStatus("Clear error: " + err.message);
  }
});


// ── Mode tabs ──────────────────────────────────────────────────
document.querySelectorAll(".mode-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".mode-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.clickMode = btn.dataset.mode;
    const isBlock = state.clickMode === "block";
    const isView  = state.clickMode === "view";
    map.getContainer().style.cursor = isView ? "default" : isBlock ? "crosshair" : "crosshair";
    // Show hint
    if (isBlock) setStatus("🚧 Block mode: click any road to block/unblock it.");
  });
});

// ── Algorithm buttons ──────────────────────────────────────────
document.querySelectorAll(".algo-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".algo-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.algorithm = btn.dataset.algo;
    dom.algoDesc.innerHTML = ALGO_INFO[state.algorithm]?.desc || "";
  });
});

// ── Scenario buttons ───────────────────────────────────────────
document.querySelectorAll(".scenario-btn").forEach(btn => {
  btn.addEventListener("click", async () => {
    document.querySelectorAll(".scenario-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.scenario = btn.dataset.scenario;
    await applyScenario(state.scenario);
  });
});

async function applyScenario(scenario) {
  setStatus(`Applying scenario: ${scenario}…`, true);
  try {
    const res  = await fetch(`${API}/api/apply-scenario`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ scenario }),
    });
    const data = await res.json();
    state.graphData = data;
    drawGraph(data);
    layers.explored.clearLayers();
    layers.path.clearLayers();
    hideResults();
    dom.clearPathBtn.disabled = true;

    // Show impact stats
    const imp = data.impact;
    const pct = n => Math.round(100 * n / imp.total);
    let msg = "";
    if (scenario === "normal") {
      msg = "✅ Normal: all roads clear. Pick any algorithm.";
    } else if (scenario === "flooded") {
      msg = `🌊 Flooded: ${imp.flooded} roads (${pct(imp.flooded)}%) flooded — use UCS/A* with high Condition weight to see rerouting.`;
    } else if (scenario === "road_blocked") {
      msg = `🚧 Blocked: ${imp.blocked} roads (${pct(imp.blocked)}%) impassable — ALL algorithms must reroute.`;
    } else if (scenario === "peak_hour") {
      msg = `🚗 Peak Hour: ${imp.hi_traf} roads (${pct(imp.hi_traf)}%) high traffic — use UCS/A* with high Traffic weight.`;
    } else if (scenario === "heavy_traffic") {
      msg = `🚦 Heavy Traffic: ALL ${imp.total} roads congested — use UCS/A* with high Traffic weight.`;
    } else if (scenario === "night") {
      msg = `🌙 Night: ALL roads high-risk — use UCS/A* with high Safety weight to see safer routes.`;
    } else if (scenario === "storm") {
      msg = `⛈ Storm: ${imp.flooded} roads flooded + max traffic + max risk — worst case scenario.`;
    }
    setStatus(msg);
  } catch (err) {
    setStatus("Scenario error: " + err.message);
  }
}

// ── Weight sliders ─────────────────────────────────────────────
["distance","traffic","condition","safety"].forEach(key => {
  const slider = $(`w-${key}`);
  const label  = $(`w-${key}-val`);
  slider.addEventListener("input", () => {
    const v = parseFloat(slider.value);
    state.weights[key] = v;
    label.textContent  = v.toFixed(1);
    // Update slider fill
    const pct = (v / 3) * 100;
    slider.style.setProperty("--pct", `${pct}%`);
  });
  // Init fill
  slider.style.setProperty("--pct", "33%");
});

// ── Animation speed ────────────────────────────────────────────
dom.animSpeed.addEventListener("input", () => {
  state.animSpeed = parseInt(dom.animSpeed.value);
  const lbl = $("anim-speed-val");
  if (lbl) lbl.textContent = state.animSpeed;
});

// ── Run single algorithm ───────────────────────────────────────
dom.runBtn.addEventListener("click", runSingle);
dom.runAllBtn.addEventListener("click", runAll);

// ── Clear path only (keep src/dest, keep manual blocks) ──────
dom.clearPathBtn.addEventListener("click", () => {
  if (state.animTimer) { clearInterval(state.animTimer); state.animTimer = null; }
  layers.explored.clearLayers();
  layers.path.clearLayers();
  hideResults();
  dom.clearPathBtn.disabled = true;
  setStatus("Path cleared — block roads then re-run.");
});

async function runSingle() {
  if (!state.source || !state.dest) return;
  clearVisualization();
  setStatus(`Running ${ALGO_INFO[state.algorithm]?.label || state.algorithm}…`, true);

  const body = buildRequestBody();
  body.algorithm = state.algorithm;

  try {
    const res    = await fetch(`${API}/api/run`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    });
    const result = await res.json();
    if (result.error) { setStatus("Error: " + result.error); return; }

    showSingleResult(result);
    animateExploration(result, () => drawPath(result));
  } catch (err) {
    setStatus("Run error: " + err.message);
  }
}

async function runAll() {
  if (!state.source || !state.dest) return;
  clearVisualization();
  setStatus("Running all 6 algorithms…", true);

  const body = buildRequestBody();

  try {
    const res  = await fetch(`${API}/api/run-all`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    });
    const data = await res.json();
    if (data.error) { setStatus("Error: " + data.error); return; }

    // Store all results for row-click path switching
    state.compareResults = data.results;

    showCompareResults(data.results);

    // Animate A* exploration, then draw its path
    const best = data.results["astar"] || Object.values(data.results).find(r => r.found);
    if (best && best.explored_coords && best.explored_coords.length) {
      setStatus("Animating A* exploration…", true);
      animateExploration(best, () => {
        drawPath(best);
        setStatus("All 6 algorithms complete. Click a row to see each path.");
      });
    } else if (best) {
      drawPath(best);
      setStatus("All 6 algorithms complete. Click a row to see each path.");
    } else {
      setStatus("⚠ No path found by any algorithm.");
    }
  } catch (err) {
    setStatus("Run-all error: " + err.message);
  }
}

function buildRequestBody() {
  return {
    source:      state.source.id,
    target:      state.dest.id,
    w_distance:  state.weights.distance,
    w_traffic:   state.weights.traffic,
    w_condition: state.weights.condition,
    w_safety:    state.weights.safety,
  };
}

// ── Animate exploration ────────────────────────────────────────
function animateExploration(result, onComplete) {
  const coords  = result.explored_coords;
  const DELAY   = [100, 60, 30, 15, 5][state.animSpeed - 1] || 20;
  let   idx     = 0;

  if (state.animTimer) clearInterval(state.animTimer);

  state.animTimer = setInterval(() => {
    if (idx >= coords.length) {
      clearInterval(state.animTimer);
      state.animTimer = null;
      onComplete();
      return;
    }

    const [lat, lon] = coords[idx];
    const dot = L.circleMarker([lat, lon], {
      radius:      4,
      fillColor:   "#ffd700",
      color:       "rgba(255,215,0,0.4)",
      weight:      1,
      fillOpacity: 0.8,
    });
    layers.explored.addLayer(dot);
    idx++;

    // Batch for high speeds
    if (state.animSpeed >= 4) {
      const batch = state.animSpeed === 5 ? 20 : 5;
      for (let i = 0; i < batch && idx < coords.length; i++, idx++) {
        const [lt, ln] = coords[idx];
        layers.explored.addLayer(L.circleMarker([lt, ln], {
          radius: 3, fillColor: "#ffd700",
          color: "transparent", fillOpacity: 0.6,
        }));
      }
    }

    setStatus(`Exploring… (${idx}/${coords.length} nodes)`, true);
  }, DELAY);
}

// ── Draw final path ────────────────────────────────────────────
function drawPath(result) {
  layers.path.clearLayers();
  if (!result.found || result.path_coords.length < 2) {
    setStatus("⚠ No path found between selected nodes.");
    return;
  }

  // Glow effect: draw twice
  L.polyline(result.path_coords, {
    color:  "rgba(0,212,255,0.3)",
    weight: 14,
    lineCap: "round",
    lineJoin: "round",
  }).addTo(layers.path);

  L.polyline(result.path_coords, {
    color:  "#00d4ff",
    weight: 5,
    lineCap: "round",
    lineJoin: "round",
  }).addTo(layers.path);

  const s = result.stats;
  setStatus(
    `Path found! ${s.distance_km} km · Cost: ${s.total_cost.toFixed(3)} · ${s.nodes_expanded} nodes · ${s.runtime_ms} ms`
  );
  dom.clearPathBtn.disabled = false;

  // Fit map to path
  const bounds = L.latLngBounds(result.path_coords);
  map.fitBounds(bounds, { padding: [60, 60] });
}

// ── Show single result ─────────────────────────────────────────
function showSingleResult(result) {
  const s = result.stats;
  dom.sAlgo.textContent    = ALGO_INFO[result.algorithm]?.label || result.algorithm;
  dom.sDist.textContent    = result.found ? s.distance_km : "—";
  dom.sCost.textContent    = result.found ? s.total_cost.toFixed(3) : "—";
  dom.sNodes.textContent   = s.nodes_expanded;
  dom.sRuntime.textContent = s.runtime_ms;

  dom.singleView.style.display = "block";
  dom.compareView.style.display = "none";
  showResults();
}

// ── Show comparison results ────────────────────────────────────
const ALGO_ORDER = ["bfs","dfs","ucs","ids","best_first","astar"];
const ALGO_LABELS = { bfs:"BFS", dfs:"DFS", ucs:"UCS", ids:"IDS", best_first:"Best-First", astar:"A★" };

function showCompareResults(results) {
  dom.singleView.style.display = "none";
  dom.compareView.style.display = "block";

  // Table
  dom.compareTbody.innerHTML = "";

  // Find best cost among found paths
  const foundResults = ALGO_ORDER.filter(a => results[a]?.found);
  const bestCost  = Math.min(...foundResults.map(a => results[a].stats.total_cost));

  ALGO_ORDER.forEach(algo => {
    const r = results[algo];
    if (!r) return;
    const s = r.stats;
    const isBest = r.found && s.total_cost === bestCost;

    const tr = document.createElement("tr");
    if (isBest) tr.classList.add("best-row");
    tr.classList.add("compare-row");
    tr.dataset.algo = algo;
    if (!r.found) tr.classList.add("not-found-row");
    tr.innerHTML = `
      <td>${ALGO_LABELS[algo]}${isBest ? " 🏆" : ""}</td>
      <td>${r.found ? "✅ Yes" : "❌ No"}</td>
      <td>${r.found ? s.distance_km : "—"}</td>
      <td>${r.found ? s.total_cost.toFixed(3) : "—"}</td>
      <td>${s.nodes_expanded}</td>
      <td>${s.runtime_ms}</td>
    `;

    // Click row → show that algo's path on map
    if (r.found) {
      tr.addEventListener("click", () => {
        // Highlight active row
        document.querySelectorAll(".compare-row").forEach(row => row.classList.remove("row-active"));
        tr.classList.add("row-active");
        // Animate exploration then draw path
        clearVisualization();
        setStatus(`Showing ${ALGO_LABELS[algo]} path…`, true);
        animateExploration(r, () => {
          drawPath(r);
          setStatus(`${ALGO_LABELS[algo]}: ${s.distance_km} km · Cost ${s.total_cost.toFixed(3)} · ${s.nodes_expanded} nodes expanded`);
        });
      });
    }

    dom.compareTbody.appendChild(tr);
  });

  // Charts
  renderCharts(results);
  showResults();
}

// ── Charts ─────────────────────────────────────────────────────
function renderCharts(results) {
  const labels = ALGO_ORDER.map(a => ALGO_LABELS[a]);
  const colors = ["#3b82f6","#ef4444","#10b981","#f59e0b","#a78bfa","#00d4ff"];

  const getVals = key => ALGO_ORDER.map(a =>
    results[a]?.found ? results[a].stats[key] : 0
  );

  const chartDefs = [
    { id: "chart-cost",     label: "Total Cost",       key: "total_cost",     yLabel: "Cost" },
    { id: "chart-nodes",    label: "Nodes Expanded",   key: "nodes_expanded", yLabel: "Nodes" },
    { id: "chart-runtime",  label: "Runtime (ms)",     key: "runtime_ms",     yLabel: "ms" },
    { id: "chart-distance", label: "Distance (km)",    key: "distance_km",    yLabel: "km" },
  ];

  chartDefs.forEach(def => {
    const canvas = $(def.id);
    const existing = state.charts[def.id];
    if (existing) existing.destroy();

    state.charts[def.id] = new Chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label:           def.label,
          data:            getVals(def.key),
          backgroundColor: colors.map(c => c + "99"),
          borderColor:     colors,
          borderWidth:     2,
          borderRadius:    6,
        }],
      },
      options: {
        responsive:         true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          title:  { display: true, text: def.label,
                    color: "#94a3b8", font: { size: 11, family: "Outfit" } },
        },
        scales: {
          x: {
            ticks: { color: "#64748b", font: { size: 10 } },
            grid:  { color: "rgba(255,255,255,0.05)" },
          },
          y: {
            beginAtZero: true,
            ticks: { color: "#64748b", font: { size: 10 } },
            grid:  { color: "rgba(255,255,255,0.05)" },
            title: { display: true, text: def.yLabel,
                     color: "#64748b", font: { size: 10 } },
          },
        },
      },
    });
  });
}

// ── Results panel show/hide ────────────────────────────────────
function showResults() {
  dom.resultsPanel.classList.remove("panel-hidden");
  dom.resultsPanel.classList.add("panel-visible");
}
function hideResults() {
  dom.resultsPanel.classList.remove("panel-visible");
  dom.resultsPanel.classList.add("panel-hidden");
}
dom.closeResultsBtn.addEventListener("click", hideResults);

// ── Clear visualization layers ─────────────────────────────────
function clearVisualization() {
  layers.explored.clearLayers();
  layers.path.clearLayers();
  if (state.animTimer) { clearInterval(state.animTimer); state.animTimer = null; }
}

// ── Initial graph load (with timeout + retry) ───────────────────
async function loadGraph(attempt = 1) {
  const MAX_ATTEMPTS = 3;
  const TIMEOUT_MS   = 8000;

  setStatus(`Loading road network${attempt > 1 ? ` (attempt ${attempt}/${MAX_ATTEMPTS})` : ""}…`, true);
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const res = await fetch(`${API}/api/graph`, { signal: controller.signal });
    clearTimeout(timer);

    const data = await res.json();
    state.graphData = data;
    drawGraph(data);
    setStatus(`Ready — ${data.stats.num_nodes} nodes, ${data.stats.num_edges} edges. Click map to set source/destination.`);
  } catch (err) {
    if (attempt < MAX_ATTEMPTS) {
      setStatus(`Graph load failed (${err.message}). Retrying in 2s…`, true);
      setTimeout(() => loadGraph(attempt + 1), 2000);
    } else {
      setStatus(`⚠ Failed to load graph after ${MAX_ATTEMPTS} attempts: ${err.message}`);
    }
  }
}

// ── Boot ───────────────────────────────────────────────────────
map.getContainer().style.cursor = "crosshair";
loadGraph();
