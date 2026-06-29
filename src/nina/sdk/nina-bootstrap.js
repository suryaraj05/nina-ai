/* nina-bootstrap.js — NINA conversational commerce widget v1
   Usage: <script src="…/sdk/nina-bootstrap.js"
                   data-site-id="…" data-api="…" data-api-key="…" defer></script>
*/
(function (W, D) {
  'use strict';

  var script = D.currentScript || D.querySelector('script[data-api-key]');
  if (!script) return;

  var CFG = {
    api:    (script.getAttribute('data-api') || '').replace(/\/$/, ''),
    key:    script.getAttribute('data-api-key') || '',
    siteId: script.getAttribute('data-site-id') || '',
    panel:  script.getAttribute('data-panel') || 'right',
    name:   script.getAttribute('data-name') || 'NINA',
    color:  script.getAttribute('data-color') || '#5b8cff',
    greeting: script.getAttribute('data-greeting') || null,
  };

  if (!CFG.api || !CFG.key) {
    console.warn('[NINA] data-api and data-api-key are required.');
    return;
  }

  /* ── Session ID (persisted per site across page loads) ── */
  var SID_KEY = 'nina_sid_' + CFG.siteId;
  function getSid() {
    var sid = localStorage.getItem(SID_KEY);
    if (!sid) {
      var arr = new Uint8Array(16);
      (W.crypto || W.msCrypto).getRandomValues(arr);
      sid = 'sid_' + Array.from(arr, function (b) { return b.toString(16).padStart(2, '0'); }).join('');
      try { localStorage.setItem(SID_KEY, sid); } catch (_) {}
    }
    return sid;
  }

  /* ── CSS ── */
  var side = CFG.panel === 'left' ? 'left' : 'right';
  var CSS = '\
  #nina-fab{position:fixed;bottom:24px;' + side + ':24px;z-index:2147483646;\
    width:54px;height:54px;border-radius:50%;background:' + CFG.color + ';\
    border:none;cursor:pointer;\
    box-shadow:0 4px 18px rgba(0,0,0,.28);\
    display:flex;align-items:center;justify-content:center;\
    transition:transform .15s,box-shadow .15s;}\
  #nina-fab:hover{transform:scale(1.08);box-shadow:0 7px 22px rgba(0,0,0,.34);}\
  #nina-fab svg{width:26px;height:26px;fill:#fff;pointer-events:none;}\
  #nina-badge{position:absolute;top:-2px;right:-2px;width:16px;height:16px;\
    background:#ff4d4d;border-radius:50%;border:2px solid #fff;\
    display:none;}\
  #nina-panel{position:fixed;bottom:90px;' + side + ':20px;\
    z-index:2147483647;width:360px;\
    max-width:calc(100vw - 32px);\
    height:540px;max-height:calc(100vh - 110px);\
    background:#fff;border-radius:18px;\
    box-shadow:0 16px 56px rgba(0,0,0,.22);\
    display:flex;flex-direction:column;overflow:hidden;\
    transform:translateY(14px) scale(.96);opacity:0;pointer-events:none;\
    transition:transform .22s cubic-bezier(.34,1.26,.64,1),opacity .18s ease;}\
  #nina-panel.nina-open{transform:translateY(0) scale(1);opacity:1;pointer-events:auto;}\
  #nina-head{padding:14px 16px;background:' + CFG.color + ';color:#fff;\
    display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}\
  .nina-head-left{display:flex;align-items:center;gap:10px;}\
  .nina-avatar{width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,.2);\
    display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.9rem;}\
  .nina-head-info{}\
  .nina-head-name{font-weight:700;font-size:.95rem;}\
  .nina-head-status{font-size:.72rem;opacity:.8;display:flex;align-items:center;gap:4px;}\
  .nina-dot{width:6px;height:6px;border-radius:50%;background:#7fffb5;display:inline-block;}\
  #nina-close{background:none;border:none;cursor:pointer;color:#fff;opacity:.75;\
    font-size:22px;line-height:1;padding:0;width:28px;height:28px;\
    display:flex;align-items:center;justify-content:center;border-radius:6px;}\
  #nina-close:hover{opacity:1;background:rgba(255,255,255,.15);}\
  #nina-msgs{flex:1;overflow-y:auto;padding:14px 12px;\
    display:flex;flex-direction:column;gap:10px;background:#f5f7fc;\
    scroll-behavior:smooth;}\
  #nina-msgs::-webkit-scrollbar{width:4px;}\
  #nina-msgs::-webkit-scrollbar-thumb{background:#d0d6e8;border-radius:2px;}\
  .nina-row{display:flex;align-items:flex-end;gap:6px;}\
  .nina-row.nina-user{flex-direction:row-reverse;}\
  .nina-bubble{max-width:78%;padding:10px 14px;border-radius:16px;\
    font-size:.875rem;line-height:1.5;word-break:break-word;\
    white-space:pre-wrap;}\
  .nina-row.nina-bot .nina-bubble{background:#fff;color:#1a1e2e;\
    border-bottom-left-radius:4px;\
    box-shadow:0 1px 5px rgba(0,0,0,.08);}\
  .nina-row.nina-user .nina-bubble{background:' + CFG.color + ';color:#fff;\
    border-bottom-right-radius:4px;}\
  .nina-row.nina-sys{justify-content:center;}\
  .nina-row.nina-sys .nina-bubble{background:transparent;color:#9aa4c0;\
    font-size:.78rem;text-align:center;max-width:100%;padding:4px 0;box-shadow:none;}\
  .nina-typing-bubble{display:flex;gap:5px;padding:12px 16px;}\
  .nina-typing-bubble span{width:7px;height:7px;border-radius:50%;background:#c0c8e0;\
    animation:nina-bounce .85s infinite;}\
  .nina-typing-bubble span:nth-child(2){animation-delay:.17s;}\
  .nina-typing-bubble span:nth-child(3){animation-delay:.34s;}\
  @keyframes nina-bounce{0%,60%,100%{transform:translateY(0);}30%{transform:translateY(-7px);}}\
  .nina-confirm-row{display:flex;gap:8px;padding:0 12px 4px;}\
  .nina-confirm-row button{flex:1;padding:9px;border-radius:10px;border:none;\
    cursor:pointer;font-size:.85rem;font-weight:700;transition:opacity .12s;}\
  .nina-confirm-row .nina-yes{background:' + CFG.color + ';color:#fff;}\
  .nina-confirm-row .nina-no{background:#eef1f9;color:#333;}\
  .nina-confirm-row button:hover{opacity:.85;}\
  #nina-foot{padding:10px 12px;background:#fff;\
    border-top:1px solid #e8edf6;flex-shrink:0;display:flex;gap:8px;align-items:flex-end;}\
  #nina-input{flex:1;border:1.5px solid #dde3f2;border-radius:12px;\
    padding:10px 13px;font-size:.875rem;font-family:inherit;\
    resize:none;outline:none;max-height:90px;min-height:40px;\
    background:#f8faff;line-height:1.4;color:#1a1e2e;\
    transition:border-color .15s;}\
  #nina-input:focus{border-color:' + CFG.color + ';background:#fff;}\
  #nina-input::placeholder{color:#b8c1d8;}\
  #nina-send{width:40px;height:40px;flex-shrink:0;border-radius:12px;\
    background:' + CFG.color + ';border:none;cursor:pointer;\
    display:flex;align-items:center;justify-content:center;\
    transition:opacity .15s,transform .1s;}\
  #nina-send:disabled{opacity:.38;cursor:default;}\
  #nina-send:not(:disabled):hover{opacity:.88;}\
  #nina-send:not(:disabled):active{transform:scale(.94);}\
  #nina-send svg{width:18px;height:18px;fill:#fff;}\
  #nina-brand{text-align:center;padding:4px 0 5px;\
    font-size:.68rem;color:#c0c8db;background:#fff;flex-shrink:0;line-height:1.6;}\
  #nina-brand a{color:#c0c8db;text-decoration:none;}\
  #nina-brand a:hover{color:#9aa4c0;}\
  .nina-products{display:flex;gap:9px;overflow-x:auto;padding:2px 2px 8px;\
    scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;}\
  .nina-products::-webkit-scrollbar{height:5px;}\
  .nina-products::-webkit-scrollbar-thumb{background:#d0d6e8;border-radius:3px;}\
  .nina-card{flex:0 0 134px;scroll-snap-align:start;background:#fff;\
    border:1px solid #eef1f9;border-radius:12px;overflow:hidden;\
    display:flex;flex-direction:column;box-shadow:0 1px 4px rgba(0,0,0,.05);}\
  .nina-card-img{width:100%;height:118px;object-fit:cover;display:block;\
    background:#eef1f7;border:none;}\
  .nina-card-body{padding:8px 9px 9px;display:flex;flex-direction:column;gap:5px;flex:1;}\
  .nina-card-title{font-size:.78rem;line-height:1.25;color:#1a1e2e;\
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;\
    overflow:hidden;min-height:2em;}\
  .nina-card-price{font-size:.82rem;font-weight:700;color:#1a1e2e;}\
  .nina-card-meta{font-size:.68rem;color:#8a93ad;}\
  .nina-card-btn{margin-top:auto;border:none;border-radius:8px;cursor:pointer;\
    background:' + CFG.color + ';color:#fff;font-size:.74rem;font-weight:700;\
    padding:7px;transition:opacity .12s;}\
  .nina-card-btn:hover{opacity:.88;}\
  .nina-products.nina-single .nina-card{flex:1 1 auto;flex-direction:row;}\
  .nina-products.nina-single .nina-card-img{width:96px;height:96px;flex-shrink:0;}\
  .nina-products.nina-single .nina-card-body{justify-content:center;}\
  @media(max-width:480px){\
    #nina-panel{bottom:0 !important;left:0 !important;right:0 !important;\
      width:100% !important;max-width:100% !important;\
      height:100dvh !important;max-height:100dvh !important;\
      border-radius:18px 18px 0 0 !important;}\
    #nina-fab{bottom:16px !important;}\
  }';

  /* ── DOM ── */
  function injectCSS() {
    var el = D.createElement('style');
    el.textContent = CSS;
    D.head.appendChild(el);
  }

  function createEl(tag, attrs, html) {
    var el = D.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (html !== undefined) el.innerHTML = html;
    return el;
  }

  function buildDOM() {
    var initial = CFG.name.charAt(0).toUpperCase();

    var fab = createEl('button', { id: 'nina-fab', 'aria-label': 'Open ' + CFG.name },
      '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>\
       <span id="nina-badge"></span>');

    var panel = createEl('div', { id: 'nina-panel', role: 'dialog', 'aria-label': CFG.name + ' assistant' },
      '<div id="nina-head">\
         <div class="nina-head-left">\
           <div class="nina-avatar">' + initial + '</div>\
           <div class="nina-head-info">\
             <div class="nina-head-name">' + CFG.name + '</div>\
             <div class="nina-head-status"><span class="nina-dot"></span>Online</div>\
           </div>\
         </div>\
         <button id="nina-close" aria-label="Close">&times;</button>\
       </div>\
       <div id="nina-msgs" role="log" aria-live="polite"></div>\
       <div id="nina-foot">\
         <textarea id="nina-input" placeholder="Ask me anything…" rows="1" aria-label="Message to ' + CFG.name + '"></textarea>\
         <button id="nina-send" aria-label="Send" disabled>\
           <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>\
         </button>\
       </div>\
       <div id="nina-brand"><a href="https://nina.ai" target="_blank" rel="noopener noreferrer">Powered by NINA</a><br>By chatting you agree to our <a href="https://nina.ai/privacy" target="_blank" rel="noopener noreferrer">Privacy&nbsp;Policy</a></div>');

    D.body.appendChild(fab);
    D.body.appendChild(panel);
    return { fab: fab, panel: panel };
  }

  /* ── Message rendering ── */
  var _msgs;
  function msgBox() { return _msgs || (_msgs = D.getElementById('nina-msgs')); }

  function addRow(role, text) {
    var row = createEl('div', { class: 'nina-row nina-' + role });
    var bbl = createEl('div', { class: 'nina-bubble' });
    bbl.textContent = text;
    row.appendChild(bbl);
    msgBox().appendChild(row);
    msgBox().scrollTop = 99999;
    return bbl;
  }

  function addTyping() {
    var row = createEl('div', { class: 'nina-row nina-bot' });
    row.innerHTML = '<div class="nina-bubble nina-typing-bubble"><span></span><span></span><span></span></div>';
    msgBox().appendChild(row);
    msgBox().scrollTop = 99999;
    return row;
  }

  function addConfirm(onYes, onNo) {
    var row = createEl('div', { class: 'nina-confirm-row' });
    row.innerHTML = '<button class="nina-yes">Confirm</button><button class="nina-no">Cancel</button>';
    row.querySelector('.nina-yes').onclick = function () { row.remove(); onYes(); };
    row.querySelector('.nina-no').onclick  = function () { row.remove(); onNo && onNo(); addRow('sys', 'Action cancelled.'); };
    msgBox().appendChild(row);
    msgBox().scrollTop = 99999;
  }

  /* ── Product cards ── */
  function renderProducts(products) {
    if (!products || !products.length) return;
    var single = products.length === 1;
    var wrap = createEl('div', { class: 'nina-products' + (single ? ' nina-single' : '') });
    products.forEach(function (p) {
      var card = createEl('div', { class: 'nina-card' });

      // Image: a real URL if given, else a soft colour swatch fallback.
      var img;
      if (p.image) {
        img = createEl('img', { class: 'nina-card-img', alt: p.title || '', loading: 'lazy' });
        img.src = p.image;
      } else {
        img = createEl('div', { class: 'nina-card-img' });
        if (p.swatch) img.style.background = p.swatch;
      }
      if (p.url) {
        img.style.cursor = 'pointer';
        img.addEventListener('click', function () { W.open(p.url, '_blank', 'noopener'); });
      }

      var body = createEl('div', { class: 'nina-card-body' });
      var title = createEl('div', { class: 'nina-card-title' });
      title.textContent = p.title || '';
      body.appendChild(title);

      if (p.meta) {
        var meta = createEl('div', { class: 'nina-card-meta' });
        meta.textContent = p.meta;       // e.g. "Size: M · In Stock"
        body.appendChild(meta);
      }

      var price = createEl('div', { class: 'nina-card-price' });
      if (p.price != null && p.price !== '') price.textContent = (p.currency || '') + p.price;
      body.appendChild(price);

      var btn = createEl('button', { class: 'nina-card-btn', type: 'button' });
      btn.textContent = p.cta || 'Add to Cart';
      btn.addEventListener('click', function () {
        if (_busy) return;
        addRow('user', 'Add ' + (p.title || 'this') + ' to cart');
        chat('add ' + (p.title || 'this item') + ' to my cart');
      });
      body.appendChild(btn);

      card.appendChild(img);
      card.appendChild(body);
      wrap.appendChild(card);
    });
    msgBox().appendChild(wrap);
    msgBox().scrollTop = 99999;
  }

  /* ── Instruction execution ── */
  function execInstructions(instructions) {
    (instructions || []).forEach(function (ins) {
      var t = ins.type;
      if (t === 'navigate' && ins.url) {
        W.location.href = ins.url;
      } else if ((t === 'fetch' || t === 'api_call') && ins.url) {
        // Only allow same-origin calls: prevents the widget from being used to
        // exfiltrate data or CSRF-attack third-party services via prompt injection.
        var targetUrl;
        try { targetUrl = new URL(ins.url, W.location.href); } catch (_) { return; }
        if (targetUrl.origin !== W.location.origin) return;
        fetch(targetUrl.href, {
          method: ins.method || 'GET',
          headers: Object.assign({ 'Content-Type': 'application/json' }, ins.headers || {}),
          body: ins.body != null ? JSON.stringify(ins.body) : undefined,
          credentials: 'include',
        }).catch(function () {});
      } else if (t === 'dom' && ins.selector) {
        var el = D.querySelector(ins.selector);
        // Never use innerHTML here — LLM output must not execute as markup.
        if (el && ins.text != null) el.textContent = ins.text;
      } else if (t === 'reload') {
        W.location.reload();
      }
    });
  }

  /* ── API call ── */
  var _busy = false;

  function setInputEnabled(on) {
    var inp  = D.getElementById('nina-input');
    var send = D.getElementById('nina-send');
    if (!inp) return;
    inp.disabled = !on;
    send.disabled = !on || !inp.value.trim();
  }

  function chat(text, opts) {
    opts = opts || {};
    if (_busy) return;
    _busy = true;
    setInputEnabled(false);

    var typing = addTyping();

    fetch(CFG.api + '/v1/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-NINA-API-Key': CFG.key,
      },
      body: JSON.stringify({
        message: text || '',
        sessionId: getSid(),
        confirmed: !!opts.confirmed,
        replayQueued: !!opts.replayQueued,
        page_context: { url: W.location.href, pageId: D.title },
      }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      typing.remove();

      if (!data || !data.ok || !data.data) {
        addRow('sys', (data && data.error && data.error.message) || 'Something went wrong. Please try again.');
        return;
      }

      var turn = data.data;
      var reply = (turn.naturalLanguageResponse || '').trim();
      if (reply) addRow('bot', reply);

      // Product cards: the engine may attach a `products` array (search /
      // recommendation results) for the shopper to browse and add inline.
      if (turn.products && turn.products.length) renderProducts(turn.products);

      var intent = turn.intent;
      if (intent === 'confirmation') {
        addConfirm(
          function () { chat('', { confirmed: true }); },
          null
        );
      } else if (intent === 'needs_login') {
        var loginUrl = null;
        (turn.instructions || []).forEach(function (i) { if (i.url && !loginUrl) loginUrl = i.url; });
        if (loginUrl) {
          var row = createEl('div', { class: 'nina-confirm-row' });
          row.innerHTML = '<button class="nina-yes" style="max-width:180px">Sign in</button>';
          row.querySelector('.nina-yes').onclick = function () { W.location.href = loginUrl; };
          msgBox().appendChild(row);
          msgBox().scrollTop = 99999;
        }
      } else {
        execInstructions(turn.instructions);
      }
    })
    .catch(function () {
      typing.remove();
      addRow('sys', 'Connection error. Check your internet and try again.');
    })
    .finally(function () {
      _busy = false;
      setInputEnabled(true);
      var inp = D.getElementById('nina-input');
      if (inp && !inp.disabled) inp.focus();
    });
  }

  /* ── Boot ── */
  function boot() {
    injectCSS();
    var els = buildDOM();
    var fab   = els.fab;
    var panel = els.panel;
    var isOpen = false;
    var greeted = false;

    // On mobile (Android especially), the soft keyboard shrinks the visual
    // viewport. We reattach the panel to the visual viewport bottom so the
    // input box is never hidden behind the keyboard.
    if (typeof window.visualViewport !== 'undefined') {
      window.visualViewport.addEventListener('resize', function () {
        if (!isOpen) return;
        var vvh = window.visualViewport.height;
        if (window.innerWidth <= 480) {
          panel.style.height = vvh + 'px';
          panel.style.top = '0';
          panel.style.bottom = 'auto';
        } else {
          panel.style.height = '';
          panel.style.top = '';
          panel.style.bottom = '';
        }
      });
    }

    function open() {
      isOpen = true;
      panel.classList.add('nina-open');
      D.getElementById('nina-badge').style.display = 'none';
      var inp = D.getElementById('nina-input');
      if (inp) setTimeout(function () { inp.focus(); }, 180);
      if (!greeted) {
        greeted = true;
        var msg = CFG.greeting || ('Hi! I\'m ' + CFG.name + '. How can I help you today?');
        setTimeout(function () { addRow('bot', msg); }, 160);
      }
    }

    function close() {
      isOpen = false;
      panel.classList.remove('nina-open');
    }

    fab.addEventListener('click', function () { isOpen ? close() : open(); });
    D.getElementById('nina-close').addEventListener('click', close);

    // Close on outside click
    D.addEventListener('click', function (e) {
      if (isOpen && !panel.contains(e.target) && e.target !== fab) close();
    });

    // Keyboard close
    D.addEventListener('keydown', function (e) { if (e.key === 'Escape' && isOpen) close(); });

    var input = D.getElementById('nina-input');
    var send  = D.getElementById('nina-send');

    input.addEventListener('input', function () {
      send.disabled = _busy || !this.value.trim();
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 90) + 'px';
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
        e.preventDefault();
        if (!send.disabled) send.click();
      }
    });

    send.addEventListener('click', function () {
      var text = input.value.trim();
      if (!text || _busy) return;
      input.value = '';
      input.style.height = 'auto';
      send.disabled = true;
      addRow('user', text);
      chat(text);
    });

    // Optional: auto-open after delay (off by default)
    // setTimeout(open, 3000);
  }

  if (D.readyState === 'loading') {
    D.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

}(window, document));
