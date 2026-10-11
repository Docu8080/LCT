'use strict';

// This is an essential-storage notice, not permission for tracking or marketing.
(() => {
  const noticeVersion = '2026-10-11-v2';
  const storageKey = 'fsp_cookie_notice';
  let acknowledged = false;
  let resizeObserver;
  const updateNoticeHeight = notice => document.documentElement.style.setProperty('--cookie-notice-height', `${notice.getBoundingClientRect().height}px`);
  try {
    acknowledged = localStorage.getItem(storageKey) === noticeVersion;
  } catch {
    // Restricted storage leaves the choice in memory for the current page only.
  }

  function showCookieNotice() {
    if (document.getElementById('cookie-notice')) return;
    const notice = document.createElement('section');
    notice.id = 'cookie-notice';
    notice.className = 'cookie-notice';
    notice.setAttribute('role', 'region');
    notice.setAttribute('aria-labelledby', 'cookie-notice-title');
    notice.innerHTML = `<div class="cookie-notice-copy"><h2 id="cookie-notice-title">Только необходимые cookie</h2><p>Cookie сохраняет вход в аккаунт. В браузере хранится отметка об ознакомлении с этим уведомлением. Рекламных и аналитических трекеров нет.</p></div><div class="cookie-notice-actions"><button type="button" data-cookie-dismiss>Понятно</button><a class="button outline" href="/cookies">Подробнее о cookie</a></div>`;
    document.body.append(notice);
    document.body.classList.add('cookie-notice-visible');
    updateNoticeHeight(notice);
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => updateNoticeHeight(notice));
      resizeObserver.observe(notice);
    }
  }

  function dismissCookieNotice() {
    acknowledged = true;
    try {
      localStorage.setItem(storageKey, noticeVersion);
    } catch {
      // The notice stays dismissed until this page is reloaded.
    }
    const notice = document.getElementById('cookie-notice');
    const hadFocus = notice?.contains(document.activeElement);
    resizeObserver?.disconnect();
    notice?.remove();
    document.body.classList.remove('cookie-notice-visible');
    document.documentElement.style.setProperty('--cookie-notice-height', '0px');
    if (hadFocus) {
      const settings = document.querySelector('[data-cookie-settings]');
      const destination = settings || document.querySelector('#main-content, #public-content');
      destination?.focus({preventScroll: true});
    }
  }

  document.addEventListener('click', event => {
    const settings = event.target.closest('[data-cookie-settings]');
    const dismiss = event.target.closest('[data-cookie-dismiss]');
    if (settings) {
      event.preventDefault();
      showCookieNotice();
      document.querySelector('[data-cookie-dismiss]')?.focus();
    } else if (dismiss) {
      dismissCookieNotice();
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      if (!acknowledged) showCookieNotice();
    }, {once: true});
  } else if (!acknowledged) {
    showCookieNotice();
  }
})();
