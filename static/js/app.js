/* ── PWA Service Worker ──────────────────────────────── */
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/service-worker.js').catch(() => {});
}

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
    setupDiary();
    setupFreeMemo();
    setupFinance();
    showView('matrix');
    autoBackup();
});

/* ── Auto Backup ────────────────────────────────────── */
async function autoBackup() {
    try {
        const last = localStorage.getItem('lastBackupTime');
        const now = Date.now();
        // 6시간마다 자동 백업
        if (last && now - parseInt(last) < 6 * 60 * 60 * 1000) return;
        const res = await fetch('/api/backup');
        if (!res.ok) return;
        const data = await res.text();
        localStorage.setItem('todoMatrixBackup', data);
        localStorage.setItem('lastBackupTime', String(now));
        console.log('자동 백업 완료:', new Date().toLocaleString('ko'));
    } catch (e) {
        console.log('자동 백업 실패:', e);
    }
}

/* ── Drawing Canvas ──────────────────────────────────── */
let drawTarget = null; // 'diary' or 'memo'
let drawCtx = null;
let drawing = false;
let drawHistory = [];
let drawMode = 'pen'; // 'pen' or 'eraser'

function openDrawModal(target) {
    drawTarget = target;
    const $m = document.getElementById('drawModal');
    const canvas = document.getElementById('drawCanvas');
    const popup = document.querySelector('.draw-popup');
    canvas.width = Math.min(window.innerWidth - 40, 800);
    canvas.height = Math.min(window.innerHeight - 120, 500);
    drawCtx = canvas.getContext('2d');
    drawCtx.fillStyle = '#fff';
    drawCtx.fillRect(0, 0, canvas.width, canvas.height);
    drawCtx.lineCap = 'round';
    drawCtx.lineJoin = 'round';
    drawHistory = [];
    saveDrawState();
    drawMode = 'pen';
    document.getElementById('drawPen').classList.add('active');
    document.getElementById('drawEraser').classList.remove('active');
    $m.classList.remove('hidden');
}

function saveDrawState() {
    drawHistory.push(drawCtx.getImageData(0, 0, drawCtx.canvas.width, drawCtx.canvas.height));
    if (drawHistory.length > 30) drawHistory.shift();
}

function getDrawPos(e) {
    const rect = drawCtx.canvas.getBoundingClientRect();
    const t = e.touches ? e.touches[0] : e;
    return { x: t.clientX - rect.left, y: t.clientY - rect.top };
}

(function setupDraw() {
    const canvas = document.getElementById('drawCanvas');
    if (!canvas) return;

    function startDraw(e) {
        e.preventDefault();
        drawing = true;
        const pos = getDrawPos(e);
        drawCtx.beginPath();
        drawCtx.moveTo(pos.x, pos.y);
    }
    function moveDraw(e) {
        if (!drawing) return;
        e.preventDefault();
        const pos = getDrawPos(e);
        drawCtx.strokeStyle = drawMode === 'eraser' ? '#ffffff' : document.getElementById('drawColor').value;
        drawCtx.lineWidth = drawMode === 'eraser' ? 20 : parseInt(document.getElementById('drawSize').value);
        drawCtx.lineTo(pos.x, pos.y);
        drawCtx.stroke();
    }
    function endDraw(e) {
        if (!drawing) return;
        drawing = false;
        saveDrawState();
    }

    canvas.addEventListener('pointerdown', startDraw);
    canvas.addEventListener('pointermove', moveDraw);
    canvas.addEventListener('pointerup', endDraw);
    canvas.addEventListener('pointerleave', endDraw);
    canvas.style.touchAction = 'none';

    document.getElementById('drawPen').addEventListener('click', () => {
        drawMode = 'pen';
        document.getElementById('drawPen').classList.add('active');
        document.getElementById('drawEraser').classList.remove('active');
    });
    document.getElementById('drawEraser').addEventListener('click', () => {
        drawMode = 'eraser';
        document.getElementById('drawEraser').classList.add('active');
        document.getElementById('drawPen').classList.remove('active');
    });
    document.getElementById('drawClear').addEventListener('click', () => {
        drawCtx.fillStyle = '#fff';
        drawCtx.fillRect(0, 0, drawCtx.canvas.width, drawCtx.canvas.height);
        saveDrawState();
    });
    document.getElementById('drawUndo').addEventListener('click', () => {
        if (drawHistory.length > 1) {
            drawHistory.pop();
            drawCtx.putImageData(drawHistory[drawHistory.length - 1], 0, 0);
        }
    });
    document.getElementById('drawCancel').addEventListener('click', () => {
        document.getElementById('drawModal').classList.add('hidden');
    });
    document.getElementById('drawSave').addEventListener('click', () => {
        const dataUrl = drawCtx.canvas.toDataURL('image/png');
        const targetEl = drawTarget === 'memo' ? 'memoContentInput' : 'diaryContentInput';
        document.getElementById(targetEl).focus();
        document.execCommand('insertHTML', false, `<img src="${dataUrl}" style="max-width:100%;border-radius:8px;margin:8px 0;cursor:pointer" onclick="resizeDiaryImg(this)">`);
        document.getElementById('drawModal').classList.add('hidden');
    });
    document.getElementById('drawModal').addEventListener('click', (e) => {
        if (e.target.id === 'drawModal') document.getElementById('drawModal').classList.add('hidden');
    });
})();

// 일기 에디터 손글씨 버튼
document.getElementById('tbDraw')?.addEventListener('click', () => openDrawModal('diary'));
// 메모 에디터 손글씨 버튼
document.getElementById('memoTbDraw')?.addEventListener('click', () => openDrawModal('memo'));

/* ── Helpers ─────────────────────────────────────────── */
function monthsBetween(a, b) {
    const [ay, am] = a.split('-').map(Number);
    const [by, bm] = b.split('-').map(Number);
    return (by - ay) * 12 + (bm - am);
}
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
    if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`${res.status}: ${text.slice(0, 200)}`);
    }
    return res.json().catch(() => ({}));
}

/* ── Header ──────────────────────────────────────────── */
function setupHeader() {
    const $d = document.getElementById('headerDate');
    $d.textContent = fmtDate(todayStr());

    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => showView(btn.dataset.view));
    });
    document.getElementById('btnAddTodo').addEventListener('click', () => openTodoModal());
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
    hMenu.querySelector('[data-action="diaryExport"]').addEventListener('click', () => { hMenu.classList.add('hidden'); showView('diaryExport'); });
    hMenu.querySelector('[data-action="backup"]').addEventListener('click', () => { hMenu.classList.add('hidden'); location.href = '/api/backup'; });
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
    } else if (name === 'diary') {
        document.getElementById('diaryView').classList.remove('hidden');
        document.getElementById('btnDiary').classList.add('active');
        refreshDiary();
    } else if (name === 'freeMemo') {
        document.getElementById('freeMemoView').classList.remove('hidden');
        document.getElementById('btnFreeMemo').classList.add('active');
        refreshFreeMemo();
    } else if (name === 'diaryExport') {
        document.getElementById('diaryExportView').classList.remove('hidden');
        refreshExport();
    } else if (name === 'diaryTrash') {
        document.getElementById('diaryTrashView').classList.remove('hidden');
        refreshTrash();
    } else if (name === 'finance') {
        document.getElementById('financeView').classList.remove('hidden');
        document.getElementById('btnFinance').classList.add('active');
        refreshFinance();
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
    document.getElementById('weeklyAddBtn').addEventListener('click', () => addStickyItem());
    refreshSticky();
}

let stickyCache = [];

async function addStickyItem() {
    const text = prompt('할 일을 입력하세요:');
    if (!text?.trim()) return;
    const tempId = Date.now();
    stickyCache.push({id: tempId, text: text.trim(), done: false});
    renderAllSticky();
    const res = await api('/api/sticky', {method:'POST', body:JSON.stringify({text: text.trim()})});
    const idx = stickyCache.findIndex(n => n.id === tempId);
    if (idx !== -1) stickyCache[idx].id = res.id;
}

async function refreshSticky() {
    stickyCache = await api('/api/sticky');
    renderAllSticky();
}

function renderAllSticky() {
    renderStickyTo(document.getElementById('weeklyList'), false);
    renderStickyTo(document.getElementById('weeklyMobile'), true);
}

function renderStickyTo($el, isMobile) {
    $el.innerHTML = '';
    if (isMobile) {
        const header = document.createElement('div');
        header.className = 'weekly-mobile-header';
        header.innerHTML = `<span>이번주 할 일</span><button class="btn-sm weekly-mobile-add">+</button>`;
        header.querySelector('.weekly-mobile-add').addEventListener('click', () => addStickyItem());
        $el.appendChild(header);
    }
    if (!stickyCache.length) {
        $el.innerHTML += '<div style="color:#bbb;font-size:11px;padding:4px">+ 버튼으로 할 일을 추가하세요</div>';
        return;
    }
    const sorted = [...stickyCache].sort((a, b) => a.done - b.done);
    sorted.forEach(n => {
        const div = document.createElement('div');
        div.className = 'weekly-item' + (n.done ? ' done' : '');
        div.innerHTML = `<input type="checkbox" class="weekly-cb" ${n.done ? 'checked' : ''}><span class="weekly-text">${esc(n.text)}</span><button class="weekly-edit" title="수정">✎</button><button class="weekly-del" title="삭제">&times;</button>`;
        div.querySelector('.weekly-cb').addEventListener('change', () => {
            n.done = !n.done;
            renderAllSticky();
            api(`/api/sticky/${n.id}`, {method:'PUT', body:JSON.stringify({done: n.done})});
        });
        div.querySelector('.weekly-edit').addEventListener('click', (ev) => {
            ev.stopPropagation();
            const newText = prompt('수정할 내용:', n.text);
            if (newText !== null && newText.trim() && newText.trim() !== n.text) {
                n.text = newText.trim();
                renderAllSticky();
                api(`/api/sticky/${n.id}`, {method:'PUT', body:JSON.stringify({text: n.text})});
            }
        });
        div.querySelector('.weekly-del').addEventListener('click', (ev) => {
            ev.stopPropagation();
            if (confirm(`'${n.text}' 삭제?`)) {
                stickyCache = stickyCache.filter(x => x.id !== n.id);
                renderAllSticky();
                api(`/api/sticky/${n.id}`, {method:'DELETE'});
            }
        });
        $el.appendChild(div);
    });
}

