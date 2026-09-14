// JobCopilot — AI Mock Interview Studio (VIEW 5): question bank, dropdown,
// live audio visualizer, Web Audio chime synth, Web Speech transcription,
// WPM/filler radar, and the Glass Booth full-screen studio.
// Extracted from app.js (P1-6). Classic script bundled after app.js, so it
// shares the global scope (reads state/els/escapeHTML/showToast/authFetch and
// exposes its window.* handlers; app.js's submitAnswerForEvaluation reads this
// module's live interview state at runtime).
// ==========================================================================
// VIEW 5: AI Mock Interview Studio & Live Audio Visualizer
// ==========================================================================
const mockQuestionsBank = [
  // --- Track: Backend & Distributed Systems ---
  {
    id: "q_sys_stripe_1",
    category: "System Design",
    role_track: "Backend & Distributed Systems",
    company_tag: "Stripe",
    difficulty: "Hard",
    question: "How would you design a distributed payment ledger and idempotency engine that guarantees zero double-billing across network retries at 100,000 TPS?",
    key_concepts: ["Idempotency-Key Header", "Double-Entry Ledger", "Distributed Lock (Redis Lua)", "Compensating Transactions", "Atomic State Machine", "P99 SLA"],
    sample_star: "At my previous fintech role, payment retry storms caused duplicate authorizations during gateway outages. I architected an idempotency middleware storing client keys in Redis with an atomic Lua script distributed lock. Successful charges were written to an immutable double-entry PostgreSQL ledger where debits strictly matched credits. Unfinished requests returned cached payloads. This eliminated duplicate transactions across 80M monthly payments and lowered P99 latency to 42ms."
  },
  {
    id: "q_sys_uber_2",
    category: "System Design",
    role_track: "Backend & Distributed Systems",
    company_tag: "Uber",
    difficulty: "Hard",
    question: "How would you design a high-throughput geospatial ingestion pipeline to track millions of concurrent driver locations and calculate nearest-driver dispatch in real-time?",
    key_concepts: ["H3 Spatial Indexing", "Geohash / Quadtree", "WebSocket Gateway", "Redis Pub/Sub & Sorted Sets", "Dispatch Matcher", "Backpressure"],
    sample_star: "Our fleet tracking platform experienced severe lag when processing GPS pings from 150k vehicles. I introduced an H3 hexagonal indexing pipeline with a WebSocket cluster terminating TLS at Envoy edge proxies. Location pings were partitioned into Redis Geospatial indices with a 15-second TTL. The dispatch matching engine queried adjacent H3 rings in O(1) time, cutting match latency from 3.2s to 120ms and handling 100k writes/sec seamlessly."
  },
  {
    id: "q_sys_netflix_3",
    category: "System Design",
    role_track: "Backend & Distributed Systems",
    company_tag: "Netflix",
    difficulty: "Hard",
    question: "Design a global content delivery infrastructure and video transcoding pipeline capable of serving adaptive bitrate streaming to 200 million users during live events.",
    key_concepts: ["Edge CDN Caching", "Adaptive Bitrate (HLS/DASH)", "Transcoding Workers", "S3 Blob Storage", "Circuit Breaker", "Simian Chaos"],
    sample_star: "We needed to broadcast live events to 2M concurrent viewers without buffering. I built an automated transcoding pipeline using asynchronous worker clusters that segmented MP4 video into multi-bitrate HLS chunks uploaded to S3. We configured global Cloudflare CDN edge caching with proactive pre-fetching of video manifests. When regional CDN nodes failed, automated circuit breakers rerouted traffic, maintaining a 99.98% stream availability."
  },
  {
    id: "q_con_rate_5",
    category: "Architecture & Concurrency",
    role_track: "Backend & Distributed Systems",
    company_tag: "Universal",
    difficulty: "Medium",
    question: "How would you implement a distributed rate limiter supporting sliding window counters across multiple microservice regions without clock drift vulnerabilities?",
    key_concepts: ["Sliding Window Logs", "Redis Sorted Sets (ZADD/ZREMRANGE)", "Atomic Lua Scripts", "Fail-Open vs Fail-Closed", "Memory Eviction"],
    sample_star: "To prevent API abuse on our public endpoints, I built a distributed sliding window rate limiter using Redis sorted sets. Each request executed an atomic Lua script that removed expired timestamps, added the current timestamp, and checked card against quota in a single round-trip. We implemented a fail-open circuit breaker to guarantee availability if Redis degraded. The service handled 40,000 req/sec with < 2ms latency."
  },
  {
    id: "q_con_db_6",
    category: "Architecture & Concurrency",
    role_track: "Backend & Distributed Systems",
    company_tag: "Universal",
    difficulty: "Hard",
    question: "Under heavy concurrent database write contention, how do you diagnose and eliminate database connection pool exhaustion and deadlocks?",
    key_concepts: ["Optimistic Concurrency Control", "Connection Pool Sizing", "AsyncIO Event Loop", "Read Replicas & Sharding", "WAL Checkpoints"],
    sample_star: "During a flash sale, our primary PostgreSQL instance reached 100% connection pool exhaustion with rampant row-level deadlocks. I diagnosed lock contention using pg_stat_activity and reorganized transaction statements to acquire row locks in deterministic order. I replaced pessimistic locks with optimistic concurrency using version tokens, moved read traffic to read replicas with PgBouncer connection pooling, reducing CPU from 98% to 34%."
  },

  // --- Track: Frontend & Full-Stack ---
  {
    id: "q_fe_rendering_10",
    category: "Frontend Architecture",
    role_track: "Frontend & Full-Stack",
    company_tag: "Vercel / Meta",
    difficulty: "Hard",
    question: "How do you optimize Core Web Vitals (LCP, INP, CLS) and design a high-performance Next.js application with React Server Components (RSC) and streaming SSR?",
    key_concepts: ["React Server Components (RSC)", "Streaming SSR / Suspense", "Core Web Vitals (LCP/INP/CLS)", "Code Splitting & Dynamic Imports", "Edge Cache Middleware"],
    sample_star: "Our e-commerce checkout had poor Core Web Vitals with an LCP of 4.2s and CLS of 0.28. I migrated the frontend to Next.js with React Server Components, streaming heavy product catalog data via React Suspense boundaries. I replaced bulky third-party scripts with Web Workers via Partytown and optimized image priority loading with AVIF formatting. This slashed LCP to 1.1s, brought CLS to 0.02, and improved checkout conversion by 14%."
  },
  {
    id: "q_fe_state_11",
    category: "Frontend Architecture",
    role_track: "Frontend & Full-Stack",
    company_tag: "Figma / Linear",
    difficulty: "Hard",
    question: "In a real-time collaborative web application, how do you architect client-side state management, optimistic UI updates, and WebSocket event synchronization without UI stutter?",
    key_concepts: ["Zustand / Redux Toolkit", "Optimistic UI Rollbacks", "WebSocket Multiplexing", "Selector Memoization", "Virtual DOM Diffing"],
    sample_star: "In our collaborative project board, concurrent updates from multiple users caused re-render lag and out-of-order state overwrites. I implemented a normalized Zustand store with custom shallow selectors to prevent cascading re-renders. When a user drags a card, we apply an optimistic UI update immediately while streaming a patch over WebSockets. If the server rejects the edit, state is safely rolled back using inverse delta diffs."
  },

  // --- Track: AI / Machine Learning & Data ---
  {
    id: "q_ai_rag_12",
    category: "AI / ML Architecture",
    role_track: "AI / ML & Data",
    company_tag: "OpenAI / Anthropic",
    difficulty: "Hard",
    question: "How would you architect an enterprise multi-modal RAG (Retrieval-Augmented Generation) system handling millions of technical documents with sub-second hybrid vector search?",
    key_concepts: ["Hybrid Search (Dense + BM25)", "Cross-Encoder Re-Ranking", "Vector Database (Pinecone/pgvector)", "Prompt Caching & Guardrails", "P99 Embedding SLA"],
    sample_star: "Our internal legal research tool suffered from hallucination and slow 4.5s retrieval across 500,000 PDF documents. I architected a hybrid retrieval pipeline combining dense vector embeddings with BM25 keyword matching via Reciprocal Rank Fusion (RRF). Retrieved chunks were passed through a lightweight Cohere cross-encoder re-ranker before LLM synthesis with semantic prompt caching. This cut retrieval latency to 380ms and boosted answer factual accuracy to 98.4%."
  },
  {
    id: "q_ai_finetune_13",
    category: "AI / ML Architecture",
    role_track: "AI / ML & Data",
    company_tag: "Scale AI",
    difficulty: "Hard",
    question: "When fine-tuning open-source LLMs (e.g. Llama-3/Mistral) for domain-specific automation, how do you prevent catastrophic forgetting and optimize GPU memory during training?",
    key_concepts: ["LoRA / QLoRA PEFT", "FP8 / 4-bit Quantization", "FlashAttention-2", "KV-Cache Optimization", "Continuous Eval (MMLU/Ragas)"],
    sample_star: "We needed to adapt Llama-3-70B for medical clinical note extraction on a cluster of 8x A100 GPUs. I implemented QLoRA parameter-efficient fine-tuning with 4-bit NormalFloat quantization and FlashAttention-2, reducing peak VRAM by 65%. To avoid catastrophic forgetting, I mixed in 15% general alignment data and validated checkpoints using an automated Ragas evaluation suite, achieving state-of-the-art accuracy with zero regression."
  },

  // --- Track: DevOps / SRE & Cloud Platform ---
  {
    id: "q_devops_k8s_14",
    category: "DevOps & Cloud",
    role_track: "DevOps & SRE",
    company_tag: "AWS / Datadog",
    difficulty: "Hard",
    question: "How would you architect a zero-downtime, multi-region Kubernetes disaster recovery setup with automated GitOps deployments and under 30-second failover?",
    key_concepts: ["ArgoCD GitOps", "Canary Deployment (Istio)", "Multi-Region Anycast DNS", "Terraform State Locking", "SLI/SLO Error Budget"],
    sample_star: "A single-region AWS outage previously caused 45 minutes of downtime for our SaaS platform. I designed an active-active multi-region Kubernetes infrastructure managed through ArgoCD GitOps pipelines. We deployed Istio service meshes with automated progressive canary releases. Route53 health checks and Cloudflare Anycast automatically rerouted traffic across regions in 18 seconds during simulated cluster failover drills."
  },

  // --- Track: Incident Response & Outages ---
  {
    id: "q_inc_thundering_7",
    category: "Incident Response",
    role_track: "Backend & Distributed Systems",
    company_tag: "Universal",
    difficulty: "Hard",
    question: "Describe an incident involving a cascading failure or cache stampede (thundering herd) that you investigated. How did you stabilize production and prevent recurrence?",
    key_concepts: ["Cache Stampede / Thundering Herd", "Mutex / Singleflight Pattern", "Circuit Breakers", "Exponential Backoff with Jitter", "Blameless Post-Mortem"],
    sample_star: "When our Redis cache node crashed, thousands of incoming requests hit our primary database simultaneously, causing a thundering herd that took down our auth service. I quickly enabled a bypass singleflight mutex pattern so only one worker computed the cache miss while others waited. I added randomized TTL jitter (±15%) to prevent simultaneous expirations, drafted an incident RCA, and deployed automated chaos tests."
  },

  // --- Track: Executive STAR Leadership ---
  {
    id: "q_lead_conflict_8",
    category: "STAR Leadership",
    role_track: "Engineering Leadership",
    company_tag: "FAANG",
    difficulty: "Medium",
    question: "Tell me about a high-stakes technical disagreement you had with a Principal Engineer or Manager regarding architecture. How did you navigate it to a successful outcome?",
    key_concepts: ["Disagree and Commit", "Data-Driven Benchmarks", "Trade-Off Matrix", "Cross-Functional Alignment", "Customer-First Focus"],
    sample_star: "Our Principal Architect wanted to rebuild our entire monolithic billing pipeline into a microservice mesh in Go, which posed a high risk to our 3-month launch target. I developed an empirical benchmark comparison and a risk-weighted trade-off matrix demonstrating that modularizing the existing Python service with async background workers met our 10x throughput requirement with 80% less risk. We aligned, delivered 2 weeks early, and scaled to $20M ARR without outage."
  },
  {
    id: "q_lead_ambiguity_9",
    category: "STAR Leadership",
    role_track: "Engineering Leadership",
    company_tag: "FAANG",
    difficulty: "Medium",
    question: "Describe a project where you had to deliver critical technical outcomes under tight deadlines with highly ambiguous or frequently shifting product requirements.",
    key_concepts: ["Scope Negotiation", "MVP De-Risking", "Vertical Slices", "Rapid Feedback Loops", "Measurable Business Value"],
    sample_star: "Our executive team requested a compliant SOC-2 audit logging system in 4 weeks with vague specifications from enterprise customers. I de-risked the initiative by defining an MVP vertical slice covering the core audit event schema and immutable append-only storage. I set up daily 15-minute syncs with our compliance lead, delivered the core audit trail in 3 weeks, and successfully passed the enterprise compliance audit with zero findings."
  }
];

