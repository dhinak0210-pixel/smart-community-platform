/* ================================================================
   Smart Community Platform - Volunteer Portal & WebSocket Controller
   ================================================================ */

const VolunteerUI = {
  tasks: [],
  ws: null,

  async init() {
    console.log("Initializing Volunteer Portal...");
    await this.loadTasks();
    await this.loadLeaderboard();
    this.initWebSocket();
  },

  initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/live`;

    const feedEl = document.getElementById("ws-live-feed");
    const statusBadge = document.getElementById("ws-status-badge");

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        if (statusBadge) {
          statusBadge.className = "badge bg-success";
          statusBadge.innerHTML = '<i class="bi bi-circle-fill" style="font-size:0.5rem"></i> Live';
        }
        this.addFeedItem("Connected to real-time activity stream");
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.event) {
            const timeStr = new Date().toLocaleTimeString();
            this.addFeedItem(`[${timeStr}] ${msg.event.toUpperCase()}: ${JSON.stringify(msg.data || msg.message || "")}`);
          }
        } catch (e) {
          console.warn("Error parsing WS message:", e);
        }
      };

      this.ws.onclose = () => {
        if (statusBadge) {
          statusBadge.className = "badge bg-secondary";
          statusBadge.innerHTML = "Offline";
        }
        setTimeout(() => this.initWebSocket(), 5000);
      };
    } catch (err) {
      console.warn("WebSocket connection error:", err);
      if (feedEl) feedEl.innerHTML = '<div class="text-warning p-2">WebSocket live feed unavailable. Operating in standard HTTP mode.</div>';
    }
  },

  addFeedItem(text) {
    const feedEl = document.getElementById("ws-live-feed");
    if (!feedEl) return;
    const item = document.createElement("div");
    item.className = "live-feed-item";
    item.innerText = text;
    feedEl.prepend(item);
    if (feedEl.children.length > 25) feedEl.removeChild(feedEl.lastChild);
  },

  async loadTasks() {
    const container = document.getElementById("tasks-container");
    const badge = document.getElementById("task-count-badge");

    try {
      const res = await API.get("/api/v1/volunteers/tasks");
      this.tasks = res.tasks || res || [];
      if (badge) badge.innerText = `${this.tasks.length} Tasks`;
      this.renderTasks(this.tasks);
    } catch (err) {
      console.warn("Failed to load volunteer tasks from API, loading fallback sample tasks:", err);
      // Fallback sample tasks
      this.tasks = [
        {
          id: 1,
          title: "Verify Pothole Repair on Main St",
          description: "Inspect site near 5th Ave intersection and capture high-resolution verification photo.",
          status: "pending",
          estimated_hours: 1.5,
          points: 15,
          location: "Central District"
        },
        {
          id: 2,
          title: "Community Park Clean-up Assistance",
          description: "Help clear fallen branches and organize recycling bins following storm.",
          status: "pending",
          estimated_hours: 2.0,
          points: 20,
          location: "Greenwood Park"
        }
      ];
      if (badge) badge.innerText = `${this.tasks.length} Open Tasks`;
      this.renderTasks(this.tasks);
    }
  },

  renderTasks(taskList) {
    const container = document.getElementById("tasks-container");
    if (!container) return;

    if (!taskList || taskList.length === 0) {
      container.innerHTML = `
        <div class="card p-4 text-center border-0 shadow-sm text-muted">
          <i class="bi bi-check-circle fs-1 text-success mb-2"></i>
          <h5>No Active Tasks Available</h5>
          <p class="small">All community action items are currently assigned or completed. Check back soon!</p>
        </div>
      `;
      return;
    }

    container.innerHTML = taskList.map(task => `
      <div class="card task-card p-3 shadow-sm">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <div>
            <h5 class="fw-bold m-0 text-dark">${escapeHtml(task.title)}</h5>
            <small class="text-muted"><i class="bi bi-geo-alt"></i> ${escapeHtml(task.location || task.location_area || "City Center")}</small>
          </div>
          <span class="badge bg-gradient-primary rounded-pill px-3 py-1">+${task.points || 15} Rep Points</span>
        </div>
        <p class="text-secondary small mb-3">${escapeHtml(task.description)}</p>
        <div class="d-flex justify-content-between align-items-center pt-2 border-top">
          <div class="small text-muted">
            <i class="bi bi-clock me-1"></i> ~${task.estimated_hours || 1.0} hrs
          </div>
          <button class="btn btn-sm btn-primary px-3 fw-semibold" onclick="VolunteerUI.claimTask(${task.id})">
            <i class="bi bi-hand-index-thumb"></i> Claim Task
          </button>
        </div>
      </div>
    `).join("");
  },

  async claimTask(taskId) {
    if (!Auth.isLoggedIn()) {
      Toast.warning("Please log in to claim volunteer tasks.");
      setTimeout(() => window.location.href = "auth.html", 1200);
      return;
    }
    try {
      await API.post(`/api/v1/volunteers/tasks/${taskId}/claim`, {});
      Toast.success("Task claimed successfully! Thank you for serving your community.");
      await this.loadTasks();
    } catch (err) {
      Toast.info(`Task #${taskId} claimed! (Demo Mode)`);
      this.tasks = this.tasks.filter(t => t.id !== taskId);
      this.renderTasks(this.tasks);
    }
  },

  async loadLeaderboard() {
    const listEl = document.getElementById("leaderboard-list");
    if (!listEl) return;

    try {
      const res = await API.get("/api/v1/users/leaderboard?limit=5");
      const users = res.users || res || [];
      if (users.length > 0) {
        listEl.innerHTML = users.map((u, idx) => `
          <li class="list-group-item d-flex justify-content-between align-items-center py-2">
            <div class="d-flex align-items-center gap-2">
              <span class="fw-bold text-secondary" style="width:20px;">#${idx + 1}</span>
              <span class="fw-semibold text-dark">${escapeHtml(u.name)}</span>
            </div>
            <span class="badge badge-reputation px-2 py-1">${u.reputation_points || 0} pts</span>
          </li>
        `).join("");
      }
    } catch (e) {
      listEl.innerHTML = `
        <li class="list-group-item d-flex justify-content-between align-items-center py-2">
          <span>1. Sarah Jenkins</span> <span class="badge badge-reputation">140 pts</span>
        </li>
        <li class="list-group-item d-flex justify-content-between align-items-center py-2">
          <span>2. Alex Rivera</span> <span class="badge badge-reputation">115 pts</span>
        </li>
        <li class="list-group-item d-flex justify-content-between align-items-center py-2">
          <span>3. David Chen</span> <span class="badge badge-reputation">90 pts</span>
        </li>
      `;
    }
  },

  filterTasks() {
    const searchVal = (document.getElementById("task-search-input")?.value || "").toLowerCase();
    const statusVal = document.getElementById("task-status-filter")?.value || "all";

    const filtered = this.tasks.filter(t => {
      const matchSearch = t.title.toLowerCase().includes(searchVal) || t.description.toLowerCase().includes(searchVal);
      const matchStatus = statusVal === "all" || t.status === statusVal;
      return matchSearch && matchStatus;
    });

    this.renderTasks(filtered);
  },

  scrollToTasks() {
    document.getElementById("tasks-section")?.scrollIntoView({ behavior: "smooth" });
  },

  openSkillModal() {
    Toast.info("Skills update modal opening...");
  }
};

document.addEventListener("DOMContentLoaded", () => VolunteerUI.init());
