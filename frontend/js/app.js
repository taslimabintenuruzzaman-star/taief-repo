const $ = (id) => document.getElementById(id);

const bootLines = [
  "SHOTTA CORE ................... SEATED",
  "CURSED ENERGY ................. OPEN",
  "MEMORY LATTICE ................ OK",
  "TOOL BUS / PUBLIC-APIS ........ OK",
  "DOMAIN EXPANSION .............. STANDBY",
  "VOICE INTERFACE ............... LISTENING",
  "KNOW YOUR PLACE, FOOL.",
];

function speak(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-GB";
  u.rate = 0.92;
  u.pitch = 0.7;
  const voices = window.speechSynthesis.getVoices();
  const pick =
    voices.find((v) => /en-GB/i.test(v.lang) && /male|daniel|george|rishi/i.test(v.name)) ||
    voices.find((v) => /en-GB/i.test(v.lang)) ||
    voices.find((v) => /en/i.test(v.lang));
  if (pick) u.voice = pick;
  window.speechSynthesis.speak(u);
}

window.speechSynthesis?.addEventListener("voiceschanged", () => {});

function typeText(el, text) {
  el.textContent = "";
  let i = 0;
  const tick = () => {
    el.textContent = text.slice(0, i++);
    if (i <= text.length) requestAnimationFrame(tick);
  };
  tick();
}

function addLog(role, text, mood) {
  const box = $("log");
  const div = document.createElement("div");
  div.className = `entry ${role} ${mood || ""}`;
  div.textContent = `${role === "user" ? "FOOL" : "SHOTTA"} // ${text}`;
  box.prepend(div);
}

function setPipeline(steps) {
  const items = [...$("pipeline").children];
  items.forEach((li) => li.classList.remove("active"));
  if (!steps?.length) return;
  steps.forEach((step, idx) => {
    if (!items[idx]) return;
    items[idx].textContent = `${step.stage}${step.detail ? " — " + step.detail : ""}`;
    setTimeout(() => items[idx].classList.add("active"), 90 * idx);
  });
}

function meter(barId, valId, pct, suffix = "%") {
  const p = Math.max(0, Math.min(100, pct || 0));
  $(barId).style.width = `${p}%`;
  $(valId).textContent = `${p.toFixed(0)}${suffix}`;
}

async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const t = data.time;
    $("clock").textContent = t.time;
    $("date-line").textContent = `${t.date}  ·  DHAKA`;
    const s = data.system;
    meter("cpu-bar", "cpu-val", s.cpu_percent);
    meter("mem-bar", "mem-val", s.memory_percent);
    meter("dsk-bar", "dsk-val", s.disk_percent);
    $("sys-kv").innerHTML = `
      <div><span>HOST</span><span>${s.host}</span></div>
      <div><span>OS</span><span>${s.platform}</span></div>
      <div><span>RAM</span><span>${s.memory_used_gb}/${s.memory_total_gb} GB</span></div>
    `;
    $("link-pill").textContent = "UPLINK LIVE";
    try {
      const b = await fetch("/api/brain").then((r) => r.json());
      const pill = $("brain-pill");
      if (pill) {
        pill.textContent = b.using_api_key_brain ? "BRAIN: CLOUD KEY" : "BRAIN: LOCAL RULES";
      }
    } catch {
      /* ignore */
    }
  } catch {
    $("link-pill").textContent = "UPLINK WEAK";
  }
}

async function ask(message) {
  if (!message.trim()) return;
  addLog("user", message);
  $("orb-state").textContent = "THINKING";
  setPipeline([
    { stage: "PERCEIVE" },
    { stage: "RECALL" },
    { stage: "PLAN" },
    { stage: "ACT" },
    { stage: "RESPOND" },
  ]);
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: "hud" }),
    });
    const data = await res.json();
    setPipeline(data.pipeline);
    typeText($("spoken"), data.reply);
    addLog("moros", data.reply, data.mood);
    speak(data.reply);
    applyHud(data.hud);
  } catch {
    typeText($("spoken"), "Command deck lost the cognition bus. Retry.");
  } finally {
    $("orb-state").textContent = "STANDBY";
  }
}

