/* ===== APPLICATION STATE ===== */
const State = {
  currentArea: '',
  currentChannel: 'tg',
  searchQuery: '',
  expandedId: null,
  selectedIds: new Set(),
  popoverContactId: null,
  pendingImportRows: null,
  dbDirHandle: null,
  hiddenFields: new Set(JSON.parse(localStorage.getItem('crm-flds') || '["address","vk"]')),
  visibleCols: new Set(['none', 'blue', 'yellow', 'green', 'red', 'gray', 'archived']),

  /* Persist hidden fields to localStorage */
  saveFieldPrefs() {
    localStorage.setItem('crm-flds', JSON.stringify(Array.from(this.hiddenFields)));
  },

  /* Toggle field visibility */
  toggleField(key) {
    if (this.hiddenFields.has(key)) {
      this.hiddenFields.delete(key);
    } else {
      this.hiddenFields.add(key);
    }
    this.saveFieldPrefs();
  },

  /* Set search query */
  setSearch(query) {
    this.searchQuery = query.trim().toLowerCase();
  },

  /* Set current channel */
  setChannel(ch) {
    this.currentChannel = ch;
    this.selectedIds.clear();
    this.expandedId = null;
  },

  /* Toggle selection of a contact */
  toggleSelect(id) {
    if (this.selectedIds.has(id)) {
      this.selectedIds.delete(id);
    } else {
      this.selectedIds.add(id);
    }
  },

  /* Select all contacts in a group */
  selectAll(ids) {
    ids.forEach(id => this.selectedIds.add(id));
  },

  /* Deselect all contacts in a group */
  deselectAll(ids) {
    ids.forEach(id => this.selectedIds.delete(id));
  },

  /* Clear all selections */
  clearSelection() {
    this.selectedIds.clear();
  },

  /* Toggle accordion expand/collapse */
  toggleExpand(id) {
    this.expandedId = this.expandedId === id ? null : id;
  },

  /* Navigate to areas list */
  goAreas() {
    this.currentArea = '';
    this.currentChannel = 'tg';
    this.selectedIds.clear();
    this.expandedId = null;
    this.closePopover();
    document.getElementById('pageContacts').style.display = 'none';
    document.getElementById('pageAreas').style.display = 'flex';
    Render.renderAreas();
  },

  /* Navigate to area checklist */
  async goArea(area) {
    this.currentArea = area;
    this.currentChannel = 'tg';
    this.selectedIds.clear();
    this.expandedId = null;
    this.closePopover();
    document.getElementById('pageAreas').style.display = 'none';
    document.getElementById('pageContacts').style.display = 'flex';
    document.getElementById('areaTitle').textContent = area;
    Render.renderFieldToggles();
    await Render.renderChecklist();
  },

  /* Open popover for contact (legacy, kept for popover fallback) */
  openPopover(id, event) {
    this.popoverContactId = id;
    Render.renderPopover(id, event);
  },

  /* Close popover */
  closePopover() {
    this.popoverContactId = null;
    const popOv = document.getElementById('popOv');
    const popPanel = document.getElementById('popPanel');
    if (popOv) popOv.style.display = 'none';
    if (popPanel) popPanel.style.display = 'none';
  },

  /* Re-open popover by ID (after update) */
  async reopenPopover() {
    const id = this.popoverContactId;
    if (!id) return;
    const card = document.querySelector('.kcard[data-id="' + escAttr(id) + '"]');
    if (card) {
      const ev = { target: card, stopPropagation: () => {} };
      this.openPopover(id, ev);
    } else {
      this.closePopover();
    }
  },
};
