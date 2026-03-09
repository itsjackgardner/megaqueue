// Minimal service worker — required for PWA install prompt.
// No caching; all requests pass through to the network.
self.addEventListener("fetch", function (event) {
  event.respondWith(fetch(event.request));
});
