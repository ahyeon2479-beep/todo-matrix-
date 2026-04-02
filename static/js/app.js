/* ── State ───────────────────────────────────────────── */
const WD = ['월','화','수','목','금','토','일'];
const Q_COLORS = {
    'true|true':   '#FFB800',
    'false|true':  '#C47888',
    'true|false':  '#6A9AB0',
    'false|false': '#9080B8',
};
const Q_LABELS = {
    'true|true':   'Q1 · 긴급하고 중요함 → 즉시 처리',
    'false|true':  'Q2 · 중요하지만 긴급하지 않음 → 일정 수립',
    'true|false':  'Q3 · 긴급하지만 중요하지 않음 → 위임',
    'false|false': 'Q4 · 긴급하지도 중요하지도 않음 → 제거',
};

let currentView = 'matrix';
let matrixDate = todayStr();
let calYear, calMonth;
let habitYear, habitMonth;
let holidays = {};

/* ── Init ────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
    const today = new Date();
    calYear = today.getFullYear();
    calMonth = today.getMonth() + 1;
    habitYear = calYear;
    habitMonth = calMonth;

    holidays = await api('/api/holidays');
    setupHeader();
    setupMatrix();
    setupCalendar();
    setupHabitFull();
    setupRepeatView();
    setupModals();
    showView('matrix');
});

/* ── Helpers ─────────────────────────────────────────── */
function todayStr() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function dateObj(s) { const [y,m,d] = s.split('-').map(Number); return new Date(y,m-1,d); }
function fmtDate(s) {
    const d = dateObj(s);
    const wd = ['일','월','화','수','목','금','토'][d.getDay()];
    return `${d.getFullYear()}년 ${d.getMonth()+1}월 ${d.getDate()}일 (${wd})`;
}
async function api(url, opts) {
    const res = await fetch(url, {
        headers: {'Content-Type':'application/json'},
        ...opts,
    });
    return res.json();
}

/* ── Header ──────────────────────────────────────────── */
function setupHeader() {
    const $d = document.getElementById('headerDate');
    $d.textContent = fmtDate(todayStr());

    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => showView(btn.dataset.view));
    });
    document.getElementById('btnAddTodo').addEventListener('click', () => openTodoModal());
    document.getElementById('sidebarAddBtn').addEventListener('click', () => openTodoModal());
    document.getElementById('showCompleted').addEventListener('change', refreshMatrix);

    // Hamburger
    const hBtn = document.getElementById('hamburgerBtn');
    const hMenu = document.getElementById('hamburgerMenu');
    hBtn.addEventListener('click', () => hMenu.classList.toggle('hidden'));
    document.addEventListener('click', e => {
        if (!hBtn.contains(e.target) && !hMenu.contains(e.target)) hMenu.classList.add('hidden');
    });
    hMenu.querySelector('[data-action="repeatView"]').addEventListener('click', () => { hMenu.classList.add('hidden'); showView('repeat'); });
    hMenu.querySelector('[data-action="habitFullView"]').addEventListener('click', () => { hMenu.classList.add('hidden'); showView('habitFull'); });
}

function showView(name) {
    currentView = name;
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    if (name === 'matrix') {
        document.getElementById('matrixView').classList.remove('hidden');
        document.getElementById('btnMatrix').classList.add('active');
        refreshMatrix();
    } else if (name === 'calendar') {
        document.getElementById('calendarView').classList.remove('hidden');
        document.getElementById('btnCalendar').classList.add('active');
        refreshCalendar();
    } else if (name === 'habitFull') {
        document.getElementById('habitFullView').classList.remove('hidden');
        document.getElementById('btnHabitFull').classList.add('active');
        refreshHabitFull();
    } else if (name === 'repeat') {
        document.getElementById('repeatView').classList.remove('hidden');
        refreshRepeatView();
    }
}

