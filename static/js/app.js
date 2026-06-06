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
  selectedStyles: [],
  selectedScenes: [],
  conversations: [],
};

// ── Camera instances ──────────────────────────────────────────────
let cameraA = null, cameraB = null;

// ── DOM refs ────────────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }

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
  state.conversations = LS.get('fashion_conversations') || [];
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
    height: parseFloat($('reg-height').value),
    weight: parseFloat($('reg-weight').value),
  };
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
  showView('view-home');
  $('home-nickname').textContent = state.user?.nickname || '';
}

$('btn-logout').addEventListener('click', async () => {
  await fetch('/api/user/logout', { method: 'POST' });
  state = { user: null, token: null, path: null, selectedStyles: [], selectedScenes: [], conversations: [] };
  ['fashion_token','fashion_user','fashion_conversations','fashion_styles','fashion_scenes','fashion_path'].forEach(k => LS.remove(k));
  showLogin();
});

// Path selection
$('btn-path-a').addEventListener('click', () => { state.path = 'a'; LS.set('fashion_path','a'); showPathA(); });
$('btn-path-b').addEventListener('click', () => { state.path = 'b'; LS.set('fashion_path','b'); showPathBStyle(); });

// ═══════════════════════════════════════════════════════════════════
//  PATH A — Upload + text → generate
// ═══════════════════════════════════════════════════════════════════

function showPathA() {
  showView('view-path-a');
  $('text-a').value = '';
  $('status-a').textContent = '';
  $('status-a').className = 'status-message';

  if (!cameraA) {
    cameraA = new CameraInstance('a');
    cameraA.start();
  } else {
    cameraA.start();
  }
}

$('btn-generate-a').addEventListener('click', async () => {
  const text = $('text-a').value.trim();
  const refUrl = cameraA?.getImageUrl();

  if (!text && !refUrl) {
    $('status-a').textContent = '请上传图片或输入文字描述';
    $('status-a').className = 'status-message show error';
    return;
  }

  await doGenerate({ text, reference_image_url: refUrl, style_tags: [], scene_tags: [] }, 'a');
});

// ═══════════════════════════════════════════════════════════════════
//  PATH B — Style → Scene → Upload → generate
// ═══════════════════════════════════════════════════════════════════

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

function buildTagGrid(containerId, tags, selectedSet) {
  const container = document.getElementById(containerId);
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
      LS.set('fashion_styles', [...state.selectedStyles]);
      LS.set('fashion_scenes', [...state.selectedScenes]);
    });
    container.appendChild(el);
  });
}

function showPathBStyle() {
  showView('view-path-b-style');
  $('text-b-style').value = '';
  state.selectedStyles = new Set(LS.get('fashion_styles') || []);
  buildTagGrid('style-tags', STYLE_TAGS, state.selectedStyles);
}

function showPathBScene() {
  showView('view-path-b-scene');
  $('text-b-scene').value = '';
  state.selectedScenes = new Set(LS.get('fashion_scenes') || []);
  buildTagGrid('scene-tags', SCENE_TAGS, state.selectedScenes);
}

$('btn-next-scene').addEventListener('click', showPathBScene);

function showPathBUpload() {
  showView('view-path-b-upload');
  $('status-b').textContent = '';
  $('status-b').className = 'status-message';

  if (!cameraB) {
    cameraB = new CameraInstance('b');
    cameraB.start();
  } else {
    cameraB.start();
  }
}

$('btn-confirm-b').addEventListener('click', () => {
  // Save style and scene selections
  LS.set('fashion_styles', [...state.selectedStyles]);
  LS.set('fashion_scenes', [...state.selectedScenes]);
  showPathBUpload();
});

$('btn-generate-b').addEventListener('click', async () => {
  const refUrl = cameraB?.getImageUrl();
  const styleText = $('text-b-style').value.trim();
  const sceneText = $('text-b-scene').value.trim();
  const combinedText = [styleText, sceneText].filter(Boolean).join('；');

  await doGenerate({
    text: combinedText || null,
    reference_image_url: refUrl,
    style_tags: [...state.selectedStyles],
    scene_tags: [...state.selectedScenes],
  }, 'b');
});

