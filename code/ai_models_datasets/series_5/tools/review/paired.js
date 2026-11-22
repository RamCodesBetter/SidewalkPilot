"use strict";
lucide.createIcons();
const data = window.PAIRED_DATA, $ = id => document.getElementById(id);
if (data?.kind !== "sidewalkpilot-paired-class1-v1" || data.count !== data.pairs.length) throw Error("Invalid paired package");
const key = "sidewalkpilot:paired:" + data.package_id;
const states = {unreviewed:"Unreviewed", correct:"Correct", needs_correction:"Needs correction", uncertain:"Uncertain"};
const correctionLevels = {1:"Minor fixes", 2:"Moderate fixes", 3:"Major fixes"};
const efforts = ["not_estimated", "none", "minor", "major"];
let decisions = {}, index = 0, active = "A", zoom = 100, loading = true, revision = 0, syncing = false;
let inspectionTimes = {}, lastTick = performance.now(), lastActivity = performance.now();
let pendingCorrection = null;
const pair = () => data.pairs[index];
const entry = (item, side) => decisions[item.id]?.[side];
const reviewed = (item, side) => entry(item, side)?.decision && entry(item, side).decision !== "unreviewed";
const complete = item => reviewed(item, "A") && reviewed(item, "B");
const message = text => { $("message").textContent = text; };

