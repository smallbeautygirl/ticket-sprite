// Tells someone who switched to another tab that the sprite has finished: the tab title gets a
// check mark, plus a system notification when the browser allows one. Browsers only offer
// notifications on https or localhost, so on the plain-http VM the title is all there is.

let originalTitle: string | null = null;

export function canNotify(): boolean {
  return typeof window !== "undefined" && "Notification" in window && window.isSecureContext;
}

function restoreTitle() {
  if (document.hidden || originalTitle === null) return;
  document.title = originalTitle;
  originalTitle = null;
  document.removeEventListener("visibilitychange", restoreTitle);
}

export function announceReady(message: string) {
  if (typeof document === "undefined" || !document.hidden) return; // they're looking already
  if (originalTitle === null) {
    originalTitle = document.title;
    document.addEventListener("visibilitychange", restoreTitle);
  }
  document.title = `✓ ${message} · ${originalTitle}`;
  if (canNotify() && Notification.permission === "granted") {
    try {
      new Notification("開票小精靈", { body: message, tag: "ticket-sprite" });
    } catch {
      // some mobile browsers only allow notifications from a service worker
    }
  }
}
