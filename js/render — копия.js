/* ===== RENDERING MODULE ===== */
const Render = {};

Render.renderAreas = async function () {
  try {
    const all = await db.contacts.toArray();
    const groups = {};

    all.forEach(c => {
      const a = c.area || 'Без области';
      if (!groups[a]) groups[a] = { t: 0, arch: 0, tg: 0, wa: 0, em: 0, sTG: 0, sWA: 0, sEM: 0 };
      groups[a].t++;
      if (c.archived) groups[a].arch++;
      if (hasChannel(c, 'telegram')) groups[a].tg++;
      if (hasChannel(c, 'whatsapp')) groups[a].wa++;
      if (hasChannel(c, 'email')) groups[a].em++;
      if (c.last_tg) groups[a].sTG++;
      if (c.last_wa) groups[a].sWA++;
      if (c.last_email) groups[a].sEM++;
    });

    const el = document.getElementById('areasList');
    const keys = Object.keys(groups).sort();

    if (!keys.length) {
      el.innerHTML = '<div class="empty-state"><i class="ri-map-2-line"></i><div class="empty-state-title">Нет областей</div><div class="empty-state-desc">Загрузите CSV файл для начала работы</div></div>';
      return;
    }

    // Compute totals
    let totalContacts = 0, totalArchived = 0, totalTG = 0, totalWA = 0, totalEM = 0, totalSTG = 0, totalSWA = 0, totalSEM = 0;
    keys.forEach(a => {
      const d = groups[a];
      totalContacts += (d.t - d.arch);
      totalArchived += d.arch;
      totalTG += d.tg; totalWA += d.wa; totalEM += d.em;
      totalSTG += d.sTG; totalSWA += d.sWA; totalSEM += d.sEM;
    });

    let h = '';

    // ── Dashboard Stats ──
    h += '<div class="dash-stats">';
    h += '<div class="dash-stat-card"><div class="dash-stat-value">' + totalContacts + '</div><div class="dash-stat-label">Контактов</div></div>';
    h += '<div class="dash-stat-card"><div class="dash-stat-value">' + keys.length + '</div><div class="dash-stat-label">Областей</div></div>';
    h += '<div class="dash-stat-card"><div class="dash-stat-value dash-stat-value--acc">' + (totalSTG + totalSWA + totalSEM) + '</div><div class="dash-stat-label">Отправлено</div></div>';
    h += '<div class="dash-stat-card"><div class="dash-stat-value dash-stat-value--tg">' + totalTG + '</div><div class="dash-stat-label">TG</div></div>';
    h += '<div class="dash-stat-card"><div class="dash-stat-value dash-stat-value--wa">' + totalWA + '</div><div class="dash-stat-label">WA</div></div>';
    h += '<div class="dash-stat-card"><div class="dash-stat-value dash-stat-value--em">' + totalEM + '</div><div class="dash-stat-label">Email</div></div>';
    h += '</div>';

    // ── Area Cards Grid ──
    h += '<div class="areas-grid">';
    keys.forEach(a => {
      const d = groups[a];
      const act = d.t - d.arch;
      const areaEncoded = btoa(encodeURIComponent(a));
      
      // Calculate progress (sent / total channels available)
      const totalChannels = d.tg + d.wa + d.em;
      const totalSent = d.sTG + d.sWA + d.sEM;
      const pct = totalChannels ? Math.round(totalSent / totalChannels * 100) : 0;

      h += '<div class="area-card" style="position:relative;animation-delay:' + (keys.indexOf(a) * 0.05) + 's">';
      h += '<div class="area-actions">';
      h += '<button class="area-btn" data-area-edit="' + escAttr(a) + '" title="Переименовать"><i class="ri-pencil-line"></i></button>';
      h += '<button class="area-btn area-btn-del" data-area-delete="' + escAttr(a) + '" title="Удалить"><i class="ri-delete-bin-line"></i></button></div>';
      
      h += '<div class="area-card-header">';
      h += '<div class="area-clickable" data-area="' + areaEncoded + '" style="cursor:pointer">';
      h += '<div class="area-card-title">' + esc(a) + '</div>';
      h += '</div>';
      h += '<i class="ri-arrow-right-s-line" style="color:var(--mut);font-size:20px;opacity:.5"></i>';
      h += '</div>';
      
      // Stats row
      h += '<div class="area-card-stats">';
      h += '<span><strong>' + act + '</strong> контактов</span>';
      if (act !== d.t) h += '<span>' + d.arch + ' в архиве</span>';
      h += '</div>';
      
      // Channel breakdown
      h += '<div class="area-card-stats" style="margin-top:6px">';
      if (d.tg) h += '<span><i class="ri-telegram-fill" style="color:#60a5fa"></i> <strong>' + d.tg + '</strong></span>';
      if (d.wa) h += '<span><i class="ri-whatsapp-fill" style="color:#4ade80"></i> <strong>' + d.wa + '</strong></span>';
      if (d.em) h += '<span><i class="ri-mail-fill" style="color:#fbbf24"></i> <strong>' + d.em + '</strong></span>';
      h += '</div>';
      
      // Progress bar
      h += '<div class="area-progress"><div class="area-progress-bar" style="width:' + pct + '%"></div></div>';
      
      // Sent stats
      h += '<div class="area-card-sent">';
      h += '<span style="color:#38bdf8">ТГ✓ ' + d.sTG + '</span>';
      h += '<span style="color:#22c55e">WA✓ ' + d.sWA + '</span>';
      h += '<span style="color:#f59e0b">Email✓ ' + d.sEM + '</span>';
      h += '<span style="margin-left:auto;color:var(--acc);font-weight:600">' + pct + '%</span>';
      h += '</div>';
      
      h += '</div>';
    });
    h += '</div>';

    el.innerHTML = h;

    // Attach click handlers after rendering
    el.querySelectorAll('.area-clickable').forEach(el => {
      el.onclick = function() {
        const areaEncoded = this.dataset.area;
        const areaName = decodeURIComponent(atob(areaEncoded));
        State.goArea(areaName);
      };
    });

    // Area action buttons - event delegation
    el.querySelectorAll('.area-btn[data-area-edit]').forEach(btn => {
      btn.onclick = function(e) {
        e.stopPropagation();
        const areaName = this.dataset.areaEdit;
        Render.editArea(areaName, e);
      };
    });
    el.querySelectorAll('.area-btn[data-area-delete]').forEach(btn => {
      btn.onclick = function(e) {
        e.stopPropagation();
        const areaName = this.dataset.areaDelete;
        Render.deleteArea(areaName, e);
      };
    });
  } catch (err) {
    console.error('renderAreas:', err);
    toast('Ошибка', 'err');
  }
};