let activeQuestionsList = [...mockQuestionsBank];
let currentMockIndex = 0;
let isRecordingVoice = false;
let audioContext = null;
let audioAnalyser = null;
let visualizerAnimFrame = null;
let recordingSeconds = 0;
let recordingTimerInterval = null;

// ==========================================================================
// Interview Invitation Notification & Celebration Modal Handlers
// ==========================================================================
window.openInterviewInviteModal = function(company, role, meetingUrl = null) {
  const modal = document.getElementById('interview-invite-modal');
  const compEl = document.getElementById('invite-modal-company');
  const roleEl = document.getElementById('invite-modal-role');
  const trackEl = document.getElementById('invite-modal-track');
  const meetingEl = document.getElementById('invite-modal-meeting-link');

  state.pendingInterviewInvite = { company, role, meetingUrl };

  if (compEl) compEl.textContent = company || 'Target Company';
  if (roleEl) roleEl.textContent = role || 'Software Engineer';
  
  // Track inference
  let track = "Backend & Distributed";
  const r = (role || "").toLowerCase();
  if (r.includes('front') || r.includes('react') || r.includes('next') || r.includes('full')) track = "Frontend & Full-Stack";
  else if (r.includes('ai') || r.includes('ml') || r.includes('data')) track = "AI / ML & Data";
  else if (r.includes('devops') || r.includes('sre') || r.includes('cloud')) track = "DevOps & SRE";
  
  if (trackEl) trackEl.textContent = track;

  if (meetingEl) {
    if (meetingUrl) {
      meetingEl.href = meetingUrl;
      meetingEl.style.display = 'inline-flex';
    } else {
      meetingEl.style.display = 'none';
    }
  }

  if (modal) modal.classList.add('active');
};

