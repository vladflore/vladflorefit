/* ── Workout Logger ─────────────────────────────────────────────────── */

const EXPORT_KEY = "flexary_export";
const LOG_PREFIX = "flexary_log_";

/* ── State ───────────────────────────────────────────────────────────── */
let workout = null; // workout object from export
let log = null; // log being built
const unit = "kg";
let timers = {}; // timerKey → { raf }
let autosaveTimeout = null;

/* ── Boot ────────────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(location.search);
  const wid = params.get("wid");

  const raw = wid ? localStorage.getItem(EXPORT_KEY) : null;
  let payload;
  try {
    payload = raw ? JSON.parse(raw) : null;
  } catch {
    payload = null;
  }
  workout = (payload?.workouts || []).find((w) => w.id === wid) || null;

  if (!workout) {
    showState("error", "No workout data found.");
    return;
  }

  // Restore or init log, then reconcile with current workout definition
  const saved = localStorage.getItem(LOG_PREFIX + wid);
  if (saved) {
    try {
      log = JSON.parse(saved);
    } catch {
      log = null;
    }
  }
  log = log ? mergeLog(log, workout) : initLog(workout);

  render();
});

/* ── Init a fresh log ────────────────────────────────────────────────── */
// For superset exercises, each round is logged as a separate set entry.
// So the effective set count is max(ex.sets, rounds).
function parseDistTarget(raw) {
  if (!raw) return { target_dist: "", target_dist_unit: "" };
  const m = raw.trim().match(/^([0-9]*\.?[0-9]*)\s*([a-zA-Z]*)$/);
  return m
    ? { target_dist: m[1] || "", target_dist_unit: m[2] || "" }
    : { target_dist: raw, target_dist_unit: "" };
}

function effectiveSets(ex, w) {
  if (!ex.superset_id) return ex.sets;
  const ss = w.supersets?.find((s) => s.id === ex.superset_id);
  return Math.max(ex.sets || 1, ss?.rounds || 1);
}

function initLog(w) {
  return {
    workout_id: w.id,
    started_at: localISOString(),
    completed_at: null,
    exercises: w.exercises.map((ex) => ({
      id: ex.id,
      name: ex.name,
      superset_id: ex.superset_id || null,
      notes: "",
      sets: Array.from({ length: effectiveSets(ex, w) }, (_, i) => ({
        set: i + 1,
        target_reps: ex.reps?.[i] ?? "",
        target_time: ex.time?.[i] ?? "",
        ...parseDistTarget(ex.distance?.[i]),
        actual_reps: "",
        actual_time: "",
        actual_dist: "",
        weight: "",
        done: false,
      })),
    })),
  };
}

/* ── Merge saved log with current workout definition ─────────────────── */
// Preserves user-entered data (reps, weight, done, notes) for exercises and
// sets that still exist, while reflecting any structural changes made to the
// workout since logging began: new/removed exercises, set count changes,
// updated targets (reps, time, distance), superset reassignments.
function mergeLog(savedLog, w) {
  return {
    ...savedLog,
    exercises: w.exercises.map((ex) => {
      const existing = savedLog.exercises.find(
        (l) => l.id === ex.id && l.name === ex.name,
      );

      // Reconcile sets: update targets; keep user data for sets that still exist
      const sets = Array.from({ length: effectiveSets(ex, w) }, (_, i) => {
        const s = existing?.sets[i];
        return {
          set: i + 1,
          target_reps: ex.reps?.[i] ?? "",
          target_time: ex.time?.[i] ?? "",
          ...parseDistTarget(ex.distance?.[i]),
          actual_reps: s?.actual_reps ?? "",
          actual_time: s?.actual_time ?? "",
          actual_dist: s?.actual_dist ?? "",
          weight: s?.weight ?? "",
          done: s?.done ?? false,
        };
      });

      return existing
        ? { ...existing, superset_id: ex.superset_id || null, sets }
        : {
            id: ex.id,
            name: ex.name,
            superset_id: ex.superset_id || null,
            notes: "",
            sets,
          };
    }),
  };
}

/* ── Main render ─────────────────────────────────────────────────────── */
function render() {
  document.getElementById("wl-workout-name").textContent = workout.name;
  document.getElementById("wl-workout-date").textContent = fmtDate(
    workout.scheduled_date,
  );
  document.getElementById("wl-topbar-back").href = "index.html";

  renderExercises();
  updateProgress();
}

