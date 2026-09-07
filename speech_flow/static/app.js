// Speech Flow: Real-time Audio Visualizer, Speech Buffer & Conversational Interface

class SpeechFlowApp {
  constructor() {
    this.ws = null;
    this.audioContext = null;
    this.analyser = null;
    this.microphoneStream = null;
    this.recognition = null;
    this.isListening = false;
    this.silenceTimer = null;
    this.lastSpeechTime = 0;
    this.animationFrameId = null;

    // TTS Settings
    this.synth = window.speechSynthesis;
    this.voices = [];
    this.selectedVoice = null;
    this.speechRate = 1.0;

    // DOM Elements
    this.btnMicToggle = document.getElementById('btnMicToggle');
    this.micIcon = document.getElementById('micIcon');
    this.micBtnText = document.getElementById('micBtnText');
    this.btnDispatchBuffer = document.getElementById('btnDispatchBuffer');
    this.btnClearBuffer = document.getElementById('btnClearBuffer');
    this.tokensContainer = document.getElementById('tokensContainer');
    this.interimDisplay = document.getElementById('interimDisplay');
    this.emptyPlaceholder = document.getElementById('emptyPlaceholder');
    this.dialogueStream = document.getElementById('dialogueStream');
    this.textInputForm = document.getElementById('textInputForm');
    this.textInput = document.getElementById('textInput');
    this.canvas = document.getElementById('audioVisualizer');
    this.canvasCtx = this.canvas.getContext('2d');
    this.listeningIndicator = document.getElementById('listeningIndicator');
    this.statusDot = document.getElementById('statusDot');
    this.statusText = document.getElementById('statusText');
    this.btnRefreshStatus = document.getElementById('btnRefreshStatus');

    // Metrics
    this.metricWordCount = document.getElementById('metricWordCount');
    this.metricWpm = document.getElementById('metricWpm');
    this.metricAudioLevel = document.getElementById('metricAudioLevel');
    this.autoSendCheckbox = document.getElementById('autoSendCheckbox');
    this.ttsVoiceSelect = document.getElementById('ttsVoiceSelect');
    this.ttsRateSlider = document.getElementById('ttsRateSlider');

    this.initWebSocket();
    this.initSpeechRecognition();
    this.initVoices();
    this.bindEvents();
    this.drawIdleVisualizer();
  }

