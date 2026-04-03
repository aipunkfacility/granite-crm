/* ===== IMPORT / EXPORT ===== */
const ImportExport = {};

/* ---------- UPLOAD MODAL ---------- */
ImportExport.openUpload = function () {
  const m = document.getElementById('uploadModal');
  m.innerHTML =
    '<div class="modal" onclick="event.stopPropagation()">' +
    '<h3 style="font-size:13px;font-weight:700;color:var(--hd);margin-bottom:12px">' +
    '<i class="ri-folder-upload-line" style="color:var(--acc)"></i> Загрузить CSV/JSON</h3>' +
    '<div id="dropZone" class="dropzone">' +
    '<i class="ri-upload-cloud-2-line" style="font-size:30px;color:var(--mut);display:block;margin-bottom:6px"></i>' +
    '<div>Перетащите файл сюда</div>' +
    '<div style="font-size:11px;margin-top:4px;color:var(--mut)">или нажмите</div>' +
    '<input type="file" id="fileIn" accept=".csv,.txt,.json" style="display:none"></div>' +
    '<div id="uploadResult" style="display:none;margin-top:14px"></div></div>';
  m.style.display = 'flex';
  m.onclick = ImportExport.closeUpload; // Close on overlay click

  const dz = document.getElementById('dropZone');
  const fi = document.getElementById('fileIn');

  dz.onclick = function (e) { e.stopPropagation(); fi.click(); };
  dz.ondragover = function (e) { e.preventDefault(); dz.classList.add('dragover'); };
  dz.ondragleave = function () { dz.classList.remove('dragover'); };
  dz.ondrop = function (e) {
    e.preventDefault();
    dz.classList.remove('dragover');
    if (e.dataTransfer.files.length) ImportExport.processFile(e.dataTransfer.files[0]);
  };
  fi.onchange = function () { if (fi.files.length) ImportExport.processFile(fi.files[0]); };
};

ImportExport.closeUpload = function () {
  document.getElementById('uploadModal').style.display = 'none';
};

/* ---------- FILE PROCESSING ---------- */
ImportExport.processFile = function (file) {
  toast('Чтение файла...');
  const reader = new FileReader();

  reader.onerror = function () { toast('Ошибка чтения', 'err'); };

  reader.onload = function (ev) {
    let text = ev.target.result;
    
    // Check if JSON
    if (file.name.endsWith('.json')) {
      try {
        const data = JSON.parse(text);
        ImportExport.doParse(data, file.name, true);
      } catch (e) {
        toast('Ошибка JSON: ' + e.message, 'err');
      }
      return;
    }

    // Try windows-1251 if UTF-8 doesn't look right
    if (!text.includes('Название') && !text.includes('ID')) {
      const r2 = new FileReader();
      r2.onload = function (ev2) {
        const t2 = ev2.target.result;
        if (t2.includes('Название') || t2.includes('ID')) {
          ImportExport.doParse(t2, file.name);
        } else {
          toast('Не удалось прочитать файл', 'err');
        }
      };
      r2.readAsText(file, 'windows-1251');
      return;
    }

    ImportExport.doParse(text, file.name);
  };

  reader.readAsText(file, 'UTF-8');
};