$('btn-skip-b').addEventListener('click', () => {
  if (cameraB) cameraB.clearImage();
  $('btn-generate-b').click();
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

    // Add to local conversations
    state.conversations.push({
      id: data.conversation_id,
      role: 'user',
      text: body.text,
      image_url: body.reference_image_url,
      style_tags: body.style_tags,
      scene_tags: body.scene_tags,
      created_at: new Date().toISOString(),
    });
    state.conversations.push({
      id: data.conversation_id + 1,
      role: 'assistant',
      image_url: data.image_url,
      original_url: data.original_url,
      text: data.revised_prompt,
      created_at: new Date().toISOString(),
    });
    LS.set('fashion_conversations', state.conversations);

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

  state.conversations.forEach(msg => {
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
        style_tags: LS.get('fashion_styles') || [],
        scene_tags: LS.get('fashion_scenes') || [],
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '生成失败');

    state.conversations.push({ role: 'user', text, created_at: new Date().toISOString() });
    state.conversations.push({
      role: 'assistant',
      image_url: data.image_url,
      original_url: data.original_url,
      text: data.revised_prompt,
      created_at: new Date().toISOString(),
    });
    LS.set('fashion_conversations', state.conversations);

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

// ═══════════════════════════════════════════════════════════════════
//  BACK NAVIGATION
// ═══════════════════════════════════════════════════════════════════

document.querySelectorAll('.btn-back').forEach(btn => {
  btn.addEventListener('click', (e) => { e.preventDefault(); showHome(); });
});
document.querySelectorAll('.btn-back-scene').forEach(btn => {
  btn.addEventListener('click', (e) => { e.preventDefault(); showPathBStyle(); });
});
document.querySelectorAll('.btn-back-home').forEach(btn => {
  btn.addEventListener('click', (e) => { e.preventDefault(); showHome(); });
});

// ═══════════════════════════════════════════════════════════════════
//  CAMERA INSTANCE — wraps existing camera logic for view switching
// ═══════════════════════════════════════════════════════════════════

class CameraInstance {
  constructor(suffix) {
    this.suffix = suffix;
    this.stream = null;
    this.capturedBlob = null;
    this.uploadFileName = 'ref.jpg'; // preserve original filename for upload
    this.imageUrl = null;       // uploaded image URL
    this._previewUrl = null;    // blob URL for preview
    this._bind(suffix);
  }

  _bind(s) {
    this.video = document.getElementById('camera-feed-' + s);
    this.canvas = this._getCanvas('camera-container-' + s);
    this.preview = document.getElementById('photo-preview-' + s);

    const btnCapture = document.getElementById('btn-capture-' + s);
    const btnRetake  = document.getElementById('btn-retake-' + s);
    const btnFile    = document.getElementById('btn-file-' + s);
    const fileInput  = document.getElementById('file-input-' + s);

    if (btnCapture) btnCapture.addEventListener('click', () => this.capture());
    if (btnRetake)  btnRetake.addEventListener('click', () => this.retake());
    if (btnFile)    btnFile.addEventListener('click', () => fileInput.click());
    if (fileInput)  fileInput.addEventListener('change', (e) => {
      const f = e.target.files[0];
      if (f) { this.capturedBlob = f; this.uploadFileName = f.name; this.imageUrl = null; this._setPreview(URL.createObjectURL(f)); this.showPreview(); }
    });
  }

  _getCanvas(containerId) {
    const container = document.getElementById(containerId);
    let c = container.querySelector('canvas');
    if (!c) { c = document.createElement('canvas'); c.style.display = 'none'; container.appendChild(c); }
    return c;
  }

  _setPreview(url) {
    if (this._previewUrl) URL.revokeObjectURL(this._previewUrl);
    this._previewUrl = url;
    this.preview.src = url;
  }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
      this.video.srcObject = this.stream;
      this.video.style.display = 'block';
      this.preview.style.display = 'none';
      this.capturedBlob = null;
      this.imageUrl = null;
      document.getElementById('btn-retake-' + this.suffix)?.classList.add('hidden');
      const captureBtn = document.getElementById('btn-capture-' + this.suffix);
      if (captureBtn) { captureBtn.classList.remove('hidden'); captureBtn.textContent = '📸 拍照'; }
    } catch {
      // Camera unavailable — fine, user can use file upload
      this.video.style.display = 'none';
      const captureBtn = document.getElementById('btn-capture-' + this.suffix);
      if (captureBtn) captureBtn.classList.add('hidden');
    }
  }

  capture() {
    if (!this.stream) return;
    this.canvas.width = this.video.videoWidth || 1280;
    this.canvas.height = this.video.videoHeight || 720;
    const ctx = this.canvas.getContext('2d');
    ctx.drawImage(this.video, 0, 0);
    this.canvas.toBlob(blob => {
      if (!blob) return;
      this.capturedBlob = blob;
      this.uploadFileName = 'photo.jpg';
      this.imageUrl = null;
      this._setPreview(URL.createObjectURL(blob));
      this.showPreview();
    }, 'image/jpeg', 0.85);
  }

  showPreview() {
    this.video.style.display = 'none';
    this.preview.style.display = 'block';
    document.getElementById('btn-capture-' + this.suffix)?.classList.add('hidden');
    document.getElementById('btn-retake-' + this.suffix)?.classList.remove('hidden');
  }

  retake() {
    this.capturedBlob = null;
    this.imageUrl = null;
    this._setPreview('');
    this.preview.style.display = 'none';
    this.video.style.display = 'block';
    document.getElementById('btn-capture-' + this.suffix)?.classList.remove('hidden');
    document.getElementById('btn-retake-' + this.suffix)?.classList.add('hidden');
  }

  async getImageUrl() {
    // If already uploaded, return URL
    if (this.imageUrl) return this.imageUrl;

    // If there's a blob, upload it
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

  clearImage() {
    this.capturedBlob = null;
    this.imageUrl = null;
    this._setPreview('');
    this.preview.style.display = 'none';
    this.video.style.display = 'block';
  }
}

// ═══════════════════════════════════════════════════════════════════
//  START
// ═══════════════════════════════════════════════════════════════════

init();