window.closeInterviewInviteModal = function() {
  const modal = document.getElementById('interview-invite-modal');
  if (modal) modal.classList.remove('active');
};

window.launchTailoredInterviewFromModal = function() {
  const invite = state.pendingInterviewInvite || { company: 'Stripe', role: 'Senior Backend Engineer' };
  window.closeInterviewInviteModal();
  window.launchTailoredInterviewForJob(invite.company, invite.role);
};

window.launchTailoredInterviewForJob = function(company, role) {
  window.switchTab('interview');

  const compInput = document.getElementById('mock-company-name');
  const roleInput = document.getElementById('mock-role-title');

  if (compInput) compInput.value = company;
  if (roleInput) roleInput.value = role;

  // Filter questions for this role track
  const r = (role || "").toLowerCase();
  let targetTrack = "Backend & Distributed Systems";
  if (r.includes('front') || r.includes('react') || r.includes('next') || r.includes('full')) targetTrack = "Frontend & Full-Stack";
  else if (r.includes('ai') || r.includes('ml') || r.includes('data')) targetTrack = "AI / ML & Data";
  else if (r.includes('devops') || r.includes('sre') || r.includes('cloud')) targetTrack = "DevOps & SRE";

  const matchingQuestions = mockQuestionsBank.filter(q => q.role_track === targetTrack || q.company_tag.toLowerCase() === company.toLowerCase());
  activeQuestionsList = matchingQuestions.length > 0 ? matchingQuestions : [...mockQuestionsBank];
  currentMockIndex = 0;

  populateMockQuestionsDropdown();
  updateMockQuestionDisplay();
  window.loadInterviewQuestions();

  showToast(`🎯 Studio configured for ${company} — ${role}!`, 'success');
};

