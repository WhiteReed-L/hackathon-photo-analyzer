class CameraApp {
  constructor() {
    this.video = document.getElementById('camera-feed');
    this.canvas = document.getElementById('capture-canvas') || this._createCanvas();
    this.preview = document.getElementById('photo-preview');
    this.statusMessage = document.getElementById('status-message');
    this.uploadLoading = document.getElementById('upload-loading');
    this.capturedBlob = null;
    this.uploadFileName = 'photo.jpg'; // default for camera capture
    this.stream = null;
    this.facingMode = 'user'; // front camera by default
    this._previewUrl = null;  // track blob URL for cleanup

    this._bindElements();
  }

  _createCanvas() {
    const canvas = document.createElement('canvas');
    canvas.id = 'capture-canvas';
    canvas.style.display = 'none';
    document.querySelector('.camera-container').appendChild(canvas);
    return canvas;
  }

  _bindElements() {
    this.btnCapture = document.getElementById('btn-capture');
    this.btnRetake = document.getElementById('btn-retake');
    this.btnUpload = document.getElementById('btn-upload');
    this.btnSwitchCamera = document.getElementById('btn-switch-camera');
    this.fileUploadArea = document.getElementById('file-upload-area');
    this.fileInput = document.getElementById('file-input');

    this.btnCapture.addEventListener('click', () => this.capturePhoto());
    this.btnRetake.addEventListener('click', () => this.retake());
    this.btnUpload.addEventListener('click', () => this.uploadPhoto());
    this.btnSwitchCamera.addEventListener('click', () => this.switchCamera());
    this.fileUploadArea.addEventListener('click', () => this.fileInput.click());
    this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
  }

  _setPreviewUrl(url) {
    // Revoke old blob URL before setting a new one
    if (this._previewUrl) {
      URL.revokeObjectURL(this._previewUrl);
    }
    this._previewUrl = url;
    this.preview.src = url;
  }

  async startCamera() {
    try {
      // Use minimal constraints for maximum compatibility.
      // Specific width/height ideals cause "AbortError: Timeout" on some Windows camera drivers.
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: this.facingMode },
        audio: false,
      });
      this.video.srcObject = this.stream;
      this.video.style.display = 'block';
      this.preview.style.display = 'none';
      this.btnRetake.classList.add('hidden');
      this.btnUpload.classList.add('hidden');
      this.btnSwitchCamera.classList.remove('hidden');
      this.btnCapture.classList.remove('hidden');
      this.showStatus('', '');
    } catch (err) {
      console.error('Camera error:', err.name, err.message);
      this.video.style.display = 'none';
      this.btnCapture.classList.add('hidden');
      this.btnSwitchCamera.classList.add('hidden');

      // Map specific errors to actionable Chinese messages
      const errorMessages = {
        NotAllowedError:
          '❌ 摄像头权限被拒绝。请在浏览器地址栏左侧的锁图标点击，将摄像头权限改为"允许"，然后刷新页面。',
        NotFoundError:
          '❌ 未检测到摄像头设备。请确认已连接摄像头，或使用下方的文件上传功能。',
        NotReadableError:
          '❌ 摄像头被其他应用占用。请关闭其他使用摄像头的程序（如微信视频、腾讯会议等），然后刷新页面。',
        OverconstrainedError:
          '❌ 摄像头不支持所需的参数，正在尝试重新获取...',
        AbortError:
          '❌ 摄像头启动超时，正在尝试重新获取...',
      };
      const msg =
        errorMessages[err.name] ||
        `❌ 无法访问相机（${err.name}: ${err.message}）。请使用下方的文件上传功能。`;

      this.showStatus(msg, 'error');

      // OverconstrainedError / AbortError: retry with bare-minimum constraints
      if (err.name === 'OverconstrainedError' || err.name === 'AbortError') {
        try {
          this.stream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: false,
          });
          this.video.srcObject = this.stream;
          this.video.style.display = 'block';
          this.btnCapture.classList.remove('hidden');
          this.btnSwitchCamera.classList.remove('hidden');
          this.showStatus('', '');
          return; // success, don't re-throw
        } catch (retryErr) {
          this.showStatus(
            errorMessages[retryErr.name] ||
              `❌ 无法访问相机（${retryErr.name}）。请使用下方的文件上传功能。`,
            'error'
          );
        }
      }

      // NotReadableError: camera may be temporarily locked — show a retry button
      if (err.name === 'NotReadableError') {
        this._showRetryButton();
      }

      throw err;
    }
  }

  _showRetryButton() {
    // Replace the capture button with a retry button temporarily
    this.btnCapture.textContent = '🔄 重新尝试连接摄像头';
    this.btnCapture.classList.remove('hidden');
    this.btnCapture.onclick = async () => {
      this.btnCapture.textContent = '📸 拍照';
      this.btnCapture.onclick = () => this.capturePhoto();
      this.btnCapture.classList.add('hidden');
      this.btnSwitchCamera.classList.add('hidden');
      this.showStatus('正在尝试重新连接摄像头...', 'info');
      try {
        await this.startCamera();
      } catch {
        // startCamera handles its own error display
      }
    };
  }

  capturePhoto() {
    if (!this.stream) return;

    this.canvas.width = this.video.videoWidth || 1280;
    this.canvas.height = this.video.videoHeight || 720;
    const ctx = this.canvas.getContext('2d');

    // Flip horizontally for front-facing camera to match mirror view
    if (this.facingMode === 'user') {
      ctx.translate(this.canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

    this.canvas.toBlob(
      (blob) => {
        if (!blob) {
          this.showStatus('拍照失败，请重试', 'error');
          return;
        }
        this.capturedBlob = blob;
        this.uploadFileName = 'photo.jpg';
        this._setPreviewUrl(URL.createObjectURL(blob));
        this.showPreview();
      },
      'image/jpeg',
      0.85
    );
  }

  showPreview() {
    this.video.style.display = 'none';
    this.preview.style.display = 'block';
    this.btnCapture.classList.add('hidden');
    this.btnRetake.classList.remove('hidden');
    this.btnUpload.classList.remove('hidden');
  }

  retake() {
    this.capturedBlob = null;
    this._setPreviewUrl('');
    this.preview.style.display = 'none';
    this.video.style.display = 'block';
    this.btnCapture.classList.remove('hidden');
    this.btnRetake.classList.add('hidden');
    this.btnUpload.classList.add('hidden');
    this.showStatus('', '');
  }

  async switchCamera() {
    this.facingMode = this.facingMode === 'user' ? 'environment' : 'user';

    // Save old stream in case the switch fails
    const oldStream = this.stream;

    // Stop current stream tracks
    if (oldStream) {
      oldStream.getTracks().forEach((track) => track.stop());
    }
    this.stream = null;

    try {
      await this.startCamera();
    } catch {
      // New camera failed — try to restore the old one
      // (old tracks are stopped, so re-request with old facing mode)
      this.facingMode = this.facingMode === 'user' ? 'environment' : 'user';
      try {
        await this.startCamera();
      } catch {
        // Both cameras unavailable; startCamera() already showed error message
      }
    }
  }

  async uploadPhoto() {
    if (!this.capturedBlob) return;

    const formData = new FormData();
    formData.append('file', this.capturedBlob, this.uploadFileName);

    this.btnUpload.disabled = true;
    this.uploadLoading.style.display = 'block';
    this.showStatus('', '');

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

      this.showStatus(
        `✅ 照片上传成功！编号: ${data.id} | 文件名: ${data.filename}`,
        'success'
      );
      this.btnUpload.classList.add('hidden');
      this.btnRetake.textContent = '🔄 再拍一张';
    } catch (err) {
      this.showStatus(`❌ 上传失败: ${err.message}`, 'error');
    } finally {
      this.btnUpload.disabled = false;
      this.uploadLoading.style.display = 'none';
    }
  }

  handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Show preview
    this.capturedBlob = file;
    this.uploadFileName = file.name;
    this._setPreviewUrl(URL.createObjectURL(file));
    this.showPreview();

    // If camera is not active, hide it
    if (!this.stream) {
      this.video.style.display = 'none';
    }

    this.showStatus(`已选择文件: ${file.name}`, 'info');
  }

  showStatus(message, type) {
    this.statusMessage.textContent = message;
    this.statusMessage.className = 'status-message';
    if (type) {
      this.statusMessage.classList.add('show', type);
    }
  }
}

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
  const app = new CameraApp();
  app.startCamera().catch(() => {
    // Error already handled and shown to user inside startCamera()
  });
});
