/**
 * emoji-export.js
 *
 * Downloads all custom emojis from the current Discord server.
 *
 * Usage (browser console while inside a server channel):
 *   1. Paste this script into the console and press Enter.
 *   2. If the token is not found automatically, set it first:
 *        window.__discordToken = "YOUR_TOKEN_HERE";
 *      Then re-run the script.
 */

(async () => {
  // ---------------------------------------------------------------------------
  // Token resolution
  // ---------------------------------------------------------------------------

  function resolveToken() {
    // Attempt 1: explicit override (useful when auto-detection fails)
    if (window.__discordToken) return window.__discordToken;

    // Attempt 2: isolated iframe to read localStorage without CORS issues
    try {
      const frame = document.createElement("iframe");
      document.body.appendChild(frame);
      const raw = frame.contentWindow.localStorage.getItem("token");
      document.body.removeChild(frame);
      if (raw) return raw.replace(/"/g, "");
    } catch (_) {}

    // Attempt 3: scan localStorage for a JWT-shaped value
    try {
      for (const key of Object.keys(localStorage)) {
        const value = localStorage.getItem(key);
        if (
          value &&
          /^"[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{25,}"$/.test(
            value,
          )
        ) {
          return value.replace(/"/g, "");
        }
      }
    } catch (_) {}

    return null;
  }

  // ---------------------------------------------------------------------------
  // Guild ID from the current URL
  // ---------------------------------------------------------------------------

  function resolveGuildId() {
    const id = window.location.pathname.split("/")[2];
    return id && id !== "@me" ? id : null;
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  async function fetchJson(url, token) {
    const res = await fetch(url, { headers: { Authorization: token } });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    return res.json();
  }

  async function downloadBlob(url, filename) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to fetch ${url}: HTTP ${res.status}`);
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);

    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);

    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // ---------------------------------------------------------------------------
  // Feature: export emojis
  // ---------------------------------------------------------------------------

  async function exportEmojis(guildId, token) {
    console.log("Fetching emoji list...");

    const guild = await fetchJson(
      `https://discord.com/api/v10/guilds/${guildId}?with_counts=false`,
      token,
    );

    const emojis = guild.emojis ?? [];
    if (emojis.length === 0) {
      console.warn("No custom emojis found in this server.");
      return;
    }

    console.log(`Found ${emojis.length} emojis. Starting download...`);

    let succeeded = 0;
    let failed = 0;

    for (const emoji of emojis) {
      const ext = emoji.animated ? "gif" : "png";
      const filename = `${emoji.name}.${ext}`;
      const cdnUrl = `https://cdn.discordapp.com/emojis/${emoji.id}.${ext}?size=128&quality=lossless`;

      try {
        await downloadBlob(cdnUrl, filename);
        console.log(`Downloaded: ${filename}`);
        succeeded++;
      } catch (err) {
        console.warn(`Failed to download ${filename}:`, err.message);
        failed++;
      }

      // Small delay
      await sleep(400);
    }

    console.log(`Done. ${succeeded} downloaded, ${failed} failed.`);
  }

  // ---------------------------------------------------------------------------
  // Entry point
  // ---------------------------------------------------------------------------

  const token = resolveToken();
  if (!token) {
    console.error(
      'Token not found. Set window.__discordToken = "YOUR_TOKEN" and re-run the script.',
    );
    return;
  }

  const guildId = resolveGuildId();
  if (!guildId) {
    console.error("Open a server channel first, then re-run the script.");
    return;
  }

  await exportEmojis(guildId, token);
})();