function shiftDate(s, delta) {
    const d = dateObj(s);
    d.setDate(d.getDate() + delta);
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

let todosCache = {};
let memoCache = {};

function refreshMatrix() {
    document.getElementById('matrixDateLabel').textContent = fmtDate(matrixDate) + ' 할일 목록';
    if (todosCache[matrixDate]) renderMatrix(todosCache[matrixDate]);
    api(`/api/todos?date=${matrixDate}`).then(todos => {
        todosCache[matrixDate] = todos;
        renderMatrix(todos);
    });
    loadMemo();
}

function renderMatrix(todos) {
    const show = document.getElementById('showCompleted').checked;
    document.querySelectorAll('.quadrant').forEach(q => {
        const u = q.dataset.urgent === 'true';
        const imp = q.dataset.important === 'true';
        const items = todos.filter(t => t.urgent === u && t.important === imp && (show || !t.completed));
        items.sort((a, b) => {
            const aHabit = a.title.startsWith('[습관]') ? 1 : 0;
            const bHabit = b.title.startsWith('[습관]') ? 1 : 0;
            return aHabit - bHabit;
        });
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
}

function refreshSummary(todos, show) {
    const $s = document.getElementById('todoSummary');
    if (!$s) return;
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
function loadMemo() {
    if (memoCache[matrixDate] !== undefined) {
        document.getElementById('memoBox').value = memoCache[matrixDate];
    }
    api(`/api/memos/${matrixDate}`).then(data => {
        memoCache[matrixDate] = data.text || '';
        document.getElementById('memoBox').value = memoCache[matrixDate];
    });
}
document.getElementById('memoBox')?.addEventListener('input', () => {
    memoCache[matrixDate] = document.getElementById('memoBox').value;
    clearTimeout(memoTimer);
    memoTimer = setTimeout(saveMemo, 800);
});
function saveMemo() {
    const text = document.getElementById('memoBox').value;
    api(`/api/memos/${matrixDate}`, {method:'PUT', body: JSON.stringify({text})});
}

/* ── Fixed Memo ──────────────────────────────────────── */
let fixedMemoTimer;
async function loadFixedMemo() {
    const data = await api('/api/fixed-memo');
    document.getElementById('fixedMemoBox').value = data.text || '';
}
document.getElementById('fixedMemoBox')?.addEventListener('input', () => {
    clearTimeout(fixedMemoTimer);
    fixedMemoTimer = setTimeout(saveFixedMemo, 800);
});
async function saveFixedMemo() {
    const text = document.getElementById('fixedMemoBox').value;
    await api('/api/fixed-memo', {method:'PUT', body: JSON.stringify({text})});
}
loadFixedMemo();

/* ── Diary Editor Toolbar ───────────────────────────── */
document.querySelectorAll('.tb-btn[data-cmd]').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.preventDefault();
        document.execCommand(btn.dataset.cmd, false, null);
        document.getElementById('diaryContentInput').focus();
    });
});
document.getElementById('tbImage')?.addEventListener('click', () => {
    document.getElementById('diaryImageInput').click();
});
document.getElementById('diaryImageInput')?.addEventListener('change', (e) => {
    const files = e.target.files;
    if (!files.length) return;
    Array.from(files).forEach(file => {
        if (!file.type.startsWith('image/')) return;
        const imgEl = new Image();
        imgEl.onload = () => {
            const canvas = document.createElement('canvas');
            const MAX = 1200;
            let w = imgEl.width, h = imgEl.height;
            if (w > MAX || h > MAX) {
                if (w > h) { h = Math.round(h * MAX / w); w = MAX; }
                else { w = Math.round(w * MAX / h); h = MAX; }
            }
            canvas.width = w; canvas.height = h;
            canvas.getContext('2d').drawImage(imgEl, 0, 0, w, h);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
            const tag = `<img src="${dataUrl}" class="diary-img" style="width:50%"> `;
            document.getElementById('diaryContentInput').focus();
            document.execCommand('insertHTML', false, tag);
        };
        imgEl.src = URL.createObjectURL(file);
    });
    e.target.value = '';
});
document.getElementById('tbLink')?.addEventListener('click', () => {
    const url = prompt('URL을 입력하세요:', 'https://');
    if (!url) return;
    const text = prompt('표시할 텍스트:', url);
    document.getElementById('diaryContentInput').focus();
    document.execCommand('insertHTML', false, `<a href="${url}" target="_blank" style="color:#1A73E8">${esc(text || url)}</a>`);
});

// 이미지 드래그 리사이즈
(function() {
    let resizing = null, startX = 0, startW = 0;
    document.addEventListener('pointerdown', (e) => {
        const img = e.target.closest('.de-editor img, .de-editor .diary-img');
        if (!img) return;
        e.preventDefault();
        resizing = img;
        startX = e.clientX;
        startW = img.offsetWidth;
        img.style.outline = '2px solid #1A73E8';
    });
    document.addEventListener('pointermove', (e) => {
        if (!resizing) return;
        const diff = e.clientX - startX;
        const newW = Math.max(50, startW + diff);
        const container = resizing.closest('.de-editor');
        const maxW = container ? container.offsetWidth - 20 : 800;
        resizing.style.width = Math.min(newW, maxW) + 'px';
    });
    document.addEventListener('pointerup', () => {
        if (resizing) {
            resizing.style.outline = '';
            resizing = null;
        }
    });
})();

/* ── Todo CRUD ───────────────────────────────────────── */
function toggleTodo(id) {
    const todos = todosCache[matrixDate];
    if (todos) {
        const t = todos.find(x => x.id === id);
        if (t) t.completed = !t.completed;
        renderMatrix(todos);
    }
    api(`/api/todos/${id}/toggle`, {method:'POST'});
}
function deleteTodo(id, title) {
    if (!confirm(`'${title}'을(를) 삭제할까요?`)) return;
    if (todosCache[matrixDate]) {
        todosCache[matrixDate] = todosCache[matrixDate].filter(t => t.id !== id);
        renderMatrix(todosCache[matrixDate]);
    }
    api(`/api/todos/${id}`, {method:'DELETE'});
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

    // ── 이번 주 빠른 체크 (모바일 상단) ──
    const $hq = document.getElementById('habitQuick');
    if ($hq) {
        const nowWeeks = getWeeks(today.getFullYear(), today.getMonth()+1);
        const nowIdx = getCurrentWeekIndex(nowWeeks);
        const nowWeek = nowWeeks[nowIdx];
        if (nowWeek && habits.length) {
            const nowDates = nowWeek[1];
            const nowChecks = await api(`/api/habits/checks?dates=${nowDates.join(',')}`);
            const d0 = dateObj(nowDates[0]), d6 = dateObj(nowDates[6]);
            const range = `${d0.getMonth()+1}/${d0.getDate()} ~ ${d6.getMonth()+1}/${d6.getDate()}`;
            let hqHtml = `<div class="habit-quick-card">`;
            hqHtml += `<div class="hq-title">✅ 이번 주 습관 체크</div>`;
            hqHtml += `<div class="hq-range">${nowWeek[0]} (${range})</div>`;
            hqHtml += `<table class="hq-table"><tr><th></th>`;
            nowDates.forEach((ds, i) => {
                const cls = i===6?'sun':i===5?'sat':'';
                hqHtml += `<th class="${cls}">${WD[i]}</th>`;
            });
            hqHtml += `</tr>`;
            habits.forEach(h => {
                hqHtml += `<tr><td class="habit-name-full">${esc(h.name)}</td>`;
                nowDates.forEach(ds => {
                    const checked = nowChecks[`${h.id}|${ds}`];
                    hqHtml += `<td><span class="stamp ${checked?'checked':'unchecked'}" data-hid="${h.id}" data-date="${ds}">${checked?'◎':'□'}</span></td>`;
                });
                hqHtml += `</tr>`;
            });
            hqHtml += `</table></div>`;
            $hq.innerHTML = hqHtml;
            $hq.querySelectorAll('.stamp').forEach(el => {
                el.addEventListener('click', async () => {
                    await api(`/api/habits/${el.dataset.hid}/toggle`, {method:'POST', body:JSON.stringify({date:el.dataset.date})});
                    refreshHabitFull();
                });
            });
        } else {
            $hq.innerHTML = '';
        }
    }

    // Chips (◀▶ 버튼 + 드래그 앤 드롭)
    const $chips = document.getElementById('habitChips');
    $chips.innerHTML = '';
    let dragHabitId = null;

    function reorderHabits(newIds) {
        // 낙관적: 로컬 순서 즉시 변경 후 렌더
        const reordered = newIds.map(id => habits.find(h => h.id === id)).filter(Boolean);
        habits.length = 0;
        reordered.forEach(h => habits.push(h));
        renderHabitChips();
        api('/api/habits/reorder', {method:'POST', body:JSON.stringify({ids: newIds})});
    }

    function renderHabitChips() {
        $chips.innerHTML = '';
        habits.forEach((h, idx) => {
            const chip = document.createElement('span');
            chip.className = 'habit-chip';
            chip.draggable = true;
            chip.dataset.habitId = h.id;
            const left = idx > 0 ? '<span class="habit-arrow habit-left">◀</span>' : '';
            const right = idx < habits.length - 1 ? '<span class="habit-arrow habit-right">▶</span>' : '';
            chip.innerHTML = `${left}<span class="habit-name">${esc(h.name)}</span>${right}<button class="habit-del">&times;</button>`;
            // ◀▶ 즉시 이동
            chip.querySelector('.habit-left')?.addEventListener('click', (ev) => {
                ev.stopPropagation();
                const ids = habits.map(x => x.id);
                [ids[idx - 1], ids[idx]] = [ids[idx], ids[idx - 1]];
                reorderHabits(ids);
            });
            chip.querySelector('.habit-right')?.addEventListener('click', (ev) => {
                ev.stopPropagation();
                const ids = habits.map(x => x.id);
                [ids[idx], ids[idx + 1]] = [ids[idx + 1], ids[idx]];
                reorderHabits(ids);
            });
            // 드래그
            chip.addEventListener('dragstart', (e) => {
                dragHabitId = h.id;
                e.dataTransfer.effectAllowed = 'move';
                setTimeout(() => chip.style.opacity = '0.3', 0);
            });
            chip.addEventListener('dragend', () => { chip.style.opacity = '1'; dragHabitId = null; });
            chip.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (dragHabitId && dragHabitId !== h.id) chip.classList.add('drag-over');
            });
            chip.addEventListener('dragleave', () => chip.classList.remove('drag-over'));
            chip.addEventListener('drop', (e) => {
                e.preventDefault();
                chip.classList.remove('drag-over');
                if (!dragHabitId || dragHabitId === h.id) return;
                const ids = habits.map(x => x.id);
                const fromIdx = ids.indexOf(dragHabitId);
                const toIdx = ids.indexOf(h.id);
                const [moved] = ids.splice(fromIdx, 1);
                ids.splice(toIdx, 0, moved);
                reorderHabits(ids);
            });
            // 삭제
            chip.querySelector('.habit-del').addEventListener('click', async (ev) => {
                ev.stopPropagation();
                if (!confirm(`'${h.name}' 습관을 삭제할까요?`)) return;
                await api(`/api/habits/${h.id}`, {method:'DELETE'});
                refreshHabitFull();
            });
            $chips.appendChild(chip);
        });
    }
    renderHabitChips();

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
    document.getElementById('todoModal').classList.add('hidden');
    // 캐시 무효화 (서버에서 다시 받아오게)
    todosCache = {};
    if (editId) {
        api(`/api/todos/${editId}`, {method:'PUT', body: JSON.stringify(data)}).then(() => {
            if (currentView === 'matrix') refreshMatrix();
            else if (currentView === 'calendar') refreshCalendar();
            else if (currentView === 'repeat') refreshRepeatView();
        });
    } else {
        api('/api/todos', {method:'POST', body: JSON.stringify(data)}).then(() => {
            if (currentView === 'matrix') refreshMatrix();
            else if (currentView === 'calendar') refreshCalendar();
            else if (currentView === 'repeat') refreshRepeatView();
        });
    }
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

