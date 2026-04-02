/* ===== CONSTANTS ===== */
const POPOVER_W = 340;
const POPOVER_MAX_H_RATIO = 0.85;
const POPOVER_MAX_H = 600;
const POPOVER_OFFSET = 12;
const POPOVER_MIN_EDGE = 10;
const SEARCH_DEBOUNCE_MS = 200;
const TOAST_DURATION_MS = 3000;
const MAX_VISIBLE_FIELDS = 3;
const DB_NAME = 'MiniCRM_v8';

/* ===== FIELD & COLUMN DEFINITIONS ===== */
const FIELDS = [
  { k: 'phone',    l: 'Телефон', icon: 'ri-phone-line' },
  { k: 'email',    l: 'Email',   icon: 'ri-mail-line' },
  { k: 'website',  l: 'Сайт',    icon: 'ri-global-line' },
  { k: 'address',  l: 'Адрес',   icon: 'ri-map-pin-line' },
  { k: 'telegram', l: 'TG',      icon: 'ri-telegram-fill' },
  { k: 'whatsapp', l: 'WA',      icon: 'ri-whatsapp-fill' },
  { k: 'vk',       l: 'VK',      icon: 'ri-brand-vk-fill' },
];

const COLS = [
  { k: 'none',     l: 'Без метки',  dot: '' },
  { k: 'blue',     l: 'Без ответа', dot: 'cb' },
  { k: 'yellow',   l: 'В работе',   dot: 'cy' },
  { k: 'green',    l: 'Заинтерес.', dot: 'cg' },
  { k: 'red',      l: 'Отказ',      dot: 'cr' },
  { k: 'gray',     l: 'Не акт.',    dot: 'cv' },
  { k: 'archived', l: 'Архив',      dot: 'cv' },
];

const COLOR_LABELS = {
  red:    'Отказ',
  yellow: 'В работе',
  green:  'Заинтересованы',
  blue:   'Без ответа',
  gray:   'Не актуально',
};

const COLOR_BG = {
  red:    'FFFEE2E2',
  yellow: 'FFFEF08A',
  green:  'FFBBF7D0',
  blue:   'FFBFDBFE',
  gray:   'FFE2E8F0',
};

const COLOR_FG = {
  red:    'FF991B1B',
  yellow: 'FF854D0E',
  green:  'FF166534',
  blue:   'FF1E40AF',
  gray:   'FF475569',
};

/* ===== CHANNEL DEFINITIONS ===== */
const CHANNELS = [
  { k: 'tg',    l: 'TG',    icon: 'ri-telegram-fill', color: '#60a5fa', field: 'telegram',  lastField: 'last_tg',    tag: 'тг' },
  { k: 'wa',    l: 'WA',    icon: 'ri-whatsapp-fill', color: '#4ade80', field: 'whatsapp',  lastField: 'last_wa',    tag: 'wa' },
  { k: 'email', l: 'Почта', icon: 'ri-mail-fill',     color: '#fbbf24', field: 'email',     lastField: 'last_email', tag: 'почта' },
];

function getChannel(k) {
  return CHANNELS.find(c => c.k === k);
}

/* ===== UTILITIES ===== */

/**
 * Escape HTML entities safely using DOM textContent.
 */
function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

/**
 * Escape for attribute values (onclick, data-*, etc.)
 */
function escAttr(s) {
  if (!s) return '';
  return esc(s)
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Parse status string into array of channel tags.
 */
function parseSt(s) {
  return s
    ? s.toLowerCase().split(/[,;\n]\s*/).map(x => x.trim()).filter(Boolean)
    : [];
}

/**
 * Show toast notification.
 */
function toast(message, type) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const d = document.createElement('div');
  d.className = 'toast' + (type === 'err' ? ' err' : '');
  d.innerHTML =
    '<i class="ri-' + (type === 'err' ? 'close-circle' : 'checkbox-circle') + '-line"></i> ' +
    esc(message);
  document.body.appendChild(d);
  setTimeout(() => { if (d.parentNode) d.remove(); }, TOAST_DURATION_MS);
}

/**
 * Create a debounced function.
 */
function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Check if a contact has a given channel available.
 */
function hasChannel(contact, channel) {
  const val = contact[channel];
  if (!val) return false;
  if (channel === 'email') return val !== '@' && val !== '';
  return val !== '-' && val !== '';
}

/**
 * Render a mini value for kanban card field row.
 */
function renderMiniVal(field, val) {
  if (field === 'website' && val !== '@') {
    return esc(val.replace(/^https?:\/\//, ''));
  }
  return esc(val);
}

/**
 * Build a stats badge HTML snippet.
 */
function stb(n, color, label) {
  return '<div class="stb">' +
    '<div class="stn" style="color:' + color + '">' + n + '</div>' +
    '<div class="stl">' + label + '</div>' +
    '</div>';
}

/**
 * Format date for display (DD.MM.YYYY) or return empty string.
 */
function fmtDate(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return '';
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yy = String(d.getFullYear()).slice(2);
    return dd + '.' + mm + '.' + yy;
  } catch {
    return '';
  }
}

/**
 * Get current ISO date string.
 */
function nowISO() {
  return new Date().toISOString();
}

/**
 * Transliterate Cyrillic to Latin for safe filenames.
 */
function transliterate(s) {
  const map = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh',
    'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
    'ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ё':'Yo','Ж':'Zh',
    'З':'Z','И':'I','Й':'Y','К':'K','Л':'L','М':'M','Н':'N','О':'O',
    'П':'P','Р':'R','С':'S','Т':'T','У':'U','Ф':'F','Х':'Kh','Ц':'Ts',
    'Ч':'Ch','Ш':'Sh','Щ':'Shch','Ъ':'','Ы':'Y','Ь':'','Э':'E','Ю':'Yu','Я':'Ya'
  };
  return s.split('').map(c => map[c] !== undefined ? map[c] : c).join('');
}
