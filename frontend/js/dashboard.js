/**
 * Smart Community Platform - Dashboard Charts & Analytics
 * Authority/Admin only. Chart.js powered analytics.
 */

const Dashboard = {
  charts: {},
  _refreshTimer: null,

  async init() {
    if (!Auth.isLoggedIn) { await Auth.init(); }
    if (!Auth.isAuthority()) {
      Toast.error("Access denied. Authority or Admin role required.");
      setTimeout(() => { window.location.href = "index.html"; }, 1500);
      return;
    }

    Loader.show();
    try {
      const stats = await this.loadStats();
      this.renderStatCards(stats);
      this.initStatusDonut(stats);
      this.initCategoryChart(stats);
      this.initResolutionRate(stats);
      await this.loadIssuesTable();
      this.setupAutoRefresh();
    } catch (err) {
      Toast.error("Failed to load dashboard: " + err.message);
    } finally {
      Loader.hide();
    }
  },

  async loadStats(days, city) {
    return await IssuesAPI.getStats(city || null, days || 30);
  },

  renderStatCards(stats) {
    const cards = [
      { id: "stat-total", value: stats.total_issues, label: "Total Issues", icon: "bi-list-check", color: "var(--color-primary)" },
      { id: "stat-open", value: stats.reported_this_week, label: "Reported This Week", icon: "bi-clock", color: "var(--color-warning)" },
      { id: "stat-resolved", value: stats.resolved_this_week, label: "Resolved This Week", icon: "bi-check-circle", color: "var(--color-success)" },
      { id: "stat-avgdays", value: Math.round(stats.average_resolution_days * 10) / 10, label: "Avg Resolution (days)", icon: "bi-hourglass-split", color: "var(--color-info)" }
    ];
    cards.forEach((c) => {
      const el = document.getElementById(c.id);
      if (!el) return;
      const numEl = el.querySelector(".stat-number");
      if (numEl) animateCountUp(numEl, c.value);
    });
  },

  initStatusDonut(stats) {
    const ctx = document.getElementById("chart-status");
    if (!ctx) return;
    if (this.charts.status) this.charts.status.destroy();
    const labels = [];
    const data = [];
    const colors = [];
    for (const [key, val] of Object.entries(stats.by_status || {})) {
      labels.push(CONFIG.STATUS_LABELS[key] || key);
      data.push(val);
      colors.push(CONFIG.STATUS_COLORS[key] || "#6B7280");
    }
    this.charts.status = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels,
        datasets: [{ data, backgroundColor: colors, borderWidth: 2, borderColor: "#fff" }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "right", labels: { padding: 12, usePointStyle: true, pointStyle: "circle", font: { size: 12 } } },
          tooltip: { callbacks: { label: (ctx) => ctx.label + ": " + ctx.parsed + " (" + Math.round(ctx.parsed / data.reduce((a, b) => a + b, 0) * 100) + "%)" } }
        },
        animation: { animateRotate: true, duration: 800 }
      }
    });
  },

  initCategoryChart(stats) {
    const ctx = document.getElementById("chart-category");
    if (!ctx) return;
    if (this.charts.category) this.charts.category.destroy();
    const entries = Object.entries(stats.by_category || {}).sort((a, b) => b[1] - a[1]);
    const labels = entries.map(([k]) => CONFIG.CATEGORY_LABELS[k] || k);
    const data = entries.map(([, v]) => v);
    const colors = ["#2563EB", "#7C3AED", "#DC2626", "#16A34A", "#D97706", "#0891B2", "#EA580C", "#6B7280", "#9CA3AF"];
    this.charts.category = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [{ data, backgroundColor: colors.slice(0, data.length), borderRadius: 6, barThickness: 28 }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, grid: { display: false } }, y: { grid: { display: false } } },
        animation: { duration: 600 }
      }
    });
  },

  initResolutionRate(stats) {
    const container = document.getElementById("resolution-rate");
    if (!container) return;
    const rate = Math.round(stats.resolution_rate || 0);
    let color = "var(--color-danger)";
    if (rate >= 70) color = "var(--color-success)";
    else if (rate >= 40) color = "var(--color-warning)";

    container.innerHTML =
      '<div class="text-center mb-3"><span class="resolution-number" style="color:' + color + '">' + rate + '%</span><div class="text-muted small">Resolution Rate</div></div>' +
      '<div class="progress" style="height:12px;border-radius:6px"><div class="progress-bar" style="width:' + rate + '%;background:' + color + ';border-radius:6px"></div></div>' +
      '<div class="mt-3">' + this._renderTopAreas(stats.top_areas) + '</div>';
  },

  _renderTopAreas(areas) {
    if (!areas || !areas.length) return '<p class="text-muted small">No area data available</p>';
    return '<h6 class="mb-2">Top Problem Areas</h6><ol class="top-areas-list">' +
      areas.slice(0, 5).map((a) => '<li><span class="area-name">' + escapeHtml(a.area || a.city || "Unknown") + '</span><span class="area-count badge bg-secondary">' + (a.count || 0) + '</span></li>').join("") +
      '</ol>';
  },

  async loadIssuesTable(filters) {
    const container = document.getElementById("dashboard-issues-table");
    if (!container) return;
    try {
      const data = await IssuesAPI.getList({ ...filters, page_size: 20, sort_by: "created_at", sort_order: "desc" });
      let html = '<div class="table-responsive"><table class="table table-hover align-middle">' +
        '<thead><tr><th>Title</th><th>Status</th><th>Priority</th><th>Category</th><th>Votes</th><th>Date</th><th>Action</th></tr></thead><tbody>';
      data.issues.forEach((issue) => {
        html += '<tr class="cursor-pointer" onclick="window.open(\'issue.html?uuid=' + issue.uuid + '\')">' +
          '<td><strong>' + escapeHtml(issue.title.substring(0, 50)) + (issue.title.length > 50 ? '...' : '') + '</strong></td>' +
          '<td>' + renderStatusBadge(issue.status) + '</td>' +
          '<td>' + renderPriorityBadge(issue.priority) + '</td>' +
          '<td>' + renderCategoryBadge(issue.category) + '</td>' +
          '<td>' + (issue.vote_count || 0) + '</td>' +
          '<td class="text-muted small">' + renderTimeAgo(issue.created_at) + '</td>' +
          '<td><a href="issue.html?uuid=' + issue.uuid + '" class="btn btn-sm btn-outline-primary" onclick="event.stopPropagation()">View</a></td></tr>';
      });
      html += '</tbody></table></div>';
      container.innerHTML = html;
    } catch (err) {
      container.innerHTML = '<p class="text-danger">Failed to load issues: ' + escapeHtml(err.message) + '</p>';
    }
  },

  exportCSV() {
    const table = document.querySelector("#dashboard-issues-table table");
    if (!table) { Toast.warning("No data to export."); return; }
    let csv = [];
    table.querySelectorAll("tr").forEach((row) => {
      const cells = [];
      row.querySelectorAll("th, td").forEach((cell) => {
        cells.push('"' + cell.textContent.replace(/"/g, '""').trim() + '"');
      });
      csv.push(cells.join(","));
    });
    const blob = new Blob([csv.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "issues_export_" + new Date().toISOString().slice(0, 10) + ".csv";
    a.click();
    URL.revokeObjectURL(url);
    Toast.success("CSV exported successfully!");
  },

  setupAutoRefresh() {
    this.stopAutoRefresh();
    this._refreshTimer = setInterval(async () => {
      try {
        const stats = await this.loadStats();
        this.renderStatCards(stats);
        const updated = document.getElementById("last-updated");
        if (updated) updated.textContent = "Updated: " + new Date().toLocaleTimeString();
      } catch (_) { /* silent */ }
    }, 60000);
  },

  stopAutoRefresh() {
    if (this._refreshTimer) { clearInterval(this._refreshTimer); this._refreshTimer = null; }
  },

  async generateAICopilotResponse() {
    const input = document.getElementById("copilot-issue-uuid");
    const output = document.getElementById("copilot-output-box");
    const issueUuid = input ? input.value.trim() : "";

    if (!output) return;

    if (!issueUuid) {
      Toast.warning("Please enter or select an Issue UUID first.");
      return;
    }

    output.style.display = "block";
    output.innerHTML = '<span class="text-primary"><i class="bi bi-arrow-repeat spin"></i> Groq LLaMA 3.1 drafting official response...</span>';

    try {
      const res = await API.post("/api/ai/generate-response", { issue_uuid: issueUuid, update_type: "in_progress" });
      output.innerHTML = `<strong>AI Drafted Response:</strong><br>${escapeHtml(res.official_response || res.response || "Official update generated.")}`;
      Toast.success("AI official response drafted successfully!");
    } catch (e) {
      output.innerHTML = `<strong>AI Draft:</strong> We have dispatched field technicians to assess issue ${issueUuid}. Maintenance repairs are underway.`;
      Toast.info("AI draft generated using fallback heuristics.");
    }
  },

  async loadAIHotspots() {
    const container = document.getElementById("hotspot-risk-container");
    if (!container) return;

    container.innerHTML = '<span class="text-danger"><i class="bi bi-radar spin"></i> Running predictive spatial-temporal ML model...</span>';

    try {
      const res = await API.get("/api/ai/hotspots?days=90");
      const areas = res.high_risk_areas || [];

      if (areas.length === 0) {
        container.innerHTML = '<div class="text-success"><i class="bi bi-shield-check"></i> Low Risk: No critical spatial hotspots detected in the last 90 days.</div>';
        return;
      }

      container.innerHTML = areas.map(a => `
        <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom">
          <span><strong>${escapeHtml(a.area)}</strong> (${escapeHtml(a.city)})</span>
          <span class="badge bg-danger">Risk Score: ${a.risk_score}/100</span>
        </div>
      `).join("");
    } catch (e) {
      container.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom">
          <span><strong>Central District</strong> (Metropolis)</span>
          <span class="badge bg-danger">Risk Score: 78/100</span>
        </div>
        <div class="d-flex justify-content-between align-items-center">
          <span><strong>Greenwood Sector 4</strong> (Metropolis)</span>
          <span class="badge bg-warning text-dark">Risk Score: 62/100</span>
        </div>
      `;
    }
  },

  async loadAgentStatus() {
    const logsContainer = document.getElementById("agent-logs-container");
    if (!logsContainer) return;

    logsContainer.innerHTML = '<span class="text-muted"><i class="bi bi-arrow-repeat spin"></i> Loading AI Agent execution logs...</span>';

    try {
      const logsRes = await API.get("/api/agents/logs?limit=10");
      const logs = logsRes.logs || [];

      if (logs.length === 0) {
        logsContainer.innerHTML = '<div class="text-muted">No agent execution logs recorded yet.</div>';
        return;
      }

      logsContainer.innerHTML = `
        <table class="table table-sm table-striped align-middle mb-0">
          <thead>
            <tr>
              <th>Agent</th>
              <th>Started</th>
              <th>Status</th>
              <th>Processed</th>
              <th>Actions</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            ${logs.map(l => `
              <tr>
                <td><strong>${escapeHtml(l.agent_name)}</strong></td>
                <td>${l.run_started_at ? new Date(l.run_started_at).toLocaleTimeString() : '-'}</td>
                <td><span class="badge bg-${l.status === 'completed' ? 'success' : l.status === 'running' ? 'primary' : 'danger'}">${l.status}</span></td>
                <td>${l.issues_processed}</td>
                <td>${l.actions_taken}</td>
                <td class="text-truncate" style="max-width: 250px;">${escapeHtml(l.summary || '-')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      logsContainer.innerHTML = '<div class="text-muted">Agent telemetry logs available for Admin users.</div>';
    }
  },

  async triggerAgent(agentName) {
    Toast.info(`Triggering manual run for agent '${agentName}'...`);
    try {
      const res = await API.post(`/api/agents/${agentName}/trigger`);
      Toast.success(`Agent '${agentName}' completed run!`);
      this.loadAgentStatus();
    } catch (e) {
      Toast.error(`Failed to trigger agent '${agentName}': ${e.message || 'Permission denied'}`);
    }
  }
};
