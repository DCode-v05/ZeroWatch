/**
 * ZeroWatch Browser SDK — IIFE, zero dependencies
 * ECDSA P-256 device binding + fingerprint + fetch interceptor + signal collection
 */
(function () {
  "use strict";

  const DB_NAME = "ZeroWatchKeys";
  const STORE_NAME = "keys";
  const KEY_ID = "device-signing-key";
  const SIGNAL_INTERVAL = 2000; // 2 seconds

  let keyPair = null;
  let sessionId = null;
  let deviceFingerprint = null;
  let signalBuffer = [];
  let keystrokes = [];
  let mousePositions = [];

  // ─── 1. ECDSA Key Management (IndexedDB) ───
  function openDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE_NAME);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function loadOrCreateKey() {
    const db = await openDB();

    // Try loading existing key
    const existing = await new Promise((resolve) => {
      const tx = db.transaction(STORE_NAME, "readonly");
      const req = tx.objectStore(STORE_NAME).get(KEY_ID);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    });

    if (existing) {
      keyPair = existing;
      console.log("[ZeroWatch] Loaded existing ECDSA key pair");
    } else {
      keyPair = await crypto.subtle.generateKey(
        { name: "ECDSA", namedCurve: "P-256" },
        false, // non-extractable private key
        ["sign", "verify"]
      );
      // Store in IndexedDB
      await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const req = tx.objectStore(STORE_NAME).put(keyPair, KEY_ID);
        req.onsuccess = () => resolve();
        req.onerror = () => reject(req.error);
      });
      console.log("[ZeroWatch] Generated new ECDSA P-256 key pair");
    }

    // Export public key for server registration
    const pubRaw = await crypto.subtle.exportKey("raw", keyPair.publicKey);
    const pubB64 = btoa(String.fromCharCode(...new Uint8Array(pubRaw)));
    sessionStorage.setItem("zw_pubkey", pubB64);

    return keyPair;
  }

  // ─── 2. Device Fingerprint ───
  async function generateFingerprint() {
    const components = [];

    // Canvas fingerprint
    try {
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      ctx.textBaseline = "top";
      ctx.font = "14px Arial";
      ctx.fillText("ZeroWatch FP 🔒", 2, 2);
      components.push(canvas.toDataURL());
    } catch (e) {
      components.push("canvas-unavailable");
    }

    // WebGL fingerprint
    try {
      const gl =
        document.createElement("canvas").getContext("webgl") ||
        document.createElement("canvas").getContext("experimental-webgl");
      if (gl) {
        const dbgInfo = gl.getExtension("WEBGL_debug_renderer_info");
        if (dbgInfo) {
          components.push(
            gl.getParameter(dbgInfo.UNMASKED_RENDERER_WEBGL) || ""
          );
        }
      }
    } catch (e) {
      components.push("webgl-unavailable");
    }

    // Screen + navigator info
    components.push(`${screen.width}x${screen.height}x${screen.colorDepth}`);
    components.push(navigator.language || "");
    components.push(String(navigator.hardwareConcurrency || ""));

    // SHA-256 hash
    const raw = components.join("|");
    const buf = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(raw)
    );
    const hash = Array.from(new Uint8Array(buf))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");

    deviceFingerprint = hash;
    sessionStorage.setItem("zw_device_fp", hash);
    console.log("[ZeroWatch] Device fingerprint:", hash.slice(0, 16) + "...");
    return hash;
  }

  // ─── 3. Fetch Interceptor ───
  const originalFetch = window.fetch;

  async function signedFetch(input, init = {}) {
    // Skip signing for signal and auth endpoints to avoid recursion
    const url = typeof input === "string" ? input : input.url || "";
    if (
      url.includes("/api/signals") ||
      url.includes("/api/auth/") ||
      url.includes("/api/users") ||
      url.includes("/api/demo/")
    ) {
      return originalFetch(input, init);
    }

    if (keyPair && sessionId) {
      try {
        const ts = Date.now().toString();
        const urlObj = new URL(url, window.location.origin);
        const path = urlObj.pathname;
        const method = (init.method || "GET").toUpperCase();
        const message = `${sessionId}|${method}|${path}|${ts}`;

        const sigBuf = await crypto.subtle.sign(
          { name: "ECDSA", hash: "SHA-256" },
          keyPair.privateKey,
          new TextEncoder().encode(message)
        );
        const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sigBuf)));

        init.headers = {
          ...(init.headers || {}),
          "X-ZW-Signature": sigB64,
          "X-ZW-Timestamp": ts,
        };
      } catch (e) {
        console.warn("[ZeroWatch] Signing failed:", e);
      }
    }

    return originalFetch(input, init);
  }

  window.fetch = signedFetch;

  // ─── 4. Signal Collection ───
  // WPM tracking
  document.addEventListener("keyup", () => {
    keystrokes.push(Date.now());
    // Keep last 60 seconds
    const cutoff = Date.now() - 60000;
    keystrokes = keystrokes.filter((t) => t > cutoff);
  });

  // Mouse velocity tracking
  let lastMouse = { x: 0, y: 0, t: 0 };
  document.addEventListener("mousemove", (e) => {
    const now = Date.now();
    if (lastMouse.t > 0) {
      const dt = (now - lastMouse.t) / 1000;
      if (dt > 0.01) {
        const dx = e.clientX - lastMouse.x;
        const dy = e.clientY - lastMouse.y;
        const velocity = Math.sqrt(dx * dx + dy * dy) / dt;
        mousePositions.push(velocity);
        if (mousePositions.length > 100) mousePositions.shift();
      }
    }
    lastMouse = { x: e.clientX, y: e.clientY, t: now };
  });

  function calculateWPM() {
    if (keystrokes.length < 2) return 0;
    const span = (keystrokes[keystrokes.length - 1] - keystrokes[0]) / 60000;
    return span > 0 ? Math.round(keystrokes.length / 5 / span) : 0;
  }

  function calculateMouseVelocity() {
    if (mousePositions.length === 0) return 0;
    return Math.round(
      mousePositions.reduce((a, b) => a + b, 0) / mousePositions.length
    );
  }

  // Batch POST signals every 2 seconds
  setInterval(async () => {
    if (!sessionId) return;
    const signals = [
      {
        session_id: sessionId,
        type: "behavioral",
        wpm: calculateWPM(),
        mouse_velocity: calculateMouseVelocity(),
        timestamp: new Date().toISOString(),
      },
    ];

    try {
      await originalFetch("/api/signals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, signals }),
        credentials: "include",
      });
    } catch (e) {
      // Silently fail
    }
  }, SIGNAL_INTERVAL);

  // ─── 5. Public API ───
  async function init(sid) {
    sessionId = sid || sessionId;
    await loadOrCreateKey();
    await generateFingerprint();

    // Register device with server
    const pubkey = sessionStorage.getItem("zw_pubkey");
    if (pubkey && sessionId) {
      try {
        await originalFetch("/api/auth/register-device", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, pubkey }),
          credentials: "include",
        });
        console.log("[ZeroWatch] Device registered with server");
      } catch (e) {
        console.warn("[ZeroWatch] Device registration failed:", e);
      }
    }
  }

  window.ZeroWatch = {
    init,
    getFingerprint: () => deviceFingerprint || sessionStorage.getItem("zw_device_fp"),
    getPublicKey: () => sessionStorage.getItem("zw_pubkey"),
    setSessionId: (sid) => { sessionId = sid; },
  };

  console.log("[ZeroWatch] SDK loaded. Call ZeroWatch.init(sessionId) after login.");
})();