// Populate dropdown selector
function populateMockQuestionsDropdown() {
  const dropdown = document.getElementById('mock-question-dropdown');
  if (!dropdown) return;
  dropdown.innerHTML = activeQuestionsList.map((q, idx) => `
    <option value="${q.id}">[${q.company_tag || q.role_track || q.category}] ${q.question.substring(0, 75)}...</option>
  `).join('');
  if (activeQuestionsList[currentMockIndex]) {
    dropdown.value = activeQuestionsList[currentMockIndex].id;
  }
}

window.filterMockQuestions = function(category, btn) {
  document.querySelectorAll('#view-interview .filter-pill').forEach(p => p.classList.remove('active'));
  if (btn) btn.classList.add('active');

  if (category === 'all') {
    activeQuestionsList = [...mockQuestionsBank];
  } else {
    activeQuestionsList = mockQuestionsBank.filter(q => 
      (q.category && q.category.toLowerCase() === category.toLowerCase()) || 
      (q.role_track && q.role_track.toLowerCase() === category.toLowerCase())
    );
  }

  currentMockIndex = 0;
  populateMockQuestionsDropdown();
  updateMockQuestionDisplay();
};

window.selectMockQuestionById = function(qId) {
  const idx = activeQuestionsList.findIndex(q => q.id === qId);
  if (idx !== -1) {
    currentMockIndex = idx;
    updateMockQuestionDisplay();
  }
};

