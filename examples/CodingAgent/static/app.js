/* ============================================
   Genesis CodingAgent — Client Application JS
   ============================================ */

(function () {
  "use strict";

  // ---- Configure marked for markdown rendering ----
  marked.setOptions({
    highlight: function (code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    },
    breaks: true,
    gfm: true,
  });

  // ---- DOM refs ----
  const socket = io(location.protocol + "//" + location.host, {
    transports: ["websocket", "polling"],
  });

  const agentSelect = document.getElementById("agent-select");
  const connectBtn = document.getElementById("connect-btn");
  const refreshBtn = document.getElementById("refresh-btn");
  const statusDot = document.getElementById("status-indicator");
  const statusText = document.getElementById("status-text");
  const chatArea = document.getElementById("chat-area");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const sendBtn = document.getElementById("send-btn");
  const fileTree = document.getElementById("file-tree");
  const refreshFilesBtn = document.getElementById("refresh-files-btn");
  const welcomeMsg = document.getElementById("welcome-msg");

  // ---- State ----
  let connected = false;
  let agentConnected = false;
  let streaming = false;
  let currentRequestId = null;
  let streamTextBuffer = "";
  let streamTextEl = null;
  let typingEl = null;
  let streamedTextShown = false;  // Track if streaming text was displayed

  // ---- Helpers ----
  function setStatus(state, text) {
    statusDot.className = "status-dot " + state;
    statusText.textContent = text;
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      chatArea.scrollTop = chatArea.scrollHeight;
    });
  }

  function hideWelcome() {
    if (welcomeMsg) welcomeMsg.style.display = "none";
  }

  function renderMarkdown(text) {
    return marked.parse(text || "");
  }

  // ---- File tree ----
  function getFileIcon(name) {
    const ext = name.split(".").pop().toLowerCase();
    const icons = {
      py: "\u{1F40D}",
      js: "\u2B22",
      ts: "\u2B22",
      html: "\u25C7",
      css: "\u25C8",
      md: "\u25A3",
      json: "\u25A2",
      sh: "\u25B6",
      txt: "\u25A1",
      yml: "\u25C6",
      yaml: "\u25C6",
      toml: "\u25C6",
    };
    return icons[ext] || "\u25AB";
  }

  function buildFileTree(files) {
    if (!files || files.length === 0) {
      fileTree.innerHTML = '<div class="empty-state">No workspace files</div>';
      return;
    }

    // Group by directory
    const dirs = {};
    const now = Date.now() / 1000;

    files.forEach((f) => {
      const parts = f.path.split("/");
      const dir = parts.length > 1 ? parts.slice(0, -1).join("/") : ".";
      if (!dirs[dir]) dirs[dir] = [];
      dirs[dir].push(f);
    });

    let html = "";
    const sortedDirs = Object.keys(dirs).sort();

    sortedDirs.forEach((dir) => {
      if (dir !== ".") {
        html += `<div class="dir-item"><span>\u{1F4C1}</span> ${dir}/</div>`;
      }
      dirs[dir]
        .sort((a, b) => a.name.localeCompare(b.name))
        .forEach((f) => {
          const isRecent = now - f.mtime < 30;
          const cls = isRecent ? "file-item recent" : "file-item";
          html += `<div class="${cls}" title="${f.path}">
          <span class="file-icon">${getFileIcon(f.name)}</span>
          <span class="file-name">${f.name}</span>
        </div>`;
        });
    });

    fileTree.innerHTML = html;
  }

  // ---- Chat message rendering ----
  function addUserMessage(text) {
    hideWelcome();
    const div = document.createElement("div");
    div.className = "chat-msg msg-user";
    div.innerHTML = `<div class="msg-label">You</div><div class="msg-content">${escapeHtml(text)}</div>`;
    chatArea.appendChild(div);
    scrollToBottom();
  }

  function addAgentMessage(text, agentName) {
    hideWelcome();
    removeTypingIndicator();

    const div = document.createElement("div");
    div.className = "chat-msg msg-agent";
    div.innerHTML = `<div class="msg-label">${escapeHtml(agentName || "Agent")}</div><div class="msg-content">${renderMarkdown(text)}</div>`;
    chatArea.appendChild(div);

    // Highlight code blocks
    div.querySelectorAll("pre code").forEach((block) => {
      hljs.highlightElement(block);
    });

    scrollToBottom();
  }

  function addStreamEvent(chunk) {
    hideWelcome();

    const type = chunk.chunk_type;

    if (type === "init") {
      // Show typing indicator
      showTypingIndicator();
      return;
    }

    if (type === "text") {
      // Accumulate text into a streaming text element
      streamTextBuffer += chunk.content;
      streamedTextShown = true;
      if (!streamTextEl) {
        removeTypingIndicator();
        const div = document.createElement("div");
        div.className = "chat-msg msg-agent";
        div.innerHTML = `<div class="msg-label">Agent</div><div class="msg-content streaming-text"></div>`;
        chatArea.appendChild(div);
        streamTextEl = div.querySelector(".streaming-text");
      }
      streamTextEl.innerHTML = renderMarkdown(streamTextBuffer);
      streamTextEl.querySelectorAll("pre code").forEach((block) => {
        hljs.highlightElement(block);
      });
      scrollToBottom();
      return;
    }

    if (type === "tool_start") {
      removeTypingIndicator();
      let detail = "";
      try {
        const meta = JSON.parse(chunk.metadata || "{}");
        if (meta.tool_input && Object.keys(meta.tool_input).length > 0) {
          detail = `<div class="event-detail collapsed" onclick="this.classList.toggle('collapsed')">${escapeHtml(JSON.stringify(meta.tool_input, null, 2))}</div>`;
        }
      } catch (e) { /* ignore */ }

      const div = document.createElement("div");
      div.className = "stream-event tool-start";
      div.innerHTML = `
        <span class="event-icon">\u2699</span>
        <div class="event-content">
          <span>${escapeHtml(chunk.content)}</span>
          ${detail}
        </div>`;
      chatArea.appendChild(div);
      showTypingIndicator();
      scrollToBottom();
      return;
    }

    if (type === "tool_result") {
      removeTypingIndicator();
      const resultText = chunk.content || "";
      let detail = "";
      if (resultText.length > 0) {
        const truncated = resultText.length > 500 ? resultText.substring(0, 500) + "..." : resultText;
        detail = `<div class="event-detail collapsed" onclick="this.classList.toggle('collapsed')">${escapeHtml(truncated)}</div>`;
      }

      const div = document.createElement("div");
      div.className = "stream-event tool-result";
      div.innerHTML = `
        <span class="event-icon">\u2713</span>
        <div class="event-content">
          <span>Result</span>
          ${detail}
        </div>`;
      chatArea.appendChild(div);
      showTypingIndicator();
      scrollToBottom();
      return;
    }

    if (type === "error") {
      removeTypingIndicator();
      const div = document.createElement("div");
      div.className = "stream-event error";
      div.innerHTML = `<span class="event-icon">\u2717</span><div class="event-content">${escapeHtml(chunk.content)}</div>`;
      chatArea.appendChild(div);
      scrollToBottom();
      return;
    }

    if (type === "done") {
      removeTypingIndicator();
      streaming = false;
      // If no streaming text was shown, display the done content as a full message
      if (chunk.content && chunk.content.length > 0 && !streamedTextShown) {
        addAgentMessage(chunk.content, "Agent");
      }
      // Reset streaming state (keep streamedTextShown until agent_response handles it)
      streamTextBuffer = "";
      streamTextEl = null;
      currentRequestId = null;
      enableInput();
      return;
    }
  }

  function showTypingIndicator() {
    if (typingEl) return;
    typingEl = document.createElement("div");
    typingEl.className = "typing-indicator";
    typingEl.id = "typing-indicator";
    typingEl.innerHTML = `<div class="typing-dots"><span></span><span></span><span></span></div><span>Agent is working...</span>`;
    chatArea.appendChild(typingEl);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    if (typingEl) {
      typingEl.remove();
      typingEl = null;
    }
  }

  function addErrorMessage(text) {
    hideWelcome();
    const div = document.createElement("div");
    div.className = "stream-event error";
    div.innerHTML = `<span class="event-icon">\u2717</span><div class="event-content">${escapeHtml(text)}</div>`;
    chatArea.appendChild(div);
    scrollToBottom();
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function enableInput() {
    chatInput.disabled = false;
    sendBtn.disabled = false;
    chatInput.focus();
  }

  function disableInput() {
    chatInput.disabled = true;
    sendBtn.disabled = true;
  }

  // ---- Socket.IO event handlers ----
  socket.on("connect", () => {
    connected = true;
    setStatus("online", "Connected");
  });

  socket.on("disconnect", () => {
    connected = false;
    setStatus("offline", "Disconnected");
  });

  socket.on("status", (data) => {
    if (data.message === "Connected") {
      setStatus("online", "Discovering...");
    }
  });

  socket.on("agents", (data) => {
    const agents = data.agents || [];
    agentSelect.innerHTML = "";
    if (agents.length === 0) {
      agentSelect.innerHTML =
        '<option value="">No agents found</option>';
      agentSelect.disabled = true;
      connectBtn.disabled = true;
      return;
    }
    agents.forEach((a) => {
      const opt = document.createElement("option");
      opt.value = a.name;
      opt.textContent = a.name;
      agentSelect.appendChild(opt);
    });
    agentSelect.disabled = false;
    connectBtn.disabled = false;
    setStatus("online", "Ready");
  });

  socket.on("agent_connected", (data) => {
    agentConnected = true;
    setStatus("online", `Connected: ${data.agent_name}`);
    enableInput();
  });

  socket.on("message_sent", (data) => {
    currentRequestId = data.request_id;
    streaming = true;
    streamedTextShown = false;
    addUserMessage(data.message);
    disableInput();
    showTypingIndicator();
    setStatus("busy", "Working...");
  });

  socket.on("stream_event", (chunk) => {
    if (!streaming && chunk.chunk_type !== "done") {
      streaming = true;
    }
    addStreamEvent(chunk);
  });

  socket.on("agent_response", (data) => {
    removeTypingIndicator();
    streaming = false;
    // Only show final response if no streamed text was already displayed
    if (!streamedTextShown && data.message) {
      addAgentMessage(data.message, data.agent_name);
    }
    // Reset all streaming state
    streamTextBuffer = "";
    streamTextEl = null;
    streamedTextShown = false;
    currentRequestId = null;
    enableInput();
    setStatus("online", `Connected: ${data.agent_name || "Agent"}`);
  });

  socket.on("error", (data) => {
    removeTypingIndicator();
    streaming = false;
    streamTextBuffer = "";
    streamTextEl = null;
    streamedTextShown = false;
    currentRequestId = null;
    addErrorMessage(data.message || "Unknown error");
    enableInput();
    if (agentConnected) {
      setStatus("online", "Ready");
    }
  });

  socket.on("file_tree", (data) => {
    buildFileTree(data.files);
  });

  // ---- UI event handlers ----
  connectBtn.addEventListener("click", () => {
    const name = agentSelect.value;
    if (name) {
      setStatus("online", `Connecting to ${name}...`);
      socket.emit("connect_to_agent", { agent_name: name });
    }
  });

  refreshBtn.addEventListener("click", () => {
    socket.emit("refresh_agents");
  });

  refreshFilesBtn.addEventListener("click", () => {
    socket.emit("refresh_files");
  });

  chatForm.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const msg = (chatInput.value || "").trim();
    if (!msg || !agentConnected) return;
    socket.emit("send_message", { message: msg });
    chatInput.value = "";
  });

  // ---- Draggable resize handles ----
  (function initResizeHandles() {
    const sidebar = document.getElementById("sidebar");
    const graphPanel = document.getElementById("graph-panel");
    const handleLeft = document.getElementById("resize-left");
    const handleRight = document.getElementById("resize-right");

    function startDrag(handle, getTarget, setWidth) {
      let startX, startW;

      function onMouseDown(e) {
        e.preventDefault();
        const target = getTarget();
        startX = e.clientX;
        startW = target.getBoundingClientRect().width;
        handle.classList.add("active");
        document.body.classList.add("resizing");
        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
      }

      function onMouseMove(e) {
        const dx = e.clientX - startX;
        setWidth(startW, dx);
      }

      function onMouseUp() {
        handle.classList.remove("active");
        document.body.classList.remove("resizing");
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
        // Trigger resize so the 3D graph canvas updates to new panel size
        window.dispatchEvent(new Event("resize"));
      }

      handle.addEventListener("mousedown", onMouseDown);
    }

    // Left handle: dragging right makes sidebar wider
    startDrag(
      handleLeft,
      () => sidebar,
      (startW, dx) => {
        const w = Math.max(120, Math.min(500, startW + dx));
        sidebar.style.width = w + "px";
      }
    );

    // Right handle: dragging left makes graph panel wider
    startDrag(
      handleRight,
      () => graphPanel,
      (startW, dx) => {
        const w = Math.max(120, Math.min(600, startW - dx));
        graphPanel.style.width = w + "px";
      }
    );
  })();
})();
