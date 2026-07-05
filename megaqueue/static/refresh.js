// Auto-refresh dashboard every 5 seconds
(function () {
  const container = document.getElementById("downloads");
  if (!container) return;

  function formatBytes(bytes) {
    if (bytes === 0) return "0 MB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  function formatSpeed(bps) {
    if (bps === 0) return "";
    return (bps / 1048576).toFixed(1) + " MB/s";
  }

  async function refresh() {
    try {
      const resp = await fetch("/api/status");
      if (!resp.ok) return;
      const downloads = await resp.json();

      downloads.forEach(function (dl) {
        const card = container.querySelector('[data-id="' + dl.id + '"]');
        if (!card) {
          location.reload();
          return;
        }

        // Check for status change by reading the badge text
        const badge = card.querySelector("[data-status]");
        const currentStatus = badge ? badge.dataset.status : "";
        if (currentStatus !== dl.status) {
          location.reload();
          return;
        }

        // Update progress bar if downloading
        if ((dl.status === "downloading" || dl.status === "queued") && dl.total_bytes > 0) {
          const pct = ((dl.progress_bytes / dl.total_bytes) * 100).toFixed(1);
          const bar = card.querySelector(".fetch-bar");
          if (bar) bar.style.width = pct + "%";

          const stats = card.querySelectorAll("[data-progress] span");
          if (stats.length >= 2) {
            stats[0].textContent =
              formatBytes(dl.progress_bytes) + " / " + formatBytes(dl.total_bytes);
            let speedStr = pct + "%";
            if (dl.speed > 0) speedStr += " · " + formatSpeed(dl.speed);
            stats[1].textContent = speedStr;
          }
        }
      });
    } catch (e) {
      // Silently ignore fetch errors
    }
  }

  setInterval(refresh, 5000);
})();
