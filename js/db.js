/* ===== DATABASE (Dexie) ===== */
let db;

/**
 * Initialize Dexie database with versioning support.
 * v1: initial schema
 * v2: added touch tracking fields (last_tg, last_wa, last_email, touch_history)
 */
function initDB() {
  db = new Dexie(DB_NAME);

  db.version(1).stores({
    contacts: 'id,area,name,city,phone,email,status,website,address,vk,telegram,whatsapp,color_label,note,archived',
  });

  db.version(2).stores({
    contacts: 'id,area,name,city,phone,email,status,website,address,vk,telegram,whatsapp,color_label,note,archived,last_tg,last_wa,last_email,touch_history',
  }).upgrade(tx => {
    return tx.contacts.toCollection().modify(c => {
      c.last_tg = c.last_tg || '';
      c.last_wa = c.last_wa || '';
      c.last_email = c.last_email || '';
      c.touch_history = c.touch_history || [];

      const sa = parseSt(c.status);
      const today = nowISO();
      if (sa.includes('тг') && !c.last_tg) c.last_tg = today;
      if (sa.includes('wa') && !c.last_wa) c.last_wa = today;
      if (sa.includes('почта') && !c.last_email) c.last_email = today;
    });
  });

  return db.open();
}

/* ===== SERVER-BASED PERSISTENCE ===== */

const SERVER_URL = (typeof window !== 'undefined' && window.location && window.location.origin) 
  ? window.location.origin 
  : 'http://localhost:8000';

const AUTH_HEADER = API_TOKEN ? { 'Authorization': 'Bearer ' + API_TOKEN } : {};

/**
 * Check if server is reachable.
 */
async function isServerUp() {
  try {
    const resp = await fetch(SERVER_URL + '/health', { signal: AbortSignal.timeout(3000) });
    return resp.ok;
  } catch {
    return false;
  }
}

/**
 * Load all JSON files from server into IndexedDB.
 */
async function loadFromServer() {
  try {
    const resp = await fetch(SERVER_URL + '/db/list', { 
      signal: AbortSignal.timeout(5000),
      headers: AUTH_HEADER
    });
    if (!resp.ok) return 0;

    const data = await resp.json();
    const files = data.files || [];
    if (!files.length) return 0;

    let loaded = 0;
    for (const file of files) {
      try {
        const fileResp = await fetch(SERVER_URL + '/db/' + encodeURIComponent(file.name), {
          headers: AUTH_HEADER
        });
        if (!fileResp.ok) continue;
        const contacts = await fileResp.json();
        if (!Array.isArray(contacts)) continue;

        await db.transaction('rw', db.contacts, async () => {
          for (const c of contacts) {
            if (!c.id) continue;
            await db.contacts.put(c);
            loaded++;
          }
        });
      } catch (e) {
        console.warn('loadFromServer: failed to load', file.name, e);
      }
    }

    return loaded;
  } catch (e) {
    console.warn('loadFromServer:', e);
    return -1; // -1 = server unreachable
  }
}

/**
 * Save all contacts to server as JSON files (one per area).
 */
async function saveToServer() {
  try {
    const all = await db.contacts.toArray();
    const areas = {};
    all.forEach(c => {
      const a = c.area || 'Без области';
      if (!areas[a]) areas[a] = [];
      areas[a].push(c);
    });

    for (const area in areas) {
      const safeName = transliterate(area).replace(/[^a-zA-Z0-9_-]/g, '-') + '.json';
      const resp = await fetch(SERVER_URL + '/db/' + encodeURIComponent(safeName), {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          ...AUTH_HEADER
        },
        body: JSON.stringify(areas[area]),
        signal: AbortSignal.timeout(10000),
      });
      if (!resp.ok) {
        console.warn('saveToServer: failed to save', safeName);
      }
    }
  } catch (e) {
    console.warn('saveToServer:', e);
    toast('Сервер недоступен — данные сохранены только локально', 'err');
  }
}

