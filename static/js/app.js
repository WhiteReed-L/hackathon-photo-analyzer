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
  sessions: [],          // all conversation sessions
  currentSessionId: null, // active session id
};

// ── Camera instances ──────────────────────────────────────────────
let cameraA1 = null, cameraA2 = null, cameraB = null;

// ── DOM refs ────────────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }

// ═══════════════════════════════════════════════════════════════════
//  SESSION MANAGEMENT
// ═══════════════════════════════════════════════════════════════════

const PATH_LABELS = { a: '试试这件', b: '镜中幻象' };

function createSession(path) {
  const session = {
    id: 'sess_' + Date.now(),
    path: path,
    label: PATH_LABELS[path] || path,
    messages: [],
    createdAt: new Date().toISOString(),
    preview: '',
  };
  state.sessions.push(session);
  state.currentSessionId = session.id;
  saveSessions();
  renderSidebarHistory();
  return session;
}

function getCurrentSession() {
  return state.sessions.find(s => s.id === state.currentSessionId) || null;
}

function getSessionMessages() {
  const session = getCurrentSession();
  return session ? session.messages : [];
}

function pushMessage(msg) {
  const session = getCurrentSession();
  if (!session) return;
  session.messages.push(msg);
  if (!session.preview && msg.role === 'user' && msg.text) {
    session.preview = msg.text.slice(0, 30);
  }
  saveSessions();
  renderSidebarHistory();
}

function saveSessions() {
  LS.set('fashion_sessions', state.sessions);
  LS.set('fashion_current_session', state.currentSessionId);
}

function loadSessions() {
  state.sessions = LS.get('fashion_sessions') || [];
  state.currentSessionId = LS.get('fashion_current_session') || null;

  // Migrate old format
  const oldA = LS.get('fashion_conversations_a');
  const oldB = LS.get('fashion_conversations_b');
  if (oldA && oldA.length > 0) {
    state.sessions.push({
      id: 'sess_migrated_a',
      path: 'a',
      label: PATH_LABELS.a,
      messages: oldA,
      createdAt: oldA[0]?.created_at || new Date().toISOString(),
      preview: oldA.find(m => m.role === 'user' && m.text)?.text?.slice(0, 30) || '',
    });
    LS.remove('fashion_conversations_a');
  }
  if (oldB && oldB.length > 0) {
    state.sessions.push({
      id: 'sess_migrated_b',
      path: 'b',
      label: PATH_LABELS.b,
      messages: oldB,
      createdAt: oldB[0]?.created_at || new Date().toISOString(),
      preview: oldB.find(m => m.role === 'user' && m.text)?.text?.slice(0, 30) || '',
    });
    LS.remove('fashion_conversations_b');
  }
  if (oldA || oldB) saveSessions();
}

// ═══════════════════════════════════════════════════════════════════
//  SIDEBAR
// ═══════════════════════════════════════════════════════════════════

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

// Sidebar static clicks
document.getElementById('sidebar-home').addEventListener('click', () => showHome());
document.getElementById('sidebar-logout').addEventListener('click', async () => {
  await fetch('/api/user/logout', { method: 'POST' });
  state = { user: null, token: null, path: null, selectedClothingTypes: [], selectedStyles: [], selectedScenes: [], sessions: [], currentSessionId: null };
  ['fashion_token','fashion_user','fashion_sessions','fashion_current_session','fashion_clothing_types','fashion_styles','fashion_scenes','fashion_path'].forEach(k => LS.remove(k));
  showLogin();
});

document.querySelectorAll('.sidebar-item[data-nav]').forEach(item => {
  item.addEventListener('click', () => {
    const target = item.dataset.nav;
    if (target === 'path-a') { state.path = 'a'; LS.set('fashion_path','a'); showPathA(); }
    else if (target === 'path-b') { state.path = 'b'; LS.set('fashion_path','b'); showPathB(); }
  });
});

function renderSidebarHistory() {
  const container = $('sidebar-history');
  if (!container) return;
  container.innerHTML = '';

  const sessionsA = state.sessions.filter(s => s.path === 'a' && s.messages.length > 0);
  const sessionsB = state.sessions.filter(s => s.path === 'b' && s.messages.length > 0);

  if (sessionsA.length > 0) {
    const titleA = document.createElement('div');
    titleA.className = 'history-group-title';
    titleA.textContent = PATH_LABELS.a;
    container.appendChild(titleA);
    sessionsA.slice().reverse().forEach(s => container.appendChild(makeHistoryItem(s)));
  }

  if (sessionsB.length > 0) {
    const titleB = document.createElement('div');
    titleB.className = 'history-group-title';
    titleB.textContent = PATH_LABELS.b;
    container.appendChild(titleB);
    sessionsB.slice().reverse().forEach(s => container.appendChild(makeHistoryItem(s)));
  }
}

