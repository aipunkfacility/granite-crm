/* ===== BACKUP MANAGER ===== */
const BackupManager = {};

// Current filter (set before opening modal)
BackupManager._filterArea = null;

/* ---------- OPEN BACKUP MODAL ---------- */
BackupManager.openModal = async function (filterArea) {
  BackupManager._filterArea = filterArea || null;
  
  const title = filterArea 
    ? 'Бекапы: ' + filterArea 
    : 'Все бекапы';
  
  const m = document.getElementById('backupModal');
  m.innerHTML =
    '<div class="modal backup-modal" onclick="event.stopPropagation()">' +
    '<div class="backup-modal-head">' +
    '<h3><i class="ri-history-line" style="color:var(--acc)"></i> ' + esc(title) + '</h3>' +
    '<button class="btn-icon" onclick="BackupManager.closeModal()"><i class="ri-close-line"></i></button>' +
    '</div>' +
    '<div id="backupList" class="backup-list">Загрузка...</div>' +
    '</div>';
  m.style.display = 'flex';
  m.onclick = BackupManager.closeModal;

  // Load backup list
  await BackupManager.loadBackupList();
};

BackupManager.closeModal = function () {
  document.getElementById('backupModal').style.display = 'none';
};

/* ---------- LOAD BACKUP LIST FROM SERVER ---------- */
BackupManager.loadBackupList = async function () {
  const listEl = document.getElementById('backupList');

  try {
    console.log('[BackupManager] Loading backups from:', SERVER_URL + '/backups');
    const resp = await fetch(SERVER_URL + '/backups', { signal: AbortSignal.timeout(5000) });
    if (!resp.ok) {
      console.error('[BackupManager] Server error:', resp.status);
      listEl.innerHTML = '<div class="backup-error"><i class="ri-error-warning-line"></i> Сервер не отвечает (' + resp.status + ')</div>';
      return;
    }

    const data = await resp.json();
    let backups = data.backups || [];
    
    // Filter by area if specified
    if (BackupManager._filterArea) {
      const areaPrefix = transliterate(BackupManager._filterArea).replace(/[^a-zA-Z0-9_-]/g, '-');
      backups = backups.filter(b => b.name.startsWith(areaPrefix));
    }

    if (!backups.length) {
      const msg = BackupManager._filterArea 
        ? 'Нет бекапов этого раздела' 
        : 'Нет бекапов';
      listEl.innerHTML = '<div class="backup-empty"><i class="ri-folder-history-line"></i> ' + msg + '</div>';
      return;
    }

    // Group by date
    const groups = {};
    backups.forEach(b => {
      const date = b.created.split('T')[0];
      if (!groups[date]) groups[date] = [];
      groups[date].push(b);
    });

    let html = '';
    const sortedDates = Object.keys(groups).sort().reverse();

    sortedDates.forEach(date => {
      html += '<div class="backup-date-group">';
      html += '<div class="backup-date-label">' + BackupManager.formatDate(date) + '</div>';

      groups[date].forEach(b => {
        const time = b.created.split('T')[1]?.substring(0, 5) || '';
        const sizeKB = Math.round(b.size / 1024);
        // Show readable area name instead of filename
        const displayName = BackupManager._filterArea 
          ? time + ' • ' + sizeKB + ' KB'
          : BackupManager.getAreaName(b.name) + ' • ' + time + ' • ' + sizeKB + ' KB';
        
        html += '<div class="backup-item" onclick="BackupManager.confirmRestore(\'' + escAttr(b.name) + '\')">';
        html += '<div class="backup-item-info">';
        html += '<i class="ri-file-code-line"></i>';
        html += '<span class="backup-item-name">' + esc(displayName) + '</span>';
        html += '</div>';
        html += '</div>';
      });

      html += '</div>';
    });

    listEl.innerHTML = html;

  } catch (e) {
    console.error('[BackupManager] loadBackupList error:', e);
    listEl.innerHTML = '<div class="backup-error"><i class="ri-wifi-off-line"></i> Ошибка соединения. Запущен ли сервер?</div>';
  }
};

/* ---------- EXTRACT AREA NAME FROM BACKUP FILENAME ---------- */
BackupManager.getAreaName = function (filename) {
  // Format: area-name.json.YYYYMMDD_HHMMSS.bak
  const base = filename.replace(/\.json\..*\.bak$/, '');
  // Convert dashes back to spaces (rough approximation)
  return base.replace(/-/g, ' ');
};

/* ---------- FORMAT DATE ---------- */
BackupManager.formatDate = function (isoDate) {
  const d = new Date(isoDate);
  const days = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
  const dayName = days[d.getDay()];
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  return day + '.' + month + ' (' + dayName + ')';
};

/* ---------- CONFIRM AND RESTORE ---------- */
BackupManager.confirmRestore = async function (backupName) {
  // Extract area name from backup filename
  // Format: filename.json.YYYYMMDD_HHMMSS.bak
  let areaName = backupName.replace(/\.json\..*\.bak$/, '').replace(/_/g, ' ');
  
  console.log('[BackupManager] Restoring:', backupName, 'Area:', areaName);

  if (!confirm('Восстановить из бекапа?\n\nФайл: ' + backupName + '\n\nТекущие данные будут заменены!')) {
    return;
  }

  toast('Восстановление...');

  try {
    const url = SERVER_URL + '/restore/' + encodeURIComponent(backupName);
    console.log('[BackupManager] Fetching:', url);
    const resp = await fetch(url, {
      method: 'POST',
      signal: AbortSignal.timeout(30000)
    });

    if (!resp.ok) {
      const err = await resp.json();
      toast('Ошибка: ' + (err.detail || 'неизвестная'), 'err');
      return;
    }

    const data = await resp.json();
    console.log('[BackupManager] Restore response:', data);
    const contacts = data.contacts || [];

    if (!contacts.length) {
      toast('Бекап пуст или повреждён', 'err');
      return;
    }

    // Determine area from backup
    const area = contacts[0]?.area || areaName;
    console.log('[BackupManager] Importing to area:', area, 'Count:', contacts.length);

    await db.transaction('rw', db.contacts, async () => {
      // Delete existing contacts in this area
      const existing = await db.contacts.where('area').equals(area).toArray();
      console.log('[BackupManager] Deleting existing:', existing.length);
      for (const c of existing) {
        await db.contacts.delete(c.id);
      }

      // Import from backup
      for (const c of contacts) {
        if (c.id) {
          await db.contacts.put(c);
        }
      }
    });

    toast('Восстановлено: ' + contacts.length + ' контактов');
    BackupManager.closeModal();

    // Refresh UI
    if (typeof State !== 'undefined' && State.currentArea === area) {
      await Render.renderChecklist();
    }
    if (typeof Render !== 'undefined') {
      Render.renderAreas();
    }
    
    // Save to server
    if (typeof saveToServer === 'function') {
      saveToServer();
    }

  } catch (e) {
    console.error('[BackupManager] restore error:', e);
    toast('Ошибка восстановления: ' + e.message, 'err');
  }
};
