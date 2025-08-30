(function () {
  const form = document.querySelector('form[hx-post="/upload"]');
  const dz = document.getElementById('dropzone');
  const fileInput = document.getElementById('file');
  const bar = document.getElementById('upload-bar');

  if (!form || !dz || !fileInput) return;

  // ---- Drag & Drop visual ----
  ['dragenter', 'dragover'].forEach(evt =>
    dz.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); dz.classList.add('dragover'); })
  );
  ['dragleave', 'dragend', 'drop'].forEach(evt =>
    dz.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); dz.classList.remove('dragover'); })
  );

  // ---- Handle drop: set files and trigger change (auto-submit via hx-trigger) ----
  dz.addEventListener('drop', e => {
    const files = e.dataTransfer?.files;
    if (!files || !files.length) return;
    // mais compatível: criar DataTransfer
    const dt = new DataTransfer();
    for (const f of files) dt.items.add(f);
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event('change', { bubbles: true })); // dispara HTMX
  });

  // ---- Progresso do upload (htmx) ----
  document.body.addEventListener('htmx:xhr:progress', function (evt) {
    if (evt?.detail?.lengthComputable) {
      const pct = Math.round((evt.detail.loaded / evt.detail.total) * 100);
      if (bar) bar.style.width = pct + '%';
    }
  });

  // reset barra quando concluir
  document.body.addEventListener('htmx:afterOnLoad', function () {
    setTimeout(() => { if (bar) bar.style.width = '0%'; }, 300);
  });
})();
