/* ══════════════════════════════════════════════════════════
   Fashion AI Assistant — Main Application
   ══════════════════════════════════════════════════════════ */

const LS = {
  get(key) { try { return JSON.parse(localStorage.getItem(key)); } catch { return null; } },
  set(key, val) { localStorage.setItem(key, JSON.stringify(val)); },
  remove(key) { localStorage.removeItem(key); }
};

let state = {
  user: null,
  token: null,
  path: null,            // 'a' | 'b'
  selectedClothingTypes: [],
  selectedStyles: [],
  selectedScenes: [],
  conversationsA: [],    // Path A conversation history
  conversationsB: [],    // Path B conversation history
};

// ── Camera instances ──────────────────────────────────────────────
let cameraA1 = null, cameraA2 = null, cameraB = null;

// ── DOM refs ────────────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }

// ── Conversations helper (path-aware) ──────────────────────────────
function getConversations() {
  return state.path === 'b' ? state.conversationsB : state.conversationsA;
}
function setConversations(arr) {
  if (state.path === 'b') {
    state.conversationsB = arr;
    LS.set('fashion_conversations_b', arr);
  } else {
    state.conversationsA = arr;
    LS.set('fashion_conversations_a', arr);
  }
}

// ── Sidebar ────────────────────────────────────────────────────────
function showSidebar() {
  document.getElementById('sidebar').classList.remove('hidden');
  document.body.classList.add('has-sidebar');
}
function hideSidebar() {
  document.getElementById('sidebar').classList.add('hidden');
  document.body.classList.remove('has-sidebar');
}

// Sidebar toggle
document.getElementById('sidebar-toggle').addEventListener('click', () => {
  document.getElementById('sidebar').classList.toggle('collapsed');
});

// Sidebar clicks
document.getElementById('sidebar-home').addEventListener('click', () => showHome());
document.getElementById('sidebar-logout').addEventListener('click', async () => {
  await fetch('/api/user/logout', { method: 'POST' });
  state = { user: null, token: null, path: null, selectedClothingTypes: [], selectedStyles: [], selectedScenes: [], conversationsA: [], conversationsB: [] };
  ['fashion_token','fashion_user','fashion_conversations_a','fashion_conversations_b','fashion_clothing_types','fashion_styles','fashion_scenes','fashion_path'].forEach(k => LS.remove(k));
  showLogin();
});
document.querySelectorAll('.sidebar-item[data-nav]').forEach(item => {
  item.addEventListener('click', () => {
    const target = item.dataset.nav;
    if (target === 'path-a') { state.path = 'a'; LS.set('fashion_path','a'); showPathA(); }
    else if (target === 'path-b') { state.path = 'b'; LS.set('fashion_path','b'); showPathB(); }
    else if (target === 'result-a') {
      state.path = 'a'; LS.set('fashion_path','a');
      if (state.conversationsA.length > 0) { showSidebar(); showView('view-result'); renderChat(); }
    }
    else if (target === 'result-b') {
      state.path = 'b'; LS.set('fashion_path','b');
      if (state.conversationsB.length > 0) { showSidebar(); showView('view-result'); renderChat(); }
    }
  });
});

// ── View switching ──────────────────────────────────────────────────
function showView(id) {
  document.querySelectorAll('[id^="view-"]').forEach(el => el.classList.add('hidden'));
  const v = document.getElementById(id);
  if (v) v.classList.remove('hidden');
}

// ═══════════════════════════════════════════════════════════════════
//  INIT — check localStorage for saved session
// ═══════════════════════════════════════════════════════════════════

async function init() {
  // Restore from localStorage
  state.token = LS.get('fashion_token');
  state.user = LS.get('fashion_user');
  state.conversationsA = LS.get('fashion_conversations_a') || [];
  state.conversationsB = LS.get('fashion_conversations_b') || [];
  state.selectedClothingTypes = LS.get('fashion_clothing_types') || [];
  state.selectedStyles = LS.get('fashion_styles') || [];
  state.selectedScenes = LS.get('fashion_scenes') || [];
  state.path = LS.get('fashion_path');

  // Verify token is still valid
  if (state.token) {
    try {
      const res = await fetch('/api/user/me');
      if (res.ok) {
        state.user = await res.json();
        LS.set('fashion_user', state.user);
        showHome();
        return;
      }
    } catch {}
    // Token expired
    state.token = null;
    LS.remove('fashion_token');
  }

  showLogin();
}

