// On-screen floating navigation menu (FoodAssistant-bzuu).
//
// Places a compact column of nav icons in a screen corner. The corner is the
// server default (data-position) unless the user has dragged it on this device,
// in which case a localStorage override wins (position is inherently per-device:
// a wall kiosk and a phone want different placement). Dragging the handle moves
// the menu; on release it snaps to the nearest corner and the choice is saved.
//
// Auto-hides when a Stream Deck is connected if that option is set, since the
// deck already provides navigation.
(function () {
  var CORNERS = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
  var STORE_KEY = 'floatNavPosition';

  function start() {
    var nav = document.getElementById('floatNav');
    if (!nav) return;

    var serverPos = nav.getAttribute('data-position') || 'off';
    var autohide = nav.getAttribute('data-autohide-streamdeck') === '1';
    var hasDeck = nav.getAttribute('data-has-streamdeck') === '1';

    // Per-device override beats the server default.
    var stored = '';
    try { stored = localStorage.getItem(STORE_KEY) || ''; } catch (e) { }
    var pos = CORNERS.indexOf(stored) !== -1 || stored === 'off' ? stored : serverPos;

    if (pos === 'off' || (autohide && hasDeck)) {
      nav.classList.add('d-none');
      return;
    }
    applyCorner(nav, CORNERS.indexOf(pos) !== -1 ? pos : 'top-right');
    nav.classList.remove('d-none');

    wireDrag(nav);
  }

  function applyCorner(nav, corner) {
    for (var i = 0; i < CORNERS.length; i++) {
      nav.classList.remove('float-nav-pos-' + CORNERS[i]);
    }
    nav.classList.add('float-nav-pos-' + corner);
    // Clear any inline offsets left over from a drag.
    nav.style.top = nav.style.left = nav.style.right = nav.style.bottom = '';
  }

  function nearestCorner(cx, cy) {
    var vert = cy < window.innerHeight / 2 ? 'top' : 'bottom';
    var horiz = cx < window.innerWidth / 2 ? 'left' : 'right';
    return vert + '-' + horiz;
  }

  function wireDrag(nav) {
    var handle = nav.querySelector('.float-nav-handle');
    if (!handle) return;
    var dragging = false, offX = 0, offY = 0;

    handle.addEventListener('pointerdown', function (e) {
      dragging = true;
      var rect = nav.getBoundingClientRect();
      offX = e.clientX - rect.left;
      offY = e.clientY - rect.top;
      nav.classList.add('dragging');
      for (var i = 0; i < CORNERS.length; i++) {
        nav.classList.remove('float-nav-pos-' + CORNERS[i]);
      }
      nav.style.right = nav.style.bottom = '';
      nav.style.left = rect.left + 'px';
      nav.style.top = rect.top + 'px';
      handle.setPointerCapture(e.pointerId);
      e.preventDefault();
    });

    handle.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      nav.style.left = (e.clientX - offX) + 'px';
      nav.style.top = (e.clientY - offY) + 'px';
    });

    function end(e) {
      if (!dragging) return;
      dragging = false;
      nav.classList.remove('dragging');
      var rect = nav.getBoundingClientRect();
      var corner = nearestCorner(rect.left + rect.width / 2, rect.top + rect.height / 2);
      applyCorner(nav, corner);
      try { localStorage.setItem(STORE_KEY, corner); } catch (err) { }
    }
    handle.addEventListener('pointerup', end);
    handle.addEventListener('pointercancel', end);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