/* ══════════════════════════════════════════════════════
   일기장
   ══════════════════════════════════════════════════════ */
let diaryViewMode = 'list'; // 'list' | 'cal'
let diaryYear, diaryMonth;
let selectedMood = '';

function setupDiary() {
    const today = new Date();
    diaryYear = today.getFullYear();
    diaryMonth = today.getMonth() + 1;

    // year filter
    const $yf = document.getElementById('diaryYearFilter');
    for (let y = today.getFullYear(); y >= today.getFullYear() - 5; y--) {
        $yf.innerHTML += `<option value="${y}">${y}년</option>`;
    }
    $yf.addEventListener('change', () => { diaryYear = +$yf.value; refreshDiary(); });

    const $mf = document.getElementById('diaryMonthFilter');
    $mf.addEventListener('change', () => { diaryMonth = $mf.value ? +$mf.value : null; refreshDiary(); });

    document.getElementById('diaryToggleView').addEventListener('click', () => {
        diaryViewMode = diaryViewMode === 'list' ? 'cal' : 'list';
        document.getElementById('diaryToggleView').textContent = diaryViewMode === 'list' ? '캘린더' : '리스트';
        refreshDiary();
    });

    document.getElementById('diaryWriteBtn').addEventListener('click', () => openDiaryModal());
    document.getElementById('diaryDownloadBtn').addEventListener('click', () => {
        showView('diaryExport');
    });
    document.getElementById('diaryTrashBtn').addEventListener('click', () => showView('diaryTrash'));
    document.getElementById('trashBackBtn').addEventListener('click', () => showView('diary'));
    document.getElementById('diaryCancel').addEventListener('click', closeDiaryEditor);
    document.getElementById('diarySave').addEventListener('click', saveDiary);
    document.getElementById('diaryPrevDay').addEventListener('click', () => navDiaryDay(-1));
    document.getElementById('diaryNextDay').addEventListener('click', () => navDiaryDay(1));

    // mood selector
    document.querySelectorAll('.mood-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.mood-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            selectedMood = btn.dataset.mood;
        });
    });

    // bucket
    document.getElementById('bucketAddBtn').addEventListener('click', addBucket);
}

let bucketCache = [];
let diaryEntriesCache = [];

function refreshDiary() {
    const year = diaryYear || new Date().getFullYear();
    document.getElementById('bucketTitle').textContent = `올해 반드시 이루겠습니다`;

    // 병렬 fetch (항상 서버에서 최신 데이터)
    let url = `/api/diary?year=${year}`;
    if (diaryMonth) url += `&month=${diaryMonth}`;
    Promise.all([api(`/api/bucket?year=${year}`), api(url)]).then(([buckets, entries]) => {
        bucketCache = buckets;
        diaryEntriesCache = entries;
        renderBuckets(buckets);
        renderDiaryEntries(entries, year);
    }).catch(e => console.error('refreshDiary error:', e));
}