/* ── Collapse helper ─────────────────────────────────────────────────── */
// Wires a trigger element to toggle the "collapsed" class on body,
// and "rotated" on the first .wl-collapse-chevron inside trigger.
function wireCollapsible(trigger, body) {
  const chevron = trigger.querySelector(".wl-collapse-chevron");
  trigger.setAttribute("role", "button");
  trigger.setAttribute("tabindex", "0");
  const toggle = () => {
    const collapsed = body.classList.toggle("collapsed");
    chevron?.classList.toggle("rotated", collapsed);
  };
  trigger.addEventListener("click", toggle);
  trigger.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
  });
}

/* ── Build a flat render plan ────────────────────────────────────────── */
// Each item is one of:
//   { type:'rest',         secs, label }
//   { type:'round-header', round, total }
//   { type:'superset-ex',  ex, roundIndex }
//   { type:'single',       ex }
function buildRenderPlan() {
  const plan = [];
  const processedSS = new Set();
  let firstItem = true;

  for (const ex of workout.exercises) {
    if (ex.superset_id) {
      if (processedSS.has(ex.superset_id)) continue;
      processedSS.add(ex.superset_id);

      const ssExes = workout.exercises.filter(
        (e) => e.superset_id === ex.superset_id,
      );
      const ss = workout.supersets?.find((s) => s.id === ex.superset_id);
      const rounds = ss?.rounds || 1;

      // Rest before the superset block.
      // May be on the superset object OR on the first exercise of the superset
      // (both map to "before this superset starts" in the original app UI).
      const restBeforeSS =
        ss?.rest_before_seconds || ssExes[0]?.rest_before_seconds || 0;
      if (!firstItem && restBeforeSS) {
        plan.push({ type: "rest", secs: restBeforeSS });
      }
      firstItem = false;

      plan.push({ type: "superset-block-start", rounds });

      for (let r = 0; r < rounds; r++) {
        plan.push({ type: "round-header", round: r + 1, total: rounds });
        plan.push({ type: "round-start" });

        ssExes.forEach((ssEx, exIdx) => {
          if (exIdx > 0 && ssEx.rest_before_seconds) {
            plan.push({ type: "rest", secs: ssEx.rest_before_seconds });
          }
          plan.push({ type: "superset-ex", ex: ssEx, roundIndex: r });
        });

        plan.push({ type: "round-end" });

        // Rest sits between round blocks (outside the collapsible round body)
        if (r < rounds - 1 && ss?.rest_after_seconds) {
          plan.push({ type: "rest", secs: ss.rest_after_seconds });
        }
      }

      plan.push({ type: "superset-block-end" });
    } else {
      if (!firstItem && ex.rest_before_seconds) {
        plan.push({ type: "rest", secs: ex.rest_before_seconds });
      }
      firstItem = false;
      plan.push({ type: "single", ex });
    }
  }

  return plan;
}

/* ── Render exercises from plan ──────────────────────────────────────── */
function renderExercises() {
  const container = document.getElementById("wl-exercises");
  container.innerHTML = "";

  let ssContentEl = null; // collapsible div for the whole superset body
  let roundContentEl = null; // collapsible div for the current round
  let pendingRoundHdr = null; // round header waiting to be wired to its content

  // Resolved append target: inside a round → roundContentEl,
  // inside a superset (no open round) → ssContentEl, else → container
  const target = () => roundContentEl ?? ssContentEl ?? container;

  buildRenderPlan().forEach((item) => {
    switch (item.type) {
      case "superset-block-start": {
        const wrap = document.createElement("div");
        wrap.className = "wl-superset-block";

        const hdr = document.createElement("div");
        hdr.className = "wl-superset-block-header";
        hdr.innerHTML =
          `<i class="bi bi-intersect"></i>` +
          `<span>Superset · ${item.rounds} round${item.rounds !== 1 ? "s" : ""}</span>` +
          `<i class="bi bi-chevron-down wl-collapse-chevron ms-auto"></i>`;

        const ssBody = document.createElement("div");
        ssBody.className = "wl-collapsible-body";
        ssContentEl = ssBody;

        wireCollapsible(hdr, ssBody);

        wrap.append(hdr, ssBody);
        container.appendChild(wrap);
        break;
      }

      case "superset-block-end":
        ssContentEl = null;
        break;

      case "round-header": {
        const hdr = roundHeader(item.round, item.total);
        ssContentEl.appendChild(hdr);
        pendingRoundHdr = hdr;
        break;
      }

      case "round-start": {
        roundContentEl = document.createElement("div");
        roundContentEl.className = "wl-collapsible-body";
        if (pendingRoundHdr) {
          wireCollapsible(pendingRoundHdr, roundContentEl);
          pendingRoundHdr = null;
        }
        ssContentEl.appendChild(roundContentEl);
        break;
      }

      case "round-end":
        roundContentEl = null;
        break;

      case "rest":
        target().appendChild(buildRestRow(item.secs));
        break;

      case "superset-ex":
        target().appendChild(exerciseCard(item.ex, item.roundIndex));
        break;

      case "single":
        target().appendChild(exerciseCard(item.ex));
        break;
    }
  });
}