// ═══════════════════════════════════════════════════════════════════
//  LOGIN / REGISTER
// ═══════════════════════════════════════════════════════════════════

function showLogin() {
  hideSidebar();
  showView('view-login');
  document.getElementById('login-form').classList.remove('hidden');
  document.getElementById('register-form').classList.add('hidden');
  document.querySelectorAll('#view-login .tab').forEach(t => t.classList.remove('active'));
  document.querySelector('#view-login .tab[data-tab="login-form"]').classList.add('active');
}

// Tab switching
document.querySelectorAll('#view-login .tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('#view-login .tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const target = tab.dataset.tab;
    document.getElementById('login-form').classList.toggle('hidden', target !== 'login-form');
    document.getElementById('register-form').classList.toggle('hidden', target !== 'register-form');
  });
});

// Login
$('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector('button');
  btn.disabled = true;
  const status = $('login-status');

  try {
    const res = await fetch('/api/user/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nickname: $('login-nickname').value.trim(),
        password: $('login-password').value,
      }),
    });
    const data = await res.json();
    if (res.ok && data.success) {
      state.token = 'session'; // cookie-based, just mark as logged in
      state.user = data.user;
      LS.set('fashion_token', state.token);
      LS.set('fashion_user', state.user);
      showHome();
    } else {
      status.textContent = data.detail || '登录失败';
      status.className = 'status-message show error';
    }
  } catch (err) {
    status.textContent = '网络错误';
    status.className = 'status-message show error';
  } finally {
    btn.disabled = false;
  }
});

// Register
$('register-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector('button');
  btn.disabled = true;
  const status = $('reg-status');

  const body = {
    nickname: $('reg-nickname').value.trim(),
    password: $('reg-password').value,
  };
  const h = parseFloat($('reg-height').value);
  const w = parseFloat($('reg-weight').value);
  if (h > 0) body.height = h;
  if (w > 0) body.weight = w;
  ['bust','waist','hip'].forEach(k => {
    const v = parseFloat($('reg-' + k).value);
    if (v > 0) body[k] = v;
  });

  try {
    const res = await fetch('/api/user/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (res.ok && data.success) {
      state.token = 'session';
      state.user = data.user;
      LS.set('fashion_token', state.token);
      LS.set('fashion_user', state.user);
      showHome();
    } else {
      status.textContent = data.detail || '注册失败';
      status.className = 'status-message show error';
    }
  } catch (err) {
    status.textContent = '网络错误';
    status.className = 'status-message show error';
  } finally {
    btn.disabled = false;
  }
});

// ═══════════════════════════════════════════════════════════════════
//  HOME
// ═══════════════════════════════════════════════════════════════════

function showHome() {
  showSidebar();
  showView('view-home');
  $('home-nickname').textContent = state.user?.nickname || '';
}

$('btn-logout').addEventListener('click', async () => {
  await fetch('/api/user/logout', { method: 'POST' });
  state = { user: null, token: null, path: null, selectedClothingTypes: [], selectedStyles: [], selectedScenes: [], conversationsA: [], conversationsB: [] };
  ['fashion_token','fashion_user','fashion_conversations_a','fashion_conversations_b','fashion_clothing_types','fashion_styles','fashion_scenes','fashion_path'].forEach(k => LS.remove(k));
  showLogin();
});

// Path selection
$('btn-path-a').addEventListener('click', () => { state.path = 'a'; LS.set('fashion_path','a'); showPathA(); });
$('btn-path-b').addEventListener('click', () => { state.path = 'b'; LS.set('fashion_path','b'); showPathB(); });

// ═══════════════════════════════════════════════════════════════════
//  PATH A — Upload + text → generate
// ═══════════════════════════════════════════════════════════════════

