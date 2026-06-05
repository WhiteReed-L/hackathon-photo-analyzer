class AdminApp {
  constructor() {
    this.currentPhotoId = null;
    this._bindElements();
    this.checkAuth();
  }

  _bindElements() {
    // Login
    this.loginPage = document.getElementById('login-page');
    this.loginForm = document.getElementById('login-form');
    this.loginStatus = document.getElementById('login-status');

    // Dashboard
    this.dashboard = document.getElementById('admin-dashboard');
    this.galleryGrid = document.getElementById('gallery-grid');
    this.galleryStats = document.getElementById('gallery-stats');
    this.emptyState = document.getElementById('empty-state');

    // Modal
    this.modalOverlay = document.getElementById('modal-overlay');
    this.modalImage = document.getElementById('modal-image');
    this.modalTitle = document.getElementById('modal-title');
    this.modalMeta = document.getElementById('modal-meta');
    this.modalAnalysis = document.getElementById('modal-analysis');
    this.modalStatus = document.getElementById('modal-status');

    // Buttons
    this.btnRefresh = document.getElementById('btn-refresh');
    this.btnLogout = document.getElementById('btn-logout');
    this.btnAnalyze = document.getElementById('btn-analyze');
    this.btnCloseModal = document.getElementById('btn-close-modal');

    // Events
    this.loginForm.addEventListener('submit', (e) => {
      e.preventDefault();
      this.login();
    });
    this.btnRefresh.addEventListener('click', () => this.loadGallery());
    this.btnLogout.addEventListener('click', () => this.logout());
    this.btnAnalyze.addEventListener('click', () => this.analyzePhoto());
    this.btnCloseModal.addEventListener('click', () => this.closeModal());
    this.modalOverlay.addEventListener('click', (e) => {
      if (e.target === this.modalOverlay) this.closeModal();
    });
  }

  // ===== Auth =====

  async checkAuth() {
    try {
      const res = await fetch('/api/admin/check');
      const data = await res.json();
      if (data.authenticated) {
        this.showDashboard();
      } else {
        this.showLogin();
      }
    } catch {
      this.showLogin();
    }
  }

  async login() {
    const password = document.getElementById('password').value;
    if (!password) {
      this._showLoginError('请输入密码');
      return;
    }

    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        this.showDashboard();
      } else {
        this._showLoginError(data.detail || '登录失败');
      }
    } catch (err) {
      this._showLoginError(`网络错误: ${err.message}`);
    }
  }

  async logout() {
    try {
      await fetch('/api/admin/logout', { method: 'POST' });
    } catch {
      // If server is unreachable, still show login on client side
    }
    this.showLogin();
  }

  _showLoginError(msg) {
    this.loginStatus.textContent = msg;
    this.loginStatus.className = 'status-message show error';
  }

  showLogin() {
    this.loginPage.classList.remove('hidden');
    this.dashboard.classList.add('hidden');
  }

  showDashboard() {
    this.loginPage.classList.add('hidden');
    this.dashboard.classList.remove('hidden');
    this.loadGallery();
  }

  // ===== Gallery =====

  async loadGallery() {
    this.galleryGrid.innerHTML =
      '<div style="text-align:center;padding:40px;"><span class="spinner spinner-dark"></span> 加载中...</div>';

    try {
      const res = await fetch('/api/photos');
      if (!res.ok) {
        if (res.status === 403) {
          this.showLogin();
          return;
        }
        throw new Error('Failed to load photos');
      }

      const data = await res.json();
      this._renderGallery(data.photos, data.total);
    } catch (err) {
      this.galleryGrid.innerHTML = '';
      this.galleryStats.textContent = `加载失败: ${err.message}`;
    }
  }

  _renderGallery(photos, total) {
    this.galleryGrid.innerHTML = '';
    this.galleryStats.textContent = `共 ${total} 张照片`;

    if (!photos || photos.length === 0) {
      this.emptyState.classList.remove('hidden');
      return;
    }

    this.emptyState.classList.add('hidden');

    photos.forEach((photo) => {
      const card = document.createElement('div');
      card.className = 'photo-card';
      card.innerHTML = `
        <img class="thumb" src="${photo.image_url}" alt="${photo.original_name}" loading="lazy">
        <div class="info">
          <div class="name" title="${photo.original_name}">${photo.original_name}</div>
          <div class="time">${this._formatTime(photo.created_at)}</div>
          <span class="badge ${photo.analysis ? 'badge-analyzed' : 'badge-pending'}">
            ${photo.analysis ? '✅ 已分析' : '⏳ 待分析'}
          </span>
        </div>
      `;
      card.addEventListener('click', () => this.showDetail(photo.id));
      this.galleryGrid.appendChild(card);
    });
  }

  // ===== Detail Modal =====

  async showDetail(photoId) {
    this.currentPhotoId = photoId;
    this.modalStatus.textContent = '';
    this.modalStatus.className = 'status-message';
    this.btnAnalyze.disabled = false;
    this.btnAnalyze.innerHTML = '🤖 AI 分析';

    try {
      const res = await fetch(`/api/photos/${photoId}`);
      if (!res.ok) {
        if (res.status === 403) {
          this.closeModal();
          this.showLogin();
          return;
        }
        throw new Error('Failed to load photo');
      }

      const photo = await res.json();

      this.modalImage.src = photo.image_url;
      this.modalTitle.textContent = photo.original_name;
      this.modalMeta.textContent = `大小: ${this._formatSize(photo.file_size)} | 上传: ${this._formatTime(photo.created_at)}`;

      if (photo.analysis) {
        this.modalAnalysis.innerHTML = this._renderAnalysis(photo.analysis);
        this.btnAnalyze.innerHTML = '🔄 重新分析';
      } else {
        this.modalAnalysis.innerHTML = `
          <div class="analysis-placeholder">
            <p>📝 尚未分析</p>
            <p style="font-size:0.85rem;color:var(--text-secondary);">点击下方按钮使用 AI 分析此照片</p>
          </div>
        `;
        this.btnAnalyze.innerHTML = '🤖 AI 分析';
      }

      this.modalOverlay.classList.remove('hidden');
    } catch (err) {
      this._showModalError(`加载详情失败: ${err.message}`);
    }
  }

  async analyzePhoto() {
    if (!this.currentPhotoId) return;

    this.btnAnalyze.disabled = true;
    this.btnAnalyze.innerHTML =
      '<span class="spinner"></span> 分析中...';
    this.modalStatus.textContent = '';
    this.modalStatus.className = 'status-message';

    try {
      const res = await fetch(`/api/photos/${this.currentPhotoId}/analyze`, {
        method: 'POST',
      });

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 403) {
          this.closeModal();
          this.showLogin();
          return;
        }
        throw new Error(data.detail || 'Analysis failed');
      }

      this.modalAnalysis.innerHTML = this._renderAnalysis(data.analysis);
      this.btnAnalyze.innerHTML = '🔄 重新分析';
      this._showModalSuccess(
        `分析完成！模型: ${data.model}, Token: ${data.usage?.total_tokens || 'N/A'}`
      );

      // Refresh gallery to update badge
      this.loadGallery();
    } catch (err) {
      this._showModalError(`分析失败: ${err.message}`);
      this.btnAnalyze.innerHTML = '🤖 AI 分析';
    } finally {
      this.btnAnalyze.disabled = false;
    }
  }

  closeModal() {
    this.modalOverlay.classList.add('hidden');
    this.currentPhotoId = null;
  }

  // ===== Helpers =====

  _renderAnalysis(text) {
    // Convert markdown-like sections to HTML
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>')
      .replace(/^/, '<p>')
      .replace(/$/, '</p>');
  }

  _formatTime(isoString) {
    if (!isoString) return '';
    try {
      const d = new Date(isoString + (isoString.endsWith('Z') ? '' : 'Z'));
      return d.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  }

  _formatSize(bytes) {
    if (!bytes) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  _showModalError(msg) {
    this.modalStatus.textContent = msg;
    this.modalStatus.className = 'status-message show error';
  }

  _showModalSuccess(msg) {
    this.modalStatus.textContent = msg;
    this.modalStatus.className = 'status-message show success';
  }
}

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
  new AdminApp();
});