  // -------------------------------------------------------------------------
  // WebSocket Connection
  // -------------------------------------------------------------------------
  initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('Connected to Speech Flow WebSocket server.');
      this.checkAdrasteaStatus();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = jsonParseSafe(event.data);
        if (!data) return;
        this.handleServerMessage(data);
      } catch (err) {
        console.error('Error handling WebSocket message:', err);
      }
    };

    this.ws.onclose = () => {
      console.warn('Speech Flow WebSocket disconnected. Reconnecting in 2s...');
      setTimeout(() => this.initWebSocket(), 2000);
    };
  }

  handleServerMessage(data) {
    switch (data.type) {
      case 'init':
        this.renderBuffer(data.buffer);
        if (data.history && data.history.length > 0) {
          data.history.forEach((item) => this.appendDialogueEntry(item, false));
        }
        break;

      case 'buffer_update':
        this.renderBuffer(data.buffer);
        break;

      case 'adrastea_thinking':
        this.showThinkingBubble(data.prompt);
        break;

      case 'adrastea_response':
        this.removeThinkingBubble();
        this.appendDialogueEntry(data.entry, true);
        break;

      case 'adrastea_status':
        this.updateAdrasteaStatusBadge(data.status);
        break;
    }
  }

  // -------------------------------------------------------------------------
  // Web Speech API: Speech-to-Text (Microphone Ingestion)
  // -------------------------------------------------------------------------
  initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('SpeechRecognition API not natively supported in this browser. Fallback to text.');
      this.micBtnText.innerText = 'Mic Not Supported';
      this.btnMicToggle.disabled = true;
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.lang = 'en-US';

    this.recognition.onstart = () => {
      this.isListening = true;
      this.btnMicToggle.classList.add('active');
      this.micBtnText.innerText = 'Listening...';
      this.listeningIndicator.classList.add('active');
      this.startAudioVisualization();
    };

    this.recognition.onresult = (event) => {
      this.lastSpeechTime = Date.now();
      let interim = '';
      let finalized = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcript = event.results[i][0].transcript;
        const confidence = event.results[i][0].confidence || 1.0;
        if (event.results[i].isFinal) {
          finalized += transcript + ' ';
          this.sendWsMessage({
            type: 'final_speech',
            text: transcript.trim(),
            confidence: confidence
          });
        } else {
          interim += transcript;
        }
      }

      if (interim) {
        this.sendWsMessage({
          type: 'interim_speech',
          text: interim.trim()
        });
      }

      // Reset auto-send silence timer
      this.resetSilenceTimer();
    };

    this.recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      if (event.error === 'not-allowed') {
        alert('Microphone access was denied. Please allow microphone permissions in your browser.');
        this.stopListening();
      }
    };

    this.recognition.onend = () => {
      if (this.isListening) {
        // Auto-restart if user did not explicitly stop
        try {
          this.recognition.start();
        } catch (e) {
          this.stopListening();
        }
      } else {
        this.stopListening();
      }
    };
  }

  toggleListening() {
    if (this.isListening) {
      this.stopListening();
    } else {
      this.startListening();
    }
  }

  startListening() {
    if (!this.recognition) return;
    try {
      this.isListening = true;
      this.recognition.start();
    } catch (err) {
      console.warn('Recognition already started:', err);
    }
  }

  stopListening() {
    this.isListening = false;
    if (this.recognition) {
      try { this.recognition.stop(); } catch (e) {}
    }
    this.btnMicToggle.classList.remove('active');
    this.micBtnText.innerText = 'Start Listening';
    this.listeningIndicator.classList.remove('active');
    this.stopAudioVisualization();
    if (this.silenceTimer) clearTimeout(this.silenceTimer);
  }

  resetSilenceTimer() {
    if (!this.autoSendCheckbox.checked) return;
    if (this.silenceTimer) clearTimeout(this.silenceTimer);

    // Auto-dispatch after 1.6s of silence following spoken words
    this.silenceTimer = setTimeout(() => {
      const hasTokens = this.tokensContainer.children.length > 0;
      if (hasTokens && this.isListening) {
        console.log('Silence detected; dispatching buffer to Adrastea...');
        this.dispatchBuffer();
      }
    }, 1600);
  }

  // -------------------------------------------------------------------------
  // Web Audio API: Live Microphone Audio Visualizer
  // -------------------------------------------------------------------------
  async startAudioVisualization() {
    try {
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      this.microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const source = this.audioContext.createMediaStreamSource(this.microphoneStream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 64;
      source.connect(this.analyser);

      this.renderVisualizer();
    } catch (err) {
      console.warn('Could not initialize audio visualizer:', err);
      this.drawIdleVisualizer();
    }
  }

  stopAudioVisualization() {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
    if (this.microphoneStream) {
      this.microphoneStream.getTracks().forEach((track) => track.stop());
      this.microphoneStream = null;
    }
    this.drawIdleVisualizer();
    this.metricAudioLevel.innerText = '0%';
  }

  renderVisualizer() {
    if (!this.analyser) return;

    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      this.animationFrameId = requestAnimationFrame(draw);
      this.analyser.getByteFrequencyData(dataArray);

      const width = this.canvas.width;
      const height = this.canvas.height;
      this.canvasCtx.clearRect(0, 0, width, height);

      let sum = 0;
      const barWidth = (width / bufferLength) * 2;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const val = dataArray[i];
        sum += val;
        const barHeight = (val / 255) * height * 0.9;

        // Gradient color: cyan to purple
        const gradient = this.canvasCtx.createLinearGradient(0, height, 0, 0);
        gradient.addColorStop(0, '#00f0ff');
        gradient.addColorStop(0.7, '#a855f7');
        gradient.addColorStop(1, '#ff007f');

        this.canvasCtx.fillStyle = gradient;
        this.canvasCtx.fillRect(x, height - barHeight, barWidth - 3, barHeight);
        x += barWidth;
      }

      const avg = Math.round((sum / bufferLength) / 2.55);
      this.metricAudioLevel.innerText = `${avg}%`;
    };

    draw();
  }

  drawIdleVisualizer() {
    const width = this.canvas.width;
    const height = this.canvas.height;
    this.canvasCtx.clearRect(0, 0, width, height);

    this.canvasCtx.strokeStyle = 'rgba(0, 240, 255, 0.2)';
    this.canvasCtx.lineWidth = 2;
    this.canvasCtx.beginPath();
    this.canvasCtx.moveTo(0, height / 2);
    this.canvasCtx.lineTo(width, height / 2);
    this.canvasCtx.stroke();
  }

  // -------------------------------------------------------------------------
  // Speech Buffer Visualization
  // -------------------------------------------------------------------------
  renderBuffer(buffer) {
    if (!buffer) return;

    const tokens = buffer.tokens || [];
    const interim = buffer.interim || '';
    const metrics = buffer.metrics || {};

    this.metricWordCount.innerText = metrics.word_count || tokens.length;
    this.metricWpm.innerText = metrics.wpm || '0.0';

    if (tokens.length === 0 && !interim) {
      this.emptyPlaceholder.style.display = 'block';
      this.tokensContainer.innerHTML = '';
      this.interimDisplay.innerText = '';
      return;
    }

    this.emptyPlaceholder.style.display = 'none';
    this.tokensContainer.innerHTML = '';

    tokens.forEach((t) => {
      const span = document.createElement('span');
      span.className = 'word-token';
      span.innerText = t.text;
      span.title = `Time: ${new Date(t.timestamp * 1000).toLocaleTimeString()}`;
      this.tokensContainer.appendChild(span);
    });

    this.interimDisplay.innerText = interim ? `... ${interim}` : '';
  }

  dispatchBuffer() {
    this.sendWsMessage({ type: 'dispatch_buffer' });
  }

  clearBuffer() {
    this.sendWsMessage({ type: 'clear_buffer' });
  }

  // -------------------------------------------------------------------------
  // Dialogue Stream & TTS Playback
  // -------------------------------------------------------------------------
  appendDialogueEntry(entry, shouldSpeak = true) {
    if (!entry) return;

    // User Message
    const userDiv = document.createElement('div');
    userDiv.className = 'dialogue-entry user';
    userDiv.innerHTML = `
      <div class="bubble user">
        <p>${escapeHtml(entry.user)}</p>
      </div>
    `;
    this.dialogueStream.appendChild(userDiv);

    // Adrastea Response
    const adrasteaDiv = document.createElement('div');
    adrasteaDiv.className = 'dialogue-entry adrastea';
    const actionBadge = entry.action && entry.action !== 'none'
      ? `<span class="action-badge">${escapeHtml(entry.action)}</span>`
      : '';

    adrasteaDiv.innerHTML = `
      <div class="bubble adrastea">
        <p>${escapeHtml(entry.adrastea)}</p>
        <div class="bubble-meta">
          ${actionBadge}
          <button class="btn-speak" onclick="window.app.speakText('${escapeQuotes(entry.adrastea)}')">🔊 Listen</button>
        </div>
      </div>
    `;
    this.dialogueStream.appendChild(adrasteaDiv);
    this.dialogueStream.scrollTop = this.dialogueStream.scrollHeight;

    // TTS Output
    if (shouldSpeak) {
      this.speakText(entry.adrastea);
    }
  }

  showThinkingBubble(prompt) {
    this.removeThinkingBubble();
    const thinkDiv = document.createElement('div');
    thinkDiv.className = 'dialogue-entry adrastea thinking-entry';
    thinkDiv.id = 'thinkingBubble';
    thinkDiv.innerHTML = `
      <div class="bubble thinking">
        <span>⚡ Adrastea reasoning & deciding response...</span>
      </div>
    `;
    this.dialogueStream.appendChild(thinkDiv);
    this.dialogueStream.scrollTop = this.dialogueStream.scrollHeight;
  }

  removeThinkingBubble() {
    const el = document.getElementById('thinkingBubble');
    if (el) el.remove();
  }

  // -------------------------------------------------------------------------
  // Text-To-Speech (TTS) Engine
  // -------------------------------------------------------------------------
  initVoices() {
    const populateVoices = () => {
      this.voices = this.synth.getVoices();
      this.ttsVoiceSelect.innerHTML = '';
      this.voices.forEach((v, idx) => {
        const opt = document.createElement('option');
        opt.value = idx;
        opt.textContent = `${v.name} (${v.lang})`;
        if (v.default || v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('David')) {
          opt.selected = true;
          this.selectedVoice = v;
        }
        this.ttsVoiceSelect.appendChild(opt);
      });
    };

    populateVoices();
    if (this.synth.onvoiceschanged !== undefined) {
      this.synth.onvoiceschanged = populateVoices;
    }
  }

  speakText(text) {
    if (!text || !this.synth) return;
    try {
      this.synth.cancel(); // Cancel any ongoing utterance
      const utterance = new SpeechSynthesisUtterance(text);
      if (this.selectedVoice) utterance.voice = this.selectedVoice;
      utterance.rate = parseFloat(this.ttsRateSlider.value) || 1.0;
      this.synth.speak(utterance);
    } catch (err) {
      console.warn('Browser TTS synthesis error:', err);
    }
  }

  // -------------------------------------------------------------------------
  // Adrastea Status
  // -------------------------------------------------------------------------
  async checkAdrasteaStatus() {
    try {
      const resp = await fetch('/api/status');
      const data = await resp.json();
      this.updateAdrasteaStatusBadge(data.adrastea_status);
    } catch (err) {
      this.updateAdrasteaStatusBadge(null);
    }
  }

  updateAdrasteaStatusBadge(status) {
    if (status && status.status === 'alive') {
      this.statusDot.className = 'status-dot online';
      const stateStr = status.sleeping ? 'SLEEPING (Keep-Alive)' : 'ACTIVE';
      this.statusText.innerText = `Adrastea ${stateStr}`;
      if (status.sleeping) {
        this.statusDot.className = 'status-dot sleeping';
      }
    } else {
      this.statusDot.className = 'status-dot offline';
      this.statusText.innerText = 'Adrastea Offline (Port 8765)';
    }
  }

  // -------------------------------------------------------------------------
  // Event Bindings
  // -------------------------------------------------------------------------
  bindEvents() {
    this.btnMicToggle.addEventListener('click', () => this.toggleListening());
    this.btnDispatchBuffer.addEventListener('click', () => this.dispatchBuffer());
    this.btnClearBuffer.addEventListener('click', () => this.clearBuffer());
    this.btnRefreshStatus.addEventListener('click', () => this.checkAdrasteaStatus());

    this.ttsVoiceSelect.addEventListener('change', (e) => {
      this.selectedVoice = this.voices[e.target.value];
    });

    // Quick Directive chips
    document.querySelectorAll('.chip-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const cmd = btn.getAttribute('data-cmd');
        if (cmd) {
          this.textInput.value = cmd;
          this.submitTextInput();
        }
      });
    });

    // Text Fallback form
    this.textInputForm.addEventListener('submit', (e) => {
      e.preventDefault();
      this.submitTextInput();
    });

    // Spacebar to talk shortcut (when not typing in text field)
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && document.activeElement !== this.textInput) {
        e.preventDefault();
        this.toggleListening();
      }
    });
  }

  async submitTextInput() {
    const text = this.textInput.value.trim();
    if (!text) return;
    this.textInput.value = '';

    this.showThinkingBubble(text);
    try {
      const resp = await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      });
      const data = await resp.json();
      this.removeThinkingBubble();
      this.appendDialogueEntry(data, true);
    } catch (err) {
      this.removeThinkingBubble();
      console.error('Error submitting command:', err);
    }
  }

  sendWsMessage(payload) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }
}

// Utility Helpers
function jsonParseSafe(str) {
  try { return JSON.parse(str); } catch { return null; }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeQuotes(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, ' ');
}

// Instantiate on page load
window.addEventListener('DOMContentLoaded', () => {
  window.app = new SpeechFlowApp();
});
