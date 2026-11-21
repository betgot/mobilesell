(() => {
  'use strict';

  const GAME_HOST = /(^|\.)mobilesell\.ru$/i;
  const GAME_FILE = /(?:^|\/)(?:decrypt|game|index|perekup)[^/]*\.html?$/i;

  function isGamePage() {
    try {
      if (GAME_HOST.test(location.hostname)) return true;
      if (location.protocol === 'file:') return true;
      if (/^(?:localhost|127\.0\.0\.1)$/i.test(location.hostname)) return true;
      return GAME_FILE.test(location.pathname);
    } catch (e) {
      return false;
    }
  }

  if (!isGamePage()) return;

  const AD_TITLE = /(?:Реклама за награду|Бонус за рекламу|Смотреть рекламу в Telegram|Чтобы войти в игру[^<]{0,120}реклам)/i;
  const GATE_TEXT = /(?:посмотрите\s+\d+\s+реклам|Чтобы войти в игру[^<]{0,160}реклам)/i;

  function removeNode(node) {
    if (node && node.parentNode) node.parentNode.removeChild(node);
  }

  function removeGate(btn) {
    let p = btn;
    while (p && p !== document.body && p !== document.documentElement) {
      let st = null;
      try { st = getComputedStyle(p); } catch (e) { /* не важно */ }
      if (st && st.position === 'fixed' && parseInt(st.zIndex || '0', 10) >= 1000000) break;
      p = p.parentElement;
    }
    if (p && p !== document.body && p !== document.documentElement) {
      removeNode(p);
      return;
    }
    // Запасной вариант: поднимаемся до прямого ребёнка body.
    let q = btn;
    while (q && q.parentElement && q.parentElement !== document.body) q = q.parentElement;
    if (q && q.parentElement === document.body) removeNode(q);
  }

  function clean(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('#eg-go').forEach(removeGate);

    root.querySelectorAll('body > div').forEach(function (el) {
      if (el.id === 'eg-go') return;
      if (GATE_TEXT.test(el.textContent || '') && !el.querySelector('.screen, #screen-home')) {
        removeNode(el);
      }
    });

    root.querySelectorAll('.dn-offer').forEach(removeNode);

    root.querySelectorAll('.dn-box').forEach(function (el) {
      if (AD_TITLE.test(el.textContent || '')) removeNode(el);
    });

    root.querySelectorAll('[data-dn-ad], [data-dn-adtg]').forEach(function (el) {
      const box = el.closest && el.closest('.dn-box');
      removeNode(box || el);
    });

    root.querySelectorAll('script[src*="adsgram"], iframe[src*="adsgram"]').forEach(removeNode);
  }

  function interesting(node) {
    if (!node || node.nodeType !== 1) return false;
    try {
      if (node.id === 'eg-go' || node.classList.contains('dn-offer') ||
          node.matches('.dn-box, [data-dn-ad], [data-dn-adtg], script[src*="adsgram"], iframe[src*="adsgram"]')) {
        return true;
      }
      return !!node.querySelector('#eg-go, .dn-offer, .dn-box, [data-dn-ad], [data-dn-adtg], script[src*="adsgram"], iframe[src*="adsgram"]');
    } catch (e) {
      return false;
    }
  }

  function start() {
    clean(document);

    const mo = new MutationObserver(function (records) {
      for (let i = 0; i < records.length; i++) {
        const added = records[i].addedNodes;
        for (let j = 0; j < added.length; j++) {
          if (interesting(added[j])) {
            clean(document);
            return;
          }
        }
      }
    });

    if (document.documentElement) {
      mo.observe(document.documentElement, { childList: true, subtree: true });
    } else {
      document.addEventListener('DOMContentLoaded', start, { once: true });
    }

    let passes = 0;
    const timer = setInterval(function () {
      clean(document);
      if (++passes >= 120) clearInterval(timer);
    }, 1000);
  }

  start();
})();