Render.editArea = async function (oldName, event) {
  event.stopPropagation();
  const newName = prompt('Новое название:', oldName);
  if (!newName || newName.trim() === oldName) return;
  const trimmed = newName.trim();

  try {
    const contacts = await db.contacts.where('area').equals(oldName).toArray();
    for (const c of contacts) {
      await db.contacts.update(c.id, { area: trimmed });
    }
    toast('Переименовано');
    if (State.currentArea === oldName) State.currentArea = trimmed;
    Render.renderAreas();
    saveToServer();
  } catch (err) {
    console.error('editArea:', err);
    toast('Ошибка', 'err');
  }
};

Render.deleteArea = async function (areaName, event) {
  event.stopPropagation();
  const count = await db.contacts.where('area').equals(areaName).count();
  if (!confirm('Удалить «' + areaName + '» и ' + count + ' контактов?')) return;

  try {
    const contacts = await db.contacts.where('area').equals(areaName).toArray();
    for (const c of contacts) {
      await db.contacts.delete(c.id);
    }
    toast('Удалено');
    if (State.currentArea === areaName) State.goAreas();
    else Render.renderAreas();
    saveToServer();
  } catch (err) {
    console.error('deleteArea:', err);
    toast('Ошибка', 'err');
  }
};

/* Field toggles now render inside the settings dropdown */
Render.renderFieldToggles = function () {
  const container = document.getElementById('fieldTogglesDD');
  if (!container) return;
  
  container.innerHTML = FIELDS.map(f => {
    const off = State.hiddenFields.has(f.k) ? ' off' : '';
    return '<span class="tog' + off + '" onclick="toggleField(\'' + f.k + '\')"><i class="' + f.icon + '"></i> ' + esc(f.l) + '</span>';
  }).join('');
};