/**
 * Debounced save — prevents excessive server writes.
 */
let _saveTimer = null;
function saveToServerDebounced() {
  if (_saveTimer) clearTimeout(_saveTimer);
  _saveTimer = setTimeout(() => saveToServer(), SAVE_DEBOUNCE_MS);
}

/* ===== LEGACY: File System Access API ===== */

async function pickDbDir() {
  if (!window.showDirectoryPicker) {
    toast('Нужен Chrome/Edge', 'err');
    return;
  }
  try {
    State.dbDirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
    toast('Папка: ' + State.dbDirHandle.name);
    await loadFromDbDir();
    Render.renderAreas();
  } catch (e) {
    if (e.name !== 'AbortError') {
      console.error('pickDbDir:', e);
      toast('Ошибка выбора папки', 'err');
    }
  }
}

async function saveToDbDir() {
  if (!State.dbDirHandle) return;
  try {
    const all = await db.contacts.toArray();
    const areas = {};
    all.forEach(c => {
      const a = c.area || 'Без области';
      if (!areas[a]) areas[a] = [];
      areas[a].push(c);
    });

    const keys = Object.keys(areas);
    for (let i = 0; i < keys.length; i++) {
      const a = keys[i];
      const cs = areas[a];
      const safeName = a.replace(/[^a-zA-Zа-яА-Я0-9_-]/g, '_') + '.json';
      const fh = await State.dbDirHandle.getFileHandle(safeName, { create: true });
      const w = await fh.createWritable();
      await w.write(JSON.stringify(cs, null, 2));
      await w.close();
    }
  } catch (e) {
    console.warn('saveToDbDir:', e);
    toast('Ошибка сохранения на диск', 'err');
  }
}
async function loadFromDbDir() {
  if (!State.dbDirHandle) return;
  try {
    for await (const entry of State.dbDirHandle.values()) {
      if (entry.kind === 'file' && entry.name.endsWith('.json')) {
        const file = await entry.getFile();
        const text = await file.text();
        const data = JSON.parse(text);
        if (Array.isArray(data)) {
          let count = 0;
          await db.transaction('rw', db.contacts, async () => {
            for (let j = 0; j < data.length; j++) {
              const r = data[j];
              if (!r.id) continue;
              const ex = await db.contacts.get(r.id);
              if (!ex) {
                await db.contacts.put(r);
                count++;
              }
            }
          });
          if (count) toast('Загружено ' + count + ' из ' + entry.name);
        }
      }
    }
  } catch (e) {
    console.warn('loadFromDbDir:', e);
    toast('Ошибка загрузки из папки', 'err');
  }
}

/* ===== TOUCH TRACKING HELPERS ===== */

async function recordTouch(id, channel, note) {
  const c = await db.contacts.get(id);
  if (!c) return;

  const entry = { ch: channel, at: nowISO(), note: note || '' };
  const history = Array.isArray(c.touch_history) ? c.touch_history.slice() : [];
  history.push(entry);

  const chDef = getChannel(channel);
  const updates = {
    touch_history: history,
  };
  if (chDef) {
    updates[chDef.lastField] = nowISO();
  }

  await db.contacts.update(id, updates);
  saveToServerDebounced();
}

async function undoTouch(id, channel) {
  const c = await db.contacts.get(id);
  if (!c) return;

  const history = Array.isArray(c.touch_history) ? c.touch_history.slice() : [];
  const idx = history.findLastIndex(t => t.ch === channel);
  if (idx >= 0) {
    history.splice(idx, 1);
  }

  const chDef = getChannel(channel);
  const updates = { touch_history: history };
  if (chDef) {
    const prev = history.filter(t => t.ch === channel).pop();
    updates[chDef.lastField] = prev ? prev.at : '';
  }

  await db.contacts.update(id, updates);
  saveToServerDebounced();
}