function validateDecisions(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw Error("Invalid decisions");
  for (const [id, sides] of Object.entries(value)) {
    const item = data.pairs.find(p => p.id === id);
    if (!item || !sides || typeof sides !== "object" || Array.isArray(sides)) throw Error("Unknown pair");
    for (const [side, record] of Object.entries(sides)) {
      if (!["A", "B"].includes(side) || !record || !Object.hasOwn(states, record.decision)
          || record.mask_sha256 !== item.candidates[side].mask_sha256
          || typeof record.notes !== "string" || !efforts.includes(record.effort)) throw Error("Invalid decision or mask identity");
      if (record.correction_level != null && (record.decision !== "needs_correction" || ![1,2,3].includes(record.correction_level))) throw Error("Invalid correction level");
    }
  }
  return value;
}
function validateTimes(value = {}) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw Error("Invalid inspection times");
  for (const [id, sides] of Object.entries(value)) {
    if (!data.pairs.some(p => p.id === id) || !sides || typeof sides !== "object" || Array.isArray(sides)) throw Error("Unknown timing pair");
    for (const [side, seconds] of Object.entries(sides)) {
      if (!["A", "B"].includes(side) || typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) throw Error("Invalid inspection duration");
    }
  }
  return value;
}
function tick() {
  const now = performance.now(), elapsed = (now - lastTick) / 1000;
  lastTick = now;
  if (loading || document.hidden || !document.hasFocus() || now - lastActivity > 60000 || elapsed < 0 || elapsed > 3) return;
  inspectionTimes[pair().id] ||= {};
  inspectionTimes[pair().id][active] = (inspectionTimes[pair().id][active] || 0) + elapsed;
}
for (const event of ["pointerdown", "keydown", "input", "wheel"]) {
  document.addEventListener(event, () => { tick(); lastActivity = performance.now(); }, {capture:true, passive:true});
}
window.addEventListener("blur", () => { lastTick = performance.now(); });
window.addEventListener("focus", () => { lastTick = lastActivity = performance.now(); });
document.addEventListener("visibilitychange", () => { lastTick = performance.now(); });
setInterval(() => { tick(); persist(); }, 1000);
function persist() {
  try { localStorage.setItem(key, JSON.stringify({decisions, index, active, inspectionTimes})); $("saved").textContent = "Saved locally"; }
  catch { $("saved").textContent = "Not saved"; message("Browser storage unavailable. Export decisions before closing."); }
}
function totals() {
  const entries = Object.values(decisions).flatMap(s => Object.values(s));
  $("progress").textContent = data.pairs.filter(complete).length + " / " + data.count + " pairs";
  $("decisions-count").textContent = entries.filter(r => r.decision !== "unreviewed").length + " / " + data.count * 2 + " decisions";
  $("correct-count").textContent = entries.filter(r => r.decision === "correct").length + " marked correct";
}
function refresh() {
  for (const side of ["A", "B"]) {
    const state = entry(pair(), side)?.decision || "unreviewed";
    const level = entry(pair(), side)?.correction_level;
    $("status-" + side).textContent = state === "needs_correction" && level != null ? correctionLevels[level] : states[state];
    $("pane-" + side).classList.toggle("active", side === active);
    document.querySelector(`.side[data-side="${side}"]`).setAttribute("aria-pressed", String(side === active));
    document.querySelectorAll(`.decisions[data-side="${side}"] button`).forEach(button => {
      if (button.dataset.decision === "unreviewed") button.removeAttribute("aria-pressed");
      else button.setAttribute("aria-pressed", String(button.dataset.decision === state));
      button.disabled = loading;
    });
  }
  $("detail-heading").textContent = "Candidate " + active;
  $("notes").value = entry(pair(), active)?.notes || "";
  $("effort").value = entry(pair(), active)?.effort || "not_estimated";
  $("notes").disabled = $("effort").disabled = loading;
  $("previous").disabled = index === 0;
  $("next").disabled = index === data.count - 1;
  $("position").value = index + 1;
  $("total").textContent = "/ " + data.count;
  $("position").max = data.count;
  totals();
}
function select(side) { tick(); active = side; refresh(); persist(); }
function store(side, change) {
  decisions[pair().id] ||= {};
  decisions[pair().id][side] = {...{decision:"unreviewed", notes:"", effort:"not_estimated", correction_level:null},
    ...entry(pair(), side), ...change, mask_sha256:pair().candidates[side].mask_sha256, updated_utc:new Date().toISOString()};
  persist(); totals();
}
async function decide(side, decision) {
  if (loading) return;
  tick();
  const level = decision === "needs_correction" ? entry(pair(), side)?.correction_level ?? null : null;
  active = side; store(side, {decision, correction_level:level}); refresh();
  if (decision === "needs_correction") {
    pendingCorrection = {id:pair().id, side};
    $("correction-context").textContent = `Candidate ${side} / image ${index + 1} of ${data.count}`;
    document.querySelectorAll('[data-level]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.level) === level)));
    $("correction-dialog").showModal();
    document.querySelector(`[data-level="${level || 1}"]`).focus();
    return;
  }
  if (decision !== "unreviewed") await advanceAfterDecision(side);
}
async function advanceAfterDecision(side) {
  const other = side === "A" ? "B" : "A";
  // Always hand A to B, including when B has a rating from an earlier visit.
  if (side === "A" || !reviewed(pair(), other)) {
    select(other);
    $("stage-" + other).focus({preventScroll:true});
  } else if ($("auto").checked && index < data.count - 1) await show(index + 1);
}
function closeCorrection() {
  pendingCorrection = null;
  if ($("correction-dialog").open) $("correction-dialog").close();
}
async function setCorrectionLevel(level) {
  if (loading || ![1,2,3].includes(level) || !$("correction-dialog").open
      || pendingCorrection?.id !== pair().id) return;
  const side = pendingCorrection.side;
  if (entry(pair(), side)?.decision !== "needs_correction") return;
  store(side, {correction_level:level});
  closeCorrection(); refresh();
  await advanceAfterDecision(side);
}
document.querySelectorAll('[data-level]').forEach(button => button.onclick = () => setCorrectionLevel(Number(button.dataset.level)));
$("close-correction").onclick = closeCorrection;
$("correction-dialog").addEventListener('cancel', () => { pendingCorrection = null; });
function draw() {
  const mode = document.querySelector('input[name="mode"]:checked').value;
  for (const side of ["A", "B"]) {
    const canvas = $("canvas-" + side), [width, height] = pair().size;
    canvas.width = width; canvas.height = height;
    canvas.style.display = mode === "source" ? "none" : "block";
    canvas.style.opacity = mode === "overlay" ? Number($("opacity").value) / 100 : 1;
    const ctx = canvas.getContext("2d"), pixels = ctx.createImageData(width, height);
    const rle = pair().candidates[side].rle;
    let offset = 0, value = rle.first;
    if (![0, 1].includes(value)) throw Error("Invalid mask RLE");
    for (const length of rle.lengths) {
      if (!Number.isSafeInteger(length) || length <= 0 || offset + length > width * height) throw Error("Invalid mask run");
      for (let i = offset; i < offset + length; i++) {
        const p = i * 4;
        pixels.data[p] = value ? 54 : 28; pixels.data[p+1] = value ? 189 : 33;
        pixels.data[p+2] = value ? 138 : 36; pixels.data[p+3] = value || mode === "mask" ? 255 : 0;
      }
      offset += length; value = 1 - value;
    }
    if (offset !== width * height) throw Error("Incomplete mask RLE");
    ctx.putImageData(pixels, 0, 0);
  }
}
function setZoom(value) {
  zoom = Math.max(100, Math.min(400, value)); $("zoom-value").textContent = zoom + "%";
  for (const side of ["A", "B"]) $("box-" + side).style.width = zoom + "%";
  $("zoom-out").disabled = zoom === 100; $("zoom-in").disabled = zoom === 400;
}
async function show(position) {
  tick();
  closeCorrection();
  index = Math.max(0, Math.min(data.count - 1, Math.trunc(Number(position)) || 0));
  active = reviewed(pair(), "A") && !reviewed(pair(), "B") ? "B" : "A";
  const token = ++revision;
  loading = true; document.body.classList.add("loading"); refresh(); persist();
  $("filename").textContent = (pair().source_pair_id ? pair().source_pair_id + " / " : "") + pair().source_name;
  for (const side of ["A", "B"]) { $("stage-" + side).scrollTo(0, 0); $("image-" + side).src = pair().image; }
  try {
    await Promise.all([$("image-A").decode(), $("image-B").decode()]);
    if (token !== revision) return;
    for (const side of ["A", "B"]) {
      if ($("image-" + side).naturalWidth !== pair().size[0] || $("image-" + side).naturalHeight !== pair().size[1]) throw Error("Source dimensions differ");
    }
    draw(); loading = false; lastTick = performance.now(); document.body.classList.remove("loading"); refresh();
  } catch (error) { if (token === revision) message("Cannot load pair: " + error.message); }
}
$("previous").onclick = () => show(index - 1);
$("next").onclick = () => show(index + 1);
$("pending").onclick = () => {
  const next = data.pairs.findIndex((p, i) => i > index && !complete(p));
  const first = data.pairs.findIndex(p => !complete(p));
  if (first < 0) message("All pairs reviewed."); else show(next >= 0 ? next : first);
};
$("position").onchange = () => show(Number($("position").value) - 1);
$("position").onkeydown = event => {
  if (event.key === "Enter") { event.preventDefault(); event.stopPropagation(); show(Number($("position").value) - 1); }
};
document.querySelectorAll(".side").forEach(button => button.onclick = () => select(button.dataset.side));
document.querySelectorAll(".decisions button").forEach(button => button.onclick = () => decide(button.parentElement.dataset.side, button.dataset.decision));
for (const side of ["A", "B"]) {
  $("stage-" + side).onpointerdown = () => select(side);
  $("stage-" + side).onscroll = event => {
    if (syncing) return; syncing = true;
    const other = $("stage-" + (side === "A" ? "B" : "A"));
    other.scrollLeft = event.target.scrollLeft; other.scrollTop = event.target.scrollTop;
    requestAnimationFrame(() => { syncing = false; });
  };
}
document.querySelectorAll('input[name="mode"]').forEach(input => input.onchange = draw);
$("opacity").oninput = () => { $("opacity-value").textContent = $("opacity").value + "%"; draw(); };
$("zoom-in").onclick = () => setZoom(zoom + 50); $("zoom-out").onclick = () => setZoom(zoom - 50);
$("fit").onclick = () => setZoom(100);
$("notes").oninput = () => { if (!loading) store(active, {notes:$("notes").value}); };
$("effort").onchange = () => { if (!loading) store(active, {effort:$("effort").value}); };
document.addEventListener("keydown", event => {
  if (event.repeat || event.ctrlKey || event.metaKey || event.altKey || event.target.closest("input,textarea,select,[contenteditable=true]")) return;
  if ($("correction-dialog").open) {
    if (["1", "2", "3"].includes(event.key)) { event.preventDefault(); setCorrectionLevel(Number(event.key)); }
    else if (["Enter", "ArrowRight", "ArrowLeft"].includes(event.key)) event.preventDefault();
    return;
  }
  const decision = {"1":"correct", "2":"needs_correction", "3":"uncertain"}[event.key];
  if (decision) { event.preventDefault(); decide(active, decision); }
  else if (["Enter", "ArrowRight", "ArrowLeft"].includes(event.key)) {
    event.preventDefault(); show(index + (event.key === "ArrowLeft" ? -1 : 1));
  }
});
$("export").onclick = () => {
  tick();
  const value = {kind:"sidewalkpilot-paired-review-v1", package_id:data.package_id,
    selection_sha256:data.selection_sha256, review_scope:data.review_scope, created_utc:new Date().toISOString(),
    complete:data.pairs.every(complete), decisions, inspection_active_seconds:inspectionTimes,
    review_ui_version:"paired-correction-levels-v2",
    timing_method:"Focused visible selected-candidate time; 60-second inactivity cutoff; timer gaps above 3 seconds excluded. Not correction time."};
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type:"application/json"}));
  const link = document.createElement("a"); link.href = url; link.download = "sidewalkpilot-paired-review.json"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$("import").onclick = () => $("import-file").click();