Render.renderChannelTabs = function (list, chKey) {
  const el = document.getElementById('channelTabs');
  
  const counts = {};
  CHANNELS.forEach(ch => {
    const withChannel = list.filter(c => hasChannel(c, ch.field));
    const unsent = withChannel.filter(c => !c[ch.lastField]).length;
    const sent = withChannel.filter(c => !!c[ch.lastField]).length;
    counts[ch.k] = { unsent, sent, total: withChannel.length };
  });

  el.innerHTML = CHANNELS.map(ch => {
    const act = State.currentChannel === ch.k ? ' act' : '';
    const c = counts[ch.k];
    return '<button class="ch-tab' + act + '" onclick="State.setChannel(\'' + ch.k + '\');Render.renderChecklist()">' +
      '<i class="' + ch.icon + '" style="color:' + (act ? '#fff' : ch.color) + '"></i> ' + esc(ch.l) +
      '<span class="ch-tab-badge">' + (c ? c.unsent : 0) + '</span></button>';
  }).join('');
};

Render.renderChecklist = async function () {
  try {
    const list = await db.contacts.where('area').equals(State.currentArea).toArray();
    const ch = getChannel(State.currentChannel);
    if (!ch) return;

    // Filter: only contacts that HAVE this channel
    const withChannel = list.filter(c => hasChannel(c, ch.field));

    const filtered = State.searchQuery
      ? withChannel.filter(c =>
          c.name.toLowerCase().includes(State.searchQuery) ||
          (c.phone || '').toLowerCase().includes(State.searchQuery))
      : withChannel;

    const unsent = filtered.filter(c => !c[ch.lastField]);
    const sent = filtered.filter(c => !!c[ch.lastField]);
    const total = filtered.length;
    const sentCount = sent.length;
    const pct = total ? Math.round(sentCount / total * 100) : 0;

    Render.renderChannelTabs(list, State.currentChannel);

    const board = document.getElementById('checklistContainer');
    let h = '';

    h += '<div class="ch-progress">';
    h += '<div class="ch-progress-track"><div class="ch-progress-bar" style="width:' + pct + '%"></div></div>';
    h += '<span class="ch-progress-text">' + sentCount + '/' + total + '</span>';
    h += '</div>';

    // Simplified batch bar with dropdown
    const batchVisible = State.selectedIds.size > 0;
    h += '<div class="ch-batch-bar' + (batchVisible ? ' visible' : '') + '">';
    h += '<div class="ch-batch-count">';
    h += '<span class="ch-batch-count-num">' + State.selectedIds.size + '</span> выбрано';
    h += '</div>';
    
    // Primary actions as icon buttons
    h += '<button class="btn btn-s btn-p" onclick="Batch.markSelected()" title="Отметить как отправленные"><i class="ri-check-line"></i></button>';
    h += '<button class="btn btn-s" onclick="Batch.sendEmails()" title="Email рассылка"><i class="ri-mail-send-line"></i></button>';
    
    // More actions dropdown
    h += '<div class="ch-batch-actions">';
    h += '<button class="btn btn-s" onclick="toggleBatchDD(event)" title="Ещё действия"><i class="ri-more-2-fill"></i></button>';
    h += '<div id="batchDD" class="ch-batch-dd">';
    h += '<div class="ch-batch-dd-item" onclick="Batch.selectUnsent(window._chkList);toggleBatchDD(event)"><i class="ri-checkbox-multiple-line"></i> Выбрать неотправленные</div>';
    h += '<div class="ch-batch-dd-item" onclick="Batch.selectSent(window._chkList);toggleBatchDD(event)"><i class="ri-checkbox-multiple-line"></i> Выбрать отправленные</div>';
    h += '<div class="ch-batch-dd-divider"></div>';
    h += '<div class="ch-batch-dd-item" onclick="State.clearSelection();Render.renderChecklist()"><i class="ri-close-line"></i> Сбросить выбор</div>';
    h += '</div></div>';
    h += '</div>';

    h += '<div class="ch-section">';
    h += '<div class="ch-section-head"><span class="ch-section-title"><i class="ri-send-plane-2-line"></i> Не отправлено (' + unsent.length + ')</span></div>';
    h += '<div class="ch-section-body">';
    if (!unsent.length) {
      h += '<div style="padding:24px;text-align:center;color:var(--mut)">Все отправлены!</div>';
    } else {
      unsent.forEach(c => { h += Render.renderCheckRow(c, ch, false); });
    }
    h += '</div></div>';

    h += '<div class="ch-section">';
    h += '<div class="ch-section-head"><span class="ch-section-title"><i class="ri-check-circle-line"></i> Отправлено (' + sent.length + ')</span></div>';
    h += '<div class="ch-section-body">';
    if (!sent.length) {
      h += '<div style="padding:24px;text-align:center;color:var(--mut)">Пока пусто</div>';
    } else {
      sent.forEach(c => { h += Render.renderCheckRow(c, ch, true); });
    }
    h += '</div></div>';

    board.innerHTML = h;
    window._chkList = filtered;

    document.getElementById('statsFooter').style.display = 'flex';
    Render.renderStats(filtered);
  } catch (err) {
    console.error('renderChecklist:', err);
    toast('Ошибка', 'err');
  }
};