function showPathA() {
  showSidebar();
  showView('view-path-a');
  $('text-a').value = '';
  $('status-a').textContent = '';
  $('status-a').className = 'status-message';

  // Camera 1: user's own photo
  if (!cameraA1) { cameraA1 = new CameraInstance('a1'); cameraA1.start(); }
  else { cameraA1.start(); }

  // Camera 2: outfit reference
  if (!cameraA2) { cameraA2 = new CameraInstance('a2'); cameraA2.start(); }
  else { cameraA2.start(); }
}

$('btn-generate-a').addEventListener('click', async () => {
  const text = $('text-a').value.trim();
  const userUrlPromise = cameraA1?.getImageUrl();
  const refUrlPromise = cameraA2?.getImageUrl();

  const [userUrl, refUrl] = await Promise.all([
    userUrlPromise || null,
    refUrlPromise || null,
  ]);

  if (!text && !userUrl && !refUrl) {
    $('status-a').textContent = '请至少上传一张图片或输入文字描述';
    $('status-a').className = 'status-message show error';
    return;
  }

  await doGenerate({
    text,
    user_image_url: userUrl,
    reference_image_url: refUrl,
    style_tags: [],
    scene_tags: [],
  }, 'a');
});

// Skip buttons for Path A upload areas
$('btn-skip-a1').addEventListener('click', () => { if (cameraA1) cameraA1.clearImage(); });
$('btn-skip-a2').addEventListener('click', () => { if (cameraA2) cameraA2.clearImage(); });

// ═══════════════════════════════════════════════════════════════════
//  PATH B — single page: upload + 3 tag sections + 1 text box
// ═══════════════════════════════════════════════════════════════════

const CLOTHING_TYPE_TAGS = [
  'T恤', '衬衫', '卫衣', '针织衫', '西装外套', '风衣', '大衣',
  '连衣裙', '半身裙', '牛仔裤', '阔腿裤', '短裤', '背心',
  '吊带', '马甲', '羽绒服', '夹克', '运动套装',
  'Polo衫', '棉麻衫',
];

const STYLE_TAGS = [
  '简约', '街头', '复古', '日系', '韩系', '欧美', '法式', '学院',
  '运动', '工装', '高街', '暗黑', '朋克', '波西米亚', '田园',
  '极简', '新中式', 'Y2K', '哥特', '海岸风',
];

const SCENE_TAGS = [
  '通勤', '约会', '面试', '逛街', '旅行', '晚宴', '婚礼', '运动健身',
  '居家', '咖啡厅', '音乐节', '海滩度假', '毕业典礼', '日常出行',
  '户外徒步', '商务会议', '周末聚会', '校园', '夜店', '艺术展',
];

function buildTagGrid(containerId, tags, selectedSet, storageKey) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';
  tags.forEach(tag => {
    const el = document.createElement('span');
    el.className = 'tag' + (selectedSet.has(tag) ? ' tag-selected' : '');
    el.textContent = tag;
    el.addEventListener('click', () => {
      if (selectedSet.has(tag)) {
        selectedSet.delete(tag);
        el.classList.remove('tag-selected');
      } else {
        selectedSet.add(tag);
        el.classList.add('tag-selected');
      }
      if (storageKey) LS.set(storageKey, [...selectedSet]);
    });
    container.appendChild(el);
  });
}

function showPathB() {
  showSidebar();
  showView('view-path-b');
  $('text-b').value = '';
  $('status-b').textContent = '';
  $('status-b').className = 'status-message';

  // Camera
  if (!cameraB) { cameraB = new CameraInstance('b'); cameraB.start(); }
  else { cameraB.start(); }

  // Tag sections
  state.selectedClothingTypes = new Set(LS.get('fashion_clothing_types') || []);
  state.selectedStyles = new Set(LS.get('fashion_styles') || []);
  state.selectedScenes = new Set(LS.get('fashion_scenes') || []);

  buildTagGrid('clothing-type-tags', CLOTHING_TYPE_TAGS, state.selectedClothingTypes, 'fashion_clothing_types');
  buildTagGrid('style-tags', STYLE_TAGS, state.selectedStyles, 'fashion_styles');
  buildTagGrid('scene-tags', SCENE_TAGS, state.selectedScenes, 'fashion_scenes');
}

$('btn-skip-b').addEventListener('click', () => {
  if (cameraB) cameraB.clearImage();
});

