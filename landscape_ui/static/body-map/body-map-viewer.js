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
    // c colour, a opacity, rim edge glow, body surface shading, pass (0 solid, 1-2 translucent sorted, 3 skin glow),
    // spec highlight strength. Colours carry no result: only the kidney outline follows the evidence band.
    var e = part.extras, g = e.group || '', s = e.structure || '';
    if (e['class'] === 'context') {
      if (g === 'VH_M_skin') return { c: [0.35, 0.6, 1.0], a: 0.30, rim: 1.5, body: 0.05, pass: 3, spec: 0 };
      if (/vertebral|pelvis|lower_limb/.test(g)) return { c: [0.78, 0.82, 0.88], a: 0.22, rim: 0.5, body: 0.45, pass: 2, spec: 0.1 };
      return { c: [0.66, 0.76, 0.95], a: 0.2, rim: 0.9, body: 0.4, pass: 2, spec: 0.1 };
    }
    if (s === 'arteries') return { c: [0.88, 0.14, 0.16], a: 1, rim: 0.3, body: 1, pass: 0, spec: 0.55 };
    if (s === 'veins') return { c: [0.22, 0.4, 0.95], a: 1, rim: 0.3, body: 1, pass: 0, spec: 0.55 };
    if (s === 'unlabelled vessels') return { c: [0.6, 0.35, 0.62], a: 1, rim: 0.3, body: 1, pass: 0, spec: 0.4 };
    if (g === 'VH_M_heart') return { c: [0.8, 0.2, 0.24], a: 1, rim: 0.3, body: 1, pass: 0, spec: 0.35 };
    if (/kidney/.test(g)) {
      var outline = config.flows && config.flows.band.outline;
      if (s === 'kidney capsule' && outline === 'warning') return { c: [1.0, 0.45, 0.2], a: 0.6, rim: 2.6, body: 0.25, pass: 3, warn: [1.0, 0.5, 0.2], spec: 0 };
      if (s === 'kidney capsule' && outline === 'caution') return { c: [1.0, 0.75, 0.3], a: 0.5, rim: 2.0, body: 0.25, pass: 3, warn: [1.0, 0.8, 0.3], spec: 0 };
      if (s === 'kidney capsule') return { c: [0.96, 0.7, 0.66], a: 0.35, rim: 1.1, body: 0.3, pass: 3, spec: 0 };
      if (s === 'renal pyramids') return { c: [0.86, 0.28, 0.32], a: 1, rim: 0.3, body: 1, pass: 0, spec: 0.2 };
      if (s === 'renal papillae') return { c: [1.0, 0.62, 0.6], a: 1, rim: 0.3, body: 1, pass: 0, spec: 0.2 };
      if (s === 'renal cortex') return { c: [1.0, 0.62, 0.56], a: 0.2, rim: 0.6, body: 0.8, pass: 1, spec: 0.12 };
      return { c: [0.9, 0.62, 0.55], a: 0.6, rim: 0.5, body: 0.75, pass: 1, spec: 0.15 };
    }
    if (/ureter|urinary_bladder|urethra/.test(g)) return { c: [0.98, 0.78, 0.3], a: 1, rim: 0.3, body: 1, pass: 0, spec: 0.45 };
    if (g === 'VH_M_small_intestine') return { c: [0.86, 0.48, 0.62], a: 0.2, rim: 0.7, body: 0.45, pass: 3, spec: 0 };
    return { c: [1, 1, 1], a: 1, rim: 0, body: 1, pass: 0, spec: 0.2 };
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
  // Lighting (rendering pass, 3 November 2026): a key light from upper left, a cool fill from the right, a back light
  // for edges, a sky/ground ambient, and a specular highlight whose strength depends on the material.
  var FS = 'precision mediump float;varying vec3 vn;uniform vec3 col,rimCol;uniform float alpha,rim,body,pick,spec;uniform vec3 pickCol;' +
    'void main(){if(pick>0.5){gl_FragColor=vec4(pickCol,1.);return;}vec3 n=normalize(vn);if(!gl_FrontFacing)n=-n;float f=pow(1.-abs(n.z),2.2);' +
    'vec3 K=normalize(vec3(-.45,.55,.75)),Fl=normalize(vec3(.7,.1,.6)),B=normalize(vec3(.2,.3,-.9));' +
    'float dk=max(dot(n,K),0.),df=max(dot(n,Fl),0.),db=pow(max(dot(n,B),0.),2.);' +
    'vec3 amb=mix(vec3(.16,.14,.24),vec3(.30,.32,.42),n.y*.5+.5);' +
    'vec3 light=amb+vec3(1.,.97,.92)*dk*.78+vec3(.55,.68,1.)*df*.28+vec3(.6,.75,1.)*db*.35;' +
    'vec3 H=normalize(K+vec3(0,0,1));float sp=pow(max(dot(n,H),0.),40.)*spec;' +
    'vec3 c=col*light*body+rimCol*f*rim+vec3(1.)*sp*body;gl_FragColor=vec4(c,alpha*min(1.,body+f*rim));}';
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
  var U = {}; ['R', 'C', 'S', 'A', 'col', 'rimCol', 'alpha', 'rim', 'body', 'pick', 'pickCol', 'spec'].forEach(function (k) { U[k] = gl.getUniformLocation(program, k); });
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
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (var v = 0; v < part.positions.length; v += 3) for (var c = 0; c < 3; c++) {
      var x = part.positions[v + c]; if (x < lo[c]) lo[c] = x; if (x > hi[c]) hi[c] = x;
    }
    part.centre = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2];
    part.radius = Math.max(0.005, Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2);
    part.id = parts.length + 1;
    part.idColor = [(part.id & 255) / 255, ((part.id >> 8) & 255) / 255, 0];
    parts.push(part);
  }

  /* ---------------------------------------------------------------- camera */
  var PRESETS = config.camera_presets;
  var cam = Object.assign({ cz: 0 }, PRESETS[0]);
  function centre() { return [cam.cx, cam.cy, cam.cz || 0]; }
  function rotation() {
    var cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw), cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
    // yaw about y, then pitch about x; column-major for WebGL
    return [cy, sy * sp, -sy * cp, 0, cp, sp, sy, -cy * sp, cy * cp];
  }
  function resize() {
    var r = Math.min(2, window.devicePixelRatio || 1), w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.round(w * r) || canvas.height !== Math.round(h * r)) {
      canvas.width = Math.round(w * r); canvas.height = Math.round(h * r);
    }
  }
  function setCommon() {
    gl.uniformMatrix3fv(U.R, false, rotation());
    gl.uniform3fv(U.C, centre());
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
    function drawPart(part, alphaScale) {
      var boost = selected === part ? 1.6 : 1;
      gl.uniform3fv(U.col, part.st.c);
      gl.uniform3fv(U.rimCol, part.st.warn || [0.55, 0.8, 1.0]);
      gl.uniform1f(U.alpha, Math.min(1, part.st.a * boost * alphaScale));
      gl.uniform1f(U.rim, part.st.rim * boost);
      gl.uniform1f(U.body, part.st.body);
      gl.uniform1f(U.spec, part.st.spec || 0);
      bind(part);
      gl.drawElements(gl.TRIANGLES, part.count, gl.UNSIGNED_INT, 0);
    }
    var R = rotation();
    var depth = function (part) {
      var q = sub(part.centre, centre());
      return R[2] * q[0] + R[5] * q[1] + R[8] * q[2];
    };
    function translucent(pass) {
      // Farthest first, ordinary alpha blending, so nearer layers cover farther ones instead of adding up to a white
      // haze. Back faces before front faces, so each organ's own far side sits behind it.
      gl.enable(gl.BLEND); gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.depthMask(false); gl.enable(gl.CULL_FACE);
      parts.filter(function (p) { return p.st.pass === pass; }).sort(function (a, b) { return depth(a) - depth(b); })
        .forEach(function (part) {
          gl.cullFace(gl.FRONT); drawPart(part, 0.6);
          gl.cullFace(gl.BACK); drawPart(part, 1);
        });
      gl.disable(gl.CULL_FACE);
    }
    // Context anatomy first, as a backdrop: it is for orientation, so it never veils the organs that carry results.
    gl.enable(gl.DEPTH_TEST);
    translucent(2);
    // Simulation organs on top of it: solid ones with depth, then the translucent ones.
    gl.depthMask(true); gl.disable(gl.BLEND);
    parts.forEach(function (part) { if (part.st.pass === 0) drawPart(part, 1); });
    translucent(1);
    // 3: glowing layers added on top: the skin, the small intestine (dose in, behind which the vessels must stay
    // visible) and the kidney capsule (whose edge colour shows the evidence band).
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    parts.forEach(function (part) { if (part.st.pass === 3) drawPart(part, 1); });
    gl.depthMask(true);
    if (flowsOn) {
      // The flow layer is a diagram drawn over the anatomy: clear depth so vessels and organs never hide it.
      gl.clear(gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST); gl.disable(gl.BLEND);
      drawTubes();
      drawParticles();
    }
    placeLabels();
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
    var pixel = new Uint8Array(4);
    if (flowsOn && pickTubes.length) {
      // Flows are drawn over the anatomy, so they are picked first, through their wider glow tube (easier to hit).
      pickTubes.forEach(function (tube, i) {
        gl.uniform3fv(U.pickCol, [(i + 1) / 255, 0, 1]);
        gl.bindBuffer(gl.ARRAY_BUFFER, tube.halo.pb); gl.vertexAttribPointer(aP, 3, gl.FLOAT, false, 0, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, tube.halo.nb); gl.vertexAttribPointer(aN, 3, gl.FLOAT, false, 0, 0);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, tube.halo.ib);
        gl.drawElements(gl.TRIANGLES, tube.halo.count, gl.UNSIGNED_INT, 0);
      });
      gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
      if (pixel[3] && pixel[2] === 255 && pixel[0]) {
        gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.uniform1f(U.pick, 0);
        return { flow: pickTubes[pixel[0] - 1].kind };
      }
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    }
    // Simulation parts are picked first through translucent context organs: draw them, then context behind.
    parts.forEach(function (part) {
      if (part.extras['class'] !== 'simulation') return;
      gl.uniform3fv(U.pickCol, part.idColor); bind(part); gl.drawElements(gl.TRIANGLES, part.count, gl.UNSIGNED_INT, 0);
    });
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

  function fillEvidence(body, evidence) {
    if (!evidence.what) { var h = document.createElement('p'); h.className = 'bm-card-sub'; h.textContent = evidence.title; body.appendChild(h); }
    if (evidence.what) { var w = document.createElement('p'); w.textContent = evidence.what; body.appendChild(w); }
    var dl = document.createElement('dl');
    evidence.rows.forEach(function (row) {
      var dt = document.createElement('dt'); dt.textContent = row[0];
      var dd = document.createElement('dd'); dd.textContent = row[1];
      dl.appendChild(dt); dl.appendChild(dd);
    });
    body.appendChild(dl);
    if (evidence.status_text) {
      var st = document.createElement('p');
      st.className = 'bm-card-status bm-status-' + evidence.status; st.textContent = evidence.status_text; body.appendChild(st);
    }
    evidence.basis.forEach(function (b) { var p = document.createElement('p'); p.className = 'bm-card-basis'; p.textContent = b; body.appendChild(p); });
    var src = document.createElement('p'); src.className = 'bm-card-ids'; src.textContent = 'Source: ' + evidence.source; body.appendChild(src);
  }
  function showCard(part) {
    if (part && part.flow) {
      selected = null; redraw();
      var fbf = card.querySelector('[data-role="card-focus"]'); if (fbf) fbf.hidden = true;
      var fc = (config.flow_cards || {})[part.flow];
      if (!fc) { card.hidden = true; return; }
      card.querySelector('[data-role="card-title"]').textContent = fc.title;
      card.querySelector('[data-role="card-class"]').textContent = 'Flow: a clearance on the elimination route, drawn as a diagram over the anatomy.';
      var fb = card.querySelector('[data-role="card-evidence"]'); fb.textContent = '';
      fillEvidence(fb, fc);
      card.querySelector('[data-role="card-ids"]').textContent = '';
      card.hidden = false;
      return;
    }
    selected = part;
    redraw();
    if (!part) { card.hidden = true; return; }
    var fb2 = card.querySelector('[data-role="card-focus"]'); if (fb2) fb2.hidden = false;
    var e = part.extras;
    var info = config.parts[part.name] || {};
    var node = e.body_map_node ? config.node_labels[e.body_map_node] : null;
    var evidence = e.body_map_node && config.cards ? config.cards[e.body_map_node] : null;
    card.querySelector('[data-role="card-title"]').textContent = info.title || part.name;
    card.querySelector('[data-role="card-class"]').textContent = node
      ? 'Simulation organ: draws "' + node + '".' + (evidence ? '' : ' Its numbers are in the table beside the view.')
      : config.context_label;
    var body = card.querySelector('[data-role="card-evidence"]');
    body.textContent = '';
    if (evidence) fillEvidence(body, evidence);
    var ids = (e.ontology_ids || []).filter(function (id) { return id.indexOf('UBERON:') === 0; });
    card.querySelector('[data-role="card-ids"]').textContent = (ids.length ? 'Anatomy IDs: ' + ids.slice(0, 3).join(', ') +
      (ids.length > 3 ? ' and ' + (ids.length - 3) + ' more' : '') : '') +
      (e.placement === 'approximate_by_hand' ? ' · placed by hand, approximate' : '');
    card.hidden = false;
  }

  /* ---------------------------------------------------------------- flows (step 1.3c) */
  var F = config.flows || null;
  var B = (F && config.blood) || null;
  var flowsOn = !!F, labelsOn = !!F, tubes = [], pickTubes = [], strands = [], bloodStrands = [], bloodOn = false;
  var reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var playing = !!F && !reducedMotion, clock = 0, last = null;

  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function mul(a, k) { return [a[0] * k, a[1] * k, a[2] * k]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function norm(a) { var l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }

  function smooth(points, perSegment) {
    // Catmull-Rom through the path points, so tubes and particles follow a smooth line.
    if (points.length < 3) {
      var out2 = [];
      for (var k = 0; k <= perSegment; k++) out2.push(add(points[0], mul(sub(points[1], points[0]), k / perSegment)));
      return out2;
    }
    var out = [], p = [points[0]].concat(points, [points[points.length - 1]]);
    for (var i = 1; i < p.length - 2; i++) {
      for (var j = 0; j < perSegment; j++) {
        var t = j / perSegment, t2 = t * t, t3 = t2 * t;
        out.push([0, 1, 2].map(function (c) {
          return 0.5 * (2 * p[i][c] + (-p[i - 1][c] + p[i + 1][c]) * t + (2 * p[i - 1][c] - 5 * p[i][c] + 4 * p[i + 1][c] - p[i + 2][c]) * t2 +
                        (-p[i - 1][c] + 3 * p[i][c] - 3 * p[i + 1][c] + p[i + 2][c]) * t3);
        }));
      }
    }
    out.push(points[points.length - 1]);
    return out;
  }

  function frames(line) {
    // Tangents and parallel-transported normals along a polyline.
    var t = line.map(function (_, i) { return norm(sub(line[Math.min(i + 1, line.length - 1)], line[Math.max(i - 1, 0)])); });
    var n = [norm(cross(t[0], Math.abs(t[0][1]) < 0.9 ? [0, 1, 0] : [1, 0, 0]))];
    for (var i = 1; i < line.length; i++) {
      var b = cross(t[i - 1], t[i]);
      var nb = Math.hypot(b[0], b[1], b[2]);
      if (nb < 1e-9) { n.push(n[i - 1]); continue; }
      n.push(norm(cross(cross(t[i], n[i - 1]), t[i])));
    }
    return { t: t, n: n };
  }

  function tubeMesh(line, radius, sides) {
    var fr = frames(line), pos = [], nor = [], idx = [];
    line.forEach(function (c, i) {
      var nn = fr.n[i], bb = cross(fr.t[i], nn);
      for (var k = 0; k < sides; k++) {
        var a = 2 * Math.PI * k / sides, d = add(mul(nn, Math.cos(a)), mul(bb, Math.sin(a)));
        pos.push.apply(pos, add(c, mul(d, radius))); nor.push.apply(nor, d);
      }
    });
    for (var i = 0; i < line.length - 1; i++) {
      for (var k = 0; k < sides; k++) {
        var a0 = i * sides + k, a1 = i * sides + (k + 1) % sides, b0 = a0 + sides, b1 = a1 + sides;
        idx.push(a0, b0, a1, a1, b0, b1);
      }
    }
    return { positions: new Float32Array(pos), normals: new Float32Array(nor), indices: new Uint32Array(idx) };
  }

  function lengths(line) {
    var acc = [0];
    for (var i = 1; i < line.length; i++) { var d = sub(line[i], line[i - 1]); acc.push(acc[i - 1] + Math.hypot(d[0], d[1], d[2])); }
    return acc;
  }

  function buildFlows() {
    if (!F) return;
    F.paths.forEach(function (path) {
      var line = smooth(path.points, 8);
      var fr = frames(line);
      var values = path.flows.map(function (kind) { return F.values[kind]; });
      var radii = values.map(function (v) { return v === null ? 0.0012 : Math.max(0.0008, 0.5 * F.tube_diameter_at_scale_m * v * path.share_per_path / F.scale_ml_min); });
      var total = radii.reduce(function (a, b) { return a + b; }, 0);
      var offset = -total;
      path.flows.forEach(function (kind, i) {
        offset += radii[i];
        var shift = path.flows.length > 1 ? offset : 0;
        var strandLine = line.map(function (c, j) { return add(c, mul(fr.n[j], shift)); });
        offset += radii[i] + 0.0006;
        var mesh = tubeMesh(strandLine, radii[i], 10);
        var color = F.colors[kind];
        var tube = { kind: kind, dashed: values[i] === null, color: color, count: mesh.indices.length };
        function buf(target, data) { var b = gl.createBuffer(); gl.bindBuffer(target, b); gl.bufferData(target, data, gl.STATIC_DRAW); return b; }
        tube.pb = buf(gl.ARRAY_BUFFER, mesh.positions); tube.nb = buf(gl.ARRAY_BUFFER, mesh.normals); tube.ib = buf(gl.ELEMENT_ARRAY_BUFFER, mesh.indices);
        var halo = tubeMesh(strandLine, radii[i] * 2.2 + 0.0008, 10);
        tube.halo = { count: halo.indices.length, pb: buf(gl.ARRAY_BUFFER, halo.positions), nb: buf(gl.ARRAY_BUFFER, halo.normals),
                      ib: buf(gl.ELEMENT_ARRAY_BUFFER, halo.indices) };
        if (values[i] !== null) tubes.push(tube);
        pickTubes.push(tube);   // every strand can be selected, including the one drawn without a value
        var acc = lengths(strandLine), value = values[i] === null ? F.scale_ml_min * 0.15 : values[i] * path.share_per_path;
        // Particle speed is proportional to clearance on the fixed scale; spacing is constant.
        strands.push({ line: strandLine, acc: acc, length: acc[acc.length - 1], color: color, speed: 0.06 * value / (F.scale_ml_min * 0.5),
                       count: Math.max(3, Math.round(acc[acc.length - 1] / 0.012)), dashed: values[i] === null });
      });
    });
    if (B) B.paths.forEach(function (path) {
      var line = smooth(path.points, 8), acc = lengths(line);
      // Constant speed and spacing: reference blood flow is the same on every page, so it carries no record value.
      bloodStrands.push({ blood: true, line: line, acc: acc, length: acc[acc.length - 1], color: B.colors[path.kind], speed: 0.05,
                          count: Math.max(4, Math.round(acc[acc.length - 1] / 0.004)) });
    });
    particleBuffer = gl.createBuffer();
  }

  function drawTubes() {
    function drawMesh(m) {
      gl.bindBuffer(gl.ARRAY_BUFFER, m.pb); gl.vertexAttribPointer(aP, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, m.nb); gl.vertexAttribPointer(aN, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, m.ib);
      gl.drawElements(gl.TRIANGLES, m.count, gl.UNSIGNED_INT, 0);
    }
    gl.uniform1f(U.spec, 0.6);
    tubes.forEach(function (tube) {
      gl.uniform3fv(U.col, tube.color); gl.uniform3fv(U.rimCol, tube.color);
      gl.uniform1f(U.alpha, 1); gl.uniform1f(U.rim, 0.6); gl.uniform1f(U.body, 0.95);
      drawMesh(tube);
    });
    // Glow: a wider, faint tube around each one, added on top (decoration; its width is not a value).
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE); gl.depthMask(false);
    gl.uniform1f(U.spec, 0);
    tubes.forEach(function (tube) {
      gl.uniform3fv(U.col, tube.color); gl.uniform3fv(U.rimCol, tube.color);
      gl.uniform1f(U.alpha, 0.22); gl.uniform1f(U.rim, 0); gl.uniform1f(U.body, 0.9);
      drawMesh(tube.halo);
    });
    gl.disable(gl.BLEND); gl.depthMask(true);
  }

  var PVS = 'attribute vec3 p;uniform mat3 R;uniform vec3 C;uniform float S,A,size;void main(){vec3 q=R*(p-C);gl_Position=vec4(q.x*S/A,q.y*S,-q.z*0.6-0.002,1.);gl_PointSize=size;}';
  var PFS = 'precision mediump float;uniform vec3 col;uniform float fade,core;void main(){vec2 d=gl_PointCoord-vec2(.5);float r=dot(d,d);if(r>.25)discard;gl_FragColor=vec4(mix(mix(col,vec3(1.),core),col*1.15,smoothstep(0.,.04,r)),(1.-smoothstep(.14,.25,r))*fade);}';
  var pProgram = null, PU = {}, pA = -1, particleBuffer = null, particleData = null;
  if (F) {
    pProgram = gl.createProgram();
    gl.attachShader(pProgram, shader(gl.VERTEX_SHADER, PVS)); gl.attachShader(pProgram, shader(gl.FRAGMENT_SHADER, PFS));
    gl.linkProgram(pProgram);
    ['R', 'C', 'S', 'A', 'size', 'col', 'fade', 'core'].forEach(function (k) { PU[k] = gl.getUniformLocation(pProgram, k); });
    pA = gl.getAttribLocation(pProgram, 'p');
  }

  function at(strand, distance) {
    var acc = strand.acc, line = strand.line, i = 1;
    while (i < acc.length - 1 && acc[i] < distance) i++;
    var span = acc[i] - acc[i - 1] || 1, t = (distance - acc[i - 1]) / span;
    return add(line[i - 1], mul(sub(line[i], line[i - 1]), Math.max(0, Math.min(1, t))));
  }

  function drawParticles() {
    if (!pProgram || !strands.length) return;
    gl.useProgram(pProgram);
    gl.uniformMatrix3fv(PU.R, false, rotation()); gl.uniform3fv(PU.C, centre());
    gl.uniform1f(PU.S, cam.scale); gl.uniform1f(PU.A, canvas.width / canvas.height);
    var dpr = Math.min(2, window.devicePixelRatio || 1), pointSize = Math.max(3, Math.min(9, 1.6 * cam.scale)) * dpr;
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE); gl.enable(gl.DEPTH_TEST); gl.depthMask(false);
    gl.disableVertexAttribArray(aN);
    function drawStrand(strand) {
      var data = new Float32Array(strand.count * 3), spacing = strand.length / strand.count;
      for (var k = 0; k < strand.count; k++) {
        var gap = strand.dashed ? Math.floor(k / 3) * 2 * spacing : 0;   // groups of 3 dots with a gap after each
        data.set(at(strand, (k * spacing + gap + clock * strand.speed) % strand.length), k * 3);
      }
      gl.uniform3fv(PU.col, strand.color);
      // a path drawn without a value (absorption): smaller, all-colour dots in short groups, so it reads as dashed
      gl.uniform1f(PU.core, strand.dashed ? 0 : 1);
      gl.uniform1f(PU.size, (strand.dashed ? 0.9 : strand.blood ? 0.8 : 1) * pointSize);
      gl.bindBuffer(gl.ARRAY_BUFFER, particleBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW);
      gl.vertexAttribPointer(pA, 3, gl.FLOAT, false, 0, 0);
      gl.drawArrays(gl.POINTS, 0, strand.count);
    }
    if (bloodOn) {
      // the blood layer: smaller, fainter dots, drawn before the drug so the drug stays on top
      gl.uniform1f(PU.fade, 0.9); gl.disable(gl.DEPTH_TEST);
      bloodStrands.forEach(drawStrand);
      gl.enable(gl.DEPTH_TEST);
    }
    gl.uniform1f(PU.fade, 1);
    strands.forEach(drawStrand);
    gl.enableVertexAttribArray(aN);
    gl.depthMask(true);
    gl.useProgram(program);
  }

  function tick(now) {
    if (!playing) { last = null; return; }
    if (last !== null) clock += Math.min(0.1, (now - last) / 1000);
    last = now;
    draw();
    requestAnimationFrame(tick);
  }

  /* labels: HTML text with leader lines, anchored to points in the body */
  var overlay = null, labelNodes = {};
  var LABELS = F ? [
    { key: 'renal', anchor: 'aorta_renal_level', dx: 150, dy: -110 },
    { key: 'urine', anchor: 'bladder', dx: 150, dy: 0 },
    { key: 'non_renal', anchor: 'aorta_renal_level', dx: 160, dy: 75 },
    { key: 'absorption', anchor: 'gut', dx: -170, dy: 70 },
  ].concat(B ? [{ key: 'blood', anchor: 'kidney_right', dx: -150, dy: -95, onlyWith: 'blood' }] : []) : [];
  function project(p) {
    var R = rotation(), q = sub(p, centre());
    var x = R[0] * q[0] + R[3] * q[1] + R[6] * q[2], y = R[1] * q[0] + R[4] * q[1] + R[7] * q[2];
    var w = canvas.clientWidth, h = canvas.clientHeight;
    return [(x * cam.scale / (w / h) + 1) / 2 * w, (1 - y * cam.scale) / 2 * h];
  }
  var key = null, scaleBar = null, scaleText = null;
  function css(c) { return 'rgb(' + c.map(function (v) { return Math.round(255 * Math.min(1, v)); }).join(',') + ')'; }
  function setupKey() {
    // Flow key: what each colour is, and a scale bar for tube thickness at the current zoom (step 1.1, 4 November 2026).
    if (!F || !config.flow_key) return;
    key = document.createElement('div'); key.className = 'bm-flow-key';
    config.flow_key.forEach(function (k) {
      var row = document.createElement('span'); row.className = 'bm-key-row';
      var sw = document.createElement('i'); sw.className = 'bm-key-swatch' + (k.dashed ? ' bm-key-dashed' : '');
      sw.style.setProperty('--c', css(F.colors[k.kind])); row.appendChild(sw);
      row.appendChild(document.createTextNode(k.label)); key.appendChild(row);
    });
    if (B) {
      var br = document.createElement('span'); br.className = 'bm-key-row bm-key-blood'; br.hidden = true;
      br.innerHTML = '<i class="bm-key-dot" style="--c:rgb(255,77,77)"></i><i class="bm-key-dot" style="--c:rgb(89,140,255)"></i>Blood in / out (reference)';
      key.appendChild(br);
    }
    var sc = document.createElement('span'); sc.className = 'bm-key-row bm-key-scale';
    scaleBar = document.createElement('i'); scaleBar.className = 'bm-key-bar';
    scaleText = document.createElement('span');
    sc.appendChild(scaleBar); sc.appendChild(scaleText); key.appendChild(sc);
    // below the 3D view, so it never covers anatomy or labels
    root.parentNode.insertBefore(key, root.nextSibling);
  }
  function updateKey() {
    if (!key) return;
    key.hidden = !flowsOn;
    var br = key.querySelector('.bm-key-blood'); if (br) br.hidden = !bloodOn;
    // a strand carrying the reference clearance is this thick on screen (same rule as the tubes: diameter on one fixed scale)
    var ref = F.scale_reference_ml_min || 25;
    var px = F.tube_diameter_at_scale_m * ref / F.scale_ml_min * cam.scale * canvas.clientHeight / 2;
    scaleBar.style.height = Math.max(1, px).toFixed(1) + 'px';
    scaleText.textContent = (px < 1 ? 'thinner than 1 px here' : 'this thickness') + ' = ' + ref + ' mL/min in one strand';
  }
  function setupLabels() {
    if (!F) return;
    overlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    overlay.setAttribute('class', 'bm-overlay'); overlay.setAttribute('aria-hidden', 'true');
    root.insertBefore(overlay, canvas.nextSibling);
    LABELS.forEach(function (l) {
      var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      overlay.appendChild(line);
      var div = document.createElement('div');
      div.className = 'bm-flow-label bm-flow-' + l.key;
      div.textContent = l.key === 'blood' ? B.label : F.labels[l.key];
      root.insertBefore(div, overlay.nextSibling);
      labelNodes[l.key] = { div: div, line: line, spec: l };
    });
    if (F.band.outline) {
      // The caution is folded to two lines by default, with a button to read it all (12 November 2026). It is never
      // removed: the same text stays on the page above the view and on the kidney and urine cards.
      var banner = document.createElement('div');
      banner.className = 'bm-band-banner bm-band-' + F.band.outline;
      banner.setAttribute('role', 'note');
      var text = document.createElement('p'); text.className = 'bm-band-text'; text.id = 'bm-band-text';
      var strong = document.createElement('strong'); strong.textContent = 'Caution for this kidney-function band: ';
      text.appendChild(strong); text.appendChild(document.createTextNode(F.band.text));
      var toggle = document.createElement('button'); toggle.type = 'button'; toggle.className = 'bm-band-toggle';
      toggle.setAttribute('aria-controls', 'bm-band-text');
      var open = false;
      try { open = window.localStorage.getItem('bm-band-open') === '1'; } catch (e) { open = false; }
      function setOpen(v) {
        open = v; banner.classList.toggle('bm-collapsed', !open);
        toggle.textContent = open ? 'Show less' : 'Read the full caution';
        toggle.setAttribute('aria-expanded', String(open));
        try { window.localStorage.setItem('bm-band-open', open ? '1' : '0'); } catch (e) { /* not stored */ }
        if (typeof placeLabels === 'function') placeLabels();
      }
      toggle.addEventListener('click', function () { setOpen(!open); });
      banner.appendChild(text); banner.appendChild(toggle);
      root.insertBefore(banner, overlay.nextSibling);
      setOpen(open);
    }
  }
  function belowToolbar() {
    // the toolbar can wrap onto two rows (narrow windows, more buttons): keep the banner and the card below it
    var toolbar = root.querySelector('.bm-toolbar');
    if (!toolbar) return;
    var top = toolbar.offsetTop + toolbar.offsetHeight + 8;
    var banner = root.querySelector('.bm-band-banner');
    if (banner) banner.style.top = top + 'px';
    card.style.top = (banner && !banner.hidden ? top + banner.offsetHeight + 8 : top) + 'px';
  }
  function placeLabels() {
    belowToolbar();
    updateKey();
    if (!overlay) return;
    var w = canvas.clientWidth, h = canvas.clientHeight;
    overlay.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    var placed = [];
    // labels stay below the toolbar and the evidence banner
    var banner = root.querySelector('.bm-band-banner'), toolbar = root.querySelector('.bm-toolbar');
    var topLimit = banner && !banner.hidden ? banner.offsetTop + banner.offsetHeight + 8 : (toolbar ? toolbar.offsetTop + toolbar.offsetHeight + 8 : 56);
    Object.keys(labelNodes).forEach(function (key) {
      var n = labelNodes[key], a = project(F.anchors[n.spec.anchor]);
      var show = labelsOn && (n.spec.onlyWith !== 'blood' || bloodOn) && a[0] > 0 && a[0] < w && a[1] > 0 && a[1] < h;
      n.div.hidden = !show; n.line.style.display = show ? '' : 'none';
      if (!show) return;
      // keep the whole label inside the view: measure it, then clamp on the side it hangs from
      var bw = n.div.offsetWidth, bh = n.div.offsetHeight, left = n.spec.dx < 0;
      var lx = a[0] + n.spec.dx;
      lx = left ? Math.max(8 + bw, Math.min(w - 8, lx)) : Math.max(8, Math.min(w - 8 - bw, lx));
      var ly = Math.max(topLimit + bh / 2, Math.min(h - 40 - bh / 2, a[1] + n.spec.dy));
      placed.push({ n: n, a: a, lx: lx, ly: ly, bw: bw, bh: bh, left: left });
    });
    // labels hanging on the same side must not overlap: push later ones down (or up near the bottom)
    placed.sort(function (p, q) { return p.ly - q.ly; });
    placed.forEach(function (p, i) {
      for (var j = 0; j < i; j++) {
        var q = placed[j];
        var x0 = p.left ? p.lx - p.bw : p.lx, x1 = x0 + p.bw, y0 = q.left ? q.lx - q.bw : q.lx, y1 = y0 + q.bw;
        if (x0 < y1 && y0 < x1 && Math.abs(p.ly - q.ly) < (p.bh + q.bh) / 2 + 6) p.ly = q.ly + (p.bh + q.bh) / 2 + 6;
      }
      if (p.ly > h - 40 - p.bh / 2) p.ly = h - 40 - p.bh / 2;
    });
    placed.forEach(function (p) {
      p.n.div.style.left = p.lx + 'px'; p.n.div.style.top = p.ly + 'px';
      p.n.div.style.transform = p.left ? 'translate(-100%,-50%)' : 'translate(0,-50%)';
      p.n.line.setAttribute('x1', p.a[0]); p.n.line.setAttribute('y1', p.a[1]);
      p.n.line.setAttribute('x2', p.lx); p.n.line.setAttribute('y2', p.ly);
    });
  }

  function addFlowControls() {
    if (!F) return;
    var toolbar = root.querySelector('.bm-toolbar'), gap = toolbar.querySelector('.bm-toolbar-gap');
    function button(label, pressed, onClick) {
      var b = document.createElement('button');
      b.type = 'button'; b.textContent = label; b.setAttribute('aria-pressed', String(pressed));
      b.addEventListener('click', function () { onClick(b); });
      toolbar.insertBefore(b, gap);
      return b;
    }
    button('Flow', true, function (b) { flowsOn = !flowsOn; b.setAttribute('aria-pressed', String(flowsOn)); redraw(); });
    button(reducedMotion ? 'Animate' : 'Pause', !reducedMotion, function (b) {
      playing = !playing; b.textContent = playing ? 'Pause' : 'Animate'; b.setAttribute('aria-pressed', String(playing));
      if (playing) requestAnimationFrame(tick);
    });
    button('Labels', true, function (b) { labelsOn = !labelsOn; b.setAttribute('aria-pressed', String(labelsOn)); redraw(); });
    if (B) button('Blood flow', false, function (b) { bloodOn = !bloodOn; b.setAttribute('aria-pressed', String(bloodOn)); redraw(); });
  }

  /* ---------------------------------------------------------------- interaction */
  // Navigation (12 November 2026, replaces 4 November): drag moves the body (or turns it, with the "Drag: turn" button);
  // Shift-drag or right-drag does the other; scrolling over the view, pinch or the + and - buttons zoom towards the
  // pointer, in small steps; double-click an organ to zoom to it and turn around it, or empty space to zoom in there;
  // arrow keys move, Shift + arrows turn. Scrolling outside the view still scrolls the page.
  var ZOOM_MIN = 0.5, ZOOM_MAX = 40, dragMode = 'move', flight = null;
  function axes() {
    var R = rotation();
    return { right: [R[0], R[3], R[6]], up: [R[1], R[4], R[7]] };
  }
  function pan(dxPx, dyPx) {
    var w = canvas.clientWidth, h = canvas.clientHeight, ax = axes();
    var dRight = 2 * dxPx / w * (w / h) / cam.scale, dUp = -2 * dyPx / h / cam.scale;
    var c = sub(centre(), add(mul(ax.right, dRight), mul(ax.up, dUp)));
    cam.cx = c[0]; cam.cy = c[1]; cam.cz = c[2];
    redraw();
  }
  function zoomAt(factor, clientX, clientY) {
    var r = canvas.getBoundingClientRect(), w = r.width, h = r.height, ax = axes();
    flight = null;
    var next = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, cam.scale * factor));
    if (clientX !== undefined) {
      // keep the point under the pointer where it is
      var nx = 2 * (clientX - r.left) / w - 1, ny = 1 - 2 * (clientY - r.top) / h;
      var off = add(mul(ax.right, nx * (w / h) / cam.scale), mul(ax.up, ny / cam.scale));
      var c = add(centre(), mul(off, 1 - cam.scale / next));
      cam.cx = c[0]; cam.cy = c[1]; cam.cz = c[2];
    }
    cam.scale = next;
    redraw();
  }
  function flyTo(target, scale) {
    // a short glide to a new centre and zoom (instant when reduced motion is preferred)
    var from = { c: centre(), s: cam.scale }, to = { c: target, s: Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, scale)) };
    function set(t) {
      var e = t * t * (3 - 2 * t), c = add(from.c, mul(sub(to.c, from.c), e));
      cam.cx = c[0]; cam.cy = c[1]; cam.cz = c[2];
      cam.scale = from.s * Math.pow(to.s / from.s, e);
      draw();
    }
    if (reducedMotion) { set(1); return; }
    var start = null, token = flight = {};
    requestAnimationFrame(function step(now) {
      if (flight !== token) return;
      if (start === null) start = now;
      var t = Math.min(1, (now - start) / 350);
      set(t);
      if (t < 1) requestAnimationFrame(step); else flight = null;
    });
  }
  function focusPart(part) {
    // fill about two fifths of the view's height with the organ, and turn around its centre from now on
    if (part && part.centre) flyTo(part.centre, 0.8 / part.radius);
  }
  function screenPoint(ev) {
    var r = canvas.getBoundingClientRect(), scale = canvas.width / r.width;
    return [Math.round((ev.clientX - r.left) * scale), Math.round((r.bottom - ev.clientY) * scale)];
  }
  var drag = null, touches = {}, pinch = null;
  canvas.addEventListener('contextmenu', function (ev) { ev.preventDefault(); });
  canvas.addEventListener('pointerdown', function (ev) {
    touches[ev.pointerId] = { x: ev.clientX, y: ev.clientY };
    var ids = Object.keys(touches);
    if (ids.length === 2) {
      var a = touches[ids[0]], b = touches[ids[1]];
      pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
      drag = null;
    } else {
      var other = ev.shiftKey || ev.button === 2 || ev.button === 1;
      flight = null;
      drag = { x: ev.clientX, y: ev.clientY, yaw: cam.yaw, pitch: cam.pitch, moved: false,
               move: (dragMode === 'move') !== other };
    }
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener('pointermove', function (ev) {
    if (touches[ev.pointerId]) touches[ev.pointerId] = { x: ev.clientX, y: ev.clientY };
    if (pinch) {
      var ids = Object.keys(touches); if (ids.length < 2) return;
      var a = touches[ids[0]], b = touches[ids[1]];
      var d = Math.hypot(a.x - b.x, a.y - b.y), mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      pan(mx - pinch.mx, my - pinch.my);
      if (pinch.d > 0) zoomAt(d / pinch.d, mx, my);
      pinch = { d: d, mx: mx, my: my };
      return;
    }
    if (!drag) return;
    var dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    if (!drag.moved) return;
    if (drag.move) {
      pan(ev.clientX - (drag.lastX === undefined ? drag.x : drag.lastX), ev.clientY - (drag.lastY === undefined ? drag.y : drag.lastY));
      drag.lastX = ev.clientX; drag.lastY = ev.clientY;
      return;
    }
    cam.yaw = drag.yaw + dx * 0.01;
    cam.pitch = Math.max(-0.6, Math.min(0.6, drag.pitch + dy * 0.005));
    redraw();
  });
  function endPointer(ev) {
    delete touches[ev.pointerId];
    if (Object.keys(touches).length < 2) pinch = null;
  }
  canvas.addEventListener('pointerup', function (ev) {
    var wasPinch = !!pinch;
    endPointer(ev);
    if (!wasPinch && drag && !drag.moved && ev.button === 0 && parts.length) {
      var sp = screenPoint(ev);
      showCard(pickAt(sp[0], sp[1]));
    }
    drag = null;
  });
  canvas.addEventListener('pointercancel', function (ev) { endPointer(ev); drag = null; });
  canvas.addEventListener('dblclick', function (ev) {
    if (!parts.length) return;
    ev.preventDefault();
    var sp = screenPoint(ev), hit = pickAt(sp[0], sp[1]);
    if (hit && !hit.flow) { showCard(hit); focusPart(hit); } else zoomAt(2, ev.clientX, ev.clientY);
  });
  canvas.addEventListener('wheel', function (ev) {
    // scrolling over the view zooms at the pointer; trackpad pinch arrives as Ctrl + wheel, with smaller steps
    ev.preventDefault();
    var dy = ev.deltaMode === 1 ? ev.deltaY * 16 : ev.deltaMode === 2 ? ev.deltaY * 400 : ev.deltaY;
    zoomAt(Math.exp(-dy * (ev.ctrlKey ? 0.01 : 0.0025)), ev.clientX, ev.clientY);
  }, { passive: false });
  canvas.tabIndex = 0;
  canvas.addEventListener('keydown', function (ev) {
    var step = 40, k = ev.key;
    if (ev.shiftKey && (k === 'ArrowLeft' || k === 'ArrowRight')) { cam.yaw += (k === 'ArrowLeft' ? -0.15 : 0.15); redraw(); }
    else if (ev.shiftKey && (k === 'ArrowUp' || k === 'ArrowDown')) { cam.pitch = Math.max(-0.6, Math.min(0.6, cam.pitch + (k === 'ArrowUp' ? -0.1 : 0.1))); redraw(); }
    else if (k === 'ArrowLeft') pan(step, 0); else if (k === 'ArrowRight') pan(-step, 0);
    else if (k === 'ArrowUp') pan(0, step); else if (k === 'ArrowDown') pan(0, -step);
    else if (k === '+' || k === '=') zoomAt(1.25); else if (k === '-' || k === '_') zoomAt(0.8);
    else return;
    ev.preventDefault();
  });
  root.querySelectorAll('[data-preset]').forEach(function (button) {
    button.addEventListener('click', function () {
      flight = null;
      cam = Object.assign({ cz: 0 }, PRESETS[Number(button.dataset.preset)]);
      root.querySelectorAll('[data-preset]').forEach(function (b) { b.setAttribute('aria-pressed', String(b === button)); });
      redraw();
    });
  });
  root.querySelectorAll('[data-zoom]').forEach(function (button) {
    button.addEventListener('click', function () {
      zoomAt(button.dataset.zoom === 'in' ? 1.25 : 0.8);
    });
  });
  root.querySelectorAll('[data-drag]').forEach(function (button) {
    button.addEventListener('click', function () {
      dragMode = button.dataset.drag;
      root.querySelectorAll('[data-drag]').forEach(function (b) { b.setAttribute('aria-pressed', String(b === button)); });
    });
  });
  var focusButton = card.querySelector('[data-role="card-focus"]');
  if (focusButton) focusButton.addEventListener('click', function () { focusPart(selected); });
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
    buildFlows();
    setupLabels();
    setupKey();
    addFlowControls();
    redraw();
    if (playing) requestAnimationFrame(tick);
    root.dataset.state = 'ready';
  }).catch(function (err) {
    parts = [];
    redraw();
    say(err.message + ' The flow diagram below shows the same numbers.', true);
    root.dataset.state = 'refused';
  });
})();