/* Toggle batch dropdown */
function toggleBatchDD(e) {
  e.stopPropagation();
  const dd = document.getElementById('batchDD');
  if (dd) {
    dd.classList.toggle('visible');
  }
}

// Close batch dropdown on outside click
document.addEventListener('click', function(e) {
  const dd = document.getElementById('batchDD');
  if (dd && dd.classList.contains('visible') && !e.target.closest('.ch-batch-actions')) {
    dd.classList.remove('visible');
  }
});

Render.renderCheckRow = function (c, ch, isSent) {
  const selected = State.selectedIds.has(c.id);
  const expanded = State.expandedId === c.id;
  const selClass = selected ? ' selected' : '';
  const sentClass = isSent ? ' sent' : '';
  const expClass = expanded ? ' expanded' : '';

  const val = c[ch.field] || '';
  const displayVal = ch.k === 'email' ? val : val.replace(/^https?:\/\//, '');
  const url = val ? Render.buildUrl(ch.k, val) : '';

  let h = '<div class="ch-row' + selClass + sentClass + '">';
  h += '<div class="ch-row-main" onclick="State.toggleExpand(\'' + escAttr(c.id) + '\');Render.renderChecklist()">';
  h += '<input type="checkbox" class="ch-row-check" ' + (selected ? 'checked' : '') + ' onclick="event.stopPropagation();State.toggleSelect(\'' + escAttr(c.id) + '\');Render.renderChecklist()" aria-label="Выбрать ' + escAttr(c.name) + '">';
  h += '<span class="ch-row-name">' + esc(c.name || '—') + '</span>';
  if (val) {
    h += '<a class="ch-row-contact" href="' + escAttr(url) + '" target="_blank" onclick="event.stopPropagation()">' + esc(displayVal) + '</a>';
  }
  if (isSent && c[ch.lastField]) {
    h += '<span class="ch-row-date">' + fmtDate(c[ch.lastField]) + '</span>';
  }
  h += '<i class="ri-arrow-down-s-line ch-row-expand' + expClass + '"></i>';
  h += '</div>';

  if (expanded) {
    h += Render.renderRowDetail(c, ch);
  }

  h += '</div>';
  return h;
};

Render.renderRowDetail = function (c, ch) {
  const fieldsToShow = ['name', 'city', 'phone', 'email', 'website', 'telegram', 'whatsapp', 'vk'];
  const fieldLabels = { name: 'Название', city: 'Город', phone: 'Телефон', email: 'Email', website: 'Сайт', telegram: 'Telegram', whatsapp: 'WhatsApp', vk: 'VK' };
  const fieldIcons = { name: 'ri-building-line', city: 'ri-map-pin-line', phone: 'ri-phone-line', email: 'ri-mail-line', website: 'ri-global-line', telegram: 'ri-telegram-fill', whatsapp: 'ri-whatsapp-fill', vk: 'ri-brand-vk-fill' };

  let h = '<div class="ch-detail">';
  h += '<div class="ch-detail-grid">';

  fieldsToShow.forEach(fk => {
    const val = c[fk] || '';
    if (!val) return;
    const isLinkable = ['phone', 'email', 'website', 'telegram', 'whatsapp', 'vk'].includes(fk);
    const url = isLinkable ? Render.buildUrl(fk, val) : '';

    h += '<div class="ch-detail-item">';
    h += '<div class="ch-detail-label"><i class="' + (fieldIcons[fk] || 'ri-information-line') + '"></i> ' + esc(fieldLabels[fk] || fk) + '</div>';
    h += '<div class="ch-detail-value">';
    if (isLinkable) {
      h += '<a href="' + escAttr(url) + '" target="_blank" rel="noopener">' + esc(val) + '</a>';
      h += '<button class="ch-copy-btn" onclick="event.stopPropagation();Render.copyValue(\'' + escAttr(val) + '\')" title="Копировать"><i class="ri-file-copy-line"></i></button>';
    } else {
      h += esc(val);
    }
    h += '</div></div>';
  });

  if (c.note) {
    h += '<div class="ch-detail-note"><i class="ri-sticky-note-line"></i> ' + esc(c.note) + '</div>';
  }

  h += '</div>';

  const history = Array.isArray(c.touch_history) ? c.touch_history.slice().reverse() : [];
  if (history.length) {
    h += '<div class="ch-timeline">';
    h += '<div class="ch-timeline-title"><i class="ri-history-line"></i> История</div>';
    h += '<div class="ch-timeline-list">';
    history.forEach(t => {
      const tCh = getChannel(t.ch);
      const tColor = tCh ? tCh.color : 'var(--mut)';
      const tIcon = tCh ? tCh.icon : 'ri-send-plane-line';
      h += '<div class="ch-timeline-item">';
      h += '<i class="' + tIcon + '" style="color:' + tColor + '"></i>';
      h += '<span class="ch-timeline-date">' + fmtDate(t.at) + '</span>';
      if (t.note) {
        h += '<span class="ch-timeline-note">— ' + esc(t.note) + '</span>';
      }
      h += '</div>';
    });
    h += '</div></div>';
  }

  const isSent = !!c[ch.lastField];
  h += '<div class="ch-detail-actions">';
  if (!isSent) {
    h += '<button class="btn btn-s btn-p" onclick="event.stopPropagation();Render.quickTouch(\'' + escAttr(c.id) + '\',\'' + ch.k + '\')"><i class="ri-check-line"></i> Отметить</button>';
  } else {
    h += '<button class="btn btn-s" onclick="event.stopPropagation();Render.undoQuickTouch(\'' + escAttr(c.id) + '\',\'' + ch.k + '\')"><i class="ri-arrow-go-back-line"></i> Отменить</button>';
  }
  h += '</div>';

  h += '</div>';
  return h;
};

Render.buildUrl = function (channel, value) {
  if (!value) return '';
  switch (channel) {
    case 'phone': return 'tel:' + value.replace(/[\s\-\(\)]/g, '');
    case 'email': return 'mailto:' + value;
    case 'website': return value.startsWith('http') ? value : 'https://' + value;
    case 'telegram': return value.startsWith('http') ? value : 'https://t.me/' + value.replace('@', '');
    case 'whatsapp': return value.startsWith('http') ? value : 'https://wa.me/' + value.replace(/[\s\-\+\(\)]/g, '');
    case 'vk': return value.startsWith('http') ? value : 'https://vk.com/' + value.replace('@', '');
    default: return value;
  }
};

Render.copyValue = function (value) {
  navigator.clipboard.writeText(value).then(() => {
    toast('Скопировано');
  }).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = value;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    toast('Скопировано');
  });
};

