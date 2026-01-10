# /opt/radio/modules/admin_panel_module.py

from flask import Flask, request, jsonify, Response, render_template_string
import json
import threading
from functools import wraps
import os
from .base_module import RadioModule
from logger import log
import config as radio_config

app = Flask(__name__)
shared_modules = {}
shared_settings = {}
settings_lock = threading.Lock()
SETTINGS_FILE = "module_settings.json"
SCHEDULE_FILE = "schedule.json"

def check_auth(u, p): return u == 'admin' and p == 'admin'
def authenticate(): return Response('Login Required', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password): return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/admin')
@requires_auth
def admin_page(): return render_template_string(AdminPanelModule.ADMIN_TEMPLATE)

@app.route('/api/state', methods=['GET'])
@requires_auth
def get_state():
    state = {"modules": {}, "schedule": []}
    with settings_lock:
        for name, module in shared_modules.items():
            if name == 'admin_panel': continue
            state["modules"][name] = {
                "schema": module.get_config_schema(), 
                "current_config": shared_settings.get(name, {}),
                "is_system": getattr(module, 'is_system', False)
            }
        try:
            with open(SCHEDULE_FILE, 'r') as f: state["schedule"] = json.load(f)
        except: pass
    return jsonify(state)

@app.route('/api/save', methods=['POST'])
@requires_auth
def save_state():
    data = request.json
    try:
        with settings_lock:
            for name, cfg in data.get('settings', {}).items():
                if name in shared_settings:
                    shared_settings[name].update(cfg)
                    if name in shared_modules: shared_modules[name].update_config(shared_settings[name])
            with open(SETTINGS_FILE, 'w') as f: json.dump(shared_settings, f, indent=2, ensure_ascii=False)
            with open(SCHEDULE_FILE, 'w') as f: json.dump(data.get('schedule', []), f, indent=2, ensure_ascii=False)
        return jsonify({"status": "ok", "message": "Сохранено!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/logs', methods=['GET'])
@requires_auth
def get_logs():
    try:
        with open(radio_config.LOG_FILE, 'r') as f: lines = f.readlines()
        return jsonify({"status": "ok", "logs": "".join(lines[-100:])})
    except: return jsonify({"status": "ok", "logs": "Нет логов."})

class AdminPanelModule(RadioModule):
    def __init__(self):
        super().__init__()
        self.is_system = True

    def get_config_schema(self): return {}
    
    def prepare(self, e, c):
        global shared_modules, shared_settings
        shared_modules, shared_settings = c.get('all_modules', {}), c.get('all_settings', {})
        try: app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
        except Exception as e: log(f"❌ Server Error: {e}")
        return None

    ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Radio Admin</title>
<script src="https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --bg: #121212; --panel: #1e1e1e; --accent: #fd429c; --text: #eee; --border: #333; }
    body { background: var(--bg); color: var(--text); font-family: sans-serif; margin: 0; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
    
    .header { height: 50px; background: var(--panel); border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 20px; font-weight: bold; color: var(--accent); flex-shrink: 0; }
    .main { display: flex; flex: 1; overflow: hidden; }
    
    /* SIDEBAR */
    .sidebar { width: 240px; background: var(--panel); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; }
    .palette-container { padding: 15px; overflow-y: auto; flex: 1; }
    .palette-item { background: #2a2a2a; padding: 12px; margin-bottom: 8px; border-radius: 4px; cursor: grab; border: 1px solid #444; display: flex; align-items: center; gap: 10px; font-weight: bold; user-select: none; }
    .palette-item:hover { border-color: var(--accent); background: #333; }
    
    /* CONTENT */
    .content { flex: 1; display: flex; flex-direction: column; min-width: 0; }
    .tabs { display: flex; background: var(--panel); border-bottom: 1px solid var(--border); flex-shrink: 0; }
    .tab { padding: 12px 20px; cursor: pointer; color: #888; font-weight: 500; border-right: 1px solid var(--border); }
    .tab.active { color: var(--accent); background: rgba(253,66,156,0.05); }
    
    .view { flex: 1; padding: 20px; overflow-y: auto; display: none; position: relative; }
    .view.active { display: block; }

    /* SCHEDULE LIST */
    #schedule-list { min-height: 200px; padding-bottom: 80px; }
    /* Default Style for ANY item */
    .sched-item { 
        background: #252525; 
        margin-bottom: 8px; 
        border-radius: 6px; 
        padding: 12px 15px; 
        display: flex; 
        align-items: center; 
        gap: 15px; 
        border-left: 5px solid #777; /* Default Gray */
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    /* Specific Styles */
    .sched-item.type-music { border-color: #4287f5; }
    .sched-item.type-dj { border-color: #f5d142; }
    .sched-item.type-ad { border-color: #f54242; } /* Red for Ad */
    .sched-item.type-news { border-color: #9b59b6; }
    
    .item-info { flex: 1; cursor: pointer; overflow: hidden; }
    .item-title { font-weight: bold; font-size: 1rem; }
    .item-desc { font-size: 0.85rem; color: #aaa; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px; }
    .btn-del { color: #666; cursor: pointer; font-size: 1.2rem; padding: 5px; transition: 0.2s; }
    .btn-del:hover { color: #ff4444; }

    /* FAB */
    .fab-save { position: absolute; bottom: 25px; right: 25px; background: var(--accent); color: white; border: none; padding: 15px 30px; border-radius: 50px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.5); font-size: 1rem; display: flex; align-items: center; gap: 8px; z-index: 10; transition: transform 0.1s; }
    .fab-save:active { transform: scale(0.95); }

    /* FORMS */
    .form-group { margin-bottom: 15px; background: #2a2a2a; padding: 15px; border-radius: 6px; }
    label { display: block; margin-bottom: 8px; color: var(--accent); }
    input, textarea, select { width: 100%; background: #151515; border: 1px solid #444; color: #fff; padding: 10px; border-radius: 4px; box-sizing: border-box; }

    /* MODAL */
    .modal-overlay { position: fixed; top:0; left:0; right:0; bottom:0; background: rgba(0,0,0,0.8); z-index: 999; display: none; justify-content: center; align-items: center; }
    .modal { background: var(--panel); width: 90%; max-width: 500px; padding: 25px; border-radius: 8px; border: 1px solid #444; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    
    @media (max-width: 768px) {
        .main { flex-direction: column-reverse; }
        .sidebar { width: 100%; height: 160px; flex-shrink: 0; border-top: 1px solid var(--border); }
    }
</style>
</head>
<body>

<div class="header">MAFIOZNIK CONTROL</div>

<div class="main">
    <div class="sidebar">
        <div style="padding:15px 15px 0; color:#666; font-size:0.8rem; font-weight:bold;">МОДУЛИ</div>
        <div id="palette" class="palette-container"></div>
    </div>

    <div class="content">
        <div class="tabs">
            <div class="tab active" onclick="setTab('program')">Эфир</div>
            <div class="tab" onclick="setTab('settings')">Настройки</div>
            <div class="tab" onclick="setTab('logs')">Логи</div>
        </div>

        <div id="view-program" class="view active">
            <div id="schedule-list"></div>
        </div>

        <div id="view-settings" class="view">
            <div id="settings-container"></div>
        </div>

        <div id="view-logs" class="view">
            <pre id="logs-output" style="white-space: pre-wrap; word-break: break-all; color:#0f0; font-family:monospace;">Loading...</pre>
        </div>

        <button class="fab-save" onclick="saveAllData()"><i class="fas fa-save"></i> СОХРАНИТЬ</button>
    </div>
</div>

<!-- Modal -->
<div class="modal-overlay" id="editModal">
    <div class="modal">
        <h3 id="modalTitle" style="margin-top:0; color:var(--accent)">Настройка</h3>
        <input type="hidden" id="modalUid">
        <div id="modalContent"></div>
        <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:20px;">
            <button onclick="document.getElementById('editModal').style.display='none'" style="padding:8px 15px; background:transparent; color:#888; border:none; cursor:pointer;">Отмена</button>
            <button onclick="applyEdit()" style="padding:8px 20px; background:var(--accent); color:white; border:none; border-radius:4px; cursor:pointer;">OK</button>
        </div>
    </div>
</div>

<script>
    const ICONS = { music: 'fa-music', dj: 'fa-microphone', ad: 'fa-bullhorn', news: 'fa-newspaper' };
    let currentSettings = {};
    let moduleSchemas = {};

    document.addEventListener('DOMContentLoaded', init);

    async function init() {
        await loadData();
        initSortable();
        setInterval(loadLogs, 3000);
        loadLogs();
    }

    function setTab(name) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        event.target.classList.add('active');
        document.getElementById('view-'+name).classList.add('active');
    }

    async function loadData() {
        try {
            const res = await fetch('/api/state');
            const data = await res.json();
            
            // 1. Palette
            const palette = document.getElementById('palette');
            palette.innerHTML = '';
            moduleSchemas = {};
            currentSettings = {};

            for (const [name, info] of Object.entries(data.modules)) {
                moduleSchemas[name] = info.schema;
                currentSettings[name] = info.current_config;
                if (info.is_system) continue;

                const div = document.createElement('div');
                div.className = 'palette-item';
                div.dataset.type = name;
                div.innerHTML = `<i class="fas ${ICONS[name]||'fa-cube'}"></i> ${name.toUpperCase()}`;
                palette.appendChild(div);
            }

            // 2. Schedule
            const list = document.getElementById('schedule-list');
            list.innerHTML = '';
            // Render directly, no index dependency issues
            for (const item of data.schedule) {
                renderScheduleItem(item);
            }

            // 3. Settings
            renderSettings();

        } catch (e) { console.error(e); }
    }

    function initSortable() {
        new Sortable(document.getElementById('palette'), {
            group: { name: 'shared', pull: 'clone', put: false },
            sort: false
        });

        new Sortable(document.getElementById('schedule-list'), {
            group: 'shared',
            animation: 150,
            handle: '.item-info',
            onAdd: (evt) => {
                const type = evt.item.dataset.type;
                evt.item.remove(); // Remove ghost
                
                // Create Default Data
                const data = { type: type };
                if(type === 'dj') data.mode = 'intro';
                
                // Insert real item at correct index
                renderScheduleItem(data, evt.newIndex);
            }
        });
    }

    // Fixed Rendering Function
    function renderScheduleItem(data, insertIndex = -1) {
        const list = document.getElementById('schedule-list');
        const uid = Math.random().toString(36).substr(2, 9);
        
        const el = document.createElement('div');
        el.className = `sched-item type-${data.type}`; // Must match CSS
        el.id = uid;
        el._data = data; // Attach data

        el.innerHTML = `
            <div class="item-info" onclick="openEditor('${uid}')">
                <div class="item-title"><i class="fas ${ICONS[data.type]||'fa-cube'}"></i> ${data.type.toUpperCase()}</div>
                <div class="item-desc">${formatDesc(data)}</div>
            </div>
            <div class="btn-del" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></div>
        `;

        if (insertIndex >= 0 && insertIndex < list.children.length) {
            list.insertBefore(el, list.children[insertIndex]);
        } else {
            list.appendChild(el);
        }
    }

    function formatDesc(d) {
        if (d.text) return `"${d.text}"`;
        if (d.mode) return `Режим: ${d.mode}`;
        if (d.source) return `RSS: ${d.source}`;
        return 'Нажмите для настройки';
    }

    // Modal Logic
    function openEditor(uid) {
        const el = document.getElementById(uid);
        const data = el._data;
        const content = document.getElementById('modalContent');
        document.getElementById('modalUid').value = uid;
        document.getElementById('modalTitle').innerText = data.type.toUpperCase();
        content.innerHTML = '';

        if (data.type === 'dj') {
            content.innerHTML = `
                <div class="form-group"><label>Режим</label>
                <select id="ed_mode" onchange="toggleDjText(this.value)">
                    <option value="intro" ${data.mode=='intro'?'selected':''}>Intro</option>
                    <option value="outro" ${data.mode=='outro'?'selected':''}>Outro</option>
                    <option value="custom" ${data.text?'selected':''}>Свой текст</option>
                </select></div>
                <div class="form-group" id="ed_text_group" style="display:${data.text?'block':'none'}">
                    <label>Текст</label><textarea id="ed_text" rows="3">${data.text||''}</textarea>
                </div>`;
        } else if (data.type === 'ad') {
            content.innerHTML = `<div class="form-group"><label>Текст рекламы</label><textarea id="ed_text" rows="4">${data.text||''}</textarea></div>`;
        } else if (data.type === 'news') {
             content.innerHTML = `<div class="form-group"><label>RSS</label><input id="ed_source" value="${data.source||''}"></div>`;
        } else {
            content.innerHTML = '<p style="color:#888">Нет настроек.</p>';
        }

        document.getElementById('editModal').style.display = 'flex';
        window.toggleDjText = (v) => document.getElementById('ed_text_group').style.display = (v==='custom'?'block':'none');
    }

    function applyEdit() {
        const uid = document.getElementById('modalUid').value;
        const el = document.getElementById(uid);
        const data = el._data; // Reference to object

        // Update Data Object
        if (document.getElementById('ed_mode')) {
            const mode = document.getElementById('ed_mode').value;
            if (mode === 'custom') {
                delete data.mode;
                data.text = document.getElementById('ed_text').value;
            } else {
                data.mode = mode;
                delete data.text;
            }
        } else if (document.getElementById('ed_text') && data.type === 'ad') {
            const txt = document.getElementById('ed_text').value.trim();
            if(txt) data.text = txt; else delete data.text;
        } else if (document.getElementById('ed_source')) {
             const src = document.getElementById('ed_source').value.trim();
             if(src) data.source = src; else delete data.source;
        }

        // Update UI
        el.querySelector('.item-desc').innerText = formatDesc(data);
        document.getElementById('editModal').style.display = 'none';
    }

    // Save Logic
    async function saveAllData() {
        const btn = document.querySelector('.fab-save');
        const oldTxt = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ...';

        // 1. Schedule from DOM order
        const schedule = [];
        document.querySelectorAll('.sched-item').forEach(el => schedule.push(el._data));

        // 2. Settings from Form
        const settings = {};
        document.querySelectorAll('.cfg-input').forEach(inp => {
            const m = inp.dataset.mod;
            const k = inp.dataset.key;
            if(!settings[m]) settings[m] = {};
            settings[m][k] = inp.value;
        });

        try {
            const res = await fetch('/api/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ schedule, settings })
            });
            const ans = await res.json();
            if(ans.status === 'ok') {
                btn.style.background = '#28a745';
                btn.innerHTML = '<i class="fas fa-check"></i> ОК';
                setTimeout(() => { btn.style.background = ''; btn.innerHTML = oldTxt; }, 1500);
            } else { alert(ans.message); btn.innerHTML = oldTxt; }
        } catch(e) { alert('Error: '+e); btn.innerHTML = oldTxt; }
    }

    function renderSettings() {
        const c = document.getElementById('settings-container');
        c.innerHTML = '';
        for (const [name, cfg] of Object.entries(currentSettings)) {
            if (!moduleSchemas[name] || Object.keys(moduleSchemas[name]).length === 0) continue;
            let h = `<div class="form-group"><h3 style="margin:0 0 10px; color:#666">${name.toUpperCase()}</h3>`;
            for(const [k, s] of Object.entries(moduleSchemas[name])) {
                const val = cfg[k] !== undefined ? cfg[k] : s.default;
                h += `<div style="margin-bottom:10px"><label>${s.label}</label>`;
                if(s.type === 'select') {
                    h += `<select class="cfg-input" data-mod="${name}" data-key="${k}">`;
                    s.options.forEach(o => h+=`<option value="${o}" ${o==val?'selected':''}>${o}</option>`);
                    h += `</select>`;
                } else if(s.type==='textarea') {
                    h += `<textarea class="cfg-input" data-mod="${name}" data-key="${k}" rows="3">${val}</textarea>`;
                } else {
                    h += `<input class="cfg-input" data-mod="${name}" data-key="${k}" value="${val}">`;
                }
                h += `</div>`;
            }
            c.innerHTML += h + `</div>`;
        }
    }

    async function loadLogs() {
        if(!document.getElementById('view-logs').classList.contains('active')) return;
        try {
            const r = await fetch('/api/logs');
            const d = await r.json();
            const el = document.getElementById('logs-output');
            el.innerText = d.logs;
            el.scrollTop = el.scrollHeight;
        } catch {}
    }
</script>
</body>
</html>
"""