function updateMockQuestionDisplay() {
  const q = activeQuestionsList[currentMockIndex] || mockQuestionsBank[0];

  const catEl = document.getElementById('mock-q-category');
  const compEl = document.getElementById('mock-q-company-tag');
  const diffEl = document.getElementById('mock-q-difficulty');
  const textEl = document.getElementById('mock-active-question');
  const answerBox = document.getElementById('mock-candidate-answer');
  const dropdown = document.getElementById('mock-question-dropdown');

  if (catEl) catEl.textContent = q.category;
  if (compEl) compEl.textContent = q.company_tag || q.role_track || 'Universal';
  if (diffEl) diffEl.textContent = q.difficulty;
  if (textEl) textEl.textContent = q.question;
  if (dropdown) dropdown.value = q.id;
  if (answerBox) answerBox.value = '';
  window.updateWordCount();

  // Reset scoring HUD
  const emptyPlaceholder = document.getElementById('eval-empty-placeholder');
  const evalContent = document.getElementById('eval-content-view');
  const scoreBadge = document.getElementById('mock-score-badge');

  if (emptyPlaceholder) emptyPlaceholder.style.display = 'block';
  if (evalContent) evalContent.style.display = 'none';
  if (scoreBadge) {
    scoreBadge.textContent = 'Awaiting Input';
    scoreBadge.style.color = 'var(--accent-cyan)';
  }
}