Render.quickTouch = async function (id, channel) {
  const note = prompt('Заметка (необязательно):');
  if (note === null) return;
  await recordTouch(id, channel, (note || '').trim());
  toast('Отмечено');
  await Render.renderChecklist();
};

Render.undoQuickTouch = async function (id, channel) {
  await undoTouch(id, channel);
  toast('Отменено');
  await Render.renderChecklist();
};

Render.renderStats = function (list) {
  let wTG = 0, wWA = 0, wEM = 0, sTG = 0, sWA = 0, sEM = 0;
  list.forEach(c => {
    if (hasChannel(c, 'telegram')) wTG++;
    if (hasChannel(c, 'whatsapp')) wWA++;
    if (hasChannel(c, 'email')) wEM++;
    if (c.last_tg) sTG++;
    if (c.last_wa) sWA++;
    if (c.last_email) sEM++;
  });
  const arch = list.filter(c => c.archived).length;
  document.getElementById('statsBar').innerHTML =
    stb(list.length, 'var(--hd)', 'Всего') +
    stb(wTG, '#60a5fa', 'TG') +
    stb(wWA, '#4ade80', 'WA') +
    stb(wEM, '#fbbf24', 'Email') +
    stb(sTG, '#38bdf8', 'ТГ✓') +
    stb(sWA, '#22c55e', 'WA✓') +
    stb(sEM, '#f59e0b', 'Email✓') +
    stb(arch, 'var(--mut)', 'Архив');
};