function renderBuckets(buckets) {
    const $bl = document.getElementById('bucketList');
    $bl.innerHTML = '';
    buckets.forEach(b => {
        const div = document.createElement('div');
        div.className = 'bucket-item' + (b.completed ? ' done' : '');
        div.innerHTML = `<input type="checkbox" ${b.completed ? 'checked' : ''}><span>${esc(b.text)}</span><button class="bucket-edit-btn" title="수정">✎</button><button class="bucket-del-btn" title="삭제">&times;</button>`;
        div.querySelector('input').addEventListener('change', () => {
            b.completed = !b.completed;
            renderBuckets(bucketCache);
            api(`/api/bucket/${b.id}`, {method:'PUT', body:JSON.stringify({completed:b.completed})});
        });
        div.querySelector('.bucket-edit-btn').addEventListener('click', () => {
            const span = div.querySelector('span');
            const oldText = b.text;
            span.style.display = 'none';
            div.querySelector('.bucket-edit-btn').style.display = 'none';
            div.querySelector('.bucket-del-btn').style.display = 'none';
            const input = document.createElement('input');
            input.type = 'text'; input.value = oldText; input.className = 'bucket-edit-input';
            const saveBtn = document.createElement('button');
            saveBtn.className = 'bucket-save-btn'; saveBtn.textContent = '✓';
            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'bucket-cancel-btn'; cancelBtn.textContent = '✕';
            span.after(input, saveBtn, cancelBtn);
            input.focus();
            const save = () => {
                const newText = input.value.trim();
                if (newText && newText !== oldText) {
                    b.text = newText;
                    api(`/api/bucket/${b.id}`, {method:'PUT', body:JSON.stringify({text: newText})});
                }
                renderBuckets(bucketCache);
            };
            saveBtn.addEventListener('click', save);
            cancelBtn.addEventListener('click', () => renderBuckets(bucketCache));
            input.addEventListener('keydown', (e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') renderBuckets(bucketCache); });
        });
        div.querySelector('.bucket-del-btn').addEventListener('click', () => {
            if (confirm(`'${b.text}' 삭제?`)) {
                bucketCache = bucketCache.filter(x => x.id !== b.id);
                renderBuckets(bucketCache);
                api(`/api/bucket/${b.id}`, {method:'DELETE'});
            }
        });
        $bl.appendChild(div);
    });
}

function renderDiaryEntries(entries, year) {
    if (diaryViewMode === 'list') {
        document.getElementById('diaryListView').classList.remove('hidden');
        document.getElementById('diaryCalView').classList.add('hidden');
        renderDiaryList(entries);
    } else {
        document.getElementById('diaryListView').classList.add('hidden');
        document.getElementById('diaryCalView').classList.remove('hidden');
        renderDiaryCal(entries, year, diaryMonth || new Date().getMonth()+1);
    }
}

function renderDiaryList(entries) {
    const $list = document.getElementById('diaryListView');
    const $bar = document.getElementById('diarySelectBar');
    const $selectAll = document.getElementById('diarySelectAll');
    const $count = document.getElementById('diarySelectCount');
    const $delBtn = document.getElementById('diaryDeleteSelected');
    $list.innerHTML = '';
    $selectAll.checked = false;
    if (!entries.length) {
        $bar.classList.add('hidden');
        $list.innerHTML = '<div style="color:#999;padding:30px;text-align:center">작성된 일기가 없습니다.</div>';
        return;
    }
    $bar.classList.remove('hidden');

    function updateSelectCount() {
        const checked = document.querySelectorAll('.diary-cb:checked');
        $count.textContent = `${checked.length}개 선택`;
        $delBtn.disabled = checked.length === 0;
        const allCbs = document.querySelectorAll('.diary-cb');
        $selectAll.checked = allCbs.length > 0 && checked.length === allCbs.length;
    }

    $selectAll.onchange = () => {
        document.querySelectorAll('.diary-cb').forEach(cb => { cb.checked = $selectAll.checked; });
        updateSelectCount();
    };

    $delBtn.onclick = async () => {
        const checked = [...document.querySelectorAll('.diary-cb:checked')];
        if (!checked.length) return;
        if (!confirm(`${checked.length}개 일기를 휴지통으로 이동할까요?`)) return;
        if (checked.length >= 2 && !confirm(`정말 ${checked.length}개 일기를 모두 삭제하시겠습니까?`)) return;
        await Promise.all(checked.map(cb => api(`/api/diary/${cb.value}`, {method:'DELETE'})));
        refreshDiary();
    };

    entries.forEach(e => {
        const card = document.createElement('div');
        card.className = 'diary-card';
        card.innerHTML = `
            <input type="checkbox" class="diary-cb" value="${e.id}">
            <div class="dc-info">
                <div class="dc-date">${e.date_str}</div>
                <div class="dc-title">${e.mood ? e.mood + ' ' : ''}${esc(e.title || '무제')}</div>
            </div>
        `;
        card.querySelector('.diary-cb').addEventListener('click', (ev) => ev.stopPropagation());
        card.querySelector('.diary-cb').addEventListener('change', updateSelectCount);
        card.addEventListener('click', (ev) => {
            if (ev.target.type === 'checkbox') return;
            openDiaryReadModal(e);
        });
        $list.appendChild(card);
    });
    updateSelectCount();
}

async function openDiaryReadModal(e) {
    const $m = document.getElementById('diaryReadModal');
    document.getElementById('drDate').textContent = e.date_str;
    document.getElementById('drMood').textContent = e.mood || '';
    document.getElementById('drTitle').textContent = e.title || '무제';
    const rc = e.content || '';
    document.getElementById('drContent').innerHTML = rc.includes('<') ? rc : rc.replace(/\n/g, '<br>');
    const $eventContent = document.getElementById('drEventContent');
    $eventContent.innerHTML = e.event ? esc(e.event).replace(/\n/g, '<br>') : '-';
    // 하루 요약 로드
    try {
        const todos = await api(`/api/todos?date=${e.date_str}`);
        const total = todos.length;
        const done = todos.filter(t => t.completed).length;
        document.getElementById('drTodo').textContent = `${total}개`;
        document.getElementById('drDone').textContent = `${done}/${total}`;
        const habits = await api('/api/habits');
        if (habits.length) {
            const checks = await api(`/api/habits/checks?dates=${e.date_str}`);
            const checked = Object.values(checks).filter(v => v).length;
            document.getElementById('drHabit').textContent = `${checked}/${habits.length}`;
        } else {
            document.getElementById('drHabit').textContent = '-';
        }
    } catch (err) {
        document.getElementById('drTodo').textContent = '-';
        document.getElementById('drDone').textContent = '-';
        document.getElementById('drHabit').textContent = '-';
    }
    $m.classList.remove('hidden');
    $m.querySelector('.dr-edit-btn').onclick = () => { $m.classList.add('hidden'); openDiaryModal(e); };
    $m.querySelector('.dr-delete-btn').onclick = async () => {
        if (confirm('이 일기를 삭제할까요?')) {
            await api(`/api/diary/${e.id}`, {method:'DELETE'});
            $m.classList.add('hidden');
            refreshDiary();
        }
    };
    $m.querySelector('.dr-close-btn').onclick = () => $m.classList.add('hidden');
    $m.addEventListener('click', (ev) => { if (ev.target === $m) $m.classList.add('hidden'); });
}

function renderDiaryCal(entries, year, month) {
    const $cal = document.getElementById('diaryCalView');
    $cal.innerHTML = '';
    const byDate = {};
    entries.forEach(e => {
        if (!byDate[e.date_str]) byDate[e.date_str] = [];
        byDate[e.date_str].push(e);
    });
    const grid = monthGrid(year, month);
    ['일','월','화','수','목','금','토'].forEach(d => {
        $cal.innerHTML += `<div class="diary-cal-head">${d}</div>`;
    });
    grid.flat().forEach(([day, yr, mo, ov]) => {
        const ds = `${yr}-${String(mo).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
        const list = byDate[ds] || [];
        const cell = document.createElement('div');
        cell.className = 'diary-cal-cell' + (list.length ? ' has-entry' : '') + (ov ? ' overflow' : '');
        cell.innerHTML = `<div class="dcc-day">${day}</div>`;
        if (list.length === 1) {
            cell.innerHTML += `<div class="dcc-mood">${list[0].mood||''}</div><div class="dcc-title">${esc(list[0].title||'')}</div>`;
            cell.addEventListener('click', () => openDiaryReadModal(list[0]));
        } else if (list.length > 1) {
            cell.innerHTML += `<div class="dcc-mood">${list[0].mood||''}</div><div class="dcc-title">${esc(list[0].title||'')}</div><div class="dcc-count">${list.length}개</div>`;
            cell.addEventListener('click', () => openDiaryPicker(ds, list));
        } else {
            cell.addEventListener('click', () => openDiaryModal({date_str: ds}));
        }
        $cal.appendChild(cell);
    });
}

function openDiaryPicker(dateStr, list) {
    const $m = document.getElementById('diaryPickerModal');
    document.getElementById('diaryPickerTitle').textContent = `${dateStr} 일기 (${list.length}개)`;
    const $list = document.getElementById('diaryPickerList');
    $list.innerHTML = '';
    list.forEach(e => {
        const item = document.createElement('div');
        item.className = 'diary-picker-item';
        item.innerHTML = `<span class="dpi-mood">${e.mood||''}</span><span class="dpi-title">${esc(e.title || '무제')}</span>`;
        item.addEventListener('click', () => {
            $m.classList.add('hidden');
            openDiaryReadModal(e);
        });
        $list.appendChild(item);
    });
    document.getElementById('diaryPickerNew').onclick = () => {
        $m.classList.add('hidden');
        openDiaryModal({date_str: dateStr});
    };
    document.getElementById('diaryPickerClose').onclick = () => $m.classList.add('hidden');
    $m.addEventListener('click', (ev) => { if (ev.target === $m) $m.classList.add('hidden'); });
    $m.classList.remove('hidden');
}

let currentEditingDiaryId = null;

function openDiaryModal(entry = null) {
    currentEditingDiaryId = entry?.id || null;
    const $e = document.getElementById('diaryEditor');
    document.getElementById('diaryModalTitle').textContent = currentEditingDiaryId ? '일기 수정' : '일기 쓰기';
    document.getElementById('diaryDateInput').value = entry?.date_str || todayStr();
    document.getElementById('diaryTitleInput').value = entry?.title || '';
    const $editor = document.getElementById('diaryContentInput');
    const rawContent = entry?.content || '';
    $editor.innerHTML = rawContent.includes('<') ? rawContent : rawContent.replace(/\n/g, '<br>');
    document.getElementById('diaryEventInput').value = entry?.event || '';
    document.getElementById('diaryEditDate').value = entry?.date_str || '';
    selectedMood = entry?.mood || '';
    document.querySelectorAll('.mood-btn').forEach(b => b.classList.toggle('selected', b.dataset.mood === selectedMood));
    $e.classList.remove('hidden');
    setTimeout(() => $editor.focus(), 100);
    loadDaySummary(document.getElementById('diaryDateInput').value);
}

async function loadDaySummary(dateStr) {
    try {
        const todos = await api(`/api/todos?date=${dateStr}`);
        const total = todos.length;
        const done = todos.filter(t => t.completed).length;
        document.getElementById('desTodo').textContent = `${total}개`;
        document.getElementById('desDone').textContent = `${done}/${total}`;
        const habits = await api('/api/habits');
        if (habits.length) {
            const checks = await api(`/api/habits/checks?dates=${dateStr}`);
            const checked = Object.values(checks).filter(v => v).length;
            document.getElementById('desHabit').textContent = `${checked}/${habits.length}`;
        } else {
            document.getElementById('desHabit').textContent = '-';
        }
    } catch (e) {
        console.log('summary load error', e);
    }
}

function closeDiaryEditor() {
    document.getElementById('diaryEditor').classList.add('hidden');
    refreshDiary();
}

function navDiaryDay(delta) {
    const current = document.getElementById('diaryDateInput').value || todayStr();
    const newDate = shiftDate(current, delta);
    openDiaryModal({ date_str: newDate });
}

async function saveDiary() {
    const dateStr = document.getElementById('diaryDateInput').value;
    if (!dateStr) { alert('날짜를 선택해주세요'); return; }
    const data = {
        date_str: dateStr,
        title: document.getElementById('diaryTitleInput').value.trim(),
        content: document.getElementById('diaryContentInput').innerHTML,
        mood: selectedMood,
        event: document.getElementById('diaryEventInput').value,
    };
    document.getElementById('diarySave').disabled = true;
    document.getElementById('diarySave').textContent = '저장 중...';
    try {
        let saved;
        if (currentEditingDiaryId) {
            saved = await api(`/api/diary/${currentEditingDiaryId}`, {method:'PUT', body:JSON.stringify(data)});
            const idx = diaryEntriesCache.findIndex(e => e.id === currentEditingDiaryId);
            if (idx !== -1) diaryEntriesCache[idx] = saved;
        } else {
            saved = await api('/api/diary', {method:'POST', body:JSON.stringify(data)});
            diaryEntriesCache.unshift(saved);
        }
        document.getElementById('diaryEditor').classList.add('hidden');
        showView('diary');
    } catch (err) {
        alert('저장 실패: ' + (err.message || err));
    } finally {
        document.getElementById('diarySave').disabled = false;
        document.getElementById('diarySave').textContent = '저장';
    }
}

async function addBucket() {
    const text = prompt('버킷리스트를 입력하세요:');
    if (!text?.trim()) return;
    await api('/api/bucket', {method:'POST', body:JSON.stringify({text: text.trim(), year: diaryYear || new Date().getFullYear()})});
    refreshDiary();
}

/* ══════════════════════════════════════════════════════
   메모장
   ══════════════════════════════════════════════════════ */
let currentMemoFolder = 'all'; // 'all', 'none', or folder id number
let memoFoldersCache = [];

function setupFreeMemo() {
    document.getElementById('memoAddBtn').addEventListener('click', () => openMemoModal());
    document.getElementById('memoCancel').addEventListener('click', () => document.getElementById('freeMemoModal').classList.add('hidden'));
    document.getElementById('memoSave').addEventListener('click', saveFreeMemo);
    // 메모 에디터 툴바
    document.querySelectorAll('.tb-btn[data-memo-cmd]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            document.execCommand(btn.dataset.memoCmd, false, null);
            document.getElementById('memoContentInput').focus();
        });
    });
    document.getElementById('memoTbCheck')?.addEventListener('click', () => {
        document.getElementById('memoContentInput').focus();
        document.execCommand('insertHTML', false, '<div><input type="checkbox" onclick="this.toggleAttribute(\'checked\')"> <span>할 일</span></div>');
    });
    document.getElementById('memoTbImage')?.addEventListener('click', () => document.getElementById('memoImageInput').click());
    document.getElementById('memoImageInput')?.addEventListener('change', (e) => {
        Array.from(e.target.files).forEach(file => {
            if (!file.type.startsWith('image/')) return;
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const MAX = 1200;
                let w = img.width, h = img.height;
                if (w > MAX || h > MAX) { if (w > h) { h = Math.round(h*MAX/w); w=MAX; } else { w = Math.round(w*MAX/h); h=MAX; } }
                canvas.width = w; canvas.height = h;
                canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                const tag = `<img src="${canvas.toDataURL('image/jpeg',0.7)}" style="width:50%;border-radius:8px;margin:8px 0;cursor:pointer" onclick="resizeDiaryImg(this)"> `;
                document.getElementById('memoContentInput').focus();
                document.execCommand('insertHTML', false, tag);
            };
            img.src = URL.createObjectURL(file);
        });
        e.target.value = '';
    });
    document.getElementById('memoTbLink')?.addEventListener('click', () => {
        const url = prompt('URL을 입력하세요:', 'https://');
        if (!url) return;
        const text = prompt('표시할 텍스트:', url);
        document.getElementById('memoContentInput').focus();
        document.execCommand('insertHTML', false, `<a href="${url}" target="_blank" style="color:#1A73E8">${esc(text||url)}</a>`);
    });
    document.getElementById('memoTbYoutube')?.addEventListener('click', () => {
        const url = prompt('유튜브 URL을 입력하세요:');
        if (!url) return;
        const match = url.match(/(?:youtu\.be\/|v=)([a-zA-Z0-9_-]{11})/);
        if (!match) { alert('유효한 유튜브 URL이 아닙니다.'); return; }
        const embed = `<div style="margin:8px 0"><iframe width="100%" height="250" src="https://www.youtube.com/embed/${match[1]}" frameborder="0" allowfullscreen style="border-radius:8px"></iframe></div>`;
        document.getElementById('memoContentInput').focus();
        document.execCommand('insertHTML', false, embed);
    });
    document.getElementById('memoFolderAddBtn').addEventListener('click', async () => {
        const name = prompt('폴더 이름을 입력하세요:');
        if (!name?.trim()) return;
        await api('/api/memo-folders', {method:'POST', body:JSON.stringify({name: name.trim()})});
        refreshMemoFolders();
    });
}

async function refreshMemoFolders() {
    memoFoldersCache = await api('/api/memo-folders');
    const $custom = document.getElementById('memoFolderListCustom');
    $custom.innerHTML = '';
    memoFoldersCache.forEach(f => {
        const div = document.createElement('div');
        div.className = 'memo-folder-item' + (currentMemoFolder == f.id ? ' active' : '');
        div.dataset.folder = f.id;
        div.innerHTML = `<span class="mf-name">📂 ${esc(f.name)}</span><button class="mf-del" title="삭제">&times;</button>`;
        div.querySelector('.mf-name').addEventListener('click', () => selectMemoFolder(f.id, f.name));
        div.querySelector('.mf-del').addEventListener('click', async (ev) => {
            ev.stopPropagation();
            if (confirm(`'${f.name}' 폴더를 삭제할까요? 안의 메모는 미분류로 이동됩니다.`)) {
                await api(`/api/memo-folders/${f.id}`, {method:'DELETE'});
                if (currentMemoFolder == f.id) { currentMemoFolder = 'all'; }
                refreshMemoFolders();
                refreshFreeMemo();
            }
        });
        $custom.appendChild(div);
    });
    // 고정 항목 active 상태
    document.querySelectorAll('.memo-folder-item[data-folder="all"], .memo-folder-item[data-folder="none"]').forEach(el => {
        el.classList.toggle('active', el.dataset.folder === String(currentMemoFolder));
        el.onclick = () => selectMemoFolder(el.dataset.folder, el.dataset.folder === 'all' ? '메모장' : '미분류');
    });
    // 모든 폴더에 드롭 이벤트
    document.querySelectorAll('.memo-folder-item').forEach(el => {
        el.addEventListener('dragover', (e) => { e.preventDefault(); el.classList.add('drag-over'); });
        el.addEventListener('dragleave', () => el.classList.remove('drag-over'));
        el.addEventListener('drop', async (e) => {
            e.preventDefault();
            el.classList.remove('drag-over');
            const memoId = e.dataTransfer.getData('text/plain');
            if (!memoId) return;
            const folderId = el.dataset.folder === 'none' ? null : (el.dataset.folder === 'all' ? undefined : parseInt(el.dataset.folder));
            if (folderId === undefined) return; // '전체'에는 드롭 불가
            await api(`/api/free-memos/${memoId}`, {method:'PUT', body:JSON.stringify({folder_id: folderId})});
            refreshFreeMemo();
        });
    });
}

function selectMemoFolder(folderId, folderName) {
    currentMemoFolder = folderId;
    document.getElementById('memoCurrentFolder').textContent = folderName || '메모장';
    document.querySelectorAll('.memo-folder-item').forEach(el => el.classList.toggle('active', el.dataset.folder == folderId));
    refreshFreeMemo();
}

async function refreshFreeMemo() {
    await refreshMemoFolders();
    let url = '/api/free-memos';
    if (currentMemoFolder === 'none') url += '?folder_id=0';
    else if (currentMemoFolder !== 'all') url += `?folder_id=${currentMemoFolder}`;
    const memos = await api(url);
    const $list = document.getElementById('freeMemoList');
    $list.innerHTML = '';
    if (!memos.length) { $list.innerHTML = '<div style="color:#999;padding:30px;text-align:center">메모가 없습니다.<br>\'+ 메모 등록\' 버튼으로 추가하세요.</div>'; return; }
    memos.forEach(m => {
        const card = document.createElement('div');
        card.className = 'memo-card';
        card.draggable = true;
        card.dataset.memoId = m.id;
        const preview = renderMarkdown(m.content).replace(/<[^>]*>/g, '');
        const shortPreview = preview.length > 100 ? preview.slice(0, 100) + '…' : preview;
        const dateStr = m.updated_at ? new Date(m.updated_at).toLocaleDateString('ko') : '';
        const folderName = m.folder_id ? (memoFoldersCache.find(f => f.id === m.folder_id)?.name || '') : '';
        card.innerHTML = `
            <div class="mc-title">${esc(m.title)}</div>
            <div class="mc-preview">${esc(shortPreview)}</div>
            ${folderName && currentMemoFolder === 'all' ? `<div class="mc-folder">📂 ${esc(folderName)}</div>` : ''}
            <div class="mc-date">${dateStr}</div>
            <div class="mc-actions">
                <button class="btn-sm edit-btn">수정</button>
                <button class="btn-sm del-btn" style="color:#e55">삭제</button>
            </div>
        `;
        card.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', m.id);
            card.style.opacity = '0.5';
        });
        card.addEventListener('dragend', () => { card.style.opacity = '1'; });
        card.querySelector('.edit-btn').addEventListener('click', (ev) => { ev.stopPropagation(); openMemoModal(m); });
        card.querySelector('.del-btn').addEventListener('click', async (ev) => {
            ev.stopPropagation();
            if (confirm(`'${m.title}' 삭제?`)) { await api(`/api/free-memos/${m.id}`, {method:'DELETE'}); refreshFreeMemo(); }
        });
        card.addEventListener('click', () => openMemoReadModal(m));
        $list.appendChild(card);
    });
}

function openMemoReadModal(memo) {
    const $m = document.getElementById('memoReadModal');
    document.getElementById('memoReadTitle').textContent = memo.title || '무제';
    const rc = memo.content || '';
    document.getElementById('memoReadContent').innerHTML = rc.includes('<') ? rc : rc.replace(/\n/g, '<br>');
    document.getElementById('memoReadClose').onclick = () => $m.classList.add('hidden');
    document.getElementById('memoReadEdit').onclick = () => { $m.classList.add('hidden'); openMemoModal(memo); };
    document.getElementById('memoReadDelete').onclick = async () => {
        if (confirm(`'${memo.title}' 삭제?`)) {
            await api(`/api/free-memos/${memo.id}`, {method:'DELETE'});
            $m.classList.add('hidden');
            refreshFreeMemo();
        }
    };
    $m.addEventListener('click', (ev) => { if (ev.target === $m) $m.classList.add('hidden'); });
    $m.classList.remove('hidden');
}

function openMemoModal(memo = null) {
    const $m = document.getElementById('freeMemoModal');
    document.getElementById('memoModalTitle').textContent = memo ? '메모 수정' : '메모 등록';
    document.getElementById('memoTitleInput').value = memo?.title || '';
    const $editor = document.getElementById('memoContentInput');
    const raw = memo?.content || '';
    $editor.innerHTML = raw.includes('<') ? raw : raw.replace(/\n/g, '<br>');
    document.getElementById('memoEditId').value = memo?.id || '';
    let $folderSelect = document.getElementById('memoFolderSelect');
    if ($folderSelect) {
        $folderSelect.innerHTML = '<option value="">미분류</option>';
        memoFoldersCache.forEach(f => {
            $folderSelect.innerHTML += `<option value="${f.id}" ${memo?.folder_id == f.id ? 'selected' : ''}>${esc(f.name)}</option>`;
        });
        if (!memo && currentMemoFolder !== 'all' && currentMemoFolder !== 'none') {
            $folderSelect.value = currentMemoFolder;
        }
    }
    $m.classList.remove('hidden');
    document.getElementById('memoTitleInput').focus();
}

async function saveFreeMemo() {
    const data = {
        title: document.getElementById('memoTitleInput').value.trim(),
        content: document.getElementById('memoContentInput').innerHTML,
        folder_id: document.getElementById('memoFolderSelect')?.value || null,
    };
    if (data.folder_id === '') data.folder_id = null;
    else if (data.folder_id) data.folder_id = parseInt(data.folder_id);
    const editId = document.getElementById('memoEditId').value;
    if (editId) {
        await api(`/api/free-memos/${editId}`, {method:'PUT', body:JSON.stringify(data)});
    } else {
        await api('/api/free-memos', {method:'POST', body:JSON.stringify(data)});
    }
    document.getElementById('freeMemoModal').classList.add('hidden');
    refreshFreeMemo();
}

function toggleMemoPreview() {
    const $p = document.getElementById('memoPreview');
    const content = document.getElementById('memoContentInput').value;
    if ($p.classList.contains('hidden')) {
        $p.innerHTML = renderMarkdown(content);
        $p.classList.remove('hidden');
    } else {
        $p.classList.add('hidden');
    }
}

function renderMarkdown(text) {
    return text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/~~(.+?)~~/g, '<del>$1</del>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
        .replace(/\n/g, '<br>');
}

/* ── Diary Export ──────────────────────────────────────── */
let exportEntries = [];

async function refreshExport() {
    exportEntries = await api('/api/diary?year=');
    const $yearFilter = document.getElementById('exportYearFilter');
    const years = [...new Set(exportEntries.map(e => e.date_str.slice(0, 4)))].sort().reverse();
    $yearFilter.innerHTML = '<option value="">전체 연도</option>';
    years.forEach(y => { $yearFilter.innerHTML += `<option value="${y}">${y}년</option>`; });
    document.getElementById('exportSelectAll').checked = false;
    renderExportList();

    document.getElementById('exportBackBtn').onclick = () => showView('diary');
    document.getElementById('exportYearFilter').onchange = renderExportList;
    document.getElementById('exportMonthFilter').onchange = renderExportList;
    document.getElementById('exportSelectAll').onchange = () => {
        const checked = document.getElementById('exportSelectAll').checked;
        document.querySelectorAll('.export-cb').forEach(cb => {
            cb.checked = checked;
            cb.closest('.export-row').classList.toggle('selected', checked);
        });
        updateExportCount();
    };
    document.getElementById('exportPdfBtn').onclick = exportPdf;
    document.getElementById('exportTxtBtn').onclick = exportTxt;
}

function getFilteredExport() {
    const y = document.getElementById('exportYearFilter').value;
    const m = document.getElementById('exportMonthFilter').value;
    return exportEntries.filter(e => {
        if (y && !e.date_str.startsWith(y)) return false;
        if (m && parseInt(e.date_str.slice(5, 7)) !== parseInt(m)) return false;
        return true;
    });
}

function renderExportList() {
    const filtered = getFilteredExport();
    const $list = document.getElementById('exportList');
    $list.innerHTML = '';
    document.getElementById('exportSelectAll').checked = false;
    if (!filtered.length) {
        $list.innerHTML = '<div style="color:#999;padding:30px;text-align:center">일기가 없습니다.</div>';
        updateExportCount();
        return;
    }
    filtered.forEach(e => {
        const row = document.createElement('div');
        row.className = 'export-row';
        row.dataset.id = e.id;
        row.innerHTML = `<input type="checkbox" class="export-cb" value="${e.id}"><div class="export-row-info"><div class="export-row-date">${e.date_str}</div><div class="export-row-title">${e.mood ? e.mood + ' ' : ''}${esc(e.title || '무제')}</div></div>`;
        row.addEventListener('click', (ev) => {
            if (ev.target.type === 'checkbox') return;
            const cb = row.querySelector('.export-cb');
            cb.checked = !cb.checked;
            row.classList.toggle('selected', cb.checked);
            updateExportCount();
        });
        row.querySelector('.export-cb').addEventListener('change', () => {
            row.classList.toggle('selected', row.querySelector('.export-cb').checked);
            updateExportCount();
        });
        $list.appendChild(row);
    });
    updateExportCount();
}

function getSelectedExportIds() {
    return [...document.querySelectorAll('.export-cb:checked')].map(cb => parseInt(cb.value));
}

function updateExportCount() {
    const count = getSelectedExportIds().length;
    document.getElementById('exportSelectedCount').textContent = count;
    document.getElementById('exportPdfBtn').disabled = count === 0;
    document.getElementById('exportTxtBtn').disabled = count === 0;
}

function exportPdf() {
    const ids = getSelectedExportIds();
    const selected = exportEntries.filter(e => ids.includes(e.id));
    let html = '<h1 style="text-align:center;color:#1A73E8;margin-bottom:30px">일기장</h1>';
    selected.forEach(e => {
        const contentHtml = (e.content || '').includes('<') ? e.content : esc(e.content || '');
        const eventHtml = e.event ? `<div style="margin:10px 0;padding:10px;background:#f8f9fa;border-radius:6px;font-size:13px;color:#666"><span style="font-size:11px;color:#1A73E8;font-weight:bold;margin-right:6px">이벤트</span>${esc(e.event).replace(/\n/g, '<br>')}</div>` : '';
        html += `<div style="margin-bottom:36px;page-break-inside:avoid"><div style="border-bottom:2px solid #1A73E8;padding-bottom:8px;margin-bottom:12px"><div style="font-size:12px;color:#999">${e.date_str}</div><div style="font-size:18px;font-weight:bold;margin-top:4px">${esc(e.title || '무제')} ${e.mood || ''}</div></div>${eventHtml}<div style="font-size:14px;line-height:1.9;word-break:break-word">${contentHtml}</div></div>`;
    });
    // 인쇄 전용 영역에 넣고 현재 페이지에서 인쇄
    let $pv = document.getElementById('printArea');
    if (!$pv) {
        $pv = document.createElement('div');
        $pv.id = 'printArea';
        document.body.appendChild($pv);
    }
    $pv.innerHTML = html;
    $pv.style.display = 'block';
    const cleanup = () => { $pv.style.display = 'none'; window.removeEventListener('afterprint', cleanup); };
    window.addEventListener('afterprint', cleanup);
    setTimeout(() => window.print(), 300);
}

function exportTxt() {
    const ids = getSelectedExportIds();
    location.href = `/diary/download/txt?ids=${ids.join(',')}`;
}

/* ── Diary Trash ──────────────────────────────────────── */
async function refreshTrash() {
    const entries = await api('/api/diary/trash');
    const $list = document.getElementById('trashListView');
    const $bar = document.getElementById('trashSelectBar');
    const $selectAll = document.getElementById('trashSelectAll');
    const $count = document.getElementById('trashSelectCount');
    const $restoreBtn = document.getElementById('trashRestoreBtn');
    const $delBtn = document.getElementById('trashDeleteBtn');
    $list.innerHTML = '';
    $selectAll.checked = false;

    if (!entries.length) {
        $bar.classList.add('hidden');
        $list.innerHTML = '<div style="color:#999;padding:30px;text-align:center">휴지통이 비어있습니다.</div>';
        return;
    }
    $bar.classList.remove('hidden');

    function updateCount() {
        const checked = document.querySelectorAll('.trash-cb:checked');
        $count.textContent = `${checked.length}개 선택`;
        $restoreBtn.disabled = checked.length === 0;
        $delBtn.disabled = checked.length === 0;
        const allCbs = document.querySelectorAll('.trash-cb');
        $selectAll.checked = allCbs.length > 0 && checked.length === allCbs.length;
    }

    $selectAll.onchange = () => {
        document.querySelectorAll('.trash-cb').forEach(cb => { cb.checked = $selectAll.checked; });
        updateCount();
    };
    $restoreBtn.onclick = async () => {
        const checked = [...document.querySelectorAll('.trash-cb:checked')];
        if (!checked.length || !confirm(`${checked.length}개 일기를 복원할까요?`)) return;
        await Promise.all(checked.map(cb => api(`/api/diary/restore/${cb.value}`, {method:'POST'})));
        refreshTrash();
    };
    $delBtn.onclick = async () => {
        const checked = [...document.querySelectorAll('.trash-cb:checked')];
        if (!checked.length) return;
        if (!confirm(`${checked.length}개 일기를 영구 삭제할까요? 복구할 수 없습니다.`)) return;
        if (!confirm('정말로 영구 삭제하시겠습니까?')) return;
        await Promise.all(checked.map(cb => api(`/api/diary/permanent/${cb.value}`, {method:'DELETE'})));
        refreshTrash();
    };

    entries.forEach(e => {
        const card = document.createElement('div');
        card.className = 'diary-card';
        card.style.opacity = '0.7';
        const delDate = e.deleted_at ? new Date(e.deleted_at).toLocaleDateString('ko-KR') : '';
        card.innerHTML = `
            <input type="checkbox" class="trash-cb" value="${e.id}">
            <div class="dc-info">
                <div class="dc-date">${e.date_str} <span style="color:#e55;font-size:10px">삭제: ${delDate}</span></div>
                <div class="dc-title">${e.mood ? e.mood + ' ' : ''}${esc(e.title || '무제')}</div>
            </div>
        `;
        card.querySelector('.trash-cb').addEventListener('click', ev => ev.stopPropagation());
        card.querySelector('.trash-cb').addEventListener('change', updateCount);
        card.addEventListener('click', (ev) => {
            if (ev.target.type === 'checkbox') return;
            openDiaryReadModal(e);
        });
        $list.appendChild(card);
    });
    updateCount();
}

/* ── Finance (가계부) ────────────────────────────────── */
let finYear, finMonth, finTab = 'dashboard';

let payAccountsCache = [];

async function loadPayAccounts() {
    payAccountsCache = await api('/api/pay-accounts');
    document.querySelectorAll('#fixedPayMethod, #loanAccount').forEach($sel => {
        const cur = $sel.value;
        $sel.innerHTML = '<option value="">선택 안 함</option>';
        payAccountsCache.forEach(a => {
            $sel.innerHTML += `<option value="${esc(a.name)}">${esc(a.name)}</option>`;
        });
        if (cur) $sel.value = cur;
    });
}

function setupFinance() {
    const today = new Date();
    finYear = today.getFullYear();
    finMonth = today.getMonth() + 1;
    document.getElementById('finPrev').addEventListener('click', () => { finMonth--; if (finMonth < 1) { finMonth = 12; finYear--; } refreshFinance(); });
    document.getElementById('finNext').addEventListener('click', () => { finMonth++; if (finMonth > 12) { finMonth = 1; finYear++; } refreshFinance(); });
    document.querySelectorAll('.fin-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            finTab = tab.dataset.ftab;
            document.querySelectorAll('.fin-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.querySelectorAll('.fin-view').forEach(v => v.classList.add('hidden'));
            document.getElementById({dashboard:'finDashboard',calendar:'finCalendar',fixed:'finFixed'}[finTab] || 'finDashboard').classList.remove('hidden');
            refreshFinance();
        });
    });
    document.querySelectorAll('.fin-type-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.fin-type-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
    document.getElementById('finAddBtn').addEventListener('click', () => openFinModal());
    // 계좌 추가 버튼 (노션처럼)
    document.querySelectorAll('.pay-account-add').forEach(btn => {
        btn.addEventListener('click', async () => {
            const name = prompt('계좌를 추가하세요:\n예: 국민 123-456-789, 신한카드');
            if (!name?.trim()) return;
            await api('/api/pay-accounts', {method:'POST', body:JSON.stringify({name: name.trim()})});
            await loadPayAccounts();
        });
    });
    document.querySelectorAll('.pay-account-del').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!payAccountsCache.length) { alert('삭제할 계좌가 없습니다'); return; }
            const list = payAccountsCache.map((a, i) => `${i+1}) ${a.name}`).join('\n');
            const idx = prompt(`삭제할 계좌 번호를 입력하세요:\n${list}`);
            if (!idx) return;
            const item = payAccountsCache[parseInt(idx) - 1];
            if (!item) { alert('잘못된 번호입니다'); return; }
            if (!confirm(`'${item.name}' 계좌를 삭제할까요?`)) return;
            await api(`/api/pay-accounts/${item.id}`, {method:'DELETE'});
            await loadPayAccounts();
        });
    });
    document.getElementById('finCancel').addEventListener('click', () => document.getElementById('finModal').classList.add('hidden'));
    document.getElementById('finSave').addEventListener('click', saveFinRecord);
    // 고정비 모달
    document.getElementById('fixedAddBtn').addEventListener('click', () => openFixedModal());
    document.getElementById('fixedCancel').addEventListener('click', () => document.getElementById('fixedModal').classList.add('hidden'));
    document.getElementById('fixedSave').addEventListener('click', async () => {
        const data = {
            name: document.getElementById('fixedName').value.trim(),
            amount: parseInt(document.getElementById('fixedAmount').value) || 0,
            category: document.getElementById('fixedCategory').value,
            day_of_month: parseInt(document.getElementById('fixedDay').value) || 1,
            pay_method: document.getElementById('fixedPayMethod').value.trim(),
            note: document.getElementById('fixedNote').value.trim(),
        };
        if (!data.name || !data.amount) { alert('항목명과 금액을 입력해주세요'); return; }
        const editId = document.getElementById('fixedEditId').value;
        if (editId) await api(`/api/finance/fixed/${editId}`, {method:'PUT', body:JSON.stringify(data)});
        else await api('/api/finance/fixed', {method:'POST', body:JSON.stringify(data)});
        document.getElementById('fixedModal').classList.add('hidden');
        refreshFinance();
    });
    // 대출 모달
    document.getElementById('loanAddBtn').addEventListener('click', () => openLoanModal());
    document.getElementById('loanCancel').addEventListener('click', () => document.getElementById('loanModal').classList.add('hidden'));
    // 잔액/금리/상환방식/만기일 변경 시 월 이자 자동계산
    ['loanRemaining', 'loanRate', 'loanRepayType', 'loanDueDate'].forEach(id => {
        document.getElementById(id).addEventListener('change', calcLoanInterest);
        document.getElementById(id).addEventListener('input', calcLoanInterest);
    });
    document.getElementById('loanSave').addEventListener('click', async () => {
        const data = {
            name: document.getElementById('loanName').value.trim(),
            bank: document.getElementById('loanBank').value.trim(),
            remaining_amount: parseInt(document.getElementById('loanRemaining').value) || 0,
            interest_rate: parseFloat(document.getElementById('loanRate').value) || 0,
            due_date: document.getElementById('loanDueDate').value || '',
            repay_type: document.getElementById('loanRepayType').value,
            prepay_fee: document.getElementById('loanPrepayFee').value.trim(),
            monthly_interest: parseInt(document.getElementById('loanMonthlyInterest').value) || 0,
            account: document.getElementById('loanAccount').value.trim(),
            pay_day: parseInt(document.getElementById('loanPayDay').value) || 0,
        };
        if (!data.name) { alert('대출명을 입력해주세요'); return; }
        // 월 이자 미입력 시 자동계산
        if (!data.monthly_interest && data.remaining_amount && data.interest_rate) {
            data.monthly_interest = Math.round(data.remaining_amount * data.interest_rate / 100 / 12);
        }
        const editId = document.getElementById('loanEditId').value;
        if (editId) await api(`/api/finance/loans/${editId}`, {method:'PUT', body:JSON.stringify(data)});
        else await api('/api/finance/loans', {method:'POST', body:JSON.stringify(data)});
        document.getElementById('loanModal').classList.add('hidden');
        refreshFinance();
    });
}

function calcLoanInterest() {
    const balance = parseInt(document.getElementById('loanRemaining').value) || 0;
    const rate = parseFloat(document.getElementById('loanRate').value) || 0;
    const type = document.getElementById('loanRepayType').value;
    const dueDate = document.getElementById('loanDueDate').value;
    const $interest = document.getElementById('loanMonthlyInterest');
    const $label = document.getElementById('loanCalcLabel');

    if (!balance || !rate) { $label.textContent = ''; return; }

    const monthlyRate = rate / 100 / 12;

    if (type === '만기일시' || type === '자유상환') {
        const interest = Math.round(balance * monthlyRate);
        $interest.value = interest;
        $label.textContent = `(자동계산: ${interest.toLocaleString()}원)`;
    } else if (type === '원리금균등' && dueDate) {
        const months = Math.max(1, monthsBetween(todayStr(), dueDate));
        const mp = balance * monthlyRate * Math.pow(1 + monthlyRate, months) / (Math.pow(1 + monthlyRate, months) - 1);
        const firstInterest = Math.round(balance * monthlyRate);
        $interest.value = firstInterest;
        $label.textContent = `(첫달 이자 ${firstInterest.toLocaleString()}원 / 월 납부 ${Math.round(mp).toLocaleString()}원)`;
    } else if (type === '원금균등' && dueDate) {
        const months = Math.max(1, monthsBetween(todayStr(), dueDate));
        const firstInterest = Math.round(balance * monthlyRate);
        const monthlyPrincipal = Math.round(balance / months);
        $interest.value = firstInterest;
        $label.textContent = `(첫달 이자 ${firstInterest.toLocaleString()}원 / 원금 ${monthlyPrincipal.toLocaleString()}원)`;
    } else {
        const interest = Math.round(balance * monthlyRate);
        $interest.value = interest;
        $label.textContent = `(자동계산: ${interest.toLocaleString()}원)`;
    }
}

async function openFixedModal(item = null) {
    await loadPayAccounts();
    document.getElementById('fixedModalTitle').textContent = item ? '고정비 수정' : '고정비 등록';
    document.getElementById('fixedCategory').value = item?.category || '기타';
    document.getElementById('fixedName').value = item?.name || '';
    document.getElementById('fixedAmount').value = item?.amount || '';
    document.getElementById('fixedDay').value = item?.day_of_month || 1;
    document.getElementById('fixedNote').value = item?.note || '';
    document.getElementById('fixedEditId').value = item?.id || '';
    document.getElementById('fixedPayMethod').value = item?.pay_method || '';
    document.getElementById('fixedModal').classList.remove('hidden');
}

async function openLoanModal(item = null) {
    await loadPayAccounts();
    document.getElementById('loanModalTitle').textContent = item ? '대출 수정' : '대출 등록';
    document.getElementById('loanName').value = item?.name || '';
    document.getElementById('loanBank').value = item?.bank || '';
    document.getElementById('loanRemaining').value = item?.remaining_amount || '';
    document.getElementById('loanRate').value = item?.interest_rate || '';
    document.getElementById('loanDueDate').value = item?.due_date || '';
    document.getElementById('loanRepayType').value = item?.repay_type || '원리금균등';
    document.getElementById('loanPrepayFee').value = item?.prepay_fee || '';
    document.getElementById('loanMonthlyInterest').value = item?.monthly_interest || '';
    document.getElementById('loanAccount').value = item?.account || '';
    document.getElementById('loanPayDay').value = item?.pay_day || '';
    document.getElementById('loanEditId').value = item?.id || '';
    document.getElementById('loanModal').classList.remove('hidden');
}

function openFinModal(record = null) {
    document.getElementById('finModalTitle').textContent = record ? '거래 수정' : '거래 등록';
    document.getElementById('finDate').value = record?.date_str || todayStr();
    document.getElementById('finAmount').value = record?.amount || '';
    document.getElementById('finDesc').value = record?.description || '';
    document.getElementById('finEditId').value = record?.id || '';
    document.querySelectorAll('.fin-type-btn').forEach(b => b.classList.toggle('active', b.dataset.type === (record?.record_type || 'expense')));
    if (record?.category) document.getElementById('finCategory').value = record.category;
    document.getElementById('finModal').classList.remove('hidden');
}

async function saveFinRecord() {
    const type = document.querySelector('.fin-type-btn.active')?.dataset.type || 'expense';
    const data = {
        date_str: document.getElementById('finDate').value,
        record_type: type,
        category: document.getElementById('finCategory').value,
        amount: parseInt(document.getElementById('finAmount').value) || 0,
        description: document.getElementById('finDesc').value,
    };
    if (!data.date_str || !data.amount) { alert('날짜와 금액을 입력해주세요'); return; }
    const editId = document.getElementById('finEditId').value;
    if (editId) await api(`/api/finance/${editId}`, {method:'PUT', body:JSON.stringify(data)});
    else await api('/api/finance', {method:'POST', body:JSON.stringify(data)});
    document.getElementById('finModal').classList.add('hidden');
    refreshFinance();
}

async function refreshFinance() {
    document.getElementById('finTitle').textContent = `${finYear}년 ${finMonth}월`;
    if (finTab === 'dashboard') await renderFinDashboard();
    else if (finTab === 'calendar') await renderFinCalendar();
    else if (finTab === 'fixed') { await renderFinFixed(); await renderFinLoans(); renderAccountSummary(); }
}

async function renderFinDashboard() {
    const [summary, records] = await Promise.all([
        api(`/api/finance/summary?year=${finYear}&month=${finMonth}`),
        api(`/api/finance?year=${finYear}&month=${finMonth}`)
    ]);
    // 요약 카드
    document.getElementById('finSummary').innerHTML = `
        <div class="fin-card fin-income"><div class="fin-card-label">수입</div><div class="fin-card-amount">+${summary.income.toLocaleString()}원</div></div>
        <div class="fin-card fin-expense"><div class="fin-card-label">지출</div><div class="fin-card-amount">-${summary.expense.toLocaleString()}원</div></div>
        <div class="fin-card fin-balance"><div class="fin-card-label">잔액</div><div class="fin-card-amount">${summary.balance.toLocaleString()}원</div></div>
    `;
    // 카테고리 차트
    const $chart = document.getElementById('finCatChart');
    const cats = Object.entries(summary.categories).sort((a,b) => b[1]-a[1]);
    if (cats.length && summary.expense > 0) {
        $chart.innerHTML = '<h3 style="font-size:13px;margin-bottom:8px">카테고리별 지출</h3>';
        cats.forEach(([cat, amt]) => {
            const pct = Math.round(amt / summary.expense * 100);
            $chart.innerHTML += `<div class="fin-cat-row"><span class="fin-cat-name">${esc(cat)}</span><div class="fin-cat-bar"><div style="width:${pct}%"></div></div><span class="fin-cat-val">${pct}% ${amt.toLocaleString()}</span></div>`;
        });
    } else { $chart.innerHTML = ''; }
    // 거래 목록
    const $list = document.getElementById('finList');
    $list.innerHTML = '';
    if (!records.length) { $list.innerHTML = '<div style="color:#999;padding:20px;text-align:center">거래 내역이 없습니다.</div>'; return; }
    records.forEach(r => {
        const div = document.createElement('div');
        div.className = 'fin-record';
        const color = r.record_type === 'income' ? '#1A73E8' : '#e55';
        const sign = r.record_type === 'income' ? '+' : '-';
        div.innerHTML = `<span class="fin-r-date">${r.date_str.slice(5)}</span><span class="fin-r-cat">${esc(r.category)}</span><span class="fin-r-amount" style="color:${color}">${sign}${r.amount.toLocaleString()}</span><span class="fin-r-desc">${esc(r.description)}</span><button class="fin-r-del" title="삭제">&times;</button>`;
        div.addEventListener('click', (e) => { if (!e.target.classList.contains('fin-r-del')) openFinModal(r); });
        div.querySelector('.fin-r-del').addEventListener('click', async (e) => {
            e.stopPropagation();
            if (confirm('삭제할까요?')) { await api(`/api/finance/${r.id}`, {method:'DELETE'}); refreshFinance(); }
        });
        $list.appendChild(div);
    });
}

async function renderFinCalendar() {
    const [records, loans, fixedItems] = await Promise.all([
        api(`/api/finance?year=${finYear}&month=${finMonth}`),
        api('/api/finance/loans'),
        api('/api/finance/fixed'),
    ]);
    const byDate = {};
    records.forEach(r => {
        if (!byDate[r.date_str]) byDate[r.date_str] = {income: 0, expense: 0, tags: []};
        if (r.record_type === 'income') byDate[r.date_str].income += r.amount;
        else byDate[r.date_str].expense += r.amount;
    });
    // 대출/고정비 상환일 정보
    const payDays = {};
    loans.forEach(l => {
        if (!l.pay_day) return;
        if (!payDays[l.pay_day]) payDays[l.pay_day] = [];
        // 월 상환금액 계산
        let monthlyPayment = l.monthly_payment || 0;
        if (!monthlyPayment && l.remaining_amount && l.interest_rate && l.due_date) {
            const r = l.interest_rate / 100 / 12;
            const months = Math.max(1, monthsBetween(todayStr(), l.due_date));
            if (l.repay_type === '원리금균등') monthlyPayment = Math.round(l.remaining_amount * r * Math.pow(1+r, months) / (Math.pow(1+r, months) - 1));
            else if (l.repay_type === '원금균등') monthlyPayment = Math.round(l.remaining_amount / months + l.remaining_amount * r);
            else if (l.repay_type === '만기일시') monthlyPayment = Math.round(l.remaining_amount * r);
            else monthlyPayment = l.monthly_interest || 0;
        }
        payDays[l.pay_day].push({type:'loan', name:l.name, monthlyPayment, account:l.account, bank:l.bank, repay_type:l.repay_type});
    });
    fixedItems.forEach(f => { if (f.day_of_month && f.is_active) { if (!payDays[f.day_of_month]) payDays[f.day_of_month] = []; payDays[f.day_of_month].push({type:'fixed', name:f.name, amount:f.amount, category:f.category}); }});

    const $grid = document.getElementById('finCalGrid');
    $grid.innerHTML = '';
    ['일','월','화','수','목','금','토'].forEach(d => {
        $grid.innerHTML += `<div class="fin-cal-head">${d}</div>`;
    });
    const grid = monthGrid(finYear, finMonth);
    grid.flat().forEach(([day, yr, mo, ov]) => {
        const ds = `${yr}-${String(mo).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
        const data = byDate[ds];
        const cell = document.createElement('div');
        cell.className = 'fin-cal-cell' + (ov ? ' overflow' : '');
        const today = todayStr();
        if (ds === today) cell.classList.add('today');
        let inner = `<div class="fin-cal-day">${day}</div>`;
        // 대출/고정비 상환일 태그
        if (!ov && mo === finMonth && payDays[day]) {
            payDays[day].forEach(p => {
                const n = p.name.length > 5 ? p.name.slice(0,5)+'…' : p.name;
                inner += `<div class="fin-cal-tag">${esc(n)}</div>`;
            });
        }
        if (data) {
            if (data.income) inner += `<div class="fin-cal-income">+${data.income.toLocaleString()}원</div>`;
            if (data.expense) inner += `<div class="fin-cal-expense">-${data.expense.toLocaleString()}원</div>`;
        } else if (!ov && mo === finMonth && !payDays[day]) {
            const d = new Date(yr, mo-1, day);
            if (d <= new Date()) inner += `<div class="fin-cal-nospend">✓</div>`;
        }
        cell.innerHTML = inner;
        cell.addEventListener('click', () => openFinDayModal(ds, day, mo, byDate[ds], payDays[day], records));
        $grid.appendChild(cell);
    });
}

function openFinDayModal(ds, day, month, dayData, tags, allRecords) {
    const $m = document.getElementById('finDayModal');
    document.getElementById('finDayTitle').textContent = ds;

    // 대출/고정비 상세 표시
    const $fixed = document.getElementById('finDayFixed');
    if (tags && tags.length) {
        let html = '<div style="font-size:12px;color:#888;margin-bottom:6px">이 날 결제</div>';
        tags.forEach(p => {
            if (p.type === 'loan') {
                html += `<div class="fin-day-card loan">
                    <div class="fin-day-card-title">🏦 ${esc(p.name)}</div>
                    <div class="fin-day-card-info">
                        ${p.monthlyPayment ? `<span>월 상환금: <strong>${p.monthlyPayment.toLocaleString()}원</strong></span>` : ''}
                        ${p.repay_type ? `<span>상환: ${esc(p.repay_type)}</span>` : ''}
                        ${p.bank ? `<span>금융기관: ${esc(p.bank)}</span>` : ''}
                        ${p.account ? `<span>계좌: ${esc(p.account)}</span>` : ''}
                    </div>
                </div>`;
            } else {
                html += `<div class="fin-day-card fixed">
                    <div class="fin-day-card-title">📋 ${esc(p.name)}</div>
                    <div class="fin-day-card-info">
                        <span>금액: <strong>${p.amount.toLocaleString()}원</strong></span>
                        ${p.category ? `<span>분류: ${esc(p.category)}</span>` : ''}
                    </div>
                </div>`;
            }
        });
        $fixed.innerHTML = html;
    } else {
        $fixed.innerHTML = '';
    }

    // 해당 날짜 거래 내역
    const $records = document.getElementById('finDayRecords');
    const dayRecords = allRecords.filter(r => r.date_str === ds);
    if (dayRecords.length) {
        $records.innerHTML = '<div style="font-size:12px;color:#888;margin:8px 0 4px">거래 내역</div>';
        dayRecords.forEach(r => {
            const color = r.record_type === 'income' ? '#1A73E8' : '#e55';
            const sign = r.record_type === 'income' ? '+' : '-';
            $records.innerHTML += `<div class="fin-day-record"><span class="fin-day-cat">${esc(r.category)}</span><span style="color:${color};font-weight:bold">${sign}${r.amount.toLocaleString()}원</span><span style="color:#999;font-size:11px">${esc(r.description)}</span></div>`;
        });
    } else {
        $records.innerHTML = '<div style="color:#999;padding:16px;text-align:center;font-size:13px">거래 내역이 없습니다</div>';
    }

    document.getElementById('finDayAddBtn').onclick = () => { $m.classList.add('hidden'); openFinModal({date_str: ds}); };
    document.getElementById('finDayClose').onclick = () => $m.classList.add('hidden');
    $m.addEventListener('click', (e) => { if (e.target === $m) $m.classList.add('hidden'); });
    $m.classList.remove('hidden');
}

async function renderAccountSummary() {
    const [fixedItems, loans] = await Promise.all([api('/api/finance/fixed'), api('/api/finance/loans')]);
    const byAccount = {};
    // 고정비
    fixedItems.filter(f => f.is_active && f.pay_method).forEach(f => {
        byAccount[f.pay_method] = (byAccount[f.pay_method] || 0) + f.amount;
    });
    // 대출 (월 이자 or 상환금)
    loans.filter(l => l.account).forEach(l => {
        let payment = l.monthly_interest || 0;
        if (!payment && l.remaining_amount && l.interest_rate) {
            payment = Math.round(l.remaining_amount * l.interest_rate / 100 / 12);
        }
        byAccount[l.account] = (byAccount[l.account] || 0) + payment;
    });
    const $el = document.getElementById('finAccountSummary');
    const entries = Object.entries(byAccount).sort((a, b) => b[1] - a[1]);
    if (!entries.length) { $el.innerHTML = ''; return; }
    const grandTotal = entries.reduce((s, [, v]) => s + v, 0);
    let html = `<h3 style="font-size:14px;margin-bottom:10px">💳 계좌별 월 출금 합계</h3>`;
    html += `<div class="fin-account-total">총 합계: <strong>${grandTotal.toLocaleString()}원</strong>/월</div>`;
    entries.forEach(([account, amount]) => {
        const pct = grandTotal > 0 ? Math.round(amount / grandTotal * 100) : 0;
        html += `<div class="fin-account-row">
            <span class="fin-acc-name">${esc(account)}</span>
            <div class="fin-acc-bar"><div style="width:${pct}%"></div></div>
            <span class="fin-acc-val">${amount.toLocaleString()}원</span>
        </div>`;
    });
    $el.innerHTML = html;
}

async function renderFinFixed() {
    const items = await api('/api/finance/fixed');
    const $list = document.getElementById('finFixedList');
    $list.innerHTML = '';
    if (!items.length) { $list.innerHTML = '<div style="color:#999;padding:20px;text-align:center">고정비가 없습니다.</div>'; return; }
    const total = items.filter(i => i.is_active).reduce((s, i) => s + i.amount, 0);
    $list.innerHTML = `<div class="fin-fixed-total">월 고정비 합계: <strong>${total.toLocaleString()}원</strong></div>`;
    items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'fin-fixed-item' + (item.is_active ? '' : ' inactive');
        div.innerHTML = `<span class="fin-f-cat">${esc(item.category)}</span><span class="fin-f-name">${esc(item.name)}</span><span class="fin-f-day">매월 ${item.day_of_month}일</span><span class="fin-f-amount">${item.amount.toLocaleString()}원</span>${item.pay_method ? `<span class="fin-f-pay">${esc(item.pay_method)}</span>` : ''}${item.note ? `<span class="fin-f-note">${esc(item.note)}</span>` : ''}<button class="fin-f-del">&times;</button>`;
        div.querySelector('.fin-f-del').addEventListener('click', async (e) => {
            e.stopPropagation();
            if (confirm(`'${item.name}' 삭제?`)) { await api(`/api/finance/fixed/${item.id}`, {method:'DELETE'}); refreshFinance(); }
        });
        div.addEventListener('click', () => openFixedModal(item));
        $list.appendChild(div);
    });
}