/* ── Round header ────────────────────────────────────────────────────── */
function roundHeader(round, total) {
  const el = document.createElement("div");
  el.className = "wl-round-header";
  el.innerHTML =
    `<span class="wl-round-pill">` +
    `<span class="wl-round-label">Round ${round} / ${total}</span>` +
    `<i class="bi bi-chevron-down wl-collapse-chevron"></i>` +
    `</span>` +
    `<span class="wl-round-line"></span>`;
  return el;
}

/* ── Exercise card ───────────────────────────────────────────────────── */
// roundIndex: undefined  → show all sets (single exercise)
// roundIndex: number     → show only that round's set (superset)
function exerciseCard(ex, roundIndex) {
  const isSupersetCard = roundIndex !== undefined;
  const logEx = log.exercises.find((l) => l.id === ex.id && l.name === ex.name);

  const card = document.createElement("div");
  card.className = "wl-exercise-card";

  // ── Header (acts as collapse toggle) ──
  const header = document.createElement("div");
  header.className = "wl-exercise-header";

  const titleWrap = document.createElement("div");
  titleWrap.className = "wl-exercise-title-wrap";

  const nameRow = document.createElement("div");
  nameRow.className = "wl-exercise-name-row";

  const nameEl = document.createElement("div");
  nameEl.className = "wl-exercise-name";
  nameEl.textContent = ex.name;
  nameRow.appendChild(nameEl);

  const hasInfo = ex.video_url || ex.instructions || ex.key_cues?.length;
  if (hasInfo) {
    const infoBtn = document.createElement("button");
    infoBtn.className = "wl-info-btn";
    infoBtn.setAttribute("aria-label", "Exercise info");
    infoBtn.innerHTML = '<i class="bi bi-info-circle"></i>';
    infoBtn.onclick = (e) => {
      e.stopPropagation();
      openInfoModal(ex);
    };
    nameRow.appendChild(infoBtn);
  }

  const meta = document.createElement("div");
  meta.className = "wl-exercise-meta";
  meta.innerHTML = (!isSupersetCard && ex.sets > 1) ? `<span>${ex.sets} sets</span>` : "";

  titleWrap.append(nameRow, meta);

  const headerChevron = document.createElement("i");
  headerChevron.className = "bi bi-chevron-down wl-collapse-chevron";

  header.append(titleWrap, headerChevron);

  // ── Collapsible body ──
  const cardBody = document.createElement("div");
  cardBody.className = "wl-collapsible-body";
  wireCollapsible(header, cardBody);

  // ── Sets table ──
  const restSecs = isSupersetCard ? 0 : ex.rest_between_sets_seconds || 0;
  const table = buildSetsTable(ex, logEx, roundIndex, restSecs);

  // ── Notes ──
  const notesToggle = document.createElement("button");
  notesToggle.className = "wl-notes-toggle" + (logEx.notes ? " open" : "");
  notesToggle.innerHTML =
    `<i class="bi bi-chat-left-text"></i><span>Notes</span>` +
    `<i class="bi bi-chevron-down ms-auto"></i>`;

  const notesArea = document.createElement("div");
  notesArea.className = "wl-notes-area" + (logEx.notes ? " open" : "");

  const notesInput = document.createElement("textarea");
  notesInput.className = "wl-notes-input";
  notesInput.placeholder = "Add notes for this exercise…";
  notesInput.value = logEx.notes || "";
  notesInput.rows = 2;
  notesInput.oninput = () => {
    logEx.notes = notesInput.value;
    scheduleAutosave();
  };
  notesArea.appendChild(notesInput);

  notesToggle.onclick = (e) => {
    e.stopPropagation(); // don't collapse the card when clicking notes
    const open = notesArea.classList.toggle("open");
    notesToggle.classList.toggle("open", open);
  };

  cardBody.appendChild(table);
  cardBody.append(notesToggle, notesArea);

  card.append(header, cardBody);

  return card;
}

