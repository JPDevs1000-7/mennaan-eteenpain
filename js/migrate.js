// Immediate 0-click redirect to the new origin, preserving the state parameters.

export function targetUrl(target, search, hash) {
  const url = new URL(target);
  if (url.protocol !== 'https:') throw new Error('Migration target must be https');
  return `${url.origin}${url.pathname}${search}${hash}`;
}

if (typeof document !== 'undefined') {
  const main = document.getElementById('app');
  try {
    const dest = targetUrl(main.dataset.target, location.search, location.hash);
    document.getElementById('go').href = dest;
    location.replace(dest);
  } catch { /* leave the manual link visible */ }
}