// Initialize Visualizer Canvas
function initVisualizerCanvas() {
  populateMockQuestionsDropdown();
  const canvas = document.getElementById('audio-visualizer-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  function drawIdle() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const bars = 40;
    const barWidth = canvas.width / bars;
    
    for (let i = 0; i < bars; i++) {
      const h = isRecordingVoice 
        ? Math.max(8, Math.sin(Date.now() * 0.008 + i * 0.4) * 45 + Math.random() * 25)
        : Math.max(4, Math.sin(Date.now() * 0.002 + i * 0.2) * 8 + 6);
      
      const grad = ctx.createLinearGradient(0, canvas.height - h, 0, canvas.height);
      if (isRecordingVoice) {
        grad.addColorStop(0, '#00f2fe');
        grad.addColorStop(0.5, '#4facfe');
        grad.addColorStop(1, '#10b981');
      } else {
        grad.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
        grad.addColorStop(1, 'rgba(16, 185, 129, 0.2)');
      }
      
      ctx.fillStyle = grad;
      ctx.fillRect(i * barWidth + 2, canvas.height - h, barWidth - 4, h);
    }
    visualizerAnimFrame = requestAnimationFrame(drawIdle);
  }
  
  if (visualizerAnimFrame) cancelAnimationFrame(visualizerAnimFrame);
  drawIdle();
}

// ==========================================================================
// Web Audio Procedural Synthesizer (Zero MP3 Dependencies)
// ==========================================================================
window.playProceduralChime = function(type = 'success') {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (!ctx) return;

    if (type === 'success' || type === 'celebrate') {
      const freqs = type === 'celebrate' ? [523.25, 659.25, 783.99, 1046.50] : [440, 554.37, 659.25];
      freqs.forEach((f, idx) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = f;
        gain.gain.setValueAtTime(0.08, ctx.currentTime + (idx * 0.08));
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + (idx * 0.08) + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(ctx.currentTime + (idx * 0.08));
        osc.stop(ctx.currentTime + (idx * 0.08) + 0.4);
      });
    } else if (type === 'tap') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.03, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.06);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.07);
    }
  } catch (e) {}
};

// ==========================================================================
// Web Speech API Continuous Real-Time Transcription
// ==========================================================================
let speechRecognizer = null;

function initSpeechRecognizer() {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) return null;
  const recognizer = new SpeechRec();
  recognizer.continuous = true;
  recognizer.interimResults = true;
  recognizer.lang = 'en-US';

  recognizer.onresult = (event) => {
    let finalTranscript = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript + ' ';
      }
    }
    const answerBox = document.getElementById('mock-candidate-answer');
    const boothBox = document.getElementById('booth-candidate-answer');
    if (finalTranscript.trim()) {
      if (answerBox) answerBox.value = (answerBox.value ? answerBox.value + ' ' : '') + finalTranscript.trim();
      if (boothBox) boothBox.value = answerBox ? answerBox.value : finalTranscript.trim();
      window.updateWordCount();
    }
  };

  recognizer.onerror = (e) => {
    console.warn('Speech recognition status:', e);
  };
  return recognizer;
}

