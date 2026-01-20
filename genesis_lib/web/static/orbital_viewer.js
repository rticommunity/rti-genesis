// ####################################################################################
// (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.
//
// RTI grants Licensee a license to use, modify, compile, and create derivative
// works of the Software. Licensee has the right to distribute object form only
// for use with RTI products. The Software is provided "as is", with no warranty
// of any type, including any warranty for fitness for any purpose. RTI is under no
// obligation to maintain or support the Software. RTI shall not be liable for any
// incidental or consequential damages arising out of the use or inability to use
// the software.
// ####################################################################################

// 3D Orbital Graph Viewer - Extracted from working index.html
// This is a direct port of the visualization logic for easy embedding
// Usage:
//   import { initGraphViewer3D } from '/genesis-graph/static/orbital_viewer.js';
//   const viewer = initGraphViewer3D(document.getElementById('graph'));

import * as THREE from 'https://esm.sh/three@0.161.0';
import { OrbitControls } from 'https://esm.sh/three@0.161.0/examples/jsm/controls/OrbitControls.js';
import { EffectComposer } from 'https://esm.sh/three@0.161.0/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'https://esm.sh/three@0.161.0/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'https://esm.sh/three@0.161.0/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'https://esm.sh/three@0.161.0/examples/jsm/postprocessing/OutputPass.js';