function makeHistoryItem(session) {
  const item = document.createElement('a');
  item.className = 'sidebar-item history-item' + (session.id === state.currentSessionId ? ' active' : '');

  const label = document.createElement('span');
  label.className = 'history-item-label';
  label.textContent = session.preview || '新对话';
  item.title = session.preview || '新对话';

  const delBtn = document.createElement('span');
  delBtn.className = 'history-item-delete';
  delBtn.textContent = '×';
  delBtn.title = '删除';
  delBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    state.sessions = state.sessions.filter(s => s.id !== session.id);
    if (state.currentSessionId === session.id) {
      state.currentSessionId = null;
    }
    saveSessions();
    renderSidebarHistory();
  });

  item.appendChild(label);
  item.appendChild(delBtn);

  item.addEventListener('click', () => {
    state.currentSessionId = session.id;
    state.path = session.path;
    LS.set('fashion_path', session.path);
    saveSessions();

    const msgs = session.messages;
    const lastAssistant = [...msgs].reverse().find(m => m.role === 'assistant' && m.image_url);
    if (lastAssistant) {
      showResult(lastAssistant.image_url, lastAssistant.original_url || lastAssistant.image_url);
    } else {
      showSidebar();
      showView('view-result');
      renderChat();
    }
    renderSidebarHistory();
  });
  return item;
}

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
  state.token = LS.get('fashion_token');
  state.user = LS.get('fashion_user');
  loadSessions();
  state.selectedClothingTypes = LS.get('fashion_clothing_types') || [];
  state.selectedStyles = LS.get('fashion_styles') || [];
  state.selectedScenes = LS.get('fashion_scenes') || [];
  state.path = LS.get('fashion_path');

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
      state.token = 'session';
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
  renderSidebarHistory();
}

$('btn-logout').addEventListener('click', async () => {
  await fetch('/api/user/logout', { method: 'POST' });
  state = { user: null, token: null, path: null, selectedClothingTypes: [], selectedStyles: [], selectedScenes: [], sessions: [], currentSessionId: null };
  ['fashion_token','fashion_user','fashion_sessions','fashion_current_session','fashion_clothing_types','fashion_styles','fashion_scenes','fashion_path'].forEach(k => LS.remove(k));
  showLogin();
});

// Path selection
$('btn-path-a').addEventListener('click', () => { state.path = 'a'; LS.set('fashion_path','a'); showPathA(); });
$('btn-path-b').addEventListener('click', () => { state.path = 'b'; LS.set('fashion_path','b'); showPathB(); });

// ═══════════════════════════════════════════════════════════════════
//  PATH A — Upload + text → generate
// ═══════════════════════════════════════════════════════════════════

function showPathA() {
  createSession('a');
  showSidebar();
  showView('view-path-a');
  $('text-a').value = '';
  $('status-a').textContent = '';
  $('status-a').className = 'status-message';

  if (!cameraA1) { cameraA1 = new CameraInstance('a1'); cameraA1.start(); }
  else { cameraA1.clearImage(); cameraA1.start(); }

  if (!cameraA2) { cameraA2 = new CameraInstance('a2'); cameraA2.start(); }
  else { cameraA2.clearImage(); cameraA2.start(); }
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

$('btn-skip-a1').addEventListener('click', () => { if (cameraA1) cameraA1.clearImage(); });
$('btn-skip-a2').addEventListener('click', () => { if (cameraA2) cameraA2.clearImage(); });

// ═══════════════════════════════════════════════════════════════════
//  PATH B — single page: upload + tag sections + text box
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
  createSession('b');
  showSidebar();
  showView('view-path-b');
  $('text-b').value = '';
  $('status-b').textContent = '';
  $('status-b').className = 'status-message';

  if (!cameraB) { cameraB = new CameraInstance('b'); cameraB.start(); }
  else { cameraB.clearImage(); cameraB.start(); }

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

    pushMessage({
      id: data.conversation_id,
      role: 'user',
      text: body.text,
      image_url: body.reference_image_url,
      clothing_tags: body.clothing_tags,
      style_tags: body.style_tags,
      scene_tags: body.scene_tags,
      created_at: new Date().toISOString(),
    });
    pushMessage({
      id: data.conversation_id + 1,
      role: 'assistant',
      image_url: data.image_url,
      original_url: data.original_url,
      text: data.description || null,
      created_at: new Date().toISOString(),
    });

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
  renderSidebarHistory();
}

