// Promote preloaded Google Fonts to stylesheet (non-blocking)
var link = document.querySelector('link[rel="preload"][as="style"]');
if (link) {
  link.rel = "stylesheet";
}
