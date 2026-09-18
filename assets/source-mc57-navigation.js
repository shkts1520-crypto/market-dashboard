(function(){
  'use strict';

  const originalTab = window.tab;
  if (typeof originalTab !== 'function') return;

  function tabLink(id) {
    return document.querySelector('nav a.tabx[href="#' + id + '"]');
  }

  function validSection(id) {
    return !!(id && document.getElementById(id) && tabLink(id));
  }

  function activateFromLocation() {
    const id = String((window.location && window.location.hash) || '').replace(/^#/, '');
    if (!validSection(id)) return;
    originalTab(id, tabLink(id));
  }

  window.tab = function(id, btn) {
    if (!validSection(id)) return;
    originalTab(id, btn || tabLink(id));

    const nextHash = '#' + id;
    if (window.location.hash !== nextHash) {
      try {
        window.history.pushState({v38Tab:id}, '', nextHash);
      } catch (_) {
        window.location.hash = nextHash;
      }
    }
  };

  window.addEventListener('popstate', activateFromLocation);
  window.addEventListener('hashchange', activateFromLocation);

  function start() {
    // source-mc57 Options is added dynamically. Run after its DOMContentLoaded
    // handler so direct links such as #t-options resolve correctly.
    setTimeout(activateFromLocation, 0);
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', start, {once:true})
    : start();
})();