// Small progressive enhancement: dismiss status messages after they have been read.
document.querySelectorAll('.flash').forEach((message) => {
  window.setTimeout(() => {
    message.classList.add('flash-dismissed');
    window.setTimeout(() => message.remove(), 250);
  }, 6500);
});