/* ── Matrix View ─────────────────────────────────────── */
function setupMatrix() {
    document.getElementById('matrixPrev').addEventListener('click', () => { matrixDate = shiftDate(matrixDate, -1); refreshMatrix(); });
    document.getElementById('matrixNext').addEventListener('click', () => { matrixDate = shiftDate(matrixDate, 1); refreshMatrix(); });
    document.getElementById('matrixToday').addEventListener('click', () => { matrixDate = todayStr(); refreshMatrix(); });
    document.querySelectorAll('.q-add').forEach(btn => {
        const q = btn.closest('.quadrant');
        btn.addEventListener('click', () => openTodoModal(null, q.dataset.urgent === 'true', q.dataset.important === 'true'));
    });
}

function shiftDate(s, delta) {
    const d = dateObj(s);
    d.setDate(d.getDate() + delta);
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

async function refreshMatrix() {
    document.getElementById('matrixDateLabel').textContent = fmtDate(matrixDate) + ' 할일 목록';
    const todos = await api(`/api/todos?date=${matrixDate}`);
    const show = document.getElementById('showCompleted').checked;

    document.querySelectorAll('.quadrant').forEach(q => {
        const u = q.dataset.urgent === 'true';
        const imp = q.dataset.important === 'true';
        const items = todos.filter(t => t.urgent === u && t.important === imp && (show || !t.completed));
        const $items = q.querySelector('.q-items');
        $items.innerHTML = '';
        items.forEach(t => {
            const div = document.createElement('div');
            div.className = 'q-item' + (t.completed ? ' completed' : '');
            div.innerHTML = `
                <input type="checkbox" ${t.completed ? 'checked' : ''}>
                <span class="q-item-title">${esc(t.title)}</span>
                <button class="q-item-btn edit-btn">&#9998;</button>
                <button class="q-item-btn del-btn">&times;</button>
            `;
            div.querySelector('input').addEventListener('change', () => toggleTodo(t.id));
            div.querySelector('.q-item-title').addEventListener('click', () => openTodoModal(t));
            div.querySelector('.edit-btn').addEventListener('click', () => openTodoModal(t));
            div.querySelector('.del-btn').addEventListener('click', () => deleteTodo(t.id, t.title));
            $items.appendChild(div);
        });
    });
    refreshSummary(todos, show);
    loadMemo();
}

function refreshSummary(todos, show) {
    const $s = document.getElementById('todoSummary');
    $s.innerHTML = '';
    const groups = [
        {u:true,i:true,color:'#FFB800',label:'Q1 긴급+중요'},
        {u:false,i:true,color:'#C47888',label:'Q2 중요'},
        {u:true,i:false,color:'#6A9AB0',label:'Q3 긴급'},
        {u:false,i:false,color:'#9080B8',label:'Q4 기타'},
    ];
    let any = false;
    groups.forEach(g => {
        const items = todos.filter(t => t.urgent===g.u && t.important===g.i && (show || !t.completed));
        if (!items.length) return;
        any = true;
        const div = document.createElement('div');
        div.className = 'summary-group';
        div.innerHTML = `<div class="summary-header" style="background:${g.color}">${g.label}</div>`;
        items.forEach(t => {
            const title = t.title.length > 16 ? t.title.slice(0,16)+'…' : t.title;
            div.innerHTML += `<div class="summary-item"><span class="summary-dot" style="background:${g.color}"></span>${esc(title)}</div>`;
        });
        $s.appendChild(div);
    });
    if (!any) $s.innerHTML = '<div style="color:#999;padding:12px;font-size:11px;">이 날의 할일이 없습니다</div>';
}

/* ── Memo ────────────────────────────────────────────── */
let memoTimer;
async function loadMemo() {
    const data = await api(`/api/memos/${matrixDate}`);
    document.getElementById('memoBox').value = data.text || '';
}
document.getElementById('memoBox')?.addEventListener('input', () => {
    clearTimeout(memoTimer);
    memoTimer = setTimeout(saveMemo, 800);
});
async function saveMemo() {
    const text = document.getElementById('memoBox').value;
    await api(`/api/memos/${matrixDate}`, {method:'PUT', body: JSON.stringify({text})});
}

/* ── Todo CRUD ───────────────────────────────────────── */
async function toggleTodo(id) {
    await api(`/api/todos/${id}/toggle`, {method:'POST'});
    refreshMatrix();
}
async function deleteTodo(id, title) {
    if (!confirm(`'${title}'을(를) 삭제할까요?`)) return;
    await api(`/api/todos/${id}`, {method:'DELETE'});
    if (currentView === 'matrix') refreshMatrix();
    else if (currentView === 'repeat') refreshRepeatView();
}

/* ── Calendar View ───────────────────────────────────── */
function setupCalendar() {
    document.getElementById('calPrev').addEventListener('click', () => { navCal(-1); });
    document.getElementById('calNext').addEventListener('click', () => { navCal(1); });
    document.getElementById('calToday').addEventListener('click', () => { const t=new Date(); calYear=t.getFullYear(); calMonth=t.getMonth()+1; refreshCalendar(); });
    document.getElementById('miniPrev').addEventListener('click', () => navCal(-1));
    document.getElementById('miniNext').addEventListener('click', () => navCal(1));
    document.getElementById('calAddBtn').addEventListener('click', () => openTodoModal());
}

function navCal(d) { calMonth+=d; if(calMonth>12){calMonth=1;calYear++;}else if(calMonth<1){calMonth=12;calYear--;} refreshCalendar(); }

async function refreshCalendar() {
    const MONTHS = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'];
    document.getElementById('calTitle').textContent = `${calYear}년 ${MONTHS[calMonth-1]}`;
    document.getElementById('miniLabel').textContent = `${calYear}년 ${MONTHS[calMonth-1]}`;

    const todos = await api('/api/todos');
    const byDate = {};
    todos.filter(t => t.due_date && !t.repeat).forEach(t => { (byDate[t.due_date] = byDate[t.due_date]||[]).push(t); });

    const grid = monthGrid(calYear, calMonth);
    const today = todayStr();

    // Main grid
    const $g = document.getElementById('calGrid');
    $g.innerHTML = '';
    grid.flat().forEach(([day, yr, mo, ov], idx) => {
        const col = idx % 7;
        const ds = `${yr}-${String(mo).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
        const isToday = ds === today;
        const hol = !ov && holidays[ds];

        const cell = document.createElement('div');
        cell.className = 'cal-cell' + (ov ? ' overflow' : '');
        cell.addEventListener('click', () => { matrixDate = ds; showView('matrix'); });

        let numClass = 'day-num';
        if (isToday) numClass += ' today';
        else if (ov) numClass += '';
        else if (col === 0 || hol) numClass += ' sun';
        else if (col === 6) numClass += ' sat';

        cell.innerHTML = `<div class="${numClass}">${day}</div>`;
        if (hol) cell.innerHTML += `<div class="holiday-name">${hol}</div>`;

        (byDate[ds]||[]).slice(0,3).forEach(t => {
            const c = Q_COLORS[`${t.urgent}|${t.important}`] || '#888';
            const short = t.title.length > 10 ? t.title.slice(0,10)+'…' : t.title;
            cell.innerHTML += `<div class="cal-chip" style="background:${c}">${esc(short)}</div>`;
        });
        $g.appendChild(cell);
    });

    // Mini calendar
    const $m = document.getElementById('miniCalGrid');
    $m.innerHTML = '';
    grid.flat().forEach(([day, yr, mo, ov], idx) => {
        const col = idx % 7;
        const ds = `${yr}-${String(mo).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
        const isToday = ds === today;
        const hol = !ov && holidays[ds];
        let cls = 'mini-day';
        if (isToday) cls += ' today';
        else if (ov) cls += ' overflow';
        else if (col === 0 || hol) cls += ' sun';
        else if (col === 6) cls += ' sat';
        const span = document.createElement('span');
        span.className = cls;
        span.textContent = day;
        span.addEventListener('click', e => { e.stopPropagation(); matrixDate = ds; showView('matrix'); });
        $m.appendChild(span);
    });

    refreshHabitSidebar();
}

function monthGrid(year, month) {
    const first = new Date(year, month-1, 1);
    const firstCol = first.getDay(); // 0=Sun
    const daysIn = new Date(year, month, 0).getDate();
    const prevDays = new Date(year, month-1, 0).getDate();
    const pm = month===1 ? [year-1,12] : [year, month-1];
    const nm = month===12 ? [year+1,1] : [year, month+1];

    const grid = [];
    let cur = 1, nxt = 1;
    for (let r = 0; r < 6; r++) {
        const week = [];
        for (let c = 0; c < 7; c++) {
            const idx = r*7+c;
            if (idx < firstCol) week.push([prevDays-firstCol+1+idx, ...pm, true]);
            else if (cur <= daysIn) { week.push([cur, year, month, false]); cur++; }
            else { week.push([nxt, ...nm, true]); nxt++; }
        }
        grid.push(week);
    }
    if (grid.length>5 && grid[5].every(c=>c[3])) grid.pop();
    return grid;
}

/* ── Habit Sidebar (Calendar) ────────────────────────── */
async function refreshHabitSidebar() {
    const $sb = document.getElementById('habitSidebar');
    const habits = await api('/api/habits');
    const weeks = getWeeks(calYear, calMonth);
    const curIdx = getCurrentWeekIndex(weeks);
    const week = weeks[curIdx];
    if (!week) { $sb.innerHTML = ''; return; }

    const checks = await api(`/api/habits/checks?dates=${week[1].join(',')}`);

    let html = `<h3>✅ 습관 체크 <button class="habit-add-sm" id="habitSidebarAdd">+</button></h3>`;
    if (!habits.length) {
        html += '<div style="color:#999;font-size:10px;padding:8px">+ 버튼으로 습관 추가</div>';
    } else {
        html += `<div style="font-size:10px;color:#888;margin:2px 0">${week[0]}</div>`;
        html += '<table class="habit-table"><tr><th></th>';
        WD.forEach((w,i) => html += `<th class="${i===6?'sun':i===5?'sat':''}">${w}</th>`);
        html += '</tr>';
        habits.forEach(h => {
            html += `<tr><td class="habit-name" title="${esc(h.name)}">${esc(h.name.slice(0,6))}</td>`;
            week[1].forEach(ds => {
                const d = dateObj(ds);
                const inMonth = d.getMonth()+1===calMonth && d.getFullYear()===calYear;
                if (!inMonth) { html += '<td><span class="habit-cell out">·</span></td>'; return; }
                const checked = checks[`${h.id}|${ds}`];
                html += `<td><span class="habit-cell ${checked?'checked':'unchecked'}" data-hid="${h.id}" data-date="${ds}">${checked?'◎':'□'}</span></td>`;
            });
            html += '</tr>';
        });
        html += '</table>';
    }
    $sb.innerHTML = html;

    $sb.querySelectorAll('.habit-cell:not(.out)').forEach(el => {
        el.addEventListener('click', async () => {
            await api(`/api/habits/${el.dataset.hid}/toggle`, {method:'POST', body:JSON.stringify({date:el.dataset.date})});
            refreshHabitSidebar();
        });
    });
    document.getElementById('habitSidebarAdd')?.addEventListener('click', () => openHabitModal());
}

/* ── Habit Full View ─────────────────────────────────── */
function setupHabitFull() {
    document.getElementById('habitPrev').addEventListener('click', () => { habitMonth--; if(habitMonth<1){habitMonth=12;habitYear--;} refreshHabitFull(); });
    document.getElementById('habitNext').addEventListener('click', () => { habitMonth++; if(habitMonth>12){habitMonth=1;habitYear++;} refreshHabitFull(); });
    document.getElementById('habitToday').addEventListener('click', () => { const t=new Date(); habitYear=t.getFullYear(); habitMonth=t.getMonth()+1; refreshHabitFull(); });
    document.getElementById('habitAddBtn').addEventListener('click', () => openHabitModal());
}

async function refreshHabitFull() {
    const MONTHS = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'];
    document.getElementById('habitFullTitle').textContent = `${habitYear}년 ${MONTHS[habitMonth-1]}`;

    const habits = await api('/api/habits');
    const weeks = getWeeks(habitYear, habitMonth);
    const allDates = weeks.flatMap(w => w[1]);
    const checks = allDates.length ? await api(`/api/habits/checks?dates=${allDates.join(',')}`) : {};
    const curIdx = getCurrentWeekIndex(weeks);
    const today = new Date();
    const isCurMonth = habitYear === today.getFullYear() && habitMonth === today.getMonth()+1;

    // Chips
    const $chips = document.getElementById('habitChips');
    $chips.innerHTML = '';
    habits.forEach(h => {
        const chip = document.createElement('span');
        chip.className = 'habit-chip';
        chip.innerHTML = `${esc(h.name)} <button data-hid="${h.id}">&times;</button>`;
        chip.querySelector('button').addEventListener('click', async () => {
            if (!confirm(`'${h.name}' 습관을 삭제할까요?`)) return;
            await api(`/api/habits/${h.id}`, {method:'DELETE'});
            refreshHabitFull();
        });
        $chips.appendChild(chip);
    });

    // Weeks
    const $weeks = document.getElementById('habitFullWeeks');
    $weeks.innerHTML = '';
    if (!habits.length) {
        $weeks.innerHTML = '<div style="color:#999;padding:40px;text-align:center">등록된 습관이 없습니다.<br>\'+ 습관 추가\' 버튼으로 추가하세요.</div>';
        return;
    }

    weeks.forEach(([label, dates], wi) => {
        const isCur = isCurMonth && wi === curIdx;
        const d0 = dateObj(dates[0]), d6 = dateObj(dates[6]);
        const range = `${d0.getMonth()+1}/${d0.getDate()} ~ ${d6.getMonth()+1}/${d6.getDate()}`;

        const card = document.createElement('div');
        card.className = 'habit-week-card' + (isCur ? ' current' : '');
        let html = `<div class="week-header"><span class="week-label${isCur?' current':''}">${label}${isCur?' (이번 주)':''}</span><span class="week-range">${range}</span></div>`;
        html += '<table class="habit-full-table"><tr><th></th>';
        dates.forEach((ds,i) => {
            const d = dateObj(ds);
            const dayClass = i===0?'sun':i===6?'sat':'';
            html += `<th class="${dayClass}">${WD[i]}<br>${d.getDate()}일</th>`;
        });
        html += '</tr>';
        habits.forEach(h => {
            html += `<tr><td class="habit-name-full">${esc(h.name)}</td>`;
            dates.forEach(ds => {
                const d = dateObj(ds);
                const inMonth = d.getMonth()+1===habitMonth && d.getFullYear()===habitYear;
                if (!inMonth) { html += '<td><span class="stamp out">·</span></td>'; return; }
                const checked = checks[`${h.id}|${ds}`];
                html += `<td><span class="stamp ${checked?'checked':'unchecked'}" data-hid="${h.id}" data-date="${ds}">${checked?'◎':'□'}</span></td>`;
            });
            html += '</tr>';
        });
        html += '</table>';
        card.innerHTML = html;
        $weeks.appendChild(card);
    });

    // Stamp click + tooltip
    $weeks.querySelectorAll('.stamp:not(.out)').forEach(el => {
        el.addEventListener('click', async () => {
            await api(`/api/habits/${el.dataset.hid}/toggle`, {method:'POST', body:JSON.stringify({date:el.dataset.date})});
            refreshHabitFull();
        });
        el.addEventListener('mouseenter', e => {
            if (!el.classList.contains('checked')) return;
            const tip = document.createElement('div');
            tip.className = 'stamp-tip';
            tip.textContent = '참잘했어요!';
            tip.style.left = e.pageX - 20 + 'px';
            tip.style.top = e.pageY - 28 + 'px';
            document.body.appendChild(tip);
            el._tip = tip;
        });
        el.addEventListener('mouseleave', () => { el._tip?.remove(); });
    });
}

/* ── Week helpers ────────────────────────────────────── */
function getWeeks(year, month) {
    const first = new Date(year, month-1, 1);
    let mon = new Date(first);
    mon.setDate(mon.getDate() - ((mon.getDay()+6)%7)); // 이번 주 월요일
    const weeks = [];
    let wn = 1;
    while (wn <= 6) {
        const dates = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(mon);
            d.setDate(d.getDate() + i);
            dates.push(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`);
        }
        const lastDate = dateObj(dates[6]);
        if (lastDate < first) { mon.setDate(mon.getDate()+7); continue; }
        const firstDate = dateObj(dates[0]);
        if (firstDate.getMonth()+1 > month && firstDate.getFullYear() >= year) break;
        weeks.push([`${wn}주차`, dates]);
        wn++;
        mon.setDate(mon.getDate() + 7);
    }
    return weeks;
}

function getCurrentWeekIndex(weeks) {
    const t = todayStr();
    for (let i = 0; i < weeks.length; i++) {
        if (weeks[i][1][0] <= t && t <= weeks[i][1][6]) return i;
    }
    return 0;
}

/* ── Repeat View ─────────────────────────────────────── */
function setupRepeatView() {
    document.getElementById('repeatAddBtn').addEventListener('click', () => openTodoModal(null, false, true, true));
}

async function refreshRepeatView() {
    const todos = await api('/api/todos');
    const repeats = todos.filter(t => t.repeat);
    const $list = document.getElementById('repeatList');
    $list.innerHTML = '';
    if (!repeats.length) {
        $list.innerHTML = '<div style="color:#999;padding:40px;text-align:center">반복 할 일이 없습니다.</div>';
        return;
    }
    const WD_NAMES = ['월','화','수','목','금','토','일'];
    repeats.forEach(t => {
        const color = Q_COLORS[`${t.urgent}|${t.important}`] || '#888';
        let schedule = '매일 반복';
        const parts = [];
        if (t.repeat_weekdays?.length) parts.push('매주 ' + t.repeat_weekdays.map(w=>WD_NAMES[w]).join('·'));
        if (t.repeat_days?.length) parts.push('매월 ' + t.repeat_days.map(d=>d+'일').join(', '));
        if (parts.length) schedule = parts.join(' / ');

        const card = document.createElement('div');
        card.className = 'repeat-card';
        card.innerHTML = `
            <div class="repeat-color-bar" style="background:${color}"></div>
            <div class="repeat-info">
                <div class="repeat-title">🔁 ${esc(t.title)}</div>
                <div class="repeat-schedule">${schedule}</div>
            </div>
            <div class="repeat-actions">
                <button class="btn-edit">수정</button>
                <button class="btn-delete">삭제</button>
            </div>
        `;
        card.querySelector('.btn-edit').addEventListener('click', () => openTodoModal(t));
        card.querySelector('.btn-delete').addEventListener('click', () => deleteTodo(t.id, t.title));
        $list.appendChild(card);
    });
}

/* ── Modals ──────────────────────────────────────────── */
function setupModals() {
    // Todo modal
    const $m = document.getElementById('todoModal');
    document.getElementById('todoCancel').addEventListener('click', () => $m.classList.add('hidden'));
    document.getElementById('todoSave').addEventListener('click', saveTodoModal);
    document.getElementById('todoUrgent').addEventListener('change', updateQPreview);
    document.getElementById('todoImportant').addEventListener('change', updateQPreview);
    document.getElementById('todoRepeat').addEventListener('change', () => {
        document.getElementById('repeatOptions').classList.toggle('hidden', !document.getElementById('todoRepeat').checked);
    });

    // Build weekday checkboxes
    const $wd = document.getElementById('repeatWeekdays');
    WD.forEach((w,i) => { $wd.innerHTML += `<label><input type="checkbox" value="${i}"><span>${w}</span></label>`; });
    const $dd = document.getElementById('repeatDays');
    for (let d=1;d<=31;d++) { $dd.innerHTML += `<label><input type="checkbox" value="${d}"><span>${d}</span></label>`; }

    // Habit modal
    document.getElementById('habitCancel').addEventListener('click', () => document.getElementById('habitModal').classList.add('hidden'));
    document.getElementById('habitSave').addEventListener('click', saveHabitModal);
    document.getElementById('habitNameInput').addEventListener('keydown', e => { if (e.key === 'Enter') saveHabitModal(); });
}

function openTodoModal(item = null, defaultUrgent = false, defaultImportant = true, defaultRepeat = false) {
    const $m = document.getElementById('todoModal');
    document.getElementById('todoModalTitle').textContent = item ? '할 일 수정' : '새 할 일 추가';
    document.getElementById('todoTitleInput').value = item?.title || '';
    document.getElementById('todoUrgent').checked = item ? item.urgent : defaultUrgent;
    document.getElementById('todoImportant').checked = item ? item.important : defaultImportant;
    document.getElementById('todoCategory').value = item?.category || '업무';
    document.getElementById('todoNote').value = item?.note || '';
    document.getElementById('todoRepeat').checked = item ? item.repeat : defaultRepeat;
    document.getElementById('todoDueDate').value = item?.due_date || matrixDate;
    document.getElementById('todoEditId').value = item?.id || '';
    document.getElementById('repeatOptions').classList.toggle('hidden', !(item?.repeat || defaultRepeat));

    // Reset repeat options
    document.querySelectorAll('#repeatWeekdays input').forEach(cb => cb.checked = (item?.repeat_weekdays||[]).includes(+cb.value));
    document.querySelectorAll('#repeatDays input').forEach(cb => cb.checked = (item?.repeat_days||[]).includes(+cb.value));

    updateQPreview();
    $m.classList.remove('hidden');
    document.getElementById('todoTitleInput').focus();
}

function updateQPreview() {
    const u = document.getElementById('todoUrgent').checked;
    const i = document.getElementById('todoImportant').checked;
    const key = `${u}|${i}`;
    const $p = document.getElementById('todoQPreview');
    $p.style.background = Q_COLORS[key];
    $p.textContent = Q_LABELS[key];
}

async function saveTodoModal() {
    const title = document.getElementById('todoTitleInput').value.trim();
    if (!title) { alert('제목을 입력해주세요.'); return; }

    const repeat_weekdays = [...document.querySelectorAll('#repeatWeekdays input:checked')].map(cb => +cb.value);
    const repeat_days = [...document.querySelectorAll('#repeatDays input:checked')].map(cb => +cb.value);

    const data = {
        title,
        category: document.getElementById('todoCategory').value,
        urgent: document.getElementById('todoUrgent').checked,
        important: document.getElementById('todoImportant').checked,
        note: document.getElementById('todoNote').value.trim(),
        repeat: document.getElementById('todoRepeat').checked,
        due_date: document.getElementById('todoDueDate').value,
        repeat_weekdays,
        repeat_days,
    };

    const editId = document.getElementById('todoEditId').value;
    if (editId) {
        await api(`/api/todos/${editId}`, {method:'PUT', body: JSON.stringify(data)});
    } else {
        await api('/api/todos', {method:'POST', body: JSON.stringify(data)});
    }

    document.getElementById('todoModal').classList.add('hidden');
    if (currentView === 'matrix') refreshMatrix();
    else if (currentView === 'calendar') refreshCalendar();
    else if (currentView === 'repeat') refreshRepeatView();
}

function openHabitModal() {
    document.getElementById('habitNameInput').value = '';
    document.getElementById('habitModal').classList.remove('hidden');
    document.getElementById('habitNameInput').focus();
}

async function saveHabitModal() {
    const name = document.getElementById('habitNameInput').value.trim();
    if (!name) return;
    await api('/api/habits', {method:'POST', body: JSON.stringify({name})});
    document.getElementById('habitModal').classList.add('hidden');
    if (currentView === 'habitFull') refreshHabitFull();
    if (currentView === 'calendar') refreshHabitSidebar();
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
