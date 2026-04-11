// ---------------------------------------------------------------------------
// Pyodide PDF Worker — started immediately so Pyodide + packages are warm by
// the time the user opens the PDF modal and clicks Download.
// ---------------------------------------------------------------------------

(function startPdfWorker() {
  let worker = null;
  let workerReady = false;
  const pending = new Map(); // id → { resolve, reject, btnEl, iconEl, origClass }
  let nextId = 0;

  function getWorker() {
    if (!worker) {
      worker = new Worker('./src/js/pyodide-worker.js');
      worker.onmessage = (event) => {
        const { type, id, bytes, message } = event.data;

        if (type === 'ready') {
          workerReady = true;
          return;
        }

        const job = pending.get(id);
        if (!job) return;
        pending.delete(id);

        if (type === 'pdf-result') {
          job.resolve(bytes);
        } else if (type === 'pdf-error') {
          job.reject(new Error(message));
        }
      };
      worker.onerror = (err) => {
        // Reject all pending jobs on fatal worker error.
        for (const [, job] of pending) job.reject(err);
        pending.clear();
        worker = null;
      };
    }
    return worker;
  }

  function generatePdfViaWorker(payload) {
    return new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, { resolve, reject });
      const w = getWorker();
      const transfer = payload.logoBytes instanceof Uint8Array
        ? [payload.logoBytes.buffer]
        : [];
      w.postMessage({ type: 'generate-pdf', id, payload }, transfer);
    });
  }

  // Attach PDF download button handler once the DOM is ready.
  document.addEventListener('DOMContentLoaded', () => {
    // Kick off worker initialisation immediately (pre-warm).
    getWorker();

    const pdfDownloadBtn = document.getElementById('pdf-download-btn');
    if (!pdfDownloadBtn) return;

    pdfDownloadBtn.addEventListener('click', async () => {
      // 1. Flush pending DOM inputs into localStorage via Python helper.
      if (typeof window.flexaryFlushForPdf === 'function') {
        try { window.flexaryFlushForPdf(); } catch (_) {}
      }

      // 2. Read modal options.
      const bwBtn = document.getElementById('pdf-bw-btn');
      const blackAndWhite = bwBtn
        ? bwBtn.classList.contains('pdf-toggle-btn--active')
        : false;

      const siteInput = document.getElementById('pdf-link-input');
      const siteUrl = siteInput ? siteInput.value.trim() : '';

      const borderColorInput = document.getElementById('pdf-border-color-input');
      const borderColor =
        borderColorInput && !borderColorInput.disabled
          ? borderColorInput.value
          : '';

      // 3. Read logo bytes (must happen before modal closes which resets the input).
      let logoBytes = null;
      const logoInput = document.getElementById('pdf-logo-input');
      if (logoInput && logoInput.files && logoInput.files.length > 0) {
        try {
          const buf = await logoInput.files[0].arrayBuffer();
          logoBytes = new Uint8Array(buf);
        } catch (_) {}
      }

      // 4. Close the modal.
      const modal = document.getElementById('pdf-color-modal');
      if (modal) modal.close();

      // 5. Show spinner on the sidebar Download button.
      const sidebarBtn = document.getElementById('download-workouts');
      const sidebarIcon = sidebarBtn ? sidebarBtn.querySelector('i') : null;
      const origClass = sidebarIcon ? sidebarIcon.className : '';
      if (sidebarIcon) sidebarIcon.className = 'bi bi-arrow-repeat spin';
      if (sidebarBtn) sidebarBtn.disabled = true;

      try {
        // 6. Collect workout + catalog + locale data for the worker.
        const workoutsJson =
          localStorage.getItem('workouts') || '[]';
        const catalogJson =
          typeof window.flexaryCatalogJson === 'string'
            ? window.flexaryCatalogJson
            : '{}';
        const localeJson = JSON.stringify(window.flexaryI18n || {});
        const isAuthenticated = !!(
          window.flexaryAuth &&
          window.flexaryAuth.state &&
          window.flexaryAuth.state.user
        ) || !!localStorage.getItem('flexary_auth_session');

        // 7. Dispatch to the worker and await bytes.
        const pdfBytes = await generatePdfViaWorker({
          workoutsJson,
          catalogJson,
          localeJson,
          isAuthenticated,
          blackAndWhite,
          siteUrl,
          borderColor,
          logoBytes,
        });

        // 8. Trigger browser download from the main thread.
        const blob = new Blob([pdfBytes], { type: 'application/pdf' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        const ts = new Date()
          .toLocaleString('en-GB', { hour12: false })
          .replace(/[/,: ]/g, (c) => (c === '/' ? '' : c === ' ' ? '_' : ''));
        anchor.download = `workouts_${ts}.pdf`;
        anchor.href = url;
        anchor.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        console.error('PDF generation failed:', err);
      } finally {
        if (sidebarIcon) sidebarIcon.className = origClass;
        if (sidebarBtn) sidebarBtn.disabled = false;
      }
    });
  });
})();

// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", function () {
  const pdfColorModal = document.getElementById("pdf-color-modal");
  document.getElementById("pdf-color-modal-close").addEventListener("click", () => pdfColorModal.close());
  pdfColorModal.addEventListener("click", (e) => { if (e.target === pdfColorModal) pdfColorModal.close(); });
  pdfColorModal.addEventListener("close", () => {
    const input = document.getElementById("pdf-logo-input");
    if (input) input.value = "";
    const filename = document.getElementById("pdf-logo-filename");
    if (filename) filename.textContent = "";
    const clearBtn = document.getElementById("pdf-logo-clear");
    if (clearBtn) clearBtn.style.display = "none";
    const linkInput = document.getElementById("pdf-link-input");
    if (linkInput) linkInput.value = "";
    const borderColorInput = document.getElementById("pdf-border-color-input");
    if (borderColorInput) { borderColorInput.value = "#ba945e"; borderColorInput.disabled = false; }
  });
  const pdfColorBtn = document.getElementById("pdf-color-btn");
  const pdfBwBtn = document.getElementById("pdf-bw-btn");
  pdfColorBtn.addEventListener("click", () => {
    pdfColorBtn.classList.add("pdf-toggle-btn--active"); pdfBwBtn.classList.remove("pdf-toggle-btn--active");
    const bci = document.getElementById("pdf-border-color-input");
    if (bci) bci.disabled = false;
  });
  pdfBwBtn.addEventListener("click", () => {
    pdfBwBtn.classList.add("pdf-toggle-btn--active"); pdfColorBtn.classList.remove("pdf-toggle-btn--active");
    const bci = document.getElementById("pdf-border-color-input");
    if (bci) bci.disabled = true;
  });
  const infoModal = document.getElementById("info-modal");
  document.getElementById("info-modal-close").addEventListener("click", () => infoModal.close());
  document.getElementById("info-modal-close-btn").addEventListener("click", () => infoModal.close());
  infoModal.addEventListener("click", (e) => { if (e.target === infoModal) infoModal.close(); });
  const sidebar = document.getElementById("workout-sidebar");
  const toggleBtn = document.getElementById("toggle-workout-sidebar");
  const sidebarBackdrop = document.getElementById("sidebar-backdrop");
  const mobileSidebarQuery = window.matchMedia("(max-width: 991px)");

  function updateButtonIcon() {
    const hidden = sidebar.classList.contains("d-none");
    const icon = toggleBtn.querySelector("i");
    if (icon) icon.className = hidden ? "bi bi-layout-sidebar-inset" : "bi bi-x-lg";
    const i18n = window.flexaryI18n || {};
    toggleBtn.title = hidden
      ? (i18n.show_workouts || "Show Workouts")
      : (i18n.hide_workouts || "Hide Workouts");
    toggleBtn.setAttribute("aria-label", toggleBtn.title);
    toggleBtn.setAttribute("aria-expanded", String(!hidden));
  }

  function setSidebarVisibility(hidden) {
    sidebar.classList.toggle("d-none", hidden);
    sidebarBackdrop.classList.add("d-none");
    updateButtonIcon();
  }

  function closeSidebar() {
    setSidebarVisibility(true);
  }

  toggleBtn.addEventListener("click", function () {
    setSidebarVisibility(!sidebar.classList.contains("d-none"));
  });

  sidebarBackdrop.addEventListener("click", closeSidebar);
  mobileSidebarQuery.addEventListener("change", () => {
    setSidebarVisibility(sidebar.classList.contains("d-none"));
  });

  window.flexarySidebar = {
    setHidden: setSidebarVisibility,
    toggle() {
      setSidebarVisibility(!sidebar.classList.contains("d-none"));
    },
    refreshButton: updateButtonIcon,
  };

  setSidebarVisibility(sidebar.classList.contains("d-none"));

  const filterToggleBtn = document.getElementById("filter-toggle-btn");
  const filterRow = document.getElementById("filter-row");
  if (filterToggleBtn && filterRow) {
    filterToggleBtn.addEventListener("click", function () {
      const isOpen = filterRow.classList.toggle("filter-panel-open");
      filterToggleBtn.setAttribute("aria-expanded", isOpen);
      filterToggleBtn.querySelector(".filter-toggle-chevron").style.transform = isOpen ? "rotate(180deg)" : "";
    });
  }

  const pmToggle = document.getElementById("primary-muscle-filter-toggle");
  const pmBody = document.getElementById("primary-muscle-filter-body");
  if (pmToggle && pmBody) {
    pmToggle.addEventListener("click", function () {
      const isOpen = pmBody.classList.toggle("is-open");
      pmToggle.setAttribute("aria-expanded", isOpen);
    });
  }

  const gdprBanner = document.getElementById("gdpr-banner");
  const gdprAccept = document.getElementById("gdpr-accept");
  if (!localStorage.getItem("gdprAccepted")) {
    gdprBanner.classList.remove("d-none");
  }
  gdprAccept.addEventListener("click", function () {
    localStorage.setItem("gdprAccepted", "true");
    gdprBanner.classList.add("d-none");
  });

  const scrollTopBtn = document.getElementById("scroll-top-btn");
  window.addEventListener("scroll", function () {
    if (window.scrollY > 300) {
      scrollTopBtn.classList.remove("d-none");
    } else {
      scrollTopBtn.classList.add("d-none");
    }
  });

  const sideActions = document.getElementById("side-actions");
  const sideActionsHandle = document.getElementById("side-actions-handle");
  if (sideActions && sideActionsHandle) {
    function setSideActionsOpen(isOpen) {
      sideActions.classList.toggle("is-open", isOpen);
      sideActionsHandle.setAttribute("aria-expanded", String(isOpen));
    }
    sideActionsHandle.addEventListener("click", function (e) {
      e.stopPropagation();
      setSideActionsOpen(!sideActions.classList.contains("is-open"));
    });
    document.addEventListener("click", function (e) {
      if (!sideActions.contains(e.target)) {
        setSideActionsOpen(false);
      }
    });
  }

  const langSelect = document.getElementById("lang-select");
  const langSelectTrigger = document.getElementById("lang-select-trigger");
  const langSelectMenu = document.getElementById("lang-select-menu");
  const langSelectCurrentCode = document.getElementById("lang-select-current-code");
  if (langSelect) {
    const SUPPORTED = ["en", "es", "ca", "de"];
    const LANG_META = {
      en: { label: "English", flag: "🇬🇧", isSvg: false },
      es: { label: "Español", flag: "🇪🇸", isSvg: false },
      ca: { label: "Català", flag: "./assets/flags/catalonia.svg", isSvg: true },
      de: { label: "Deutsch", flag: "🇩🇪", isSvg: false }
    };
    const stored = localStorage.getItem("flexary_lang");
    const nav = (navigator.language || "en").split("-")[0].toLowerCase();
    langSelect.value = (stored && SUPPORTED.includes(stored))
      ? stored
      : (SUPPORTED.includes(nav) ? nav : "en");
    function renderSelectedLang(value) {
      const meta = LANG_META[value] || LANG_META.en;
      if (langSelectCurrentCode) {
        langSelectCurrentCode.textContent = value.toUpperCase();
      }
      if (langSelectTrigger) {
        langSelectTrigger.setAttribute("aria-label", meta.label);
      }
      const options = document.querySelectorAll(".lang-select-option");
      options.forEach((option) => {
        option.classList.toggle("is-selected", option.dataset.langValue === value);
        option.setAttribute("aria-selected", String(option.dataset.langValue === value));
      });
    }
    function setLangMenuOpen(isOpen) {
      if (!langSelectTrigger || !langSelectMenu) return;
      langSelectTrigger.setAttribute("aria-expanded", String(isOpen));
      langSelectMenu.classList.toggle("d-none", !isOpen);
    }
    renderSelectedLang(langSelect.value);
    langSelect.addEventListener("change", function () {
      localStorage.setItem("flexary_lang", langSelect.value);
      location.reload();
    });
    if (langSelectTrigger && langSelectMenu) {
      langSelectTrigger.addEventListener("click", function (e) {
        e.stopPropagation();
        setLangMenuOpen(langSelectMenu.classList.contains("d-none"));
      });
      document.querySelectorAll(".lang-select-option").forEach((option) => {
        option.addEventListener("click", function () {
          const value = option.dataset.langValue;
          if (!value || value === langSelect.value) {
            setLangMenuOpen(false);
            return;
          }
          langSelect.value = value;
          renderSelectedLang(value);
          setLangMenuOpen(false);
          langSelect.dispatchEvent(new Event("change", { bubbles: true }));
        });
      });
      document.addEventListener("click", function (e) {
        if (!langSelectTrigger.parentElement.contains(e.target)) {
          setLangMenuOpen(false);
        }
      });
    }
  }
});
