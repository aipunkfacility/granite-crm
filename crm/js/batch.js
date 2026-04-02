/* ===== BATCH OPERATIONS ===== */
const Batch = {
  /* Mark all selected contacts as touched for current channel */
  async markSelected(note) {
    const ids = Array.from(State.selectedIds);
    if (!ids.length) { toast('Ничего не выбрано', 'err'); return; }

    const ch = State.currentChannel;
    let count = 0;
    for (const id of ids) {
      await recordTouch(id, ch, note);
      count++;
    }

    State.clearSelection();
    toast('Отмечено: ' + count);
    await Render.renderChecklist();
    saveToServer();
  },

  /* Undo touch for all selected contacts */
  async undoSelected() {
    const ids = Array.from(State.selectedIds);
    if (!ids.length) { toast('Ничего не выбрано', 'err'); return; }

    const ch = State.currentChannel;
    let count = 0;
    for (const id of ids) {
      await undoTouch(id, ch);
      count++;
    }

    State.clearSelection();
    toast('Снято: ' + count);
    await Render.renderChecklist();
    saveToServer();
  },

  /* Select all contacts in the "not sent" group */
  selectUnsent(list) {
    const ch = getChannel(State.currentChannel);
    if (!ch) return;
    const unsent = list.filter(c => !c[ch.lastField]);
    State.selectAll(unsent.map(c => c.id));
    Render.renderChecklist();
  },

  /* Select all contacts in the "sent" group */
  selectSent(list) {
    const ch = getChannel(State.currentChannel);
    if (!ch) return;
    const sent = list.filter(c => !!c[ch.lastField]);
    State.selectAll(sent.map(c => c.id));
    Render.renderChecklist();
  },

  /* Mark ALL unsent contacts (no selection needed) */
  async markAllUnsent(note) {
    const list = await db.contacts.where('area').equals(State.currentArea).toArray();
    const ch = getChannel(State.currentChannel);
    if (!ch) return;

    const unsent = list.filter(c => !c[ch.lastField]);
    if (!unsent.length) { toast('Все уже отмечены', 'err'); return; }

    for (const c of unsent) {
      await recordTouch(c.id, ch.k, note);
    }

    toast('Отмечено все: ' + unsent.length);
    await Render.renderChecklist();
    saveToServer();
  },

  /* Undo ALL sent contacts */
  async undoAllSent() {
    const list = await db.contacts.where('area').equals(State.currentArea).toArray();
    const ch = getChannel(State.currentChannel);
    if (!ch) return;

    const sent = list.filter(c => !!c[ch.lastField]);
    if (!sent.length) { toast('Нет отправленных', 'err'); return; }

    for (const c of sent) {
      await undoTouch(c.id, ch.k);
    }

    toast('Снято все: ' + sent.length);
    await Render.renderChecklist();
    saveToServer();
  },

  /* Open email sending modal for selected contacts */
  async sendEmails() {
    const ids = Array.from(State.selectedIds);
    if (!ids.length) {
      toast('Выберите контакты для рассылки', 'err');
      return;
    }

    const contacts = await Promise.all(ids.map(id => db.contacts.get(id)));
    const allWithEmail = contacts
      .filter(c => c && c.email && c.email.includes('@') && c.email !== '@')
      .map(c => ({ id: c.id, name: c.name || '—', email: c.email }));

    if (!allWithEmail.length) {
      toast('Нет контактов с email в выборке', 'err');
      return;
    }

    // Deduplicate by email
    const seen = new Map();
    const deduped = [];
    allWithEmail.forEach(c => {
      const e = c.email.toLowerCase();
      if (!seen.has(e)) {
        seen.set(e, true);
        deduped.push(c);
      }
    });

    EmailSender.openModal(deduped);
  },
};
