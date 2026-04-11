/**
 * Pyodide Web Worker — PDF generation off the main thread.
 *
 * The worker starts loading Pyodide + fpdf2 / pillow / qrcode as soon as the
 * page loads (triggered from ui.js).  By the time the user opens the PDF
 * modal and clicks Download, the runtime is already warm and the heavy
 * computation never touches the main thread.
 */

/* global loadPyodide */
importScripts('https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js');

// Resolve the app root from this worker script's own URL.
// Worker lives at:  <root>/src/js/pyodide-worker.js
// App root:         <root>/
const APP_ROOT = new URL('../../', self.location.href).href;

let pyodide = null;

const initPromise = (async () => {
  pyodide = await loadPyodide({
    indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/',
  });

  // Install the packages required by the PDF generator.
  await pyodide.loadPackage('micropip');
  const micropip = pyodide.pyimport('micropip');
  await micropip.install(['fpdf2==2.8.3', 'pillow==10.0.0', 'qrcode==7.4.2']);

  // Fetch Python source files and write them into the virtual FS so they can
  // be imported normally with `import models` / `import pdf_worker`.
  const sources = [
    ['src/py/models.py', 'models.py'],
    ['src/py/pdf_worker.py', 'pdf_worker.py'],
  ];
  for (const [srcPath, destName] of sources) {
    const resp = await fetch(new URL(srcPath, APP_ROOT).href);
    if (!resp.ok) throw new Error(`Failed to fetch ${srcPath}: ${resp.status}`);
    pyodide.FS.writeFile(destName, await resp.text());
  }

  // Bootstrap the Python environment.
  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, '/')
import models          # registers module; workouts_from_json is imported lazily inside pdf_worker
import pdf_worker
pdf_worker.set_app_root('${APP_ROOT}')
  `);

  self.postMessage({ type: 'ready' });
})().catch((err) => {
  self.postMessage({ type: 'init-error', message: String(err) });
});

// ---------------------------------------------------------------------------
// Message handler
// ---------------------------------------------------------------------------

self.onmessage = async (event) => {
  const { type, id, payload } = event.data;
  if (type !== 'generate-pdf') return;

  try {
    await initPromise;

    // Push all inputs into the Python global namespace before running.
    pyodide.globals.set('_workouts_json', payload.workoutsJson);
    pyodide.globals.set('_catalog_json', payload.catalogJson);
    pyodide.globals.set('_locale_json', payload.localeJson);
    pyodide.globals.set('_is_authenticated', !!payload.isAuthenticated);
    pyodide.globals.set('_black_and_white', !!payload.blackAndWhite);
    pyodide.globals.set('_custom_site_url', payload.siteUrl || '');
    pyodide.globals.set('_custom_border_color', payload.borderColor || '');

    const logoBytes = payload.logoBytes;
    if (logoBytes instanceof Uint8Array && logoBytes.length > 0) {
      pyodide.globals.set('_logo_bytes', pyodide.toPy(logoBytes));
    } else {
      pyodide.globals.set('_logo_bytes', null);
    }

    // Run the async Python PDF generator.
    const pdfProxy = await pyodide.runPythonAsync(`
await pdf_worker.generate_pdf_bytes(
    workouts_json=_workouts_json,
    catalog_json=_catalog_json,
    locale_json=_locale_json,
    is_authenticated=_is_authenticated,
    black_and_white=_black_and_white,
    custom_logo_bytes=bytes(_logo_bytes) if _logo_bytes is not None else None,
    custom_site_url=_custom_site_url or None,
    custom_border_color=_custom_border_color or None,
)
    `);

    // Convert the Python bytes result to a transferable Uint8Array.
    const bytes = pdfProxy.toJs({ create_proxies: false });
    pdfProxy.destroy();

    self.postMessage({ type: 'pdf-result', id, bytes }, [bytes.buffer]);
  } catch (err) {
    self.postMessage({ type: 'pdf-error', id, message: String(err) });
  }
};
