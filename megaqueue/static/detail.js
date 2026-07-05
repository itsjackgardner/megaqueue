var renameDetails = document.getElementById("rename-details");
var renameForm = document.getElementById("rename-form");

if (renameDetails && renameForm) {
  renameDetails.addEventListener("toggle", function () {
    renameForm.style.display = this.open ? "" : "none";
  });
}

(function () {
  var card = document.getElementById("detail-card");
  if (!card) return;

  var downloadId = Number(card.dataset.id);
  var initialStatus = card.dataset.status;

  if (initialStatus !== "downloading" && initialStatus !== "queued") return;

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
      var resp = await fetch("/api/status");
      if (!resp.ok) return;
      var downloads = await resp.json();

      var dl = downloads.find(function (d) { return d.id === downloadId; });
      if (!dl) return;

      if (dl.status !== initialStatus) {
        location.reload();
        return;
      }

      // Overall progress bar
      if (dl.total_bytes > 0) {
        var overall = document.getElementById("overall-progress");
        if (!overall) {
          location.reload();
          return;
        }
        var pct = ((dl.progress_bytes / dl.total_bytes) * 100).toFixed(1);
        var bar = overall.querySelector(".fetch-bar");
        if (bar) bar.style.width = pct + "%";

        var stats = overall.querySelectorAll("[data-progress] span");
        if (stats.length >= 2) {
          stats[0].textContent = formatBytes(dl.progress_bytes) + " / " + formatBytes(dl.total_bytes);
          var speedStr = pct + "%";
          if (dl.speed > 0) speedStr += " · " + formatSpeed(dl.speed);
          stats[1].textContent = speedStr;
        }
      }

      // Per-file progress bars
      dl.files.forEach(function (f) {
        var fileCard = card.querySelector('[data-file-id="' + f.id + '"]');
        if (!fileCard) return;

        if (f.status === "downloading" && f.total_bytes > 0) {
          var fpct = ((f.progress_bytes / f.total_bytes) * 100).toFixed(1);
          var fbar = fileCard.querySelector(".fetch-bar");

          if (!fbar) {
            location.reload();
            return;
          }

          fbar.style.width = fpct + "%";

          var fstats = fileCard.querySelectorAll("[data-file-progress] span");
          if (fstats.length >= 2) {
            fstats[0].textContent = formatBytes(f.progress_bytes) + " / " + formatBytes(f.total_bytes);
            var fspeedStr = fpct + "%";
            if (f.speed > 0) fspeedStr += " · " + formatSpeed(f.speed);
            fstats[1].textContent = fspeedStr;
          }
        }
      });
    } catch (e) {
      // Silently ignore fetch errors
    }
  }

  setInterval(refresh, 5000);
})();