/* ── Sets table ──────────────────────────────────────────────────────── */
// roundIndex: undefined → render all rows; number → render only that row
// restSecs: if > 0, a rest row is inserted after each set except the last
function buildSetsTable(ex, logEx, roundIndex, restSecs = 0) {
  const hasWeight = !ex.time?.some(Boolean) && !ex.distance?.some(Boolean);
  const hasReps = ex.reps?.some(Boolean) || hasWeight;
  const hasTime = ex.time?.some(Boolean);
  const hasDist = ex.distance?.some(Boolean);

  const table = document.createElement("table");
  table.className = "wl-sets-table";

  // Head — hide "Set #" column in superset mode (always round 1 row)
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headRow.className = "wl-sets-head";

  if (roundIndex === undefined) {
    const thSet = document.createElement("th");
    thSet.textContent = "Set";
    headRow.appendChild(thSet);
  }

  const thTarget = document.createElement("th");
  thTarget.textContent = "Target";
  headRow.appendChild(thTarget);

  if (hasReps) {
    const th = document.createElement("th");
    th.textContent = "Reps";
    headRow.appendChild(th);
  }
  if (hasTime) {
    const th = document.createElement("th");
    th.textContent = "Time";
    headRow.appendChild(th);
  }
  if (hasDist) {
    const th = document.createElement("th");
    th.textContent = "Dist";
    headRow.appendChild(th);
  }
  if (hasWeight) {
    const th = document.createElement("th");
    th.textContent = unit;
    th.className = "wl-weight-header";
    headRow.appendChild(th);
  }

  const thDone = document.createElement("th");
  thDone.textContent = "✓";
  headRow.appendChild(thDone);

  thead.appendChild(headRow);
  table.appendChild(thead);

  // Body
  const tbody = document.createElement("tbody");

  // Which set indices to render
  const indices =
    roundIndex !== undefined ? [roundIndex] : logEx.sets.map((_, i) => i);

  indices.forEach((i, loopIdx) => {
    const setLog = logEx.sets[i];
    const tr = document.createElement("tr");
    tr.className = "wl-set-row" + (setLog.done ? " is-done-row" : "");

    if (roundIndex === undefined) {
      const tdNum = document.createElement("td");
      tdNum.className = "wl-set-num";
      tdNum.textContent = i + 1;
      tr.appendChild(tdNum);
    }

    const tdTarget = document.createElement("td");
    tdTarget.className = "wl-set-target";
    const targetParts = [
      setLog.target_reps ? `${setLog.target_reps} reps` : "",
      setLog.target_time || "",
      setLog.target_dist ? `${setLog.target_dist}${setLog.target_dist_unit ? " " + setLog.target_dist_unit : ""}` : "",
    ].filter(Boolean);
    tdTarget.textContent = targetParts.join(" / ") || "—";
    tr.appendChild(tdTarget);

    if (hasReps) {
      const td = document.createElement("td");
      const inp = setInput("numeric", setLog.actual_reps, (val) => {
        setLog.actual_reps = val;
        checkInputFilled(inp, val);
        scheduleAutosave();
      });
      td.appendChild(inp);
      tr.appendChild(td);
    }
    if (hasTime) {
      const td = document.createElement("td");
      const inp = timeInput(setLog.actual_time, (val) => {
        setLog.actual_time = val;
        scheduleAutosave();
      });
      td.appendChild(inp);
      tr.appendChild(td);
    }
    if (hasDist) {
      const td = document.createElement("td");
      const wrap = document.createElement("div");
      wrap.className = "wl-unit-input";
      const inp = setInput("decimal", setLog.actual_dist, (val) => {
        setLog.actual_dist = val;
        checkInputFilled(inp, val);
        scheduleAutosave();
      });
      const distUnitLabel = setLog.target_dist_unit || "";
      if (distUnitLabel) {
        const lbl = document.createElement("span");
        lbl.className = "wl-unit-label";
        lbl.textContent = distUnitLabel;
        wrap.append(inp, lbl);
      } else {
        wrap.appendChild(inp);
      }
      td.appendChild(wrap);
      tr.appendChild(td);
    }
    if (hasWeight) {
      const td = document.createElement("td");
      const inp = setInput("decimal", setLog.weight, (val) => {
        setLog.weight = val;
        checkInputFilled(inp, val);
        scheduleAutosave();
      });
      td.appendChild(inp);
      tr.appendChild(td);
    }

    const tdDone = document.createElement("td");
    const doneBtn = document.createElement("button");
    doneBtn.className = "wl-set-done-btn" + (setLog.done ? " done" : "");
    doneBtn.innerHTML = '<i class="bi bi-check-lg"></i>';
    doneBtn.onclick = () => {
      setLog.done = !setLog.done;
      doneBtn.classList.toggle("done", setLog.done);
      tr.classList.toggle("is-done-row", setLog.done);
      updateProgress();
      scheduleAutosave();
    };
    tdDone.appendChild(doneBtn);
    tr.appendChild(tdDone);

    tbody.appendChild(tr);

    // Rest row after every set except the last
    if (restSecs > 0 && loopIdx < indices.length - 1) {
      const restTr = document.createElement("tr");
      restTr.className = "wl-rest-between-sets-row";
      const restTd = document.createElement("td");
      restTd.setAttribute("colspan", "10");
      restTd.appendChild(
        buildRestRow(restSecs, {
          key: `sets_${ex.id}_${ex.name}_${i}`,
          inline: true,
        }),
      );
      restTr.appendChild(restTd);
      tbody.appendChild(restTr);
    }
  });

  table.appendChild(tbody);
  return table;
}

