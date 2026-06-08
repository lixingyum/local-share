import os
import json
import uuid
import socket
import subprocess
import re
from datetime import datetime, timedelta
from flask import Flask, request, send_from_directory, jsonify, render_template_string, make_response
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
#客户端 JS 执行 const socket = io();，自动向 当前页面同源 的服务器发起 WebSocket 连接（默认路径 /socket.io/）。
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = 'shared_files'
META_FILE = 'metadata.json'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------- 跨平台 IP 检测（电脑 + Termux 通用）----------
def get_local_ips():
    ips = set()

    # 方法1：hostname -I（部分 Linux/Termux 可用）
    try:
        out = subprocess.check_output(['hostname', '-I'], text=True).strip()
        for ip in out.split():
            if ip:
                ips.add(ip)
    except:
        pass

    # 方法2：ip addr（需要 iproute2，Termux 可装）
    try:
        out = subprocess.check_output(['ip', 'addr'], text=True)
        for match in re.finditer(r'inet\s+([\d.]+)', out):
            ips.add(match.group(1))
    except:
        pass

    # 方法3：UDP 连接法（最可靠，获取出站 IP）
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        # 连接外部ip，但不发送数据
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        ips.add(ip)
        s.close()
    except:
        pass

    # 方法4：socket 标准方法（降级）
    if not ips:
        try:
            hostname = socket.gethostname()
            ips.update(socket.gethostbyname_ex(hostname)[2])
        except:
            pass

    ips.add('127.0.0.1')
    ips.add('::1')
    return ips

LOCAL_IPS = get_local_ips()

def is_admin(request):
    return request.remote_addr in LOCAL_IPS