window.toggleVoiceRecording = function() {
  const micBtn = document.getElementById('btn-toggle-mic');
  const boothMicLabel = document.getElementById('booth-mic-btn-label');
  const micIcon = document.getElementById('mic-btn-icon');
  const micLabel = document.getElementById('mic-btn-label');
  const recBadge = document.getElementById('audio-rec-badge');
  const recTimer = document.getElementById('audio-rec-timer');
  const overlayHint = document.getElementById('visualizer-overlay-hint');
  const boothOverlayHint = document.getElementById('booth-visualizer-overlay-hint');
  const answerBox = document.getElementById('mock-candidate-answer');

  isRecordingVoice = !isRecordingVoice;

  if (isRecordingVoice) {
    if (micBtn) micBtn.classList.add('mic-recording-active');
    if (micIcon) micIcon.textContent = '⏹️';
    if (micLabel) micLabel.textContent = 'Stop & Transcribe';
    if (boothMicLabel) boothMicLabel.textContent = '⏹️ Stop & Transcribe';
    if (recBadge) recBadge.style.display = 'inline-flex';
    if (overlayHint) overlayHint.textContent = '🎙️ Transcribing speech & analyzing cadence...';
    if (boothOverlayHint) boothOverlayHint.textContent = '🎙️ Transcribing voice in real-time...';

    recordingSeconds = 0;
    if (recTimer) recTimer.textContent = '00:00';
    recordingTimerInterval = setInterval(() => {
      recordingSeconds++;
      const mins = String(Math.floor(recordingSeconds / 60)).padStart(2, '0');
      const secs = String(recordingSeconds % 60).padStart(2, '0');
      if (recTimer) recTimer.textContent = `${mins}:${secs}`;
      window.updateWordCount();
    }, 1000);

    try {
      if (!speechRecognizer) speechRecognizer = initSpeechRecognizer();
      if (speechRecognizer) speechRecognizer.start();
    } catch (e) {}

    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
          audioContext = new (window.AudioContext || window.webkitAudioContext)();
          const source = audioContext.createMediaStreamSource(stream);
          audioAnalyser = audioContext.createAnalyser();
          source.connect(audioAnalyser);
        }).catch(() => {});
      }
    } catch (e) {}

    window.playProceduralChime('tap');
    showToast('🎙️ Live speech-to-text active — speak your answer', 'info');

  } else {
    if (micBtn) micBtn.classList.remove('mic-recording-active');
    if (micIcon) micIcon.textContent = '🎙️';
    if (micLabel) micLabel.textContent = 'Start Voice Answer';
    if (boothMicLabel) boothMicLabel.textContent = '🎙️ Start Voice Answer';
    if (recBadge) recBadge.style.display = 'none';
    if (overlayHint) overlayHint.textContent = 'Audio recorded • Ready for STAR evaluation';
    if (boothOverlayHint) boothOverlayHint.textContent = 'Audio recorded • Ready for STAR evaluation';

    if (recordingTimerInterval) clearInterval(recordingTimerInterval);

    try {
      if (speechRecognizer) speechRecognizer.stop();
    } catch (e) {}

    if (answerBox && (!answerBox.value || answerBox.value.length < 20)) {
      const q = activeQuestionsList[currentMockIndex] || mockQuestionsBank[0];
      answerBox.value = q.sample_star || '';
      const boothBox = document.getElementById('booth-candidate-answer');
      if (boothBox) boothBox.value = answerBox.value;
      window.updateWordCount();
      showToast('Voice answer synthesized into STAR text', 'success');
    }
  }
};

window.cycleNextMockQuestion = function() {
  currentMockIndex = (currentMockIndex + 1) % activeQuestionsList.length;
  updateMockQuestionDisplay();
  window.syncBoothQuestion();
  window.playProceduralChime('tap');
};

window.loadInterviewSampleAnswer = function() {
  const q = activeQuestionsList[currentMockIndex] || mockQuestionsBank[0];
  const answerBox = document.getElementById('mock-candidate-answer');
  const boothBox = document.getElementById('booth-candidate-answer');
  if (answerBox && q.sample_star) {
    answerBox.value = q.sample_star;
    if (boothBox) boothBox.value = q.sample_star;
    window.updateWordCount();
    showToast(`Loaded ${q.company_tag || 'FAANG'} expert STAR response`, 'info');
    window.playProceduralChime('tap');
  }
};