function setInput(mode, value, onChange) {
  const input = document.createElement("input");
  input.type = "text";
  input.inputMode = mode;
  input.pattern = mode === "decimal" ? "[0-9]*[.,]?[0-9]*" : "[0-9]*";
  input.className = "wl-set-input" + (value ? " filled" : "");
  input.value = value || "";
  input.addEventListener("input", () => onChange(input.value));
  return input;
}

function checkInputFilled(input, val) {
  input.classList.toggle("filled", !!val);
}

// Renders three small h / m / s inputs. Stores value as "H:MM:SS" string.
// Auto-advances focus after 2 digits; backspace on empty field goes back.
function timeInput(value, onChange) {
  const parts = (value || "").split(":").map((p) => p.replace(/^0+/, "") || "");
  const [initH = "", initM = "", initS = ""] = parts;

  const wrap = document.createElement("div");
  wrap.className = "wl-time-input" + (value ? " filled" : "");

  const mkSeg = (placeholder, initVal, maxVal, prev) => {
    const inp = document.createElement("input");
    inp.type = "text";
    inp.inputMode = "numeric";
    inp.pattern = "[0-9]*";
    inp.maxLength = 2;
    inp.placeholder = placeholder;
    inp.className = "wl-time-seg";
    inp.value = initVal;

    inp.addEventListener("input", () => {
      inp.value = inp.value.replace(/\D/g, "");
      if (inp.value !== "" && Number(inp.value) > maxVal)
        inp.value = String(maxVal);
      flush();
    });

    inp.addEventListener("keydown", (e) => {
      if (e.key === "Backspace" && inp.value === "" && prev) {
        e.preventDefault();
        prev.focus();
      }
    });

    return inp;
  };

  const hInp = mkSeg("h", initH, 99, null);
  const mInp = mkSeg("m", initM, 59, hInp);
  const sInp = mkSeg("s", initS, 59, mInp);

  // Wire auto-advance now that all three exist
  hInp.addEventListener("input", () => { if (hInp.value.length === 2) mInp.focus(); });
  mInp.addEventListener("input", () => { if (mInp.value.length === 2) sInp.focus(); });

  const flush = () => {
    const h = hInp.value, m = mInp.value, s = sInp.value;
    const val = (h || m || s)
      ? `${h || "0"}:${(m || "0").padStart(2, "0")}:${(s || "0").padStart(2, "0")}`
      : "";
    wrap.classList.toggle("filled", !!val);
    onChange(val);
  };

  wrap.append(hInp, document.createTextNode(":"), mInp, document.createTextNode(":"), sInp);
  return wrap;
}

/* ── Unified rest row ────────────────────────────────────────────────── */
// inline: false → standalone row (between exercises/supersets/rounds)
// inline: true  → inside an exercise card (between sets)
function buildRestRow(secs, { key = null, inline = false } = {}) {
  const el = document.createElement("div");
  el.className = "wl-rest-badge" + (inline ? " wl-rest-badge--inline" : "");

  const timerKey = key ?? "rest_" + Math.random().toString(36).slice(2);

  const unit = secs < 60 ? "s" : "min";

  el.innerHTML =
    `<div class="wl-rest-fill"></div>` +
    `<i class="bi bi-hourglass-split wl-rest-icon"></i>` +
    `<span class="wl-rest-time">Rest <span class="wl-rest-time-val">${fmtSecs(secs)}</span> ${unit}</span>` +
    `<button class="wl-rest-timer-btn">Start</button>`;

  const btn = el.querySelector(".wl-rest-timer-btn");
  const timeSpan = el.querySelector(".wl-rest-time-val");
  const fill = el.querySelector(".wl-rest-fill");

  btn.onclick = (e) => {
    if (inline) e.stopPropagation();

    if (timers[timerKey]) {
      // Stop — cancel animation, reset to full
      cancelAnimationFrame(timers[timerKey].raf);
      delete timers[timerKey];
      timeSpan.textContent = fmtSecs(secs);
      fill.style.transition = "none";
      fill.style.width = "100%";
      btn.textContent = "Start";
      return;
    }

    // Start — drive bar and text from the same elapsed time via RAF
    btn.textContent = "Stop";
    const startTime = performance.now();
    let lastDisplaySecs = secs;
    timeSpan.textContent = fmtSecs(secs);

    const tick = (now) => {
      const elapsed = (now - startTime) / 1000;
      const remaining = secs - elapsed;

      if (remaining <= 0) {
        fill.style.transition = "none";
        fill.style.width = "0%";
        timeSpan.textContent = fmtSecs(0);
        btn.textContent = "Start";
        delete timers[timerKey];
        showToast("Rest over — go!");
        return;
      }

      // Bar: update every frame without CSS transition
      fill.style.transition = "none";
      fill.style.width = (remaining / secs) * 100 + "%";

      // Text: update only when the displayed second changes
      const displaySecs = Math.ceil(remaining);
      if (displaySecs !== lastDisplaySecs) {
        lastDisplaySecs = displaySecs;
        timeSpan.textContent = fmtSecs(displaySecs);
      }

      timers[timerKey].raf = requestAnimationFrame(tick);
    };

    timers[timerKey] = { raf: requestAnimationFrame(tick) };
  };

  return el;
}


/* ── Progress bar ────────────────────────────────────────────────────── */
function updateProgress() {
  const { total, done } = countSets();
  const pct = total ? Math.round((done / total) * 100) : 0;
  const fill = document.getElementById("wl-progress-fill");
  const lbl = document.getElementById("wl-progress-label");
  if (fill) fill.style.width = pct + "%";
  if (lbl) lbl.textContent = `${done} / ${total} sets`;
}

/* ── Set counting ─────────────────────────────────────────────────────── */
function countSets() {
  const total = log.exercises.reduce((s, e) => s + e.sets.length, 0);
  const done = log.exercises.reduce((s, e) => s + e.sets.filter((st) => st.done).length, 0);
  return { total, done };
}

/* ── Autosave ─────────────────────────────────────────────────────────── */
function scheduleAutosave() {
  clearTimeout(autosaveTimeout);
  autosaveTimeout = setTimeout(saveLog, 500);
}

function saveLog() {
  localStorage.setItem(LOG_PREFIX + workout.id, JSON.stringify(log));
}

/* ── Finish ───────────────────────────────────────────────────────────── */
function finish() {
  const { total, done } = countSets();
  if (done < total) {
    const remaining = total - done;
    const msg = `${remaining} set${remaining !== 1 ? "s" : ""} not yet marked as done. Finish anyway?`;
    document.getElementById("wl-confirm-msg").textContent = msg;
    document.getElementById("wl-confirm-modal").hidden = false;
    return;
  }

  saveWorkout();
}

function saveWorkout() {
  log.completed_at = localISOString();
  saveLog();
  showToast("Workout saved!");
}

/* ── Confirm modal ────────────────────────────────────────────────────── */
function wlConfirmOk() {
  document.getElementById("wl-confirm-modal").hidden = true;
  saveWorkout();
}

function wlConfirmCancel() {
  document.getElementById("wl-confirm-modal").hidden = true;
}