# ---------- 工具函数 ----------
def load_meta():
    if not os.path.exists(META_FILE):
        return []
    try:
        with open(META_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_meta(meta):
    with open(META_FILE, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def generate_preview(text, max_len=50):
    preview_text = text.replace('\n', ' ').replace('\r', ' ')
    if len(preview_text) > max_len:
        return preview_text[:max_len] + '...'
    return preview_text

# ---------- HTML 模板（所有功能保持不变）----------
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>共享暂存板</title>
    <style>
        :root {
            --bg: #f0f2f5;
            --surface: #ffffff;
            --primary: #4f6ef7;
            --primary-hover: #3a56d4;
            --text: #1e293b;
            --text-secondary: #64748b;
            --border: #e2e8f0;
            --shadow: 0 4px 24px rgba(0,0,0,0.05);
            --radius: 16px;
            --radius-sm: 10px;
            --transition: 0.2s ease;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #f0f2f5, #e9edf3);
            min-height: 100vh; display: flex; justify-content: center;
            padding: 24px 16px; color: var(--text);
        }
        .container { width: 100%; max-width: 720px; display: flex; flex-direction: column; gap: 20px; }
        .header { text-align: center; padding-top: 8px; }
        .header h1 {
            font-weight: 600; font-size: 2rem;
            background: linear-gradient(135deg, #4f6ef7, #7c5cfc);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .badge { display: inline-block; font-size: 0.75rem; padding: 2px 10px; border-radius: 12px; margin-left: 8px; }
        .badge.admin { background: #e0e7ff; color: #4338ca; }
        .badge.client { background: #fef3c7; color: #b45309; }
        .card {
            background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow);
            padding: 24px; transition: box-shadow var(--transition);
        }
        .card:hover { box-shadow: 0 8px 30px rgba(0,0,0,0.08); }
        .compose-area { display: flex; align-items: flex-end; gap: 12px; margin-bottom: 12px; }
        .compose-box {
            flex: 1; border: 1px solid var(--border); border-radius: var(--radius-sm);
            padding: 14px 18px; font-size: 0.95rem; line-height: 1.6;
            outline: none; background: #f8fafc; transition: all var(--transition);
            max-height: 160px; overflow-y: auto; word-break: break-word;
        }
        .compose-box:focus { border-color: var(--primary); background: #fff; box-shadow: 0 0 0 3px rgba(79,110,247,0.1); }
        .compose-box:empty::before { content: attr(placeholder); color: #94a3b8; }
        .send-btn {
            background: var(--primary); border: none; color: white; padding: 14px 24px;
            border-radius: var(--radius-sm); font-size: 1rem; font-weight: 500; cursor: pointer;
            white-space: nowrap; transition: all var(--transition);
            display: flex; align-items: center; gap: 6px;
            box-shadow: 0 2px 8px rgba(79,110,247,0.3);
        }
        .send-btn:hover { background: var(--primary-hover); box-shadow: 0 4px 12px rgba(79,110,247,0.4); transform: translateY(-1px); }
        .send-btn:active { transform: scale(0.97); }
        .toolbar {
            display: flex; align-items: center; justify-content: space-between;
            font-size: 0.85rem; color: var(--text-secondary);
        }
        .file-upload-btn {
            background: none; border: 1px solid var(--border); padding: 8px 16px;
            border-radius: 8px; cursor: pointer; background: #f8fafc;
            transition: all var(--transition); color: var(--text); font-weight: 500;
            display: flex; align-items: center; gap: 6px;
        }
        .file-upload-btn:hover { background: #f1f5f9; border-color: #cbd5e1; }
        .filter-bar { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
        .filter-btn {
            background: #f1f5f9; border: 1px solid var(--border);
            padding: 6px 14px; border-radius: 8px; cursor: pointer;
            font-size: 0.85rem; font-weight: 500; color: var(--text); transition: all var(--transition);
        }
        .filter-btn.active { background: var(--primary); color: white; border-color: var(--primary); }
        .view-all-btn { background: #fef3c7; border: 1px solid #fcd34d; color: #b45309; }
        .view-all-btn.active { background: #b45309; color: white; border-color: #b45309; }
        .status-toast {
            position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
            padding: 12px 24px; border-radius: 30px; font-weight: 500; font-size: 0.9rem;
            z-index: 1000; box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px); opacity: 0; transition: opacity 0.3s; pointer-events: none;
        }
        .status-toast.show { opacity: 1; }
        .status-toast.success { background: rgba(34,197,94,0.9); color: white; }
        .status-toast.error { background: rgba(239,68,68,0.9); color: white; }
        .item-list { display: flex; flex-direction: column; gap: 4px; }
        .item {
            display: flex; align-items: center; padding: 14px 0;
            border-bottom: 1px solid #f1f5f9; gap: 16px;
            animation: fadeInUp 0.25s ease;
        }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .item:last-child { border-bottom: none; }
        .item img { width: 48px; height: 48px; border-radius: 10px; object-fit: cover; background: #f1f5f9; }
        .item .info { flex: 1; min-width: 0; }
        .item .preview { color: var(--text-secondary); font-size: 0.9rem; white-space: pre-wrap; word-break: break-word; max-height: 3.6em; overflow: hidden; line-height: 1.4; }
        .item .meta { font-size: 0.78rem; color: #94a3b8; margin-top: 4px; }
        .item-actions { display: flex; gap: 8px; flex-wrap: wrap; }
        .action-btn {
            background: #f1f5f9; border: none; padding: 6px 14px;
            border-radius: 8px; cursor: pointer; font-size: 0.85rem; font-weight: 500;
            color: var(--primary); transition: all var(--transition); white-space: nowrap;
        }
        .action-btn:hover { background: #e0e7ff; transform: translateY(-1px); }
        .action-btn.resend { color: #b45309; background: #fef3c7; }
        .action-btn.resend:hover { background: #fde68a; }
        .empty-state { text-align: center; padding: 40px 0; color: #94a3b8; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>📋 共享暂存板 <span id="role-badge" class="badge"></span></h1>
    </div>

    <div class="card">
        <div class="compose-area">
            <div id="compose-box" class="compose-box" contenteditable="true"
                 placeholder="打字输入，或粘贴文本/图片…  Ctrl+Enter 发送"></div>
            <button id="send-btn" class="send-btn">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <path d="M22 2L11 13"></path>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
                发送
            </button>
        </div>
        <div class="toolbar">
            <span>Shift+Enter 换行 · 粘贴文本自动发送</span>
            <input type="file" id="file-input" multiple style="display:none" accept="*/*">
            <button id="file-upload-btn" class="file-upload-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"></path>
                </svg>
                选择文件
            </button>
        </div>
    </div>

    <div id="status-toast" class="status-toast"></div>

    <div class="card">
        <div class="content-header">
            <h2>🗂️ 共享内容</h2>
            <span style="color:var(--text-secondary);font-size:0.85rem;">实时同步</span>
        </div>
        <div class="filter-bar">
            <button class="filter-btn active" data-filter="all">全部</button>
            <button class="filter-btn" data-filter="text">📝 文本</button>
            <button class="filter-btn" data-filter="image">🖼️ 图片</button>
            <button class="filter-btn" data-filter="file">📁 文件</button>
            <button id="view-all-btn" class="filter-btn view-all-btn" style="display:none;">📂 显示全部文件</button>
        </div>
        <div id="item-list" class="item-list">
            <div class="empty-state">暂无内容，粘贴或输入文字吧</div>
        </div>
    </div>
</div>

<script src="/static/socket.io.min.js"></script>
<script>
    const socket = io();
    const composeBox = document.getElementById('compose-box');
    const sendBtn = document.getElementById('send-btn');
    const fileInput = document.getElementById('file-input');
    const listDiv = document.getElementById('item-list');
    const toast = document.getElementById('status-toast');
    const roleBadge = document.getElementById('role-badge');
    const viewAllBtn = document.getElementById('view-all-btn');
    const filterBtns = document.querySelectorAll('.filter-btn:not(.view-all-btn)');

    let isAdmin = false;
    let showingAll = false;
    let currentFilter = 'all';
    let allServerItems = [];

    function showToast(text, isError = false) {
        toast.textContent = text;
        toast.className = `status-toast show ${isError ? 'error' : 'success'}`;
        setTimeout(() => { toast.className = 'status-toast'; }, 2800);
    }

    function setAdminMode(admin) {
        isAdmin = admin;
        roleBadge.textContent = admin ? '管理端' : '共享端';
        roleBadge.className = `badge ${admin ? 'admin' : 'client'}`;
        viewAllBtn.style.display = admin ? 'inline-block' : 'none';
    }

    function getVisibleItems() {
        let items = allServerItems;
        if (!showingAll) {
            const cutoff = new Date(Date.now() - 10 * 60 * 1000);
            items = items.filter(item => new Date(item.timestamp) >= cutoff);
        }
        if (currentFilter !== 'all') {
            items = items.filter(item => item.type === currentFilter);
        }
        return items;
    }

    function renderList() {
        const filtered = getVisibleItems();
        if (filtered.length === 0) {
            listDiv.innerHTML = `<div class="empty-state">暂无内容</div>`;
            return;
        }
        listDiv.innerHTML = filtered.map(createItemHTML).join('');
    }

    viewAllBtn.addEventListener('click', () => {
        if (!isAdmin) return;
        showingAll = !showingAll;
        viewAllBtn.textContent = showingAll ? '🕒 仅显示10分钟' : '📂 显示全部文件';
        viewAllBtn.classList.toggle('active', showingAll);
        if (showingAll) {
            socket.emit('request_all_items');
        } else {
            socket.emit('request_list');
        }
    });

    function sendTextFromBox() {
        const text = composeBox.innerText.trim();
        if (!text) { showToast('请输入内容', true); return; }
        uploadText(text);
        composeBox.innerHTML = '';
    }
    sendBtn.addEventListener('click', sendTextFromBox);
    composeBox.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            sendTextFromBox();
        }
    });

    composeBox.addEventListener('paste', async (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;
        let hasImage = false, hasText = false;
        for (const item of items) {
            if (item.kind === 'file' && item.type.startsWith('image/')) hasImage = true;
            if (item.kind === 'string' && item.type === 'text/plain') hasText = true;
        }
        if (hasImage) {
            e.preventDefault();
            for (const item of items) {
                if (item.kind === 'file' && item.type.startsWith('image/')) {
                    const blob = item.getAsFile();
                    await uploadFile(blob, `clipboard_image_${Date.now()}.png`);
                } else if (item.kind === 'string') {
                    const text = await new Promise(resolve => item.getAsString(resolve));
                    if (text.trim()) await uploadText(text);
                }
            }
            composeBox.innerHTML = '';
            return;
        }
        if (hasText && !hasImage && composeBox.innerText.trim() === '') {
            e.preventDefault();
            const text = await new Promise(resolve => {
                for (const item of items) if (item.kind === 'string') { item.getAsString(resolve); break; }
            });
            if (text && text.trim()) {
                await uploadText(text);
                composeBox.innerHTML = '';
                showToast('📋 文本已粘贴并发送');
            }
        }
    });

    fileInput.addEventListener('change', () => {
        for (const file of fileInput.files) uploadFile(file, file.name);
        fileInput.value = '';
    });
    document.getElementById('file-upload-btn').addEventListener('click', () => fileInput.click());

    async function uploadText(text) {
        const form = new FormData(); form.append('text', text);
        try {
            const resp = await fetch('/upload/text', { method: 'POST', body: form });
            if (!resp.ok) throw new Error(await resp.text());
            showToast('✅ 已发送');
        } catch (e) { showToast('❌ 发送失败: ' + e.message, true); }
    }

    async function uploadFile(fileOrBlob, fileName) {
        const form = new FormData(); form.append('file', fileOrBlob, fileName);
        try {
            const resp = await fetch('/upload/file', { method: 'POST', body: form });
            if (!resp.ok) throw new Error('上传失败');
            showToast('✅ 文件已上传');
        } catch (e) { showToast('❌ 上传失败: ' + e.message, true); }
    }

    async function resendItem(itemId) {
        try {
            const resp = await fetch(`/reupload/${itemId}`, { method: 'POST' });
            if (!resp.ok) throw new Error(await resp.text());
            showToast('🔄 已重新发送');
        } catch (e) { showToast('❌ 重新发送失败: ' + e.message, true); }
    }

    socket.on('init_list', (data) => {
        allServerItems = data.items || [];
        setAdminMode(data.is_admin);
        showingAll = false;
        viewAllBtn.textContent = '📂 显示全部文件';
        viewAllBtn.classList.remove('active');
        renderList();
    });

    socket.on('all_items', (data) => {
        if (showingAll) {
            allServerItems = data.items || [];
            renderList();
        }
    });

    socket.on('new_item', (item) => {
        allServerItems.unshift(item);
        if (!showingAll && new Date(item.timestamp) < new Date(Date.now() - 10 * 60 * 1000)) return;
        renderList();
    });

    socket.on('connect', () => {
        socket.emit('request_list');
    });

    socket.on('disconnect', () => {
        showToast('⚠️ 连接断开，重连中…', true);
    });

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            renderList();
        });
    });

    function createItemHTML(item) {
        const sizeStr = formatSize(item.size);
        const timeStr = new Date(item.timestamp).toLocaleString();
        const resendBtn = (isAdmin && showingAll) ? `<button class="action-btn resend" onclick="resendItem('${item.id}')">🔄 重新发送</button>` : '';
        if (item.type === 'text') {
            const preview = item.preview ? escapeHtml(item.preview) : '（无内容）';
            return `<div class="item" data-id="${item.id}">
                <div class="info">
                    <div class="preview">${preview}</div>
                    <div class="meta">${sizeStr} · ${timeStr}</div>
                </div>
                <div class="item-actions">
                    <button class="action-btn" onclick="copyTextContent('${item.filename}')">📋 复制</button>
                    ${resendBtn}
                </div>
            </div>`;
        } else if (item.type === 'image') {
            return `<div class="item" data-id="${item.id}">
                <img src="/file/${item.filename}" alt="${escapeHtml(item.name)}" loading="lazy">
                <div class="info">
                    <div class="name">🖼️ ${escapeHtml(item.name)}</div>
                    <div class="meta">${sizeStr} · ${timeStr}</div>
                </div>
                <div class="item-actions">
                    <button class="action-btn" onclick="downloadFile('${item.filename}')">⬇️ 下载</button>
                    <button class="action-btn" onclick="copyImageToClipboard('${item.filename}')">📋 复制</button>
                    ${resendBtn}
                </div>
            </div>`;
        } else {
            return `<div class="item" data-id="${item.id}">
                <div class="info">
                    <div class="name">📁 ${escapeHtml(item.name)}</div>
                    <div class="meta">${sizeStr} · ${timeStr}</div>
                </div>
                <div class="item-actions">
                    <button class="action-btn" onclick="downloadFile('${item.filename}')">⬇️ 下载</button>
                    ${resendBtn}
                </div>
            </div>`;
        }
    }

    function downloadFile(filename) {
        const link = document.createElement('a');
        link.href = '/file/' + filename;
        link.download = filename.split('-').pop() || filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    async function copyTextContent(filename) {
        try {
            const resp = await fetch('/text/' + filename);
            if (!resp.ok) throw new Error('读取失败');
            const text = await resp.text();
            copyToClipboard(text);
            showToast('✅ 已复制');
        } catch (e) { showToast('❌ 复制失败', true); }
    }

    async function copyImageToClipboard(filename) {
        try {
            const resp = await fetch('/file/' + filename);
            const blob = await resp.blob();
            if (navigator.clipboard?.write) {
                await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
                showToast('✅ 图片已复制');
            } else throw new Error('不支持');
        } catch (e) { showToast('请下载后手动复制图片', true); }
    }

    function copyToClipboard(text) {
        if (navigator.clipboard?.writeText) {
            navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
        } else fallbackCopy(text);
    }

    function fallbackCopy(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.cssText = 'position:fixed;opacity:0;';
        document.body.appendChild(textarea);
        textarea.select();
        try { document.execCommand('copy'); } catch(e) {}
        document.body.removeChild(textarea);
    }

    function formatSize(bytes) {
        if (!bytes) return '0 B';
        const k = 1024, sizes = ['B','KB','MB','GB'];
        const i = Math.floor(Math.log(bytes)/Math.log(k));
        return parseFloat((bytes/Math.pow(k,i)).toFixed(1)) + ' ' + sizes[i];
    }

    function escapeHtml(str) {
        return String(str).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[m]);
    }
</script>
</body>
</html>
'''

# ---------- 后端路由 ----------
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('request_list')
def handle_request_list():
    admin = is_admin(request)
    meta = load_meta()
    cutoff = datetime.now() - timedelta(minutes=10)
    meta = [item for item in meta if datetime.fromisoformat(item['timestamp']) >= cutoff]
    emit('init_list', {'items': list(reversed(meta)), 'is_admin': admin})

@socketio.on('request_all_items')
def handle_request_all():
    if not is_admin(request):
        return
    emit('all_items', {'items': list(reversed(load_meta()))})

@app.route('/upload/text', methods=['POST'])
def upload_text():
    text = request.form.get('text', '')
    if not text.strip():
        return '内容为空', 400
    meta = load_meta()
    item_id = str(uuid.uuid4())
    filename = f"{item_id}.txt"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
    except Exception as e:
        return f'保存失败: {str(e)}', 500

    preview = generate_preview(text)
    new_item = {
        'id': item_id,
        'type': 'text',
        'name': '文本片段',
        'filename': filename,
        'preview': preview,
        'timestamp': datetime.now().isoformat(),
        'size': len(text.encode('utf-8'))
    }
    meta.append(new_item)
    save_meta(meta)
    socketio.emit('new_item', new_item)
    return jsonify({'status': 'ok'})

@app.route('/upload/file', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if not file:
        return '未收到文件', 400
    original_name = file.filename or '未命名'
    safe_name = secure_filename(original_name) if original_name != '未命名' else 'unnamed'
    item_id = str(uuid.uuid4())
    ext = os.path.splitext(safe_name)[1]
    filename = f"{item_id}{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    try:
        file.save(filepath)
    except Exception as e:
        return f'文件保存失败: {str(e)}', 500
    mime = file.content_type or ''
    file_type = 'image' if mime.startswith('image/') else 'file'

    new_item = {
        'id': item_id,
        'type': file_type,
        'name': safe_name,
        'filename': filename,
        'timestamp': datetime.now().isoformat(),
        'size': os.path.getsize(filepath)
    }
    meta = load_meta()
    meta.append(new_item)
    save_meta(meta)
    socketio.emit('new_item', new_item)
    return jsonify({'status': 'ok'})

@app.route('/reupload/<item_id>', methods=['POST'])
def reupload(item_id):
    meta = load_meta()
    item = next((it for it in meta if it['id'] == item_id), None)
    if not item:
        return '文件不存在', 404
    item['timestamp'] = datetime.now().isoformat()
    save_meta(meta)
    socketio.emit('new_item', item)
    return jsonify({'status': 'ok'})

@app.route('/list')
def list_items():
    admin = is_admin(request)
    meta = load_meta()
    if not admin:
        cutoff = datetime.now() - timedelta(minutes=10)
        meta = [item for item in meta if datetime.fromisoformat(item['timestamp']) >= cutoff]
    return jsonify(list(reversed(meta)))

@app.route('/file/<filename>')
def download_file(filename):
    safe_name = secure_filename(filename)
    meta = load_meta()
    original_name = safe_name
    for item in meta:
        if item.get('filename') == safe_name:
            original_name = item.get('name', safe_name)
            break
    return send_from_directory(UPLOAD_FOLDER, safe_name, as_attachment=True, download_name=original_name)

@app.route('/text/<filename>')
def get_text(filename):
    safe_name = secure_filename(filename)
    if not safe_name.endswith('.txt'):
        return 'Not a text file', 400
    return send_from_directory(UPLOAD_FOLDER, safe_name, mimetype='text/plain; charset=utf-8')

if __name__ == '__main__':
    print(f"本机管理 IP 集合: {LOCAL_IPS}")
    print("启动服务...")
    socketio.run(app, host='0.0.0.0', port=4001, debug=True, allow_unsafe_werkzeug=True)