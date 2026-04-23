/* ── Theme ── */
function getTheme() { return localStorage.getItem('vt_theme') || 'light'; }
function applyTheme() {
  const dark = getTheme() === 'dark';
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : '');
  const btn = document.getElementById('themeBtn');
  if (btn) btn.innerHTML = dark ? '&#9728; Light' : '&#127769; Dark';
}
function toggleTheme() {
  localStorage.setItem('vt_theme', getTheme() === 'dark' ? 'light' : 'dark');
  applyTheme();
}
applyTheme();

/* ── Mobile sidebar ── */
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('overlay').classList.toggle('open');
}

/* ── Delete modal ── */
let _deleteCb = null;
function deleteEntry(url, callback) {
  const modal = document.getElementById('deleteModal');
  modal.classList.remove('hidden');
  _deleteCb = async () => {
    await fetch(url, { method: 'DELETE' });
    closeDeleteModal();
    if (callback) callback();
  };
  document.getElementById('confirmDeleteBtn').onclick = _deleteCb;
}
function closeDeleteModal() {
  document.getElementById('deleteModal').classList.add('hidden');
  _deleteCb = null;
}

/* ── Helpers ── */
function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
function fmtDate(d) {
  if (!d) return '-';
  const p = d.split('-');
  return p[2] + '/' + p[1] + '/' + p[0];
}
function fmtDateTime(dt) {
  if (!dt) return '-';
  return dt.slice(0, 10).split('-').reverse().join('/') + ' ' + (dt.slice(11, 16) || '');
}

/* ── Calendar rendering (used by dashboard) ── */
const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

function renderCalendar(data, year, month) {
  const monthIdx = month - 1;
  const titleEl = document.getElementById('calTitle');
  if (titleEl) titleEl.textContent = MONTHS[monthIdx] + ' ' + year;

  const grid = document.getElementById('calGrid');
  if (!grid) return;

  const firstDay = new Date(year, monthIdx, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const today = new Date();

  const scheduledDays = getScheduledDays(data.rules, year, monthIdx, daysInMonth);

  const visitMap = {};
  data.visits.forEach(v => {
    const d = new Date(v.date);
    const key = d.getDate();
    if (!visitMap[key]) visitMap[key] = [];
    visitMap[key].push(v);
  });

  const incidentDays = new Set();
  data.incidents.forEach(i => {
    const d = new Date(i.date);
    incidentDays.add(d.getDate());
  });

  let html = '';
  ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].forEach(d => html += `<div class="day-label">${d}</div>`);

  const prevDays = new Date(year, monthIdx, 0).getDate();
  for (let i = firstDay - 1; i >= 0; i--) {
    html += `<div class="cal-cell other">${prevDays - i}</div>`;
  }

  for (let day = 1; day <= daysInMonth; day++) {
    let cls = 'cal-cell';
    if (today.getDate() === day && today.getMonth() === monthIdx && today.getFullYear() === year) cls += ' today';

    const dayVisits = visitMap[day];
    const isScheduled = scheduledDays.has(day);

    if (dayVisits) {
      const hasNoShow = dayVisits.some(v => v.punctuality === 'noshow');
      const hasLate = dayVisits.some(v => v.punctuality === 'late');
      if (hasNoShow) cls += ' missed';
      else if (hasLate) cls += ' late';
      else cls += ' completed';
    } else if (isScheduled) {
      const cellDate = new Date(year, monthIdx, day);
      if (cellDate < today) cls += ' missed';
      else cls += ' scheduled';
    }

    if (incidentDays.has(day)) cls += ' incident';
    html += `<div class="${cls}">${day}</div>`;
  }

  const totalCells = firstDay + daysInMonth;
  const remaining = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
  for (let i = 1; i <= remaining; i++) {
    html += `<div class="cal-cell other">${i}</div>`;
  }

  grid.innerHTML = html;
}

function getScheduledDays(rules, year, monthIdx, daysInMonth) {
  const days = new Set();
  (rules || []).forEach(rule => {
    const cfg = rule.config || {};
    if (rule.rule_type === 'weekly') {
      for (let d = 1; d <= daysInMonth; d++) {
        if ((cfg.days || []).includes(new Date(year, monthIdx, d).getDay())) days.add(d);
      }
    } else if (rule.rule_type === 'biweekly') {
      const refDate = new Date(cfg.refStart);
      const refWeekStart = new Date(refDate);
      refWeekStart.setDate(refDate.getDate() - refDate.getDay());
      for (let d = 1; d <= daysInMonth; d++) {
        const current = new Date(year, monthIdx, d);
        const currentWeekStart = new Date(current);
        currentWeekStart.setDate(current.getDate() - current.getDay());
        const diffWeeks = Math.round((currentWeekStart - refWeekStart) / (7 * 24 * 60 * 60 * 1000));
        if (diffWeeks % 2 === 0 && (cfg.days || []).includes(current.getDay())) days.add(d);
      }
    } else if (rule.rule_type === 'monthly') {
      (cfg.dates || []).forEach(date => { if (date >= 1 && date <= daysInMonth) days.add(date); });
    }
  });
  return days;
}