/* ---------- CSV PARSING ---------- */
ImportExport.doParse = function (data, fileName, isJson = false) {
  try {
    let rows = [];
    if (isJson) {
      rows = Array.isArray(data) ? data : [data];
    } else {
      const result = Papa.parse(data, { header: true, skipEmptyLines: true });
      rows = result.data;
    }

    let autoId = 0;
    State.pendingImportRows = rows.map(r => {
      const rawId = (r['ID'] || r['id'] || '').toString().trim();
      return {
      id: rawId || ('imp_' + Date.now() + '_' + (++autoId)),
      name: (r['Название'] || r['name'] || r['Name'] || '').trim(),
      city: (r['Город'] || r['city'] || '').trim(),
      phone: (r['Телефон'] || r['phone'] || '').trim(),
      email: (r['Email'] || r['email'] || '').trim(),
      website: (r['Сайт'] || r['site'] || r['website'] || '').trim(),
      address: (r['Адрес'] || r['address'] || '').trim(),
      vk: (r['VK'] || r['vk'] || '').trim(),
      telegram: (r['Telegram'] || r['telegram'] || '').trim(),
      whatsapp: (r['WhatsApp'] || r['whatsapp'] || '').trim(),
      };
    }).filter(r => r.id || r.name);

    if (!State.pendingImportRows.length) {
      toast('Файл пуст', 'err');
      return;
    }

    const res = document.getElementById('uploadResult');
    res.style.display = 'block';
    res.innerHTML =
      '<div style="font-size:13px;margin-bottom:8px">' +
      '<i class="ri-file-text-line" style="color:var(--acc)"></i> ' +
      '<b>' + esc(fileName) + '</b> — ' + State.pendingImportRows.length + ' записей</div>' +
      '<label style="font-size:11px;font-weight:500;color:var(--mut)">Название области</label>' +
      '<input type="text" id="areaInp" class="inp mt2" placeholder="Ростовская обл.">' +
      '<div class="fl jc" style="gap:8px;margin-top:12px">' +
      '<button class="btn btn-s" onclick="ImportExport.closeUpload()">Отмена</button>' +
      '<button class="btn btn-p btn-s" onclick="ImportExport.doImport()">' +
      '<i class="ri-check-line"></i> Импорт</button></div>';

    setTimeout(() => {
      const ai = document.getElementById('areaInp');
      if (ai) ai.focus();
    }, 100);
  } catch (err) {
    toast('Ошибка CSV: ' + err.message, 'err');
  }
};

/* ---------- IMPORT INTO DB ---------- */
ImportExport.doImport = async function () {
  const ai = document.getElementById('areaInp');
  const area = ai ? ai.value.trim() : '';

  if (!area) {
    if (ai) { ai.style.borderColor = '#ef4444'; ai.focus(); }
    toast('Укажите область', 'err');
    return;
  }

  if (!State.pendingImportRows || !State.pendingImportRows.length) return;

  let imp = 0, upd = 0;

  try {
    await db.transaction('rw', db.contacts, async () => {
      for (let i = 0; i < State.pendingImportRows.length; i++) {
        const r = State.pendingImportRows[i];
        const full = {};
        for (const k in r) full[k] = r[k];
        full.area = area;
        full.color_label = '';
        full.note = '';
        full.archived = 0;
        full.status = '';
        full.last_tg = '';
        full.last_wa = '';
        full.last_email = '';
        full.touch_history = [];

        const ex = await db.contacts.get(r.id);
        if (ex) {
          // Preserve user-set fields on re-import
          if (ex.color_label) full.color_label = ex.color_label;
          if (ex.archived) full.archived = ex.archived;
          if (ex.note) full.note = ex.note;
          if (ex.status) full.status = ex.status;
          if (ex.last_tg) full.last_tg = ex.last_tg;
          if (ex.last_wa) full.last_wa = ex.last_wa;
          if (ex.last_email) full.last_email = ex.last_email;
          if (ex.touch_history && ex.touch_history.length) full.touch_history = ex.touch_history;
          await db.contacts.put(full);
          upd++;
        } else {
          await db.contacts.put(full);
          imp++;
        }
      }
    });

    State.pendingImportRows = null;
    ImportExport.closeUpload();
    toast('+' + imp + ' новых, ~' + upd + ' обновлено');
    saveToServer();
    Render.renderAreas();

    if (State.currentArea === area) await Render.renderChecklist();
  } catch (err) {
    toast('Ошибка импорта: ' + err.message, 'err');
  }
};

/* ---------- EXPORT DROPDOWN ---------- */
ImportExport.openExportDD = function (event) {
  event.stopPropagation();
  const d = document.getElementById('exportDD');
  const btn = event.target.closest('button');
  const r = btn.getBoundingClientRect();
  d.style.top = (r.bottom + 4) + 'px';
  d.style.left = (r.left + r.width - 180) + 'px';
  d.style.display = d.style.display === 'block' ? 'none' : 'block';
};