async function renderFinLoans() {
    const items = await api('/api/finance/loans');
    const $list = document.getElementById('finLoanList');
    $list.innerHTML = '';
    if (!items.length) { $list.innerHTML = '<div style="color:#999;padding:20px;text-align:center">대출이 없습니다.</div>'; return; }
    items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'fin-loan-card';
        // 상환 시뮬레이션 계산
        let scheduleHtml = '';
        if (item.remaining_amount > 0 && item.interest_rate > 0) {
            const r = item.interest_rate / 100 / 12;
            let balance = item.remaining_amount;
            let rows = '';
            const maxMonths = item.due_date ? Math.max(1, monthsBetween(todayStr(), item.due_date)) : 12;
            const showMonths = Math.min(maxMonths, 24);
            const payD = item.pay_day || 1;
            const now = new Date();
            const startY = now.getFullYear();
            const startM = now.getMonth(); // 0-based

            function getPayDate(idx) {
                const d = new Date(startY, startM + idx, 1);
                return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(payD).padStart(2,'0')}`;
            }

            if (item.repay_type === '원리금균등' && maxMonths > 0) {
                const mp = balance * r * Math.pow(1+r, maxMonths) / (Math.pow(1+r, maxMonths) - 1);
                for (let i = 1; i <= showMonths; i++) {
                    const interest = Math.round(balance * r);
                    const principal = Math.round(mp - interest);
                    balance = Math.max(0, balance - principal);
                    rows += `<tr><td>${getPayDate(i)}</td><td>${Math.round(mp).toLocaleString()}</td><td>${principal.toLocaleString()}</td><td>${interest.toLocaleString()}</td><td>${balance.toLocaleString()}</td></tr>`;
                }
            } else if (item.repay_type === '원금균등' && maxMonths > 0) {
                const monthlyPrincipal = Math.round(item.remaining_amount / maxMonths);
                for (let i = 1; i <= showMonths; i++) {
                    const interest = Math.round(balance * r);
                    const total = monthlyPrincipal + interest;
                    balance = Math.max(0, balance - monthlyPrincipal);
                    rows += `<tr><td>${getPayDate(i)}</td><td>${total.toLocaleString()}</td><td>${monthlyPrincipal.toLocaleString()}</td><td>${interest.toLocaleString()}</td><td>${balance.toLocaleString()}</td></tr>`;
                }
            } else if (item.repay_type === '만기일시') {
                const interest = Math.round(balance * r);
                for (let i = 1; i <= showMonths; i++) {
                    rows += `<tr><td>${getPayDate(i)}</td><td>${interest.toLocaleString()}</td><td>0</td><td>${interest.toLocaleString()}</td><td>${balance.toLocaleString()}</td></tr>`;
                }
            }
            if (rows) {
                scheduleHtml = `<div class="fin-l-schedule"><div class="fin-l-schedule-toggle">▼ 상환 스케줄</div><table class="fin-l-table hidden"><tr><th>회차</th><th>납부액</th><th>원금</th><th>이자</th><th>잔액</th></tr>${rows}</table></div>`;
            }
        }
        div.innerHTML = `
            <div class="fin-l-header"><span class="fin-l-name">${esc(item.name)}</span><button class="fin-l-del">&times;</button></div>
            ${item.bank ? `<div class="fin-l-sub">${esc(item.bank)}</div>` : ''}
            <div class="fin-l-info">
                <span>잔액 <strong>${item.remaining_amount.toLocaleString()}원</strong></span>
                ${item.interest_rate ? `<span>금리 ${item.interest_rate}%</span>` : ''}
                ${item.monthly_interest ? `<span>월 이자 ${item.monthly_interest.toLocaleString()}원</span>` : ''}
                ${item.repay_type ? `<span>상환: ${esc(item.repay_type)}</span>` : ''}
                ${item.due_date ? `<span>만기 ${item.due_date}</span>` : ''}
                ${item.account ? `<span>계좌: ${esc(item.account)}</span>` : ''}
            </div>
            ${item.prepay_fee ? `<div class="fin-l-fee">중도상환: ${esc(item.prepay_fee)}</div>` : ''}
            ${scheduleHtml}
        `;
        // 스케줄 토글
        const toggle = div.querySelector('.fin-l-schedule-toggle');
        if (toggle) {
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const table = div.querySelector('.fin-l-table');
                table.classList.toggle('hidden');
                toggle.textContent = table.classList.contains('hidden') ? '▼ 상환 스케줄' : '▲ 상환 스케줄 접기';
            });
        }
        div.querySelector('.fin-l-del').addEventListener('click', async (e) => {
            e.stopPropagation();
            if (confirm(`'${item.name}' 삭제?`)) { await api(`/api/finance/loans/${item.id}`, {method:'DELETE'}); refreshFinance(); }
        });
        div.addEventListener('click', () => openLoanModal(item));
        $list.appendChild(div);
    });
}