$('btn-generate-b').addEventListener('click', async () => {
  const refUrl = cameraB ? await cameraB.getImageUrl() : null;
  const text = $('text-b')?.value?.trim() || '';

  await doGenerate({
    text: text || null,
    reference_image_url: refUrl || null,
    clothing_tags: [...state.selectedClothingTypes],
    style_tags: [...state.selectedStyles],
    scene_tags: [...state.selectedScenes],
  }, 'b');
});

// ═══════════════════════════════════════════════════════════════════
//  GENERATE — common logic for both paths
// ═══════════════════════════════════════════════════════════════════

async function doGenerate(body, pathKey) {
  const overlay = $('loading-overlay');
  overlay.classList.remove('hidden');

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || '生成失败');

    // Add to path-specific conversations
    const convs = getConversations();
    convs.push({
      id: data.conversation_id,
      role: 'user',
      text: body.text,
      image_url: body.reference_image_url,
      clothing_tags: body.clothing_tags,
      style_tags: body.style_tags,
      scene_tags: body.scene_tags,
      created_at: new Date().toISOString(),
    });
    convs.push({
      id: data.conversation_id + 1,
      role: 'assistant',
      image_url: data.image_url,
      original_url: data.original_url,
      text: null,
      created_at: new Date().toISOString(),
    });
    setConversations(convs);

    showResult(data.image_url, data.original_url);
  } catch (err) {
    const statusEl = pathKey === 'a' ? $('status-a') : $('status-b');
    statusEl.textContent = '生成失败: ' + err.message;
    statusEl.className = 'status-message show error';
  } finally {
    overlay.classList.add('hidden');
  }
}

// ═══════════════════════════════════════════════════════════════════
//  RESULT VIEW — display image + chat
// ═══════════════════════════════════════════════════════════════════

function showResult(imageUrl, originalUrl) {
  showSidebar();
  showView('view-result');
  $('result-img').src = imageUrl;
  $('result-img').dataset.originalUrl = originalUrl || imageUrl;
  $('chat-input').value = '';
  $('chat-status').textContent = '';
  $('chat-status').className = 'status-message';
  renderChat();
}

function renderChat() {
  const container = $('chat-messages');
  container.innerHTML = '';

  const convs = getConversations();
  convs.forEach(msg => {
    const div = document.createElement('div');
    div.className = 'chat-msg chat-' + msg.role;

    if (msg.image_url) {
      const img = document.createElement('img');
      img.src = msg.image_url;
      img.style.maxWidth = '200px';
      img.style.borderRadius = '8px';
      img.style.display = 'block';
      div.appendChild(img);
    }
    if (msg.text) {
      const p = document.createElement('p');
      p.textContent = msg.text;
      div.appendChild(p);
    }
    container.appendChild(div);
  });
  container.scrollTop = container.scrollHeight;
}

$('btn-chat-send').addEventListener('click', async () => {
  const text = $('chat-input').value.trim();
  if (!text) return;

  const overlay = $('loading-overlay');
  overlay.classList.remove('hidden');

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        clothing_tags: LS.get('fashion_clothing_types') || [],
        style_tags: LS.get('fashion_styles') || [],
        scene_tags: LS.get('fashion_scenes') || [],
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '生成失败');

    const convs = getConversations();
    convs.push({ role: 'user', text, created_at: new Date().toISOString() });
    convs.push({
      role: 'assistant',
      image_url: data.image_url,
      original_url: data.original_url,
      text: null,
      created_at: new Date().toISOString(),
    });
    setConversations(convs);

    $('result-img').src = data.image_url;
    $('result-img').dataset.originalUrl = data.original_url;
    $('chat-input').value = '';
    renderChat();
  } catch (err) {
    $('chat-status').textContent = '生成失败: ' + err.message;
    $('chat-status').className = 'status-message show error';
  } finally {
    overlay.classList.add('hidden');
  }
});

$('btn-save').addEventListener('click', () => {
  const url = $('result-img').dataset.originalUrl || $('result-img').src;
  if (!url) return;
  const a = document.createElement('a');
  a.href = url;
  a.download = 'outfit_' + Date.now() + '.png';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
});