$("import-file").onchange = async event => {
  try {
    const file = event.target.files[0]; if (!file) return;
    const value = JSON.parse(await file.text());
    if (value.kind !== "sidewalkpilot-paired-review-v1" || value.package_id !== data.package_id
        || value.selection_sha256 !== data.selection_sha256
        || JSON.stringify(value.review_scope) !== JSON.stringify(data.review_scope)) throw Error("Review belongs to another package or scope");
    const incoming = validateDecisions(value.decisions);
    const incomingTimes = validateTimes(value.inspection_active_seconds);
    if (Object.keys(decisions).length && !confirm("Replace this package's local decisions with this import?")) return;
    decisions = incoming; inspectionTimes = incomingTimes; lastTick = performance.now(); persist(); refresh(); message("Decisions imported.");
  } catch (error) { message(error.message); }
  finally { event.target.value = ""; }
};
$("clear").onclick = () => {
  if (!confirm("Clear decisions for this paired review only? Images and masks will not change.")) return;
  decisions = {}; inspectionTimes = {}; lastTick = performance.now(); persist(); refresh(); message("This review's decisions were cleared.");
};
try {
  const saved = JSON.parse(localStorage.getItem(key) || "null");
  if (saved) { decisions = validateDecisions(saved.decisions); inspectionTimes = validateTimes(saved.inspectionTimes); index = Number.isInteger(saved.index) ? saved.index : 0; }
} catch { message("Saved review could not be loaded. Import an exported review to recover it."); }
setZoom(100); show(index);