/* ── Error / empty states ────────────────────────────────────────────── */
function showState(type, html) {
  const icon = type === "error" ? "bi-exclamation-circle" : "bi-inbox";
  document.getElementById("wl-root").innerHTML =
    `<div class="wl-state"><i class="bi ${icon}"></i><p>${html}</p></div>`;
}

/* ── Toast ────────────────────────────────────────────────────────────── */
function showToast(msg) {
  const toast = document.getElementById("wl-toast");
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2200);
}

/* ── Helpers ──────────────────────────────────────────────────────────── */
function localISOString() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const offset = -d.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const absOff = Math.abs(offset);
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` +
    `${sign}${pad(Math.floor(absOff / 60))}:${pad(absOff % 60)}`
  );
}

function fmtSecs(s) {
  if (!s || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function fmtDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

/* ── Collapse / expand all ────────────────────────────────────────────── */
let allCollapsed = false;

function toggleAll() {
  allCollapsed = !allCollapsed;

  document.querySelectorAll(".wl-collapsible-body").forEach((el) => {
    el.classList.toggle("collapsed", allCollapsed);
  });
  document.querySelectorAll(".wl-collapse-chevron").forEach((el) => {
    el.classList.toggle("rotated", allCollapsed);
  });

  const btn = document.getElementById("wl-collapse-all");
  const icon = btn.querySelector("i");
  const text = btn.querySelector("span");
  if (allCollapsed) {
    icon.className = "bi bi-arrows-expand";
    text.textContent = "Expand all";
  } else {
    icon.className = "bi bi-arrows-collapse";
    text.textContent = "Collapse all";
  }
}

/* ── Exercise info modal ─────────────────────────────────────────────── */
function ytEmbedUrl(url) {
  if (!url) return null;
  const m = url.match(/[?&]v=([^&]+)/);
  return m ? `https://www.youtube.com/embed/${m[1]}` : null;
}

function openInfoModal(ex) {
  const modal = document.getElementById("wl-info-modal");
  const title = document.getElementById("wl-info-title");
  const body = document.getElementById("wl-info-body");

  title.textContent = ex.name;
  body.innerHTML = "";

  // Video
  const embedUrl = ytEmbedUrl(ex.video_url);
  const wrap = document.createElement("div");
  wrap.className = "wl-info-video-wrap";
  if (embedUrl) {
    const iframe = document.createElement("iframe");
    iframe.src = embedUrl;
    iframe.setAttribute("allowfullscreen", "");
    iframe.setAttribute("loading", "lazy");
    iframe.setAttribute(
      "allow",
      "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
    );
    wrap.appendChild(iframe);
  } else {
    wrap.classList.add("wl-info-video-placeholder");
    wrap.innerHTML =
      '<i class="bi bi-camera-video-off"></i><span>No video available</span>';
  }
  body.appendChild(wrap);

  // Instructions
  if (ex.instructions) {
    const sec = document.createElement("div");
    sec.className = "wl-info-section";
    const h = document.createElement("h4");
    h.className = "wl-info-section-title";
    h.textContent = "Instructions";
    const p = document.createElement("p");
    p.className = "wl-info-instructions";
    p.textContent = ex.instructions;
    sec.append(h, p);
    body.appendChild(sec);
  }

  // Key cues
  if (ex.key_cues?.length) {
    const sec = document.createElement("div");
    sec.className = "wl-info-section";
    const h = document.createElement("h4");
    h.className = "wl-info-section-title";
    h.textContent = "Key Cues";
    const ul = document.createElement("ul");
    ul.className = "wl-info-cues";
    ex.key_cues.forEach((cue) => {
      const li = document.createElement("li");
      li.textContent = cue;
      ul.appendChild(li);
    });
    sec.append(h, ul);
    body.appendChild(sec);
  }

  modal.hidden = false;
}

function closeInfoModal() {
  const modal = document.getElementById("wl-info-modal");
  modal.hidden = true;
  // Clear body to stop any playing video
  document.getElementById("wl-info-body").innerHTML = "";
}

/* ── Expose to HTML ──────────────────────────────────────────────────── */
window.wlFinish = finish;
window.wlConfirmOk = wlConfirmOk;
window.wlConfirmCancel = wlConfirmCancel;
window.wlToggleAll = toggleAll;
window.wlCloseInfo = closeInfoModal;
