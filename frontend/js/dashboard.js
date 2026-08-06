/**
 * Analytics Dashboard Module with Chart.js
 */

document.addEventListener('DOMContentLoaded', () => {
  loadDashboardData();
});

async function loadDashboardData() {
  try {
    const response = await fetch(`${CONFIG.API_BASE_URL}/dashboard/stats`);
    const data = await response.json();

    // Update KPI metric numbers
    document.getElementById('statTotalIssues').textContent = data.summary.total_issues;
    document.getElementById('statResolutionRate').textContent = `${data.summary.resolution_rate}%`;
    document.getElementById('statInProgress').textContent = data.summary.in_progress_issues;
    document.getElementById('statTotalCitizens').textContent = data.summary.total_citizens;

    // Render Category Donut Chart
    const catCtx = document.getElementById('categoryChart').getContext('2d');
    const categories = Object.keys(data.by_category);
    const categoryCounts = Object.values(data.by_category);

    new Chart(catCtx, {
      type: 'doughnut',
      data: {
        labels: categories.map(c => c.replace('_', ' ').toUpperCase()),
        datasets: [{
          data: categoryCounts.length > 0 ? categoryCounts : [1],
          backgroundColor: ['#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#64748b'],
          borderWidth: 0,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'bottom', labels: { color: '#94a3b8' } }
        }
      }
    });

    // Render Status Bar Chart
    const statusCtx = document.getElementById('statusChart').getContext('2d');
    new Chart(statusCtx, {
      type: 'bar',
      data: {
        labels: ['Reported', 'In Progress', 'Resolved'],
        datasets: [{
          label: 'Number of Issues',
          data: [
            data.summary.reported_issues,
            data.summary.in_progress_issues,
            data.summary.resolved_issues
          ],
          backgroundColor: ['#f59e0b', '#38bdf8', '#10b981'],
          borderRadius: 8,
        }]
      },
      options: {
        responsive: true,
        scales: {
          x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
          y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255, 255, 255, 0.05)' } }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });

  } catch (err) {
    console.error('Failed to load dashboard stats:', err);
  }
}