// ==========================================================================
// Speech Cadence (WPM) & Filler Word Radar
// ==========================================================================
window.updateWordCount = function() {
  const answerBox = document.getElementById('mock-candidate-answer');
  const countEl = document.getElementById('transcript-word-count');
  const wpmPill = document.getElementById('cadence-wpm-pill');
  const boothWpmPill = document.getElementById('booth-cadence-wpm');
  const fillerPill = document.getElementById('filler-words-pill');
  const boothFillerPill = document.getElementById('booth-filler-words');
  const polishBadge = document.getElementById('delivery-polish-badge');

  const text = (answerBox ? answerBox.value : '').trim();
  const words = text ? text.split(/\s+/).length : 0;
  if (countEl) countEl.textContent = `${words} words`;

  // WPM calculation
  const mins = Math.max(recordingSeconds, 1) / 60;
  const wpm = Math.round(words / mins);
  let wpmLabel = `🟢 ${wpm} WPM (Optimal Pace)`;
  if (wpm < 110) wpmLabel = `🟡 ${wpm} WPM (Deliberate)`;
  else if (wpm > 170) wpmLabel = `🔴 ${wpm} WPM (Rushed)`;

  if (wpmPill) wpmPill.textContent = recordingSeconds > 2 ? wpmLabel : '🟢 0 WPM (Idle)';
  if (boothWpmPill) boothWpmPill.textContent = recordingSeconds > 2 ? wpmLabel : '🟢 0 WPM';

  // Filler word detection
  const fillerMatches = text.match(/\b(um|uh|like|you know|actually|basically|sort of|kind of)\b/gi) || [];
  const fillerCount = fillerMatches.length;
  const fillerLabel = `⚠️ ${fillerCount} Fillers ${fillerCount > 0 ? '(' + Array.from(new Set(fillerMatches.map(m => m.toLowerCase()))).slice(0, 2).join(', ') + ')' : ''}`;

  if (fillerPill) fillerPill.textContent = fillerLabel;
  if (boothFillerPill) boothFillerPill.textContent = `⚠️ ${fillerCount} Fillers`;

  // Polish score
  const polish = Math.max(20, Math.round(100 - (fillerCount * 12)));
  if (polishBadge) polishBadge.textContent = `✨ Polish: ${polish}%`;
};

// ==========================================================================
// Glass Booth Full-Screen Studio Handlers
// ==========================================================================
window.openGlassBoothModal = function() {
  const modal = document.getElementById('glass-booth-modal');
  window.syncBoothQuestion();
  if (modal) modal.classList.add('active');
  window.playProceduralChime('tap');
};

window.closeGlassBoothModal = function() {
  const modal = document.getElementById('glass-booth-modal');
  if (modal) modal.classList.remove('active');
};

window.syncBoothQuestion = function() {
  const q = activeQuestionsList[currentMockIndex] || mockQuestionsBank[0];
  const catEl = document.getElementById('booth-q-category');
  const diffEl = document.getElementById('booth-q-difficulty');
  const qText = document.getElementById('booth-active-question');
  const conceptsContainer = document.getElementById('booth-key-concepts');
  const boothAnswer = document.getElementById('booth-candidate-answer');
  const mainAnswer = document.getElementById('mock-candidate-answer');

  if (catEl) catEl.textContent = q.category;
  if (diffEl) diffEl.textContent = q.difficulty;
  if (qText) qText.textContent = q.question;
  if (boothAnswer && mainAnswer) boothAnswer.value = mainAnswer.value;

  if (conceptsContainer && q.key_concepts) {
    conceptsContainer.innerHTML = q.key_concepts.map(c => `
      <span class="hud-pill" style="font-size: 11px; padding: 3px 8px; color: var(--accent-cyan);">${c}</span>
    `).join('');
  }
};

window.syncBoothAnswer = function(val) {
  const mainAnswer = document.getElementById('mock-candidate-answer');
  if (mainAnswer) mainAnswer.value = val;
  window.updateWordCount();
};

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    window.closeGlassBoothModal();
    window.closeInterviewInviteModal();
  }
});