const voice = {
  rec: null,
  lang: "en-US",
  on: false,
  buffer: "",
  sendTimer: null,
  media: null,
  chunks: [],
  booth: null,
};

function framed() {
  try {
    return window.self !== window.top;
  } catch {
    return true;
  }
}

function hint(msg) {
  const el = $("voice-hint");
  if (el) el.textContent = msg;
}

function setListening(on) {
  voice.on = on;
  $("orb").classList.toggle("listening", on);
  $("mic").classList.toggle("hot", on);
  $("mic").textContent = on ? "STOP" : "MIC";
  $("waveform").hidden = !on;
  $("orb-state").textContent = on ? "LISTENING" : "STANDBY";
}

function RecEngine() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function wireRec(rec) {
  rec.lang = voice.lang;
  rec.interimResults = true;
  rec.continuous = true;
  rec.maxAlternatives = 3;
  rec.onstart = () => {
    setListening(true);
    window.speechSynthesis?.cancel();
    hint("I am listening. Speak. Click STOP when done.");
    $("spoken").textContent = "…listening…";
  };
  rec.onerror = (ev) => {
    const err = ev.error;
    if (err === "not-allowed") {
      hint("Microphone blocked. Click Allow, or open this preview in a new tab (Chrome).");
      setListening(false);
    } else if (err === "no-speech") {
      hint("Heard silence. Keep talking — I am still listening.");
    } else if (err === "network") {
      hint("Speech needs Chrome + internet. Type below if this preview iframe blocks the mic.");
    } else if (err !== "aborted") {
      hint(`Voice error: ${err}. You can type instead.`);
    }
  };
  rec.onresult = (ev) => {
    let live = "";
    let finals = [];
    for (let i = 0; i < ev.results.length; i++) {
      const t = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) finals.push(t);
      else live += t;
    }
    const heard = (finals.join(" ") + " " + live).trim();
    voice.buffer = heard;
    $("cmd").value = heard;
    $("spoken").textContent = heard || "…listening…";
    hint("Heard: " + heard);
    clearTimeout(voice.sendTimer);
    if (finals.length && !live) {
      voice.sendTimer = setTimeout(() => commitVoice(), 900);
    }
  };
  rec.onend = () => {
    if (voice.on) {
      try {
        rec.start();
      } catch {
        setTimeout(() => {
          if (voice.on) {
            try {
              rec.start();
            } catch {
              /* give up */
            }
          }
        }, 250);
      }
    }
  };
}

function makeRec() {
  const Engine = RecEngine();
  if (!Engine) return null;
  const rec = new Engine();
  wireRec(rec);
  voice.rec = rec;
  return rec;
}

function openMicBooth() {
  const url = `/voice?lang=${encodeURIComponent(voice.lang)}`;
  let booth = null;
  try {
    booth = window.open(url, "moros-mic", "popup=yes,width=440,height=740");
  } catch {
    booth = null;
  }
  voice.booth = booth;
  const banner = $("mic-banner");
  if (!booth) {
    hint("Popup blocked. Click OPEN MIC WINDOW (allow popups), then TAP TO SPEAK there.");
    if (banner) banner.hidden = false;
    return false;
  }
  try {
    booth.focus();
  } catch {
    /* ignore */
  }
  hint("Mic window opened. Click TAP TO SPEAK, Allow microphone, then talk.");
  setListening(true);
  if (banner) banner.hidden = false;
  return true;
}

function onMicClick(e) {
  e.preventDefault();
  e.stopPropagation();
  if (voice.on && !(voice.booth && !voice.booth.closed)) {
    toggleListen();
    return;
  }
  if (voice.booth && !voice.booth.closed) {
    try {
      voice.booth.focus();
    } catch {
      /* ignore */
    }
    hint("Speak in the MIC WINDOW. Click TAP TO SPEAK if it is waiting.");
    return;
  }
  if (framed()) {
    openMicBooth();
    return;
  }
  toggleListen();
}

function commitVoice() {
  clearTimeout(voice.sendTimer);
  const said = (voice.buffer || $("cmd").value || "").trim();
  voice.buffer = "";
  if (!said) {
    hint("I did not catch words. Click MIC, wait for LISTENING, then speak clearly.");
    return;
  }
  $("cmd").value = "";
  ask(said);
}

async function startTape() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
  const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
  voice.chunks = [];
  rec.ondataavailable = (e) => {
    if (e.data.size) voice.chunks.push(e.data);
  };
  rec.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    setListening(false);
    const blob = new Blob(voice.chunks, { type: rec.mimeType || "audio/webm" });
    if (blob.size < 800) {
      hint("Recording too short. Type in the box — preview iframes often block speech.");
      $("cmd").focus();
      return;
    }
    hint("Sending voice to server…");
    const fd = new FormData();
    fd.append("file", blob, "speech.webm");
    try {
      const res = await fetch("/api/stt", { method: "POST", body: fd });
      const data = await res.json();
      if (data.text) {
        hint("Heard: " + data.text);
        ask(data.text);
      } else {
        hint((data.error || "No speech key") + " — type below. This preview cannot hear you without Chrome STT or a Whisper key.");
        $("cmd").focus();
      }
    } catch {
      hint("STT failed. Type your message and press Enter.");
      $("cmd").focus();
    }
  };
  voice.media = rec;
  rec.start();
  setListening(true);
  hint("Recording… click STOP when you finish speaking.");
}

async function toggleListen() {
  if (voice.on) {
    voice.on = false;
    try {
      voice.rec && voice.rec.stop();
    } catch {
      /* ignore */
    }
    if (voice.media && voice.media.state !== "inactive") {
      voice.media.stop();
      voice.media = null;
      return;
    }
    setListening(false);
    commitVoice();
    return;
  }
  const ok = await unlockMic();
  if (!ok) {
    $("cmd").focus();
    return;
  }
  if (RecEngine()) {
    const rec = makeRec();
    rec.lang = voice.lang;
    voice.buffer = "";
    $("cmd").value = "";
    try {
      rec.start();
      setListening(true);
      return;
    } catch (err) {
      hint("Browser STT failed (" + (err.message || err) + "). Trying recorder…");
    }
  }
  try {
    await startTape();
  } catch {
    hint("Mic blocked in this preview. Type your words in the bar and press Enter.");
    $("cmd").focus();
  }
}

function particles() {
  const c = $("field");
  const ctx = c.getContext("2d");
  const dots = Array.from({ length: 70 }, () => ({
    x: Math.random(),
    y: Math.random(),
    v: 0.0003 + Math.random() * 0.0008,
    r: Math.random() * 1.4 + 0.4,
  }));
  const loop = () => {
    c.width = innerWidth;
    c.height = innerHeight;
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.fillStyle = "rgba(0,232,255,0.55)";
    dots.forEach((d) => {
      d.y -= d.v;
      if (d.y < 0) d.y = 1;
      ctx.beginPath();
      ctx.arc(d.x * c.width, d.y * c.height, d.r, 0, Math.PI * 2);
      ctx.fill();
    });
    requestAnimationFrame(loop);
  };
  loop();
}

async function boot() {
  const log = $("boot-log");
  for (let i = 0; i < bootLines.length; i++) {
    const li = document.createElement("li");
    li.textContent = `> ${bootLines[i]}`;
    log.appendChild(li);
    $("boot-fill").style.width = `${((i + 1) / bootLines.length) * 100}%`;
    await new Promise((r) => setTimeout(r, 280));
  }
  await new Promise((r) => setTimeout(r, 420));
  $("boot").style.opacity = "0";
  $("boot").style.transition = "opacity 0.6s";
  $("hud").hidden = false;
  setTimeout(() => $("boot").remove(), 650);
  const intro =
    "Tch. Digital shotta online. Know your place, fool. The king is seated. What do you want?";
  typeText($("spoken"), intro);
  speak(intro);
  refreshFeeds();
}

