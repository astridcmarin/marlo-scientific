/* Body map 3D viewer (Digital human 1.0, step 1.3b).
 *
 * Draws the pinned HRA organ models with plain WebGL: no external library. Each model's SHA-256 is checked against the
 * manifest before anything is drawn; a changed file is refused and the 2D diagram stays the only view.
 * Simulation organs (elimination route) are coloured; context organs are faint and never carry a result.
 */
(function () {
  'use strict';
  var root = document.getElementById('body-map-viewer');
  var configNode = document.getElementById('body-map-config');
  if (!root || !configNode) return;
  var config = JSON.parse(configNode.textContent);
  var canvas = root.querySelector('canvas');
  var status = root.querySelector('[data-role="status"]');
  var card = root.querySelector('[data-role="card"]');

  function say(text, isError) {
    status.textContent = text;
    status.hidden = !text;
    status.classList.toggle('bm-error', !!isError);
  }

  function hex(buffer) {
    return Array.prototype.map.call(new Uint8Array(buffer), function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
  }

  /* ---------------------------------------------------------------- GLB parsing (positions, normals, indices) */
  function parseGlb(buffer) {
    var view = new DataView(buffer);
    if (view.getUint32(0, true) !== 0x46546C67 || view.getUint32(4, true) !== 2) throw new Error('Not a glTF 2.0 file.');
    var jsonLength = view.getUint32(12, true);
    var gltf = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 20, jsonLength)));
    var binStart = 20 + jsonLength + 8;
    var types = { 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array };
    var sizes = { SCALAR: 1, VEC3: 3 };
    function accessor(i) {
      var a = gltf.accessors[i], v = gltf.bufferViews[a.bufferView];
      var T = types[a.componentType];
      return new T(buffer, binStart + (v.byteOffset || 0) + (a.byteOffset || 0), a.count * sizes[a.type]);
    }
    return gltf.nodes.filter(function (n) { return n.mesh !== undefined; }).map(function (n) {
      if (n.matrix || n.translation || n.rotation || n.scale) throw new Error('Unexpected node transform in ' + n.name + '.');
      var p = gltf.meshes[n.mesh].primitives[0];
      return { name: n.name, extras: n.extras || {}, positions: accessor(p.attributes.POSITION),
               normals: accessor(p.attributes.NORMAL), indices: accessor(p.indices) };
    });
  }

  /* ---------------------------------------------------------------- styles */
  function style(part) {
    var e = part.extras, g = e.group || '', s = e.structure || '';
    if (e['class'] === 'context') {
      if (g === 'VH_M_skin') return { c: [0.35, 0.6, 1.0], a: 0.30, rim: 1.5, body: 0.05, pass: 3 };
      if (/vertebral|pelvis|lower_limb/.test(g)) return { c: [0.75, 0.8, 0.85], a: 0.16, rim: 0.5, body: 0.35, pass: 2 };
      return { c: [0.6, 0.72, 0.85], a: 0.16, rim: 0.8, body: 0.28, pass: 2 };
    }
    if (s === 'arteries') return { c: [0.92, 0.16, 0.16], a: 1, rim: 0.35, body: 1, pass: 0 };
    if (s === 'veins') return { c: [0.25, 0.42, 1.0], a: 1, rim: 0.35, body: 1, pass: 0 };
    if (s === 'unlabelled vessels') return { c: [0.6, 0.35, 0.6], a: 1, rim: 0.3, body: 1, pass: 0 };
    if (g === 'VH_M_heart') return { c: [0.85, 0.22, 0.25], a: 1, rim: 0.35, body: 1, pass: 0 };
    if (/kidney/.test(g)) {
      if (s === 'kidney capsule') return { c: [0.98, 0.62, 0.58], a: 0.35, rim: 0.9, body: 0.5, pass: 1 };
      if (s === 'renal pyramids') return { c: [0.95, 0.3, 0.32], a: 1, rim: 0.4, body: 1, pass: 0 };
      if (s === 'renal papillae') return { c: [1.0, 0.75, 0.35], a: 1, rim: 0.4, body: 1, pass: 0 };
      return { c: [0.95, 0.6, 0.55], a: 0.5, rim: 0.6, body: 0.6, pass: 1 };
    }
    if (/ureter|urinary_bladder|urethra/.test(g)) return { c: [1.0, 0.8, 0.32], a: 1, rim: 0.4, body: 1, pass: 0 };
    if (g === 'VH_M_small_intestine') return { c: [0.85, 0.45, 0.6], a: 0.22, rim: 0.7, body: 0.45, pass: 1 };
    return { c: [1, 1, 1], a: 1, rim: 0, body: 1, pass: 0 };
  }

  /* ---------------------------------------------------------------- WebGL */
  var gl = canvas.getContext('webgl', { antialias: true, alpha: true, preserveDrawingBuffer: true });
  if (!gl || !gl.getExtension('OES_element_index_uint')) {
    say('3D view not available in this browser. The flow diagram below shows the same numbers.', false);
    return;
  }
  if (!window.crypto || !window.crypto.subtle) {
    say('This browser cannot check the 3D files\' checksums here (it needs a secure connection), so the 3D view is not shown. The flow diagram below shows the same numbers.', false);
    return;
  }
  var VS = 'attribute vec3 p;attribute vec3 n;uniform mat3 R;uniform vec3 C;uniform float S,A;varying vec3 vn;' +
    'void main(){vec3 q=R*(p-C);vn=R*n;gl_Position=vec4(q.x*S/A,q.y*S,-q.z*0.6,1.);}';
  var FS = 'precision mediump float;varying vec3 vn;uniform vec3 col;uniform float alpha,rim,body,pick;uniform vec3 pickCol;' +
    'void main(){if(pick>0.5){gl_FragColor=vec4(pickCol,1.);return;}vec3 n=normalize(vn);float f=pow(1.-abs(n.z),2.2);' +
    'vec3 L=normalize(vec3(-.4,.5,.8));float d=max(dot(n,L),0.);float s=pow(max(dot(reflect(-L,n),vec3(0,0,1)),0.),28.);' +
    'vec3 c=col*(0.28+0.72*d)*body+vec3(.55,.8,1.)*f*rim+vec3(1.)*s*.22*body;gl_FragColor=vec4(c,alpha*min(1.,body+f*rim));}';
  function shader(type, src) {
    var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }
  var program = gl.createProgram();
  gl.attachShader(program, shader(gl.VERTEX_SHADER, VS));
  gl.attachShader(program, shader(gl.FRAGMENT_SHADER, FS));
  gl.linkProgram(program);
  gl.useProgram(program);
  var U = {}; ['R', 'C', 'S', 'A', 'col', 'alpha', 'rim', 'body', 'pick', 'pickCol'].forEach(function (k) { U[k] = gl.getUniformLocation(program, k); });
  var aP = gl.getAttribLocation(program, 'p'), aN = gl.getAttribLocation(program, 'n');
  gl.enableVertexAttribArray(aP); gl.enableVertexAttribArray(aN);

  var parts = [];
  function upload(part) {
    function buf(target, data) { var b = gl.createBuffer(); gl.bindBuffer(target, b); gl.bufferData(target, data, gl.STATIC_DRAW); return b; }
    var indices = part.indices instanceof Uint32Array ? part.indices : new Uint32Array(part.indices);
    part.pb = buf(gl.ARRAY_BUFFER, part.positions);
    part.nb = buf(gl.ARRAY_BUFFER, part.normals);
    part.ib = buf(gl.ELEMENT_ARRAY_BUFFER, indices);
    part.count = indices.length;
    part.st = style(part);
    part.id = parts.length + 1;
    part.idColor = [(part.id & 255) / 255, ((part.id >> 8) & 255) / 255, 0];
    parts.push(part);
  }

  /* ---------------------------------------------------------------- camera */
  var PRESETS = config.camera_presets;
  var cam = Object.assign({}, PRESETS[0]);
  function rotation() {
    var cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw), cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
    // yaw about y, then pitch about x; column-major for WebGL
    return [cy, sy * sp, -sy * cp, 0, cp, sp, sy, -cy * sp, cy * cp];
  }
  function resize() {
    var r = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.round(w * r) || canvas.height !== Math.round(h * r)) {
      canvas.width = Math.round(w * r); canvas.height = Math.round(h * r);
    }
  }
  function setCommon() {
    gl.uniformMatrix3fv(U.R, false, rotation());
    gl.uniform3fv(U.C, [cam.cx, cam.cy, 0]);
    gl.uniform1f(U.S, cam.scale);
    gl.uniform1f(U.A, canvas.width / canvas.height);
  }
  function bind(part) {
    gl.bindBuffer(gl.ARRAY_BUFFER, part.pb); gl.vertexAttribPointer(aP, 3, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, part.nb); gl.vertexAttribPointer(aN, 3, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, part.ib);
  }
  var selected = null;
  function draw() {
    resize();
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.uniform1f(U.pick, 0);
    setCommon();
    [0, 1, 2, 3].forEach(function (pass) {
      if (pass === 0) { gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND); }
      else { gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE); gl.depthMask(false); }
      parts.forEach(function (part) {
        if (part.st.pass !== pass) return;
        var boost = selected === part ? 1.6 : 1;
        gl.uniform3fv(U.col, part.st.c);
        gl.uniform1f(U.alpha, Math.min(1, part.st.a * boost));
        gl.uniform1f(U.rim, part.st.rim * boost);
        gl.uniform1f(U.body, part.st.body);
        bind(part);
        gl.drawElements(gl.TRIANGLES, part.count, gl.UNSIGNED_INT, 0);
      });
    });
    gl.depthMask(true);
  }
  var pending = false;
  function redraw() { if (!pending) { pending = true; requestAnimationFrame(function () { pending = false; draw(); }); } }

  /* ---------------------------------------------------------------- picking (ID colours in an offscreen buffer) */
  var fbo = null, fboTex = null, fboDepth = null, fboSize = [0, 0];
  function pickAt(x, y) {
    var w = canvas.width, h = canvas.height;
    if (!fbo || fboSize[0] !== w || fboSize[1] !== h) {
      fbo = fbo || gl.createFramebuffer(); fboTex = fboTex || gl.createTexture(); fboDepth = fboDepth || gl.createRenderbuffer();
      gl.bindTexture(gl.TEXTURE_2D, fboTex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
      gl.bindRenderbuffer(gl.RENDERBUFFER, fboDepth);
      gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT16, w, h);
      gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, fboTex, 0);
      gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, fboDepth);
      fboSize = [w, h];
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.viewport(0, 0, w, h);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
    gl.uniform1f(U.pick, 1);
    setCommon();
    // Simulation parts are picked first through translucent context organs: draw them, then context behind.
    parts.forEach(function (part) {
      if (part.extras['class'] !== 'simulation') return;
      gl.uniform3fv(U.pickCol, part.idColor); bind(part); gl.drawElements(gl.TRIANGLES, part.count, gl.UNSIGNED_INT, 0);
    });
    var pixel = new Uint8Array(4);
    gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    if (!pixel[3]) {
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      parts.forEach(function (part) {
        if (part.extras['class'] !== 'context' || part.extras.group === 'VH_M_skin') return;
        gl.uniform3fv(U.pickCol, part.idColor); bind(part); gl.drawElements(gl.TRIANGLES, part.count, gl.UNSIGNED_INT, 0);
      });
      gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.uniform1f(U.pick, 0);
    var id = pixel[3] ? pixel[0] + (pixel[1] << 8) : 0;
    return id ? parts[id - 1] : null;
  }

  function showCard(part) {
    selected = part;
    redraw();
    if (!part) { card.hidden = true; return; }
    var e = part.extras;
    var info = config.parts[part.name] || {};
    var node = e.body_map_node ? config.node_labels[e.body_map_node] : null;
    card.querySelector('[data-role="card-title"]').textContent = info.title || part.name;
    card.querySelector('[data-role="card-class"]').textContent = node
      ? 'Simulation organ: draws "' + node + '". Its numbers are in the table beside the view.'
      : config.context_label;
    var ids = (e.ontology_ids || []).filter(function (id) { return id.indexOf('UBERON:') === 0; });
    card.querySelector('[data-role="card-ids"]').textContent = (ids.length ? 'Anatomy IDs: ' + ids.slice(0, 3).join(', ') +
      (ids.length > 3 ? ' and ' + (ids.length - 3) + ' more' : '') : '') +
      (e.placement === 'approximate_by_hand' ? ' · placed by hand, approximate' : '');
    card.hidden = false;
  }

  /* ---------------------------------------------------------------- interaction */
  var drag = null;
  canvas.addEventListener('pointerdown', function (ev) {
    drag = { x: ev.clientX, y: ev.clientY, yaw: cam.yaw, pitch: cam.pitch, moved: false };
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener('pointermove', function (ev) {
    if (!drag) return;
    var dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    if (!drag.moved) return;
    cam.yaw = drag.yaw + dx * 0.01;
    cam.pitch = Math.max(-0.6, Math.min(0.6, drag.pitch + dy * 0.005));
    redraw();
  });
  canvas.addEventListener('pointerup', function (ev) {
    if (drag && !drag.moved && parts.length) {
      var r = canvas.getBoundingClientRect(), scale = canvas.width / r.width;
      showCard(pickAt(Math.round((ev.clientX - r.left) * scale), Math.round((r.bottom - ev.clientY) * scale)));
    }
    drag = null;
  });
  root.querySelectorAll('[data-preset]').forEach(function (button) {
    button.addEventListener('click', function () {
      cam = Object.assign({}, PRESETS[Number(button.dataset.preset)]);
      root.querySelectorAll('[data-preset]').forEach(function (b) { b.setAttribute('aria-pressed', String(b === button)); });
      redraw();
    });
  });
  root.querySelectorAll('[data-zoom]').forEach(function (button) {
    button.addEventListener('click', function () {
      cam.scale = Math.max(0.6, Math.min(12, cam.scale * (button.dataset.zoom === 'in' ? 1.25 : 0.8)));
      redraw();
    });
  });
  window.addEventListener('resize', redraw);
  card.querySelector('[data-role="card-close"]').addEventListener('click', function () { showCard(null); });

  /* ---------------------------------------------------------------- load: check checksums, then draw */
  say('Loading the 3D anatomy and checking its checksums…');
  var models = config.models.slice().sort(function (a, b) { return a['class'] === 'simulation' ? -1 : b['class'] === 'simulation' ? 1 : 0; });
  models.reduce(function (chain, model) {
    return chain.then(function () {
      return fetch(model.url, { cache: 'force-cache' }).then(function (r) {
        if (!r.ok) throw new Error('Could not load ' + model.url + '.');
        return r.arrayBuffer();
      }).then(function (buffer) {
        return crypto.subtle.digest('SHA-256', buffer).then(function (sum) {
          if (hex(sum) !== model.sha256) throw new Error('A 3D model file does not match its recorded checksum; the 3D view is not shown.');
          parseGlb(buffer).forEach(upload);
          redraw();
        });
      });
    });
  }, Promise.resolve()).then(function () {
    say('');
    root.dataset.state = 'ready';
  }).catch(function (err) {
    parts = [];
    redraw();
    say(err.message + ' The flow diagram below shows the same numbers.', true);
    root.dataset.state = 'refused';
  });
})();
