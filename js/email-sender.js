/* ===== EMAIL SENDER MODULE ===== */
const EmailSender = {
  get SERVER_URL() {
    return (typeof window !== 'undefined' && window.location && window.location.origin) 
      ? window.location.origin 
      : 'http://localhost:8000';
  },
  get AUTH_HEADER() {
    return API_TOKEN ? { 'Authorization': 'Bearer ' + API_TOKEN } : {};
  },
  currentJobId: null,
  pollInterval: null,
  pendingContacts: [],
  lastReport: null,
  _lastResultCount: 0,

  findDuplicates(contacts) {
    const map = {};
    contacts.forEach(c => {
      const e = c.email.toLowerCase();
      if (!map[e]) map[e] = [];
      map[e].push(c.name);
    });
    return Object.entries(map)
      .filter(([, names]) => names.length > 1)
      .map(([email, names]) => ({ email, names }));
  },

  deduplicateContacts(contacts) {
    const seen = new Map();
    const result = [];
    contacts.forEach(c => {
      const e = c.email.toLowerCase();
      if (!seen.has(e)) {
        seen.set(e, { ...c, _allIds: [c.id], _allNames: [c.name] });
        result.push(seen.get(e));
      } else {
        const existing = seen.get(e);
        if (c.id && !existing._allIds.includes(c.id)) existing._allIds.push(c.id);
        if (!existing._allNames.includes(c.name)) existing._allNames.push(c.name);
      }
    });
    return result;
  },

  async checkServer() {
    try {
      const r = await fetch(this.SERVER_URL + '/health', { signal: AbortSignal.timeout(3000) });
      return r.ok;
    } catch {
      return false;
    }
  },

  async getTemplate() {
    const tr = await fetch(this.SERVER_URL + '/template', { headers: this.AUTH_HEADER });
    if (tr.ok) {
      const td = await tr.json();
      return td.html || '';
    }
    return '';
  },

  async startBatch(contacts, html) {
    const r = await fetch(this.SERVER_URL + '/send/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...this.AUTH_HEADER },
      body: JSON.stringify({ contacts, html }),
      signal: AbortSignal.timeout(10000),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  },

  async getStatus(jobId) {
    const r = await fetch(this.SERVER_URL + '/send/status/' + jobId, { headers: this.AUTH_HEADER });
    if (!r.ok) return null;
    return r.json();
  },

  async cancelBatch(jobId) {
    await fetch(this.SERVER_URL + '/send/cancel/' + jobId, { 
      method: 'POST',
      headers: this.AUTH_HEADER
    });
  },

  triggerSend() {
    const ids = Array.from(State.selectedIds);
    if (!ids.length) {
      toast('Выберите контакты для рассылки', 'err');
      return;
    }
    this.openModalByIds(ids);
  },

  async openModalByIds(ids) {
    const contacts = await Promise.all(ids.map(id => db.contacts.get(id)));
    const allWithEmail = contacts
      .filter(c => c && c.email && isValidEmail(c.email))
      .map(c => ({ id: c.id, name: c.name || '—', email: c.email }));

    const totalChecked = ids.length;
    const withEmailCount = allWithEmail.length;
    const invalidEmails = contacts
      .filter(c => c && c.email && c.email !== '@' && !isValidEmail(c.email))
      .map(c => c.name + ' (' + esc(c.email) + ')');

    if (!allWithEmail.length) {
      toast('Нет контактов с email в выборке', 'err');
      return;
    }

    if (invalidEmails.length) {
      toast(invalidEmails.length + ' невалидных email: ' + invalidEmails.join(', '), 'err');
    }

    if (withEmailCount < totalChecked) {
      toast(totalChecked + ' контактов → ' + withEmailCount + ' с email');
    }

    const dupes = this.findDuplicates(allWithEmail);
    if (dupes.length) {
      const msgs = dupes.map(d => d.email + ' (' + d.names.length + ' компании)').join(', ');
      toast('Найдены дубликаты: ' + msgs, 'err');
    }

    const deduped = this.deduplicateContacts(allWithEmail);
    this.openModal(deduped, totalChecked, withEmailCount);
  },

  async openModal(contacts, totalChecked, withEmailCount) {
    this.pendingContacts = contacts;
    this.currentJobId = null;
    if (this.pollInterval) { clearInterval(this.pollInterval); this.pollInterval = null; }

    const serverUp = await this.checkServer();
    let templateHtml = '';
    if (serverUp) {
      templateHtml = await this.getTemplate();
    }

    const statusDot = serverUp ? '🟢' : '🔴';
    const statusText = serverUp ? 'Подключено' : 'Не подключено';
    const countLabel = totalChecked && withEmailCount
      ? 'Получатели (' + withEmailCount + ' из ' + totalChecked + ')'
      : 'Получатели (' + contacts.length + ')';
    const recipientsHtml = contacts.map(c =>
      '<div class="email-recipient-item">' +
        '<span class="email-recipient-name">' + esc(c.name) + '</span>' +
        '<span class="email-recipient-email">' + esc(c.email) + '</span>' +
      '</div>'
    ).join('');

    const previewHtml = templateHtml
      ? '<div class="email-preview-toggle" onclick="EmailSender.togglePreview()">' +
          '<i class="ri-eye-line"></i> Показать шаблон' +
        '</div>' +
        '<div id="emailPreview" class="email-preview" style="display:none">' +
          '<div class="email-preview-inner">' + DOMPurify.sanitize(templateHtml) + '</div>' +
        '</div>'
      : '';

    const modal = document.getElementById('emailModal');
    modal.innerHTML =
      '<div class="modal email-modal">' +
        '<div class="email-modal-head">' +
          '<h3><i class="ri-mail-send-line"></i> Email-рассылка</h3>' +
          '<button class="btn-icon" onclick="EmailSender.closeModal()"><i class="ri-close-line"></i></button>' +
        '</div>' +

        '<div class="email-server-status">' +
          '<span class="email-status-dot">' + statusDot + '</span> ' +
          '<span class="email-status-text">' + statusText + '</span>' +
          (!serverUp ? '<span class="email-status-hint">Запустите: cd email && uvicorn server:app --port 8000</span>' : '') +
        '</div>' +

        '<div class="email-recipients">' +
          '<div class="email-recipients-head">' + countLabel + '</div>' +
          '<div class="email-recipients-list">' + recipientsHtml + '</div>' +
        '</div>' +

        previewHtml +

        '<div id="emailProgress" class="email-progress-wrap" style="display:none">' +
          '<div class="email-progress-track"><div id="emailProgressBar" class="email-progress-bar" style="width:0%"></div></div>' +
          '<span id="emailProgressText" class="email-progress-text">0 / ' + contacts.length + '</span>' +
        '</div>' +

        '<div id="emailLog" class="email-log" style="display:none"></div>' +

        '<div class="email-actions">' +
          '<button id="emailSendBtn" class="btn btn-p" onclick="EmailSender.startSend()" ' + (serverUp ? '' : 'disabled') + '>' +
            '<i class="ri-send-plane-2-fill"></i> Отправить' +
          '</button>' +
          '<button id="emailCancelBtn" class="btn" onclick="EmailSender.cancelSend()" style="display:none">' +
            '<i class="ri-stop-line"></i> Отмена' +
          '</button>' +
          '<button class="btn" onclick="EmailSender.closeModal()">' +
            '<i class="ri-close-line"></i> Закрыть' +
          '</button>' +
        '</div>' +
      '</div>';

    modal.style.display = 'flex';
  },

  togglePreview() {
    const el = document.getElementById('emailPreview');
    if (!el) return;
    const show = el.style.display === 'none';
    el.style.display = show ? 'block' : 'none';
    const tog = el.previousElementSibling;
    if (tog) tog.innerHTML = show
      ? '<i class="ri-eye-off-line"></i> Скрыть шаблон'
      : '<i class="ri-eye-line"></i> Показать шаблон';
  },

  async startSend() {
    const sendBtn = document.getElementById('emailSendBtn');
    const cancelBtn = document.getElementById('emailCancelBtn');
    const progressWrap = document.getElementById('emailProgress');
    const logEl = document.getElementById('emailLog');

    sendBtn.disabled = true;
    sendBtn.style.display = 'none';
    cancelBtn.style.display = 'inline-flex';
    progressWrap.style.display = 'flex';
    logEl.style.display = 'block';

    this.log('Начало рассылки...', 'ok');

    const contactsToSend = this.pendingContacts.map(c => ({ id: c.id, email: c.email, name: c.name }));

    try {
      const data = await this.startBatch(contactsToSend, null);

      this.currentJobId = data.job_id;
      this.log('Задача: ' + data.job_id.slice(0, 8) + '... всего ' + data.total, 'ok');

      this._sseResults = [];
      this._sseDone = false;
      this._sseSource = new EventSource(this.SERVER_URL + '/send/stream/' + data.job_id);

      this._sseSource.addEventListener('init', (e) => {
        const init = JSON.parse(e.data);
        if (init.results && init.results.length) {
          this._sseResults.push(...init.results);
          for (const res of init.results) {
            this.log((res.success ? '✓ ' : '✗ ') + res.email, res.success ? 'ok' : 'err');
          }
        }
        this._updateProgress(init.sent, init.failed, init.total);
      });

      this._sseSource.addEventListener('result', (e) => {
        const res = JSON.parse(e.data);
        this._sseResults.push(res);
        this.log((res.success ? '✓ ' : '✗ ') + res.email + (res.error ? ' — ' + res.error : ''), res.success ? 'ok' : 'err');
        this._updateProgress(res.sent, res.failed, res.total);
      });

      this._sseSource.addEventListener('done', (e) => {
        const done = JSON.parse(e.data);
        this._sseSource.close();
        this._sseSource = null;
        this._sseDone = true;

        const cancelBtn = document.getElementById('emailCancelBtn');
        if (cancelBtn) cancelBtn.style.display = 'none';

        if (done.status === 'cancelled') {
          this.log('Рассылка отменена. Отправлено: ' + done.sent, 'err');
        } else {
          this.log('Завершено! Отправлено: ' + done.sent + ', ошибок: ' + done.failed, 'ok');
        }

        const resultsWithIds = this._sseResults.map(res => {
          const contact = this.pendingContacts.find(c => c.email.toLowerCase() === res.email.toLowerCase());
          return {
            email: res.email,
            name: contact ? contact.name : (contact && contact._allNames ? contact._allNames.join(', ') : '—'),
            success: res.success,
            error: res.error || '',
            ids: contact ? (contact._allIds || [contact.id]) : [],
          };
        });

        this.showReport(resultsWithIds);
        this.onComplete({ sent: done.sent, failed: done.failed, results: this._sseResults });
      });

      this._sseSource.onerror = () => {
        if (!this._sseDone) {
          this.log('Соединение потеряно, проверяю статус...', 'warn');
          this._sseSource.close();
          this._sseSource = null;
          this._fallbackPoll();
        }
      };
    } catch (e) {
      this.log('Ошибка: ' + e.message, 'err');
      toast('Сервер не отвечает. Запустите сервер.', 'err');
      sendBtn.disabled = false;
      sendBtn.style.display = 'inline-flex';
      cancelBtn.style.display = 'none';
    }
  },

  _updateProgress(sent, failed, total) {
    const pct = total ? Math.round((sent + failed) / total * 100) : 0;
    const bar = document.getElementById('emailProgressBar');
    const txt = document.getElementById('emailProgressText');
    if (bar) bar.style.width = pct + '%';
    if (txt) txt.textContent = (sent + failed) + ' / ' + total;
  },

  async _fallbackPoll() {
    if (!this.currentJobId) return;
    try {
      const data = await this.getStatus(this.currentJobId);
      if (!data) return;

      const newResults = data.results.slice((this._sseResults || []).length);
      for (const res of newResults) {
        this._sseResults.push(res);
        this.log((res.success ? '✓ ' : '✗ ') + res.email + (res.error ? ' — ' + res.error : ''), res.success ? 'ok' : 'err');
      }
      this._updateProgress(data.sent, data.failed, data.total);

      if (data.status === 'completed' || data.status === 'cancelled') {
        const cancelBtn = document.getElementById('emailCancelBtn');
        if (cancelBtn) cancelBtn.style.display = 'none';

        if (data.status === 'cancelled') {
          this.log('Рассылка отменена. Отправлено: ' + data.sent, 'err');
        } else {
          this.log('Завершено! Отправлено: ' + data.sent + ', ошибок: ' + data.failed, 'ok');
        }

        const resultsWithIds = this._sseResults.map(res => {
          const contact = this.pendingContacts.find(c => c.email.toLowerCase() === res.email.toLowerCase());
          return {
            email: res.email,
            name: contact ? contact.name : (contact && contact._allNames ? contact._allNames.join(', ') : '—'),
            success: res.success,
            error: res.error || '',
            ids: contact ? (contact._allIds || [contact.id]) : [],
          };
        });

        this.showReport(resultsWithIds);
        await this.onComplete({ sent: data.sent, failed: data.failed, results: this._sseResults });
      } else {
        this.pollInterval = setInterval(() => this._fallbackPoll(), 5000);
      }
    } catch (e) {
      console.warn('fallback poll error:', e);
    }
  },

  classifyError(msg) {
    if (!msg) return 'err';
    const lower = msg.toLowerCase();
    if (lower.includes('smtp') || lower.includes('mail') || lower.includes('recipient') || lower.includes('sender') || lower.includes('auth')) return 'err';
    return 'warn';
  },

  async cancelBatch() {
    if (!this.currentJobId) return;
    try {
      await fetch(this.SERVER_URL + '/send/cancel/' + this.currentJobId, { method: 'POST', headers: this.AUTH_HEADER });
      this.log('Запрос на отмену отправлен...', 'err');
    } catch (e) {
      this.log('Ошибка отмены: ' + e.message, 'err');
    }
  },

  cancelSend() {
    this.cancelBatch();
  },

  async onComplete(results) {
    const sent = results.sent || 0;
    const failed = results.failed || 0;
    const sentEmails = new Set();

    for (const res of (results.results || [])) {
      if (res.success) {
        const contact = this.pendingContacts.find(c => c.email.toLowerCase() === res.email.toLowerCase());
        if (contact) {
          const ids = contact._allIds || [contact.id];
          ids.forEach(id => id && sentEmails.add(id));
        }
      }
    }

    for (const id of sentEmails) {
      await recordTouch(id, 'email', 'рассылка');
    }

    toast('Рассылка: ' + sent + ' отправлено, ' + failed + ' ошибок');
    await Render.renderChecklist();
    saveToServer();
  },

  showReport(results) {
    this.lastReport = {
      date: new Date().toISOString(),
      total: results.length,
      sent: results.filter(r => r.success).length,
      failed: results.filter(r => !r.success).length,
      results: results,
    };

    const r = this.lastReport;
    const listHtml = results.map(res => {
      const cls = res.success ? 'email-report-item-ok' : 'email-report-item-err';
      const icon = res.success ? '✓' : '✗';
      const errHtml = res.error
        ? '<div class="email-report-error">' + esc(res.error.length > 80 ? res.error.slice(0, 80) + '…' : res.error) + '</div>'
        : '';
      return '<div class="email-report-item ' + cls + '">' +
        '<span class="email-report-icon">' + icon + '</span>' +
        '<div class="email-report-item-info">' +
          '<div class="email-report-item-name">' + esc(res.name) + '</div>' +
          '<div class="email-report-item-email">' + esc(res.email) + '</div>' +
          errHtml +
        '</div>' +
      '</div>';
    }).join('');

    const modal = document.getElementById('emailReportModal');
    if (!modal) {
      const wrapper = document.createElement('div');
      wrapper.id = 'emailReportModal';
      wrapper.className = 'ov';
      wrapper.style.display = 'none';
      document.body.appendChild(wrapper);
    }
    const reportModal = document.getElementById('emailReportModal');
    reportModal.innerHTML =
      '<div class="modal" style="max-width:500px">' +
        '<h3 style="font-size:15px;font-weight:700;color:var(--hd);margin-bottom:16px;display:flex;align-items:center;gap:8px">' +
          '<i class="ri-bar-chart-2-line"></i> Отчёт о рассылке' +
        '</h3>' +
        '<div class="email-report-summary">' +
          '<div class="email-report-stat">' +
            '<span class="email-report-label">Всего:</span>' +
            '<span class="email-report-value">' + r.total + '</span>' +
          '</div>' +
          '<div class="email-report-stat">' +
            '<span class="email-report-label">Успешно:</span>' +
            '<span class="email-report-value" style="color:var(--cg)">' + r.sent + '</span>' +
          '</div>' +
          '<div class="email-report-stat">' +
            '<span class="email-report-label">Ошибки:</span>' +
            '<span class="email-report-value" style="color:var(--cr)">' + r.failed + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="email-report-list">' + listHtml + '</div>' +
        '<div class="fl jc gap2 mt3">' +
          '<button class="btn btn-s" onclick="EmailSender.exportReport()">' +
            '<i class="ri-file-download-line"></i> Экспорт' +
          '</button>' +
          '<button class="btn btn-s btn-p" onclick="EmailSender.closeReport()">Закрыть</button>' +
        '</div>' +
      '</div>';
    reportModal.style.display = 'flex';
  },

  closeReport() {
    const modal = document.getElementById('emailReportModal');
    if (modal) modal.style.display = 'none';
  },

  exportReport() {
    if (!this.lastReport) return;
    const json = JSON.stringify(this.lastReport, null, 2);
    const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = 'email-report-' + ts + '.json';
    if (typeof saveAs !== 'undefined') {
      saveAs(blob, filename);
    } else {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    }
    toast('Отчёт сохранён: ' + filename);
  },

  log(msg, type) {
    const el = document.getElementById('emailLog');
    if (!el) return;
    const cls = type === 'err' ? 'email-log-err' : type === 'warn' ? 'email-log-warn' : 'email-log-ok';
    const time = new Date().toLocaleTimeString('ru-RU');
    el.innerHTML += '<div class="' + cls + '"><span class="email-log-time">[' + time + ']</span> ' + esc(msg) + '</div>';
    el.scrollTop = el.scrollHeight;
  },

  closeModal() {
    if (this.pollInterval) { clearInterval(this.pollInterval); this.pollInterval = null; }
    if (this._sseSource) { this._sseSource.close(); this._sseSource = null; }
    this.currentJobId = null;
    this.pendingContacts = [];
    this._lastResultCount = 0;
    this._sseResults = [];
    this._sseDone = false;
    const modal = document.getElementById('emailModal');
    if (modal) modal.style.display = 'none';
  },
};