function applyHud(hud) {
  if (!hud) return;
  if (hud.weather?.temperature_c != null) {
    $("wx-temp").textContent = `${hud.weather.temperature_c}°C`;
    $("wx-desc").textContent = `${hud.weather.description}  ·  humidity ${hud.weather.humidity}%`;
  }
  if (hud.crypto?.prices?.bitcoin?.usd) {
    $("btc-val").textContent = `$${hud.crypto.prices.bitcoin.usd}`;
  }
  if (hud.fx?.usd_bdt) $("fx-val").textContent = hud.fx.usd_bdt;
  if (hud.prayer?.timings?.Fajr) $("fajr-val").textContent = hud.prayer.timings.Fajr;
  if (hud.quote?.quote) $("quote-line").textContent = `“${hud.quote.quote}” — ${hud.quote.author}`;
  const img = $("intel-img");
  if (hud.image) {
    img.src = hud.image;
    img.hidden = false;
  }
}

async function refreshFeeds() {
  try {
    const res = await fetch("/api/feeds");
    const data = await res.json();
    applyHud({
      weather: data.weather && !data.weather.error ? data.weather : null,
      crypto: data.crypto && !data.crypto.error ? data.crypto : null,
      fx: data.fx && !data.fx.error ? data.fx : null,
      prayer: data.prayer && !data.prayer.error ? data.prayer : null,
      quote: data.quote && !data.quote.error ? data.quote : null,
    });
  } catch {
    /* optional */
  }
}

function main() {
  particles();
  refreshStatus();
  setInterval(refreshStatus, 4000);
  setInterval(refreshFeeds, 120000);
  $("send").onclick = () => {
    const v = $("cmd").value;
    $("cmd").value = "";
    ask(v);
  };
  $("cmd").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const v = $("cmd").value;
      $("cmd").value = "";
      ask(v);
    }
  });
  if ($("lang")) {
    $("lang").textContent = "EN";
    $("lang").onclick = () => {
      voice.lang = voice.lang === "bn-BD" ? "en-US" : "bn-BD";
      if (voice.rec) voice.rec.lang = voice.lang;
      $("lang").textContent = voice.lang === "bn-BD" ? "BN" : "EN";
      hint(voice.lang === "bn-BD" ? "Bangla speech on. Click MIC, then speak." : "English speech on. Click MIC, then speak.");
    };
  }
  $("mic").onclick = onMicClick;
  $("orb").onclick = onMicClick;
  if ($("mic-window")) {
    $("mic-window").addEventListener("click", () => {
      hint("Mic window opening. Click TAP TO SPEAK, Allow microphone, then talk.");
      setListening(true);
    });
  }
  window.addEventListener("message", (ev) => {
    if (ev.origin !== location.origin) return;
    const data = ev.data || {};
    if (data.type !== "moros-voice") return;
    if (data.event === "interim" && data.text) {
      voice.buffer = data.text;
      $("cmd").value = data.text;
      $("spoken").textContent = data.text;
      hint("Heard: " + data.text);
      setListening(true);
    }
    if (data.event === "final" && data.text) {
      voice.buffer = data.text;
      $("cmd").value = data.text;
      setListening(false);
      commitVoice();
    }
    if (data.event === "status" && data.text) hint(data.text);
    if (data.event === "closed") setListening(false);
  });
  if (framed()) {
    const banner = $("mic-banner");
    if (banner) banner.hidden = false;
    hint("Preview iframe blocks the mic. Click MIC or OPEN MIC WINDOW, Allow, then speak.");
  }
  boot();
}

main();