ImportExport.closeExportDD = function () {
  const el = document.getElementById('exportDD');
  if (el) el.style.display = 'none';
};

/* ---------- XLSX EXPORT ---------- */
ImportExport.doExport = async function (mode) {
  ImportExport.closeExportDD();

  try {
    let list = await db.contacts.where('area').equals(State.currentArea).toArray();
    if (mode === 'active') list = list.filter(c => !c.archived);

    if (!list.length) {
      toast('Нет данных', 'err');
      return;
    }

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('Контакты');

    ws.columns = [
      { header: 'ID', key: 'id', width: 10 },
      { header: 'Название', key: 'name', width: 35 },
      { header: 'Город', key: 'city', width: 20 },
      { header: 'Телефон', key: 'phone', width: 25 },
      { header: 'Email', key: 'email', width: 28 },
      { header: 'Статус', key: 'status', width: 16 },
      { header: 'Сайт', key: 'website', width: 30 },
      { header: 'Адрес', key: 'address', width: 30 },
      { header: 'VK', key: 'vk', width: 25 },
      { header: 'Telegram', key: 'telegram', width: 25 },
      { header: 'WhatsApp', key: 'whatsapp', width: 25 },
      { header: 'Метка', key: 'cl', width: 14 },
      { header: 'Заметка', key: 'note', width: 30 },
      { header: 'Посл. TG', key: 'ltg', width: 14 },
      { header: 'Посл. WA', key: 'lwa', width: 14 },
      { header: 'Посл. Email', key: 'lem', width: 14 },
    ];

    // Header styling
    ws.getRow(1).eachCell(c => {
      c.font = { bold: true, size: 11, color: { argb: 'FFFFFFFF' } };
      c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF334155' } };
      c.alignment = { horizontal: 'center', vertical: 'middle' };
    });

    // Data rows
    list.forEach((c, i) => {
      const row = ws.addRow({
        id: c.id, name: c.name, city: c.city, phone: c.phone,
        email: c.email, status: c.status, website: c.website,
        address: c.address, vk: c.vk, telegram: c.telegram,
        whatsapp: c.whatsapp, cl: c.color_label ? COLOR_LABELS[c.color_label] || '' : '',
        note: c.note || '',
        ltg: c.last_tg ? fmtDate(c.last_tg) : '',
        lwa: c.last_wa ? fmtDate(c.last_wa) : '',
        lem: c.last_email ? fmtDate(c.last_email) : '',
      });

      // Alternating row colors
      if (i % 2 === 1) {
        row.eachCell({ includeEmpty: true }, c => {
          c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF8FAFC' } };
        });
      }

      // Color label cell styling
      if (c.color_label && COLOR_BG[c.color_label]) {
        const lc = row.getCell(12);
        lc.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: COLOR_BG[c.color_label] } };
        lc.font = { size: 11, color: { argb: COLOR_FG[c.color_label] }, bold: true };
      }

      // Archive: strikethrough
      if (c.archived) {
        row.eachCell({ includeEmpty: true }, c => {
          c.font = { size: c.font.size || 11, color: { argb: 'FF94A3B8' }, strike: true };
        });
      }
    });

    // Auto-filter
    ws.autoFilter = { from: 'A1', to: 'P' + (list.length + 1) };

    // Download
    const buf = await wb.xlsx.writeBuffer();
    const blob = new Blob([buf], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    const safeArea = State.currentArea.replace(/\s+/g, '_');
    const dateStr = new Date().toISOString().slice(0, 10);
    saveAs(blob, 'crm_' + safeArea + '_' + dateStr + '.xlsx');

    toast('Выгружено: ' + list.length);
  } catch (err) {
    toast('Ошибка экспорта: ' + err.message, 'err');
  }
};