function renderChat() {
  const container = $('chat-messages');
  container.innerHTML = '';

  const msgs = getSessionMessages();
  msgs.forEach(msg => {
    const div = document.createElement('div');
    div.className = 'chat-msg chat-' + msg.role;

    if (msg.image_url) {
      const img = document.createElement('img');
      img.src = msg.image_url;
      img.style.maxWidth = '200px';
      img.style.borderRadius = '0';
      img.style.display = 'block';
      div.appendChild(img);

      const saveBtn = document.createElement('a');
      saveBtn.href = msg.original_url || msg.image_url;
      saveBtn.download = 'outfit_' + Date.now() + '.png';
      saveBtn.className = 'btn btn-outline';
      saveBtn.textContent = '保存';
      saveBtn.style.cssText = 'display:inline-block;margin-top:6px;padding:4px 12px;font-size:12px;';
      div.appendChild(saveBtn);
    }
    if (msg.text) {
      const p = document.createElement('p');
      p.style.whiteSpace = 'pre-line';
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
  $('chat-input').value = '';

  // Show user message immediately
  pushMessage({ role: 'user', text, created_at: new Date().toISOString() });
  renderChat();

  try {
    // Step 1: Ask dialogue model to classify intent
    const history = getSessionMessages().slice(-6).map(m => ({ role: m.role, text: m.text || '' }));
    const chatRes = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        history,
        path: state.path || null,
        clothing_tags: LS.get('fashion_clothing_types') || [],
        style_tags: LS.get('fashion_styles') || [],
        scene_tags: LS.get('fashion_scenes') || [],
      }),
    });
    const chatData = await chatRes.json();
    if (!chatRes.ok) throw new Error(chatData.detail || '对话失败');

    if (chatData.action === 'generate') {
      // Show confirmation text from dialogue model
      if (chatData.text) {
        pushMessage({ role: 'assistant', text: chatData.text, created_at: new Date().toISOString() });
        renderChat();
      }

      // Step 2: Trigger image generation using enriched prompt
      const lastImage = $('result-img').dataset.originalUrl || null;
      const genText = chatData.prompt || text;
      const genRes = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: genText,
          user_image_url: lastImage,
          clothing_tags: LS.get('fashion_clothing_types') || [],
          style_tags: LS.get('fashion_styles') || [],
          scene_tags: LS.get('fashion_scenes') || [],
        }),
      });
      const genData = await genRes.json();
      if (!genRes.ok) throw new Error(genData.detail || '生成失败');

      pushMessage({
        role: 'assistant',
        image_url: genData.image_url,
        original_url: genData.original_url,
        text: genData.description || null,
        created_at: new Date().toISOString(),
      });

      $('result-img').src = genData.image_url;
      $('result-img').dataset.originalUrl = genData.original_url;
    } else {
      // Pure reply — no image generation
      pushMessage({ role: 'assistant', text: chatData.text, created_at: new Date().toISOString() });
    }

    renderChat();
  } catch (err) {
    $('chat-status').textContent = err.message;
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
//  CAMERA INSTANCE — uses native camera via capture attribute
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

    if (this.btnCapture) {
      this.btnCapture.addEventListener('click', () => {
        if (this.captureInput) this.captureInput.click();
      });
    }
    if (this.btnRetake) {
      this.btnRetake.addEventListener('click', () => {
        this.clearImage();
        if (this.captureInput) this.captureInput.click();
      });
    }
    if (this.btnFile) {
      this.btnFile.addEventListener('click', () => {
        if (this.fileInput) this.fileInput.click();
      });
    }
    if (this.captureInput) {
      this.captureInput.addEventListener('change', (e) => this._handleFile(e.target.files[0]));
    }
    if (this.fileInput) {
      this.fileInput.addEventListener('change', (e) => this._handleFile(e.target.files[0]));
    }
  }

  _handleFile(file) {
    if (!file) return;
    this.capturedBlob = file;
    this.uploadFileName = file.name;
    this.imageUrl = null;
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

  start() {}

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