$('btn-retry').addEventListener('click', () => {
  if (state.path === 'b') {
    showPathB();
    // Scroll to text input for convenience
    $('text-b')?.focus();
  } else {
    showPathA();
    $('text-a')?.focus();
  }
});

// ═══════════════════════════════════════════════════════════════════
//  BACK NAVIGATION
// ═══════════════════════════════════════════════════════════════════

document.querySelectorAll('.btn-back').forEach(btn => {
  btn.addEventListener('click', (e) => { e.preventDefault(); showHome(); });
});
document.querySelectorAll('.btn-back-home').forEach(btn => {
  btn.addEventListener('click', (e) => { e.preventDefault(); showHome(); });
});

// ═══════════════════════════════════════════════════════════════════
//  CAMERA INSTANCE — uses native camera via capture attribute, no getUserMedia
// ═══════════════════════════════════════════════════════════════════

class CameraInstance {
  constructor(suffix) {
    this.suffix = suffix;
    this.capturedBlob = null;
    this.uploadFileName = 'photo.jpg';
    this.imageUrl = null;
    this._bind(suffix);
  }

  _bind(s) {
    this.preview = document.getElementById('photo-preview-' + s);
    this.btnCapture = document.getElementById('btn-capture-' + s);
    this.btnRetake  = document.getElementById('btn-retake-' + s);
    this.btnFile    = document.getElementById('btn-file-' + s);
    this.captureInput = document.getElementById('capture-input-' + s);
    this.fileInput    = document.getElementById('file-input-' + s);

    // "拍照" → triggers native camera (mobile) or file picker (desktop)
    if (this.btnCapture) {
      this.btnCapture.addEventListener('click', () => {
        if (this.captureInput) this.captureInput.click();
      });
    }
    // "重拍" → clear and re-trigger capture
    if (this.btnRetake) {
      this.btnRetake.addEventListener('click', () => {
        this.clearImage();
        if (this.captureInput) this.captureInput.click();
      });
    }
    // "选择文件" → standard file picker
    if (this.btnFile) {
      this.btnFile.addEventListener('click', () => {
        if (this.fileInput) this.fileInput.click();
      });
    }
    // Capture input change
    if (this.captureInput) {
      this.captureInput.addEventListener('change', (e) => this._handleFile(e.target.files[0]));
    }
    // File input change
    if (this.fileInput) {
      this.fileInput.addEventListener('change', (e) => this._handleFile(e.target.files[0]));
    }
  }

  _handleFile(file) {
    if (!file) return;
    this.capturedBlob = file;
    this.uploadFileName = file.name;
    this.imageUrl = null;
    // Show preview
    if (this._previewUrl) URL.revokeObjectURL(this._previewUrl);
    this._previewUrl = URL.createObjectURL(file);
    this.preview.src = this._previewUrl;
    this.preview.style.display = 'block';
    this._showCaptured();
  }

  _showCaptured() {
    if (this.btnCapture) this.btnCapture.classList.add('hidden');
    if (this.btnRetake) this.btnRetake.classList.remove('hidden');
  }

  start() {
    // No-op: no live preview, camera opens on demand when user clicks "拍照"
  }

  showPreview() { this._showCaptured(); }

  retake() { this.clearImage(); }

  clearImage() {
    this.capturedBlob = null;
    this.imageUrl = null;
    if (this._previewUrl) { URL.revokeObjectURL(this._previewUrl); this._previewUrl = null; }
    this.preview.src = '';
    this.preview.style.display = 'none';
    if (this.btnCapture) this.btnCapture.classList.remove('hidden');
    if (this.btnRetake) this.btnRetake.classList.add('hidden');
  }

  async getImageUrl() {
    if (this.imageUrl) return this.imageUrl;
    if (this.capturedBlob) {
      const fd = new FormData();
      fd.append('file', this.capturedBlob, this.uploadFileName);
      const res = await fetch('/api/upload', { method: 'POST', body: fd });
      if (res.ok) {
        const data = await res.json();
        this.imageUrl = '/api/uploads/' + data.filename;
        return this.imageUrl;
      }
    }
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════════
//  START
// ═══════════════════════════════════════════════════════════════════

init();
