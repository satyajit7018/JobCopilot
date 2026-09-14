// JobCopilot — client-side error reporter.
// Captures uncaught errors and unhandled promise rejections and forwards them to
// the backend (/api/client-errors), so frontend failures are no longer invisible.
// Standalone + defensive: loaded before app.js, never throws, and never reports
// its own failures (which would loop).
(function () {
  'use strict';
  var API_BASE = (location.origin.indexOf('localhost') !== -1 || location.origin.indexOf('127.0.0.1') !== -1)
    ? location.origin + '/api'
    : '/api';
  var ENDPOINT = API_BASE + '/client-errors';

  var MAX_REPORTS = 20;        // per page load — a broken client shouldn't flood the sink
  var sent = 0;
  var seen = {};              // dedupe identical messages

  function report(info) {
    try {
      if (sent >= MAX_REPORTS) return;
      var key = (info.message || '') + '@' + (info.source || '') + ':' + (info.line || '');
      if (seen[key]) return;
      seen[key] = true;
      sent++;
      info.url = location.href;
      info.userAgent = navigator.userAgent;
      // keepalive lets the report survive a navigation/unload.
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(info),
        keepalive: true
      }).catch(function () { /* never surface reporter failures */ });
    } catch (_) { /* swallow */ }
  }

  window.addEventListener('error', function (e) {
    report({
      message: (e && e.message) || 'Uncaught error',
      source: e && e.filename,
      line: e && e.lineno,
      col: e && e.colno,
      stack: e && e.error && e.error.stack ? String(e.error.stack).slice(0, 4000) : undefined
    });
  });

  window.addEventListener('unhandledrejection', function (e) {
    var reason = e && e.reason;
    report({
      message: 'Unhandled promise rejection: ' + (reason && reason.message ? reason.message : String(reason)),
      stack: reason && reason.stack ? String(reason.stack).slice(0, 4000) : undefined
    });
  });
})();
