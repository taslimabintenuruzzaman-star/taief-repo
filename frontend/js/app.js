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
  lang: "en-US",
  on: false,
  buffer: "",
  sendTimer: null,
};

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

async function unlockMic() {
  if (!navigator.mediaDevices?.getUserMedia) {
    hint("No microphone API here. Use Chrome, or type.");
    return false;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((t) => t.stop());
    return true;
  } catch (err) {
    hint("Allow microphone when the browser asks. If nothing pops up, open preview in a new tab.");
    return false;
  }
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

async function toggleListen() {
  if (voice.on) {
    voice.on = false;
    try {
      voice.rec && voice.rec.stop();
    } catch {
      /* ignore */
    }
    setListening(false);
    commitVoice();
    return;
  }
  if (!RecEngine()) {
    hint("This browser cannot do speech-to-text (common in Firefox / locked iframes). Type, or open in Chrome.");
    $("cmd").focus();
    return;
  }
  const ok = await unlockMic();
  if (!ok) return;
  const rec = makeRec();
  rec.lang = voice.lang;
  voice.buffer = "";
  $("cmd").value = "";
  try {
    rec.start();
    setListening(true);
  } catch (err) {
    hint("Could not start listener: " + (err.message || err));
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
  $("mic").onclick = (e) => {
    e.preventDefault();
    toggleListen();
  };
  $("orb").onclick = (e) => {
    e.preventDefault();
    toggleListen();
  };
  boot();
}

main();
