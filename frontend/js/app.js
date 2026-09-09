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
  lang: "bn-BD",
  holding: false,
  armed: false,
  stream: null,
};

function hint(msg) {
  const el = $("voice-hint");
  if (el) el.textContent = msg;
}

function setListening(on) {
  $("orb").classList.toggle("listening", on);
  $("mic").classList.toggle("hot", on);
  $("waveform").hidden = !on;
  $("orb-state").textContent = on ? "LISTENING" : "STANDBY";
}

async function unlockMic() {
  if (!navigator.mediaDevices?.getUserMedia) {
    hint("This browser has no microphone API. Chrome খুলো, বা টাইপ করো.");
    return false;
  }
  try {
    if (!voice.stream) {
      voice.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    }
    voice.armed = true;
    return true;
  } catch (err) {
    const name = err?.name || "denied";
    if (name === "NotAllowedError" || name === "PermissionDeniedError") {
      hint("Microphone blocked. Address bar এ Allow চাপো, বা preview কে new tab-এ খোলো.");
    } else if (name === "NotFoundError") {
      hint("কোনো মাইক পাইনি. হেডফোন/মাইক লাগাও.");
    } else {
      hint(`Mic error: ${name}. Type in the bar instead.`);
    }
    return false;
  }
}

function initVoice() {
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Rec) {
    hint("Speech engine missing (Firefox/iframe). Chrome/Edge use করো, বা টাইপ করো.");
    return null;
  }
  const rec = new Rec();
  rec.lang = voice.lang;
  rec.interimResults = true;
  rec.continuous = true;
  rec.maxAlternatives = 1;
  rec.onstart = () => {
    setListening(true);
    hint(voice.lang === "bn-BD" ? "শুনছি… Bangla-এ কথা বলো." : "Listening… speak now.");
  };
  rec.onerror = (ev) => {
    const err = ev.error;
    if (err === "not-allowed") hint("Mic permission denied. Allow microphone, then hold MIC.");
    else if (err === "no-speech") hint("কিছু শুনিনি. MIC চেপে ধরে আবার বলো.");
    else if (err === "audio-capture") hint("মাইক ক্যাপচার ব্যর্থ. Device check করো.");
    else if (err === "network") hint("Speech network error. Internet/Chrome লাগবে.");
    else hint(`Voice error: ${err}`);
  };
  rec.onresult = (ev) => {
    let finalTxt = "";
    let live = "";
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const t = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) finalTxt += t;
      else live += t;
    }
    const shown = (finalTxt || live).trim();
    if (shown) $("cmd").value = shown;
    if (finalTxt.trim()) {
      $("cmd").value = finalTxt.trim();
      hint(`Heard: ${finalTxt.trim()}`);
    }
  };
  rec.onend = () => {
    setListening(false);
    if (voice.holding) {
      try {
        rec.start();
      } catch {
        /* already started */
      }
    }
  };
  voice.rec = rec;
  return rec;
}

async function startListen() {
  const rec = voice.rec || initVoice();
  if (!rec) return;
  const ok = await unlockMic();
  if (!ok) return;
  rec.lang = voice.lang;
  voice.holding = true;
  try {
    rec.start();
  } catch {
    /* InvalidStateError = already running */
  }
}

function stopListen() {
  voice.holding = false;
  const rec = voice.rec;
  const said = ($("cmd").value || "").trim();
  try {
    rec && rec.stop();
  } catch {
    /* ignore */
  }
  setListening(false);
  if (said) {
    $("cmd").value = "";
    ask(said);
  } else {
    hint("কিছু ধরা পড়েনি. MIC চেপে ধরে স্পষ্ট করে বলো, বা টাইপ করো.");
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
  const rec = initVoice();
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
  const listen = () => rec && rec.start();
  $("mic").onclick = listen;
  $("orb").onclick = listen;
  boot();
}

main();