export function initGraphViewer3D(container, options = {}) {
  const socketUrl = options.socketUrl || `${window.location.protocol}//${window.location.host}`;
  
  // Ensure container is positioned for overlays
  try {
    const cs = window.getComputedStyle(container);
    if (cs.position === 'static') container.style.position = 'relative';
  } catch (_) {}
  
  // Core Three.js objects
  let scene, camera, renderer, composer, controls, clock;
  let activeEffects = [];
  let currentThemeIndex = 0;
  let currentLayout = 'orbital';
  let edgeLabelsVisible = false;
  let speedMultiplier = { Interface: 1.0, Agent: 1.0, Service: 1.0, FunctionMoon: 1.0 };
  let orbitsFrozen = false;
  let orbitTime = 0;
  let lastOrbitTs = null;
  
  // Graph data management - matching index.html structure
  const graphData = {
    nodes: [],
    links: []
  };
  let filteredGraphData = { ...graphData };
  let knownNodeIds = new Set();
  
  // Helper to get consistent IDs
  function idOf(val) {
    if (val && typeof val === 'object') return String(val.id ?? '');
    return String(val ?? '');
  }
  
  // Map node types to theme keys like index.html
  function mapTypeToThemeKey(t) {
    if (!t) return 'Function';
    const T = String(t).toUpperCase();
    if (T === 'INTERFACE' || T.includes('INTERFACE')) return 'Interface';
    if (T === 'SERVICE' || T.includes('SERVICE')) return 'Service';
    if (T === 'FUNCTION' || T.includes('FUNCTION')) return 'Function';
    if (T === 'PRIMARY_AGENT' || T === 'AGENT_PRIMARY' || T === 'SPECIALIZED_AGENT' || T === 'AGENT' || T.includes('AGENT')) return 'Agent';
    // Default based on common patterns
    if (t.includes('Agent')) return 'Agent';
    if (t.includes('Service')) return 'Service';
    if (t.includes('Interface')) return 'Interface';
    return 'Function';
  }
  
  // Convert snapshot elements to graph data format
  function elementsToGraphData(elements) {
    const nodes = [];
    const links = [];
    (elements?.nodes || []).forEach(n => {
      const d = n.data || {};
      const id = String(d.id || d.node_id || '');
      if (!id) return;
      nodes.push({ id, type: mapTypeToThemeKey(d.type), name: d.label || id });
    });
    (elements?.edges || []).forEach(e => {
      const d = e.data || {};
      const source = String(d.source || d.source_id || '');
      const target = String(d.target || d.target_id || '');
      if (!source || !target) return;
      links.push({ source, target });
    });
    return { nodes, links };
  }
  
  // Debug panel - collapsed by default
  const debugContainer = document.createElement('div');
  debugContainer.style.cssText = 'position:absolute; left:8px; right:8px; bottom:8px; z-index:10;';
  container.appendChild(debugContainer);
  
  const debugToggle = document.createElement('button');
  debugToggle.textContent = '▶ Show Debug';
  debugToggle.style.cssText = 'background:rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.15); color:#8fa; ' +
    'font:10px ui-monospace,monospace; padding:4px 8px; border-radius:4px; cursor:pointer; margin-bottom:4px;';
  debugContainer.appendChild(debugToggle);
  
  const debugPanel = document.createElement('div');
  debugPanel.style.cssText = 'max-height:180px; overflow:auto; display:none; ' +
    'background:rgba(0,0,0,0.35); border:1px solid rgba(255,255,255,0.08); color:#cfe; ' +
    'font:11px/1.3 ui-monospace,monospace; padding:6px 8px; border-radius:8px;';
  debugContainer.appendChild(debugPanel);
  
  let debugVisible = false;
  debugToggle.addEventListener('click', () => {
    debugVisible = !debugVisible;
    debugPanel.style.display = debugVisible ? 'block' : 'none';
    debugToggle.textContent = debugVisible ? '▼ Hide Debug' : '▶ Show Debug';
  });
  
  function appendDebugLine(text) {
    const div = document.createElement('div');
    div.textContent = text;
    debugPanel.appendChild(div);
    while (debugPanel.childElementCount > 500) debugPanel.removeChild(debugPanel.firstElementChild);
    debugPanel.scrollTop = debugPanel.scrollHeight;
  }
  
  // Shaders from index.html
  const nodeVertexShader = `
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec2 vUv;
    void main() {
      vPosition = position;
      vNormal = normal;
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `;
  
  const nodeFragmentShader = `
    uniform float time;
    uniform vec3 baseColor;
    uniform vec3 accentColor;
    uniform float energy;
    uniform float baseIntensity;
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec2 vUv;
    float noise(vec2 p) {
      return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
    }
    void main() {
      vec2 uv = vUv + time * 0.02;
      float n1 = noise(uv * 8.0);
      float n2 = noise(uv * 16.0);
      float pattern = n1 * 0.7 + n2 * 0.3;
      vec3 color = mix(baseColor, accentColor, pattern);
      float fresnel = pow(1.0 - abs(dot(vNormal, vec3(0.0, 0.0, 1.0))), 1.5);
      color += fresnel * accentColor * 0.5;
      color *= baseIntensity * (1.0 + energy * 0.8);
      gl_FragColor = vec4(color, 1.0);
    }
  `;
  
  const edgeVertexShader = `
    varying vec2 vUv;
    varying vec3 vPosition;
    void main() {
      vUv = uv;
      vPosition = position;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `;
  
  const edgeFragmentShader = `
    uniform float time;
    uniform vec3 color;
    uniform float opacity;
    uniform float energy;
    varying vec2 vUv;
    varying vec3 vPosition;
    void main() {
      float flow = abs(sin(vUv.x * 15.0 - time * 12.0));
      float pulse = sin(time * 8.0) * 0.5 + 0.5;
      float pattern = pow(flow, 1.5) * (1.0 + pulse * energy);
      float fade = sin(vUv.x * 3.14159);
      vec3 finalColor = color * (pattern * 2.0 + 0.3);
      float alpha = fade * opacity * (pattern + 0.2) * (1.0 + energy);
      gl_FragColor = vec4(finalColor, alpha);
    }
  `;
  
  // Themes
  const themes = [
    {
      name: 'Contrast',
      nodeColors: {
        Interface: [0.20, 0.70, 1.00],   // blue
        Agent:     [0.20, 1.00, 0.55],   // green
        Service:   [1.00, 0.60, 0.20],   // orange
        Function:  [0.90, 0.30, 0.95]    // magenta
      },
      accentColors: {
        Interface: [0.60, 0.90, 1.00],
        Agent:     [0.60, 1.00, 0.85],
        Service:   [1.00, 0.85, 0.60],
        Function:  [1.00, 0.60, 1.00]
      },
      edgeColor: 0xeef3ff,
      ambientLightColor: 0x0a1020,
      pointLightColor: 0xaad4ff,
      dirLight1: 0x44aaff,
      dirLight2: 0x44ff88
    }
  ];
  
  // Three.js object tracking
  let nodeMaterials = {};
  let nodeMeshes = new Map();
  let llmActiveByNode = new Map();
  let edgeGeom;
  let edgeMaterial;
  let linkObjects = new Map();
  let nodePositions = {};
  let orbitalAnimationId = null;
  let orbitalActive = false;
  
  // Lighting references
  let ambientLight, pointLight, dirLight1, dirLight2;
  
  function init() {
    scene = new THREE.Scene();
    clock = new THREE.Clock();
    
    camera = new THREE.PerspectiveCamera(55, container.clientWidth / container.clientHeight, 0.1, 10000);
    // Position camera further out for better initial overview
    camera.position.set(350, 280, 350);
    
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 2;
    container.appendChild(renderer.domElement);
    
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 10;
    controls.maxDistance = 3000;
    
    setupLighting();
    setupPostProcessing();
    createEnvironment();
    initEdgeMaterial();
    applyTheme(currentThemeIndex);
    
    // Start with orbital layout
    setLayout('orbital');
    
    window.addEventListener('resize', onWindowResize);
    
    // Socket connection
    setupSocket();
  }
  
  function setupLighting() {
    ambientLight = new THREE.AmbientLight(0x1a2440, 0.8);
    scene.add(ambientLight);
    
    pointLight = new THREE.PointLight(0xffe4b5, 3, 500);
    pointLight.position.set(0, 0, 0);
    scene.add(pointLight);
    
    dirLight1 = new THREE.DirectionalLight(0x4488ff, 0.5);
    dirLight1.position.set(-200, 100, -100);
    scene.add(dirLight1);
    
    dirLight2 = new THREE.DirectionalLight(0x8844ff, 0.3);
    dirLight2.position.set(100, -50, 200);
    scene.add(dirLight2);
  }
  
  function setupPostProcessing() {
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(container.clientWidth, container.clientHeight),
      0.8, 0.4, 0.1
    );
    composer.addPass(bloomPass);
    composer.addPass(new OutputPass());
  }
  
  function createEnvironment() {
    // Starfield layers like index.html
    const layers = [
      { count: 5000, distance: [200, 500], size: [0.5, 1.0], color: 0x6688bb },
      { count: 3000, distance: [500, 1000], size: [0.8, 1.5], color: 0x88aadd },
      { count: 2000, distance: [1000, 2000], size: [1.0, 2.0], color: 0xaaccff }
    ];
    
    layers.forEach(layer => {
      const geometry = new THREE.BufferGeometry();
      const positions = new Float32Array(layer.count * 3);
      const colors = new Float32Array(layer.count * 3);
      const sizes = new Float32Array(layer.count);
      const color = new THREE.Color(layer.color);
      
      for (let i = 0; i < layer.count; i++) {
        const theta = Math.random() * 2 * Math.PI;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = layer.distance[0] + Math.random() * (layer.distance[1] - layer.distance[0]);
        
        positions[i*3] = r * Math.sin(phi) * Math.cos(theta);
        positions[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
        positions[i*3+2] = r * Math.cos(phi);
        
        colors[i*3] = color.r;
        colors[i*3+1] = color.g;
        colors[i*3+2] = color.b;
        
        sizes[i] = layer.size[0] + Math.random() * (layer.size[1] - layer.size[0]);
      }
      
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
      
      const material = new THREE.PointsMaterial({
        size: 1.5,
        vertexColors: true,
        sizeAttenuation: true,
        transparent: true,
        opacity: 0.7
      });
      
      scene.add(new THREE.Points(geometry, material));
    });
  }
  
  function initEdgeMaterial() {
    edgeMaterial = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0.0 },
        color: { value: new THREE.Color(themes[currentThemeIndex].edgeColor) },
        opacity: { value: 0.02 },
        energy: { value: 0.0 }
      },
      vertexShader: edgeVertexShader,
      fragmentShader: edgeFragmentShader,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    edgeGeom = new THREE.CylinderGeometry(1, 1, 1, 8, 1, false);
    edgeGeom.rotateX(Math.PI / 2);
  }
  
  function applyTheme(index) {
    const theme = themes[index];
    ambientLight.color.set(theme.ambientLightColor);
    pointLight.color.set(theme.pointLightColor);
    dirLight1.color.set(theme.dirLight1);
    dirLight2.color.set(theme.dirLight2);
    if (edgeMaterial && edgeMaterial.uniforms && edgeMaterial.uniforms.color) {
      edgeMaterial.uniforms.color.value.set(theme.edgeColor);
    }
    // Update existing node materials
    Object.values(nodeMaterials).forEach(mat => {
      if (!mat || !mat.uniforms) return;
      const type = mat.userDataType || 'Agent';
      const base = theme.nodeColors[type];
      const acc = theme.accentColors[type];
      if (base && acc) {
        mat.uniforms.baseColor.value.set(...base);
        mat.uniforms.accentColor.value.set(...acc);
      }
    });
  }
  
  function createTextSprite(text) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const fontSize = 64;
    const padding = 16;
    
    ctx.font = `${fontSize}px Inter, Arial, sans-serif`;
    const metrics = ctx.measureText(text);
    canvas.width = Math.ceil(metrics.width + padding * 2);
    canvas.height = Math.ceil(fontSize + padding * 2);
    
    ctx.font = `${fontSize}px Inter, Arial, sans-serif`;
    ctx.fillStyle = 'rgba(255,255,255,0.95)';
    ctx.textBaseline = 'top';
    ctx.fillText(text, padding, padding);
    
    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    
    const material = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthWrite: false
    });
    
    const sprite = new THREE.Sprite(material);
    const scaleFactor = 0.05;
    sprite.scale.set(canvas.width * scaleFactor, canvas.height * scaleFactor, 1);
    sprite.userData.isLinkLabel = true;
    return sprite;
  }
  
  function updateGraphData() {
    // For now show all nodes
    filteredGraphData = { ...graphData };
    knownNodeIds = new Set(filteredGraphData.nodes.map(n => String(n.id)));
    
    const wasEmpty = linkObjects.size === 0;
    if (wasEmpty) {
      appendDebugLine(`updateGraphData initial build, nodes=${filteredGraphData.nodes.length} links=${filteredGraphData.links.length}`);
    } else {
      appendDebugLine(`updateGraphData preserving ${linkObjects.size} link objects, nodes=${filteredGraphData.nodes.length} links=${filteredGraphData.links.length}`);
    }
    
    ensureNodeMeshes();
    ensureLinkObjects();
  }
  
  function ensureNodeMeshes() {
    const currentIds = new Set((filteredGraphData.nodes || []).map(n => n.id));
    
    // Remove stale meshes
    Array.from(nodeMeshes.keys()).forEach(id => {
      if (!currentIds.has(id)) {
        const mesh = nodeMeshes.get(id);
        if (mesh) scene.remove(mesh);
        nodeMeshes.delete(id);
      }
    });
    
    // Create missing meshes
    (filteredGraphData.nodes || []).forEach(node => {
      if (!nodeMeshes.get(node.id)) {
        const geo = new THREE.IcosahedronGeometry(6 + Math.random() * 4, 3);
        const mat = new THREE.ShaderMaterial({
          uniforms: {
            time: { value: 0.0 },
            baseColor: { value: new THREE.Vector3(...themes[currentThemeIndex].nodeColors[node.type || 'Function']) },
            accentColor: { value: new THREE.Vector3(...themes[currentThemeIndex].accentColors[node.type || 'Function']) },
            energy: { value: 0.0 },
            baseIntensity: { value: 0.15 }
          },
          vertexShader: nodeVertexShader,
          fragmentShader: nodeFragmentShader
        });
        mat.userDataType = node.type || 'Function';
        mat.userData = mat.userData || {};
        mat.userData.baseDim = 0.15;
        
        const mesh = new THREE.Mesh(geo, mat);
        mesh.userData.node = node;
        scene.add(mesh);
        nodeMeshes.set(node.id, mesh);
        
        // Check for active LLM
        const cur = llmActiveByNode.get(String(node.id)) || 0;
        if (cur > 0 && mesh.material && mesh.material.uniforms && mesh.material.uniforms.baseIntensity) {
          mesh.material.uniforms.baseIntensity.value = (mesh.material.userData.baseDim || 0.15) * 3.0;
        }
      }
    });
  }
  
  function createLinkObject(srcId, tgtId) {
    const key = `${srcId}->${tgtId}`;
    if (linkObjects.get(key)) return;
    
    const group = new THREE.Group();
    
    // Base cylinder
    const cylinder = new THREE.Mesh(edgeGeom.clone(), edgeMaterial.clone());
    cylinder.name = 'edgeCylinder';
    group.add(cylinder);
    
    // Pulse overlay
    const pulseMat = edgeMaterial.clone();
    pulseMat.uniforms.opacity.value = 0.0;
    const pulse = new THREE.Mesh(edgeGeom.clone(), pulseMat);
    pulse.name = 'edgePulse';
    pulse.scale.set(1.2, 1.2, 1);
    group.add(pulse);
    
    // Label
    const srcName = (filteredGraphData.nodes || []).find(n => n.id === srcId)?.name || srcId;
    const tgtName = (filteredGraphData.nodes || []).find(n => n.id === tgtId)?.name || tgtId;
    const label = createTextSprite(`${srcName} -> ${tgtName}`);
    label.name = 'edgeLabel';
    label.visible = edgeLabelsVisible;
    label.position.set(0, 2, 0);
    group.add(label);
    
    group.userData.linkKey = key;
    linkObjects.set(key, group);
    scene.add(group);
  }
  
  function ensureLinkObjects() {
    const keys = new Set((filteredGraphData.links || []).map(l => `${String(l.source)}->${String(l.target)}`));
    
    // Remove stale
    Array.from(linkObjects.keys()).forEach(k => {
      if (!keys.has(k)) {
        const obj = linkObjects.get(k);
        if (obj) scene.remove(obj);
        linkObjects.delete(k);
      }
    });
    
    // Create missing
    (filteredGraphData.links || []).forEach(l => createLinkObject(String(l.source), String(l.target)));
    updateLinkPositions();
  }
  
  function rebuildSceneForData() {
    ensureNodeMeshes();
    ensureLinkObjects();
    if (currentLayout === 'orbital') {
      applyOrbitalLayout();
      orbitalActive = true;
      if (!orbitalAnimationId) startOrbitalAnimation();
    }
  }
  
  function setLayout(layout) {
    currentLayout = layout;
    if (layout === 'orbital') {
      addOrbitalRings();
      orbitalActive = true;
      startOrbitalAnimation();
    }
  }
  
  function applyOrbitalLayout() {
    // Dynamic sizing based on node counts
    const countInterface = filteredGraphData.nodes.filter(n => n.type === 'Interface').length || 1;
    const countAgent = filteredGraphData.nodes.filter(n => n.type === 'Agent').length || 1;
    const countService = filteredGraphData.nodes.filter(n => n.type === 'Service').length || 1;
    
    const baseRing = 180;
    const perItem = 9;
    const orbits = {
      Interface: { radius: baseRing + perItem * Math.max(0, countInterface - 8), height: 120, speed: 0.05 },
      Agent: { radius: baseRing + perItem * Math.max(0, countAgent - 8), height: 0, speed: 0.08 },
      Service: { radius: baseRing + perItem * Math.max(0, countService - 12), height: -120, speed: 0.1 },
      Function: { radius: 34, height: 0, speed: 0.3 }
    };
    
    // Group nodes by type
    const nodesByType = {
      Interface: [],
      Agent: [],
      Service: [],
      Function: []
    };
    
    // Find service-function relationships
    const functionsByService = {};
    
    filteredGraphData.nodes.forEach(node => {
      const type = node.type || 'Function';
      if (nodesByType[type]) {
        nodesByType[type].push(node);
      }
    });
    
    // Map functions to services
    filteredGraphData.links.forEach(link => {
      const source = filteredGraphData.nodes.find(n => n.id === idOf(link.source));
      const target = filteredGraphData.nodes.find(n => n.id === idOf(link.target));
      
      if (source && target) {
        if (source.type === 'Service' && target.type === 'Function') {
          if (!functionsByService[source.id]) functionsByService[source.id] = [];
          functionsByService[source.id].push(target);
        } else if (target.type === 'Service' && source.type === 'Function') {
          if (!functionsByService[target.id]) functionsByService[target.id] = [];
          functionsByService[target.id].push(source);
        }
      }
    });
    
    // Reset positions
    nodePositions = {};
    const nodeOrbitalData = {};
    
    // Position primary orbital nodes
    ['Interface', 'Agent', 'Service'].forEach(type => {
      const nodes = nodesByType[type];
      const orbit = orbits[type];
      
      if (nodes.length === 0) return;
      
      nodes.forEach((node, index) => {
        const angle = (index / nodes.length) * Math.PI * 2;
        const x = Math.cos(angle) * orbit.radius;
        const z = Math.sin(angle) * orbit.radius;
        
        nodePositions[node.id] = {
          x: x,
          y: orbit.height,
          z: z
        };
        
        nodeOrbitalData[node.id] = {
          radius: orbit.radius,
          angle: angle,
          speed: orbit.speed,
          height: orbit.height,
          type: 'primary',
          offset: 0
        };
        
        console.log(`Positioned ${type} ${node.id} at angle ${angle.toFixed(2)} rad, pos (${x.toFixed(1)}, ${orbit.height}, ${z.toFixed(1)})`);
      });
    });
    
    // Position function moons
    Object.entries(functionsByService).forEach(([serviceId, functions]) => {
      const servicePos = nodePositions[serviceId];
      if (servicePos) {
        functions.forEach((func, index) => {
          const moonAngle = (index / functions.length) * Math.PI * 2;
          const moonRadius = 25;
          
          nodePositions[func.id] = {
            x: servicePos.x + Math.cos(moonAngle) * moonRadius,
            y: servicePos.y,
            z: servicePos.z + Math.sin(moonAngle) * moonRadius
          };
          
          nodeOrbitalData[func.id] = {
            parentId: serviceId,
            radius: moonRadius,
            angle: moonAngle,
            speed: 0.3,
            height: servicePos.y,
            type: 'moon',
            offset: 0
          };
        });
      }
    });
    
    // Position unconnected functions
    const unconnectedFunctions = nodesByType['Function'].filter(
      func => !Object.values(functionsByService).flat().includes(func)
    );
    if (unconnectedFunctions.length > 0) {
      unconnectedFunctions.forEach((func, index) => {
        const angle = (index / unconnectedFunctions.length) * Math.PI * 2;
        const radius = 40;
        const height = -150;
        nodePositions[func.id] = {
          x: Math.cos(angle) * radius,
          y: height,
          z: Math.sin(angle) * radius
        };
        
        nodeOrbitalData[func.id] = {
          radius: radius,
          angle: angle,
          speed: 0.2,
          height: height,
          type: 'primary'
        };
      });
    }
    
    // Apply to nodes
    filteredGraphData.nodes.forEach(node => {
      const pos = nodePositions[node.id];
      if (pos) {
        node.fx = pos.x;
        node.fy = pos.y;
        node.fz = pos.z;
        node.orbitalData = nodeOrbitalData[node.id];
      }
    });
    
    // Store orbital data
    orbitalActive = true;
    
    // Position meshes
    setTimeout(() => {
      scene.traverse(obj => {
        if (obj.userData && obj.userData.node) {
          const node = obj.userData.node;
          const pos = nodePositions[node.id];
          if (pos) {
            obj.position.set(pos.x, pos.y, pos.z);
            node.x = pos.x;
            node.y = pos.y;
            node.z = pos.z;
            console.log(`Positioned node ${node.id} at (${pos.x.toFixed(1)}, ${pos.y.toFixed(1)}, ${pos.z.toFixed(1)})`);
          }
        }
      });
      
      updateLinkPositions();
    }, 100);
    
    addOrbitalRings();
    startOrbitalAnimation();
  }
  
  function addOrbitalRings() {
    // Remove existing
    scene.children = scene.children.filter(child => !child.userData.isOrbitalRing);
    
    const countInterface = filteredGraphData.nodes.filter(n => n.type === 'Interface').length || 1;
    const countAgent = filteredGraphData.nodes.filter(n => n.type === 'Agent').length || 1;
    const countService = filteredGraphData.nodes.filter(n => n.type === 'Service').length || 1;
    const baseRing = 180;
    const perItem = 9;
    
    const ringInfo = [
      { radius: baseRing + perItem * Math.max(0, countInterface - 8), height: 120, color: 0x3366ff, opacity: 0.15, label: 'INTERFACES' },
      { radius: baseRing + perItem * Math.max(0, countAgent - 8), height: 0, color: 0x33ff66, opacity: 0.15, label: 'AGENTS' },
      { radius: baseRing + perItem * Math.max(0, countService - 12), height: -120, color: 0xff9933, opacity: 0.15, label: 'SERVICES' }
    ];
    
    ringInfo.forEach(ring => {
      // Glowing torus
      const edgeGeometry = new THREE.TorusGeometry(ring.radius, 2, 16, 100);
      const edgeMaterial = new THREE.MeshBasicMaterial({
        color: ring.color,
        transparent: true,
        opacity: 0.4,
        depthWrite: false
      });
      const edgeMesh = new THREE.Mesh(edgeGeometry, edgeMaterial);
      edgeMesh.rotation.x = -Math.PI / 2;
      edgeMesh.position.y = ring.height;
      edgeMesh.userData.isOrbitalRing = true;
      scene.add(edgeMesh);
      
      // Subtle disc
      const discGeometry = new THREE.RingGeometry(0, ring.radius + 10, 64);
      const discMaterial = new THREE.MeshBasicMaterial({
        color: ring.color,
        transparent: true,
        opacity: 0.02,
        side: THREE.DoubleSide,
        depthWrite: false
      });
      const discMesh = new THREE.Mesh(discGeometry, discMaterial);
      discMesh.rotation.x = -Math.PI / 2;
      discMesh.position.y = ring.height;
      discMesh.userData.isOrbitalRing = true;
      scene.add(discMesh);
      
      // Label
      const labelSprite = createLayerLabel(ring.label, ring.color);
      labelSprite.position.set(ring.radius + 30, ring.height, 0);
      labelSprite.userData.isOrbitalRing = true;
      scene.add(labelSprite);
    });
  }
  
  function createLayerLabel(text, color) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const fontSize = 48;
    const padding = 20;
    
    ctx.font = `bold ${fontSize}px Orbitron, Arial, sans-serif`;
    const metrics = ctx.measureText(text);
    
    canvas.width = Math.ceil(metrics.width + padding * 2);
    canvas.height = Math.ceil(fontSize + padding * 2);
    
    ctx.font = `bold ${fontSize}px Orbitron, Arial, sans-serif`;
    ctx.fillStyle = new THREE.Color(color).getStyle();
    ctx.globalAlpha = 0.6;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'center';
    ctx.fillText(text, canvas.width / 2, canvas.height / 2);
    
    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    
    const material = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthWrite: false,
      depthTest: false
    });
    
    const sprite = new THREE.Sprite(material);
    const scale = 0.3;
    sprite.scale.set(canvas.width * scale, canvas.height * scale, 1);
    
    return sprite;
  }
  
  function startOrbitalAnimation() {
    if (orbitalAnimationId) return;
    
    // Set initial positions
    scene.traverse(obj => {
      if (obj.userData && obj.userData.node) {
        const node = obj.userData.node;
        const pos = nodePositions[node.id];
        if (pos) {
          obj.position.set(pos.x, pos.y, pos.z);
        }
      }
    });
    
    const animate = () => {
      if (currentLayout !== 'orbital' || !orbitalActive) {
        orbitalAnimationId = null;
        return;
      }
      
      // Update orbit time
      const now = clock.getElapsedTime();
      if (lastOrbitTs === null) lastOrbitTs = now;
      if (!orbitsFrozen) {
        orbitTime += (now - lastOrbitTs);
      }
      lastOrbitTs = now;
      
      // Update positions
      scene.traverse(obj => {
        if (obj.userData && obj.userData.node && obj.userData.node.orbitalData) {
          const node = obj.userData.node;
          const data = node.orbitalData;
          
          if (data.type === 'primary') {
            const typeKey = node.type;
            const sm = (typeKey === 'Interface') ? speedMultiplier.Interface : 
                      (typeKey === 'Agent') ? speedMultiplier.Agent : 
                      (typeKey === 'Service') ? speedMultiplier.Service : 1.0;
            const angle = data.angle + orbitTime * data.speed * sm + (data.offset || 0);
            const x = Math.cos(angle) * data.radius;
            const z = Math.sin(angle) * data.radius;
            obj.position.set(x, data.height, z);
            
            node.x = x;
            node.y = data.height;
            node.z = z;
          } else if (data.type === 'moon' && data.parentId) {
            // Find parent
            let parentPos = null;
            scene.traverse(parentObj => {
              if (parentObj.userData && parentObj.userData.node && parentObj.userData.node.id === data.parentId) {
                parentPos = parentObj.position;
              }
            });
            
            if (parentPos) {
              const angle = data.angle + orbitTime * data.speed * speedMultiplier.FunctionMoon + (data.offset || 0);
              const x = parentPos.x + Math.cos(angle) * data.radius;
              const z = parentPos.z + Math.sin(angle) * data.radius;
              obj.position.set(x, parentPos.y, z);
              
              node.x = x;
              node.y = parentPos.y;
              node.z = z;
            }
          }
        }
      });
      
      updateLinkPositions();
      
      orbitalAnimationId = requestAnimationFrame(animate);
    };
    
    orbitalAnimationId = requestAnimationFrame(animate);
  }
  
  function updateLinkPositions() {
    linkObjects.forEach((linkObj, key) => {
      const [srcId, tgtId] = key.split('->');
      let srcPos = null, tgtPos = null;
      
      scene.traverse(obj => {
        if (obj.userData && obj.userData.node) {
          if (obj.userData.node.id === srcId) srcPos = obj.position;
          if (obj.userData.node.id === tgtId) tgtPos = obj.position;
        }
      });
      
      if (srcPos && tgtPos && linkObj.parent) {
        const mid = new THREE.Vector3(
          (srcPos.x + tgtPos.x) / 2,
          (srcPos.y + tgtPos.y) / 2,
          (srcPos.z + tgtPos.z) / 2
        );
        linkObj.position.copy(mid);
        linkObj.lookAt(tgtPos);
        
        const cylinder = linkObj.getObjectByName('edgeCylinder');
        const pulse = linkObj.getObjectByName('edgePulse');
        const distance = srcPos.distanceTo(tgtPos);
        
        if (cylinder) cylinder.scale.set(1, 1, distance);
        if (pulse) pulse.scale.set(pulse.scale.x, pulse.scale.y, distance);
      }
    });
  }
  
  function removeNodeById(nodeId) {
    try {
      const id = String(nodeId);
      graphData.nodes = (graphData.nodes || []).filter(n => String(n.id) !== id);
      graphData.links = (graphData.links || []).filter(l => String(idOf(l.source)) !== id && String(idOf(l.target)) !== id);
      const mesh = nodeMeshes.get(id);
      if (mesh) { scene.remove(mesh); nodeMeshes.delete(id); }
      Array.from(linkObjects.keys()).forEach(k => {
        const [s, t] = k.split('->');
        if (s === id || t === id) {
          const obj = linkObjects.get(k);
          if (obj) scene.remove(obj);
          linkObjects.delete(k);
        }
      });
      updateGraphData();
      rebuildSceneForData();
    } catch (_) {}
  }
  
  function removeEdgeByEndpoints(srcId, tgtId) {
    try {
      const sid = String(srcId), tid = String(tgtId);
      graphData.links = (graphData.links || []).filter(l => !(String(idOf(l.source)) === sid && String(idOf(l.target)) === tid));
      const key = `${sid}->${tid}`;
      const obj = linkObjects.get(key);
      if (obj) { scene.remove(obj); linkObjects.delete(key); }
      updateGraphData();
    } catch (_) {}
  }
  
  function updateNodeIntensityForLLM(nodeId) {
    try {
      const id = String(nodeId || '');
      if (!id) return;
      const mesh = nodeMeshes.get(id);
      if (!mesh || !mesh.material || !mesh.material.uniforms) return;
      const baseDim = mesh.material.userData?.baseDim ?? 0.15;
      const activeCount = Math.max(0, llmActiveByNode.get(id) || 0);
      const target = activeCount > 0 ? baseDim * 3.0 : baseDim;
      mesh.material.uniforms.baseIntensity.value = target;
    } catch (_) {}
  }
  
  function pulseLink(sourceId, targetId, colorHex) {
    try {
      const key = `${sourceId}->${targetId}`;
      let obj = linkObjects.get(key);
      if (!obj) {
        // Try reverse
        const rkey = `${targetId}->${sourceId}`;
        const robj = linkObjects.get(rkey);
        const allKeys = Array.from(linkObjects.keys());
        appendDebugLine(`pulse_lookup key=${key} exists=${!!obj} rkey=${rkey} rexists=${!!robj} total_keys=${allKeys.length}`);
        if (robj) {
          obj = robj;
          appendDebugLine(`redirect_pulse ${key} -> ${rkey}`);
        }
      }
      if (!obj) {
        const srcKnown = knownNodeIds.has(String(sourceId));
        const tgtKnown = knownNodeIds.has(String(targetId));
        if (srcKnown && tgtKnown) {
          appendDebugLine(`UNMATCHED activity link ${key}`);
        }
        return false;
      }
      const pulse = obj.getObjectByName('edgePulse');
      const cylinder = obj.getObjectByName('edgeCylinder');
      if (!pulse || !pulse.material || !pulse.material.uniforms) return false;
      const mat = pulse.material;
      const baseMat = cylinder ? cylinder.material : null;
      const baseColor = new THREE.Color(themes[currentThemeIndex].edgeColor);
      const isStartColor = (colorHex === 0xe74c3c);
      const effect = {
        startTime: clock.getElapsedTime(),
        duration: isStartColor ? 3.0 : 2.2,
        update: (elapsed) => {
          const progress = elapsed / effect.duration;
          if (progress > 1) return;
          const intensity = Math.sin(progress * Math.PI);
          mat.uniforms.energy.value = 0.4 + intensity * (isStartColor ? 3.6 : 3.2);
          mat.uniforms.opacity.value = (isStartColor ? 0.15 : 0.1) + 0.9 * intensity;
          mat.uniforms.color.value.set(colorHex);
          if (baseMat && baseMat.uniforms) {
            baseMat.uniforms.opacity.value = 0.02 + 0.18 * (1.0 - intensity);
          }
        },
        end: () => {
          mat.uniforms.energy.value = 0.0;
          mat.uniforms.opacity.value = 0.0;
          mat.uniforms.color.value.copy(baseColor);
          if (baseMat && baseMat.uniforms) {
            baseMat.uniforms.opacity.value = 0.02;
          }
        }
      };
      activeEffects.push(effect);
      return true;
    } catch (_) { return false; }
  }
  
  function setupSocket() {
    try {
      const ioUrl = socketUrl;
      const socket = window.io && window.io(ioUrl, { transports: ['websocket', 'polling'] });
      if (!socket) {
        appendDebugLine('Socket.IO not available');
      } else {
        socket.on('connect', () => { 
          appendDebugLine('socket connected'); 
          socket.emit('graph_snapshot'); 
        });
        socket.on('graph_snapshot', (data) => {
          try {
            const nodes = data?.elements?.nodes?.length || 0;
            const edges = data?.elements?.edges?.length || 0;
            appendDebugLine(`graph_snapshot nodes=${nodes} edges=${edges}`);
            const gd = elementsToGraphData(data.elements || {});
            // Breakdown like index.html
            try {
              const byType = {};
              (gd.nodes || []).forEach(n => {
                const t = n.type || 'Function';
                if (!byType[t]) byType[t] = [];
                byType[t].push(n);
              });
              const typeSummary = Object.entries(byType)
                .map(([t, arr]) => `${t}=${arr.length}`)
                .join(' ');
              appendDebugLine(`snapshot_types ${typeSummary}`);
              Object.entries(byType).forEach(([t, arr]) => {
                arr.slice(0, 50).forEach(n => {
                  appendDebugLine(`  ${t}: ${n.name || ''} [${n.id}]`);
                });
              });
              (gd.links || []).slice(0, 100).forEach(l => {
                appendDebugLine(`  edge: ${String(l.source)} -> ${String(l.target)}`);
              });
            } catch (__) {}
            graphData.nodes = gd.nodes;
            graphData.links = gd.links;
            updateGraphData();
            rebuildSceneForData();
          } catch (e) { console.error(e); appendDebugLine(`snapshot error: ${e}`); }
        });
        socket.on('node_update', (payload) => {
          try {
            const n = payload.node || payload || {};
            const id = String(n.component_id || n.node_id || n.id || '');
            if (!id) return;
            const type = mapTypeToThemeKey(n.component_type || n.node_type || n.type);
            
            // Improved label extraction - try multiple fields
            let label = '';
            if (n.attrs) {
              label = n.attrs.prefered_name || n.attrs.preferred_name || n.attrs.service_name || 
                      n.attrs.function_name || n.attrs.agent_name || n.attrs.name || '';
            }
            if (!label) {
              label = n.node_name || n.name || n.label || '';
            }
            // If still no label, create a readable one from the ID
            if (!label || label === 'Unknown') {
              // Try to extract meaningful name from ID
              if (id.includes('-') && id.length > 20) {
                // UUID-like - use first segment + type
                label = `${type}_${id.split('-')[0]}`;
              } else {
                label = id;
              }
            }
            
            let existing = graphData.nodes.find(nd => nd.id === id);
            if (!existing) {
              graphData.nodes.push({ id, type, name: label });
              appendDebugLine(`node_add id=${id} type=${type} label="${label}"`);
            } else {
              existing.name = label; existing.type = type;
              appendDebugLine(`node_update id=${id} type=${type} label="${label}"`);
            }
            updateGraphData();
            rebuildSceneForData();
          } catch (e) {}
        });
        socket.on('edge_update', (payload) => {
          try {
            const e = payload.edge || payload || {};
            const sid = String(e.source_id || e.source || '');
            const tid = String(e.target_id || e.target || '');
            if (!sid || !tid) return;
            if (!graphData.links.find(l => String(l.source) === sid && String(l.target) === tid)) {
              graphData.links.push({ source: sid, target: tid });
              appendDebugLine(`edge_add ${sid} -> ${tid}`);
            }
            updateGraphData();
            ensureLinkObjects();
          } catch (e) {}
        });
        socket.on('node_remove', (payload) => {
          try {
            const nodeId = String((payload && (payload.node_id || (payload.node && payload.node.node_id))) || '');
            if (!nodeId) return;
            appendDebugLine(`node_remove id=${nodeId}`);
            removeNodeById(nodeId);
          } catch (_) {}
        });
        socket.on('edge_remove', (payload) => {
          try {
            const e = (payload && (payload.edge || payload)) || {};
            const sid = String(e.source_id || e.source || '');
            const tid = String(e.target_id || e.target || '');
            if (!sid || !tid) return;
            appendDebugLine(`edge_remove ${sid} -> ${tid}`);
            removeEdgeByEndpoints(sid, tid);
          } catch (_) {}
        });
        socket.on('activity', (act) => {
          try {
            const sid = act.source_id || '';
            const tid = act.target_id || '';
            const ev = String(act.event_type || '');
            const isStart = ev.endsWith('_START');
            const isComplete = ev.endsWith('_COMPLETE') || ev.endsWith('RECEIVED');
            
            appendDebugLine(`${ev} ${sid || '?'} -> ${tid || '?'}`);
            
            // LLM intensity
            if (ev.startsWith('LLM_CALL_')) {
              const agentId = act.primary_agent_id || (sid === 'OpenAI' ? tid : sid);
              if (agentId) {
                const keyId = String(agentId);
                if (isStart) {
                  llmActiveByNode.set(keyId, (llmActiveByNode.get(keyId) || 0) + 1);
                  updateNodeIntensityForLLM(keyId);
                } else if (isComplete) {
                  const cur = (llmActiveByNode.get(keyId) || 0) - 1;
                  if (cur > 0) llmActiveByNode.set(keyId, cur); else llmActiveByNode.delete(keyId);
                  updateNodeIntensityForLLM(keyId);
                }
              }
            }
            
            if (sid && tid) {
              if (isStart) {
                pulseLink(sid, tid, 0xe74c3c);
              } else if (isComplete) {
                setTimeout(() => {
                  pulseLink(sid, tid, 0x2ecc71);
                }, 180);
              }
            }
          } catch (e) {}
        });
      }
    } catch (e) { appendDebugLine(`socket error: ${e}`); }
  }
  
  function onWindowResize() {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
    composer.setSize(container.clientWidth, container.clientHeight);
  }
  
  function animate() {
    requestAnimationFrame(animate);
    const delta = clock.getDelta();
    const time = clock.getElapsedTime();
    
    // Update shaders
    scene.traverse(obj => {
      if (obj.userData.node && obj.material && obj.material.uniforms && obj.material.uniforms.time) {
        obj.material.uniforms.time.value = time;
      }
      if (obj.material && obj.material.uniforms && obj.material.uniforms.time) {
        obj.material.uniforms.time.value = time;
      }
    });
    
    activeEffects.forEach((effect, i) => {
      const elapsed = time - effect.startTime;
      if (elapsed > effect.duration) {
        effect.end();
        activeEffects.splice(i, 1);
      } else {
        effect.update(elapsed);
      }
    });
    
    controls.update();
    composer.render();
  }
  
  init();
  animate();
  
  return {
    destroy() {
      try {
        if (orbitalAnimationId) {
          cancelAnimationFrame(orbitalAnimationId);
          orbitalAnimationId = null;
        }
        window.removeEventListener('resize', onWindowResize);
        container.removeChild(renderer.domElement);
        container.removeChild(debugPanel);
      } catch (_) {}
    }
  };
}
