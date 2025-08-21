// Minimal reference viewer JS module
// Usage:
//   import { initGraphViewer } from "/genesis-graph/static/reference.js";
//   const viewer = initGraphViewer(document.getElementById("graph"), { socketUrl: window.location.origin });

export function initGraphViewer(container, options = {}) {
  const socketUrl = options.socketUrl || `${window.location.protocol}//${window.location.host}`;
  const debug = options.debug ?? true;

  // Create a simple DOM skeleton
  const root = document.createElement('div');
  root.style.cssText = 'position:relative;width:100%;height:100%;font:12px/1.4 system-ui, sans-serif;color:#eee;background:#0b0f16;';
  const header = document.createElement('div');
  header.textContent = 'Genesis Graph Viewer (reference)';
  header.style.cssText = 'position:absolute;top:8px;left:8px;background:rgba(255,255,255,0.06);padding:6px 8px;border-radius:6px;';
  const list = document.createElement('div');
  list.style.cssText = 'position:absolute;top:40px;left:8px;right:8px;bottom:8px;overflow:auto;background:rgba(255,255,255,0.03);padding:8px;border-radius:8px;';
  // Canvas for a minimal 2D visualization
  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:absolute;inset:0;z-index:0;';
  function resizeCanvas(){ canvas.width = container.clientWidth; canvas.height = container.clientHeight; }
  const ctx = canvas.getContext('2d');
  root.appendChild(header);
  root.appendChild(canvas);
  root.appendChild(list);
  container.appendChild(root);

  function logLine(text) {
    if (!debug) return;
    const div = document.createElement('div');
    div.textContent = text;
    list.appendChild(div);
    while (list.childElementCount > 500) list.removeChild(list.firstElementChild);
    list.scrollTop = list.scrollHeight;
  }

  // Socket wiring (expects global io from socket.io client script)
  let socket = null;
  try {
    socket = window.io && window.io(socketUrl, { transports: ['websocket','polling'] });
  } catch (e) {
    logLine(`socket error: ${e}`);
  }

  if (!socket) {
    logLine('Socket.IO not available');
  } else {
    socket.on('connect', () => { logLine('socket connected'); socket.emit('graph_snapshot'); });
    socket.on('disconnect', () => { logLine('socket disconnected'); });
    socket.on('graph_snapshot', (data) => {
      try {
        const nodes = data?.elements?.nodes?.length || 0;
        const edges = data?.elements?.edges?.length || 0;
        logLine(`snapshot nodes=${nodes} edges=${edges}`);
        graph.applySnapshot(data?.elements || { nodes:[], edges:[] });
        draw();
      } catch(e) { logLine(`snapshot error: ${e}`); }
    });
    socket.on('node_update', (payload) => {
      try {
        const n = payload.node || payload || {};
        const id = String(n.component_id || n.node_id || n.id || '');
        const type = String(n.component_type || n.node_type || '');
        const label = (n.attrs && (n.attrs.prefered_name || n.attrs.service_name || n.attrs.function_name)) || n.node_name || id;
        logLine(`node_update id=${id} type=${type} label="${label}"`);
        graph.addOrUpdateNode({id, label, type});
        draw();
      } catch (_) {}
    });
    socket.on('edge_update', (payload) => {
      try {
        const e = payload.edge || payload || {};
        const sid = String(e.source_id || e.source || '');
        const tid = String(e.target_id || e.target || '');
        if (!sid || !tid) return;
        logLine(`edge_update ${sid} -> ${tid}`);
        graph.addEdge(sid, tid);
        draw();
      } catch (_) {}
    });
    socket.on('node_remove', (payload) => {
      try {
        const nodeId = String((payload && (payload.node_id || (payload.node && payload.node.node_id))) || '');
        if (!nodeId) return;
        logLine(`node_remove id=${nodeId}`);
        graph.removeNode(nodeId);
        draw();
      } catch (_) {}
    });
    socket.on('edge_remove', (payload) => {
      try {
        const e = (payload && (payload.edge || payload)) || {};
        const sid = String(e.source_id || e.source || '');
        const tid = String(e.target_id || e.target || '');
        if (!sid || !tid) return;
        logLine(`edge_remove ${sid} -> ${tid}`);
        graph.removeEdge(sid, tid);
        draw();
      } catch (_) {}
    });
    // Optional batched updates
    socket.on('graph_batch', (batch) => {
      try {
        const nu = (batch && batch.node_updates) || [];
        const eu = (batch && batch.edge_updates) || [];
        const nr = (batch && batch.node_removes) || [];
        const er = (batch && batch.edge_removes) || [];
        logLine(`graph_batch nu=${nu.length} eu=${eu.length} nr=${nr.length} er=${er.length}`);
        nu.forEach(p => {
          const n = p.node || p || {};
          const id = String(n.component_id || n.node_id || n.id || '');
          const type = String(n.component_type || n.node_type || '');
          const label = (n.attrs && (n.attrs.prefered_name || n.attrs.service_name || n.attrs.function_name)) || n.node_name || id;
          logLine(`node_update id=${id} type=${type} label="${label}"`);
          graph.addOrUpdateNode({id, label, type});
        });
        eu.forEach(p => {
          const e = p.edge || p || {};
          const sid = String(e.source_id || e.source || '');
          const tid = String(e.target_id || e.target || '');
          if (sid && tid) { logLine(`edge_update ${sid} -> ${tid}`); graph.addEdge(sid, tid); }
        });
        nr.forEach(p => {
          const nodeId = String((p && (p.node_id || (p.node && p.node.node_id))) || '');
          if (nodeId) { logLine(`node_remove id=${nodeId}`); graph.removeNode(nodeId); }
        });
        er.forEach(p => {
          const e = (p && (p.edge || p)) || {};
          const sid = String(e.source_id || e.source || '');
          const tid = String(e.target_id || e.target || '');
          if (sid && tid) { logLine(`edge_remove ${sid} -> ${tid}`); graph.removeEdge(sid, tid); }
        });
        draw();
      } catch(_) {}
    });
  }

  // Minimal in-memory graph and renderer
  const graph = (() => {
    const nodes = new Map(); // id -> {id,label,type}
    const edges = new Set(); // "a->b"
    return {
      applySnapshot(elements){
        nodes.clear(); edges.clear();
        (elements.nodes||[]).forEach(n => {
          const d = n.data || {};
          const id = String(d.id || d.node_id || '');
          if (!id) return; nodes.set(id, {id, label: d.label || id, type: d.type || ''});
        });
        (elements.edges||[]).forEach(e => {
          const d = e.data || {};
          const s = String(d.source || d.source_id || '');
          const t = String(d.target || d.target_id || '');
          if (s && t) edges.add(`${s}->${t}`);
        });
      },
      addOrUpdateNode(n){ nodes.set(n.id, n); },
      addEdge(s,t){ edges.add(`${s}->${t}`); },
      removeNode(id){ nodes.delete(id); [...edges].forEach(k=>{ if(k.startsWith(id+"->")||k.endsWith("->"+id)) edges.delete(k); }); },
      removeEdge(s,t){ edges.delete(`${s}->${t}`); },
      snapshot(){ return { nodes:[...nodes.values()], edges:[...edges].map(k=>k.split('->')) }; }
    };
  })();

  function draw(){
    try{
      resizeCanvas();
      const {nodes, edges} = ( ()=>{ const s=graph.snapshot(); return {nodes:s.nodes, edges:s.edges}; })();
      ctx.clearRect(0,0,canvas.width,canvas.height);
      const W=canvas.width, H=canvas.height;
      const cx=W*0.55, cy=H*0.55; const R=Math.min(W,H)*0.35;
      const N=nodes.length || 1;
      const pos=new Map();
      nodes.forEach((n,i)=>{
        const ang = (i/N)*Math.PI*2;
        const x = cx + R*Math.cos(ang);
        const y = cy + R*Math.sin(ang);
        pos.set(n.id,{x,y});
      });
      // edges
      ctx.strokeStyle = 'rgba(180,200,255,0.35)'; ctx.lineWidth=1.2;
      edges.forEach(([s,t])=>{
        const a=pos.get(s), b=pos.get(t); if(!a||!b) return;
        ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
      });
      // nodes
      nodes.forEach(n=>{
        const p=pos.get(n.id); if(!p) return;
        ctx.beginPath(); ctx.fillStyle = colorForType(n.type);
        ctx.arc(p.x,p.y,7,0,Math.PI*2); ctx.fill();
        ctx.fillStyle='#ddd'; ctx.font='12px system-ui'; ctx.textAlign='center'; ctx.fillText(n.label||n.id, p.x, p.y-12);
      });
    }catch(_){/* ignore */}
  }

  function colorForType(t){
    const T=String(t||'').toUpperCase();
    if(T.includes('INTERFACE')) return '#66aaff';
    if(T.includes('SERVICE')) return '#ff9933';
    if(T.includes('AGENT')) return '#33ff99';
    if(T.includes('FUNCTION')) return '#ff66ff';
    return '#cccccc';
  }

  window.addEventListener('resize', draw);

  return {
    destroy() {
      try { if (socket) socket.close(); } catch(_) {}
      try { container.removeChild(root); } catch(_) {}
    }
  };
}


