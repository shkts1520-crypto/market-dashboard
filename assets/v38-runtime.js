(function (global) {
  'use strict';

  const REQUIRED_META = [
    'session_date', 'generated_at', 'coverage', 'source',
    'schema_version', 'calculation_version'
  ];

  function missing(value) {
    return value === null ||
      value === undefined ||
      value === '' ||
      (typeof value === 'number' && !Number.isFinite(value));
  }

  function display(value, decimals) {
    if (missing(value)) return '—';
    if (typeof value === 'number' && Number.isInteger(decimals)) {
      return value.toFixed(decimals);
    }
    return String(value);
  }

  function assessShard(obj, targetSession) {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
      return {status: 'DATA_REQUIRED', reason: 'EXPECTED_JSON_OBJECT'};
    }
    const absent = REQUIRED_META.filter((key) => !(key in obj));
    if (absent.length) {
      return {status: 'DATA_REQUIRED', reason: 'MISSING_METADATA', missing: absent};
    }
    if (obj.session_date !== targetSession) {
      return {
        status: 'STALE', reason: 'SESSION_MISMATCH',
        session_date: obj.session_date
      };
    }
    return {status: 'READY', reason: 'CURRENT_SESSION'};
  }

  async function loadJson(path) {
    const response = await fetch(path, {cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status + ' for ' + path);
    return response.json();
  }

  function appendExtension(src, name) {
    const script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.dataset.v38Extension = name;
    document.head.appendChild(script);
  }

  function loadDisplayExtensions() {
    appendExtension('assets/v38-observables.js', 'observables');
    appendExtension('assets/v38-polish.js', 'polish');
    appendExtension('assets/v38-final-ui.js', 'final-ui');
  }

  global.V38Runtime = Object.freeze({
    missing,
    display,
    assessShard,
    loadJson
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadDisplayExtensions, {once: true});
  } else {
    loadDisplayExtensions();
  }
})(window);
