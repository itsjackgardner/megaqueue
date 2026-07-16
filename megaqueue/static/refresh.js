// Auto-refresh dashboard every 5 seconds
(function () {
  const container = document.getElementById("downloads");
  const ongoingContainer = document.getElementById("ongoing");
  if (!container) return;

  function formatBytes(bytes) {
    if (bytes === 0) return "0 MB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  function formatSpeed(bps) {
    if (bps === 0) return "";
    return (bps / 1048576).toFixed(1) + " MB/s";
  }

  function findCard(id) {
    return container.querySelector('[data-id="' + id + '"]')
      || (ongoingContainer && ongoingContainer.querySelector('[data-id="' + id + '"]'));
  }

  function cardCount() {
    let n = container.querySelectorAll("[data-id]").length;
    if (ongoingContainer) n += ongoingContainer.querySelectorAll("[data-id]").length;
    return n;
  }

  async function refresh() {
    try {
      const resp = await fetch("/api/status");
      if (!resp.ok) return;
      const downloads = await resp.json();

      if (downloads.length !== cardCount()) {
        location.reload();
        return;
      }

      for (const dl of downloads) {
        const card = findCard(dl.id);
        if (!card) {
          location.reload();
          return;
        }

        const badge = card.querySelector("[data-status]");
        const currentStatus = badge ? badge.dataset.status : "";
        if (currentStatus !== dl.status) {
          location.reload();
          return;
        }

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
      }
    } catch (e) {
      // Silently ignore fetch errors
    }
  }

  setInterval(refresh, 5000);
})();
