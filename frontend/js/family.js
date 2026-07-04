/**
 * Guardian Angel — Family Dashboard Controller
 * Handles alert feed display, filtering, linked elder management,
 * invite code redemption, stats updates, and live polling for active incidents.
 */

const currentUser = requireAuth("family");

// Initialize page
document.getElementById("user-display").textContent = `${currentUser.name} (Family)`;

let allAlerts = [];
let currentFilter = "all";

async function init() {
  await loadLinkedElders();
  await loadAlerts();

  // Poll every 4 seconds for live updates
  setInterval(async () => {
    await loadAlerts();
  }, 4000);
}

/**
 * Fetch alerts for this family member from the API.
 */
async function loadAlerts() {
  try {
    const alerts = await apiRequest(`/alerts/family/${currentUser.id}`);
    const alertsList = document.getElementById("family-alerts-list");
    const noAlertsMsg = document.getElementById("no-alerts-msg");
    const incidentBanner = document.getElementById("live-incident-banner");
    const incidentText = document.getElementById("live-incident-text");

    if (!alerts || alerts.length === 0) {
      allAlerts = [];
      alertsList.innerHTML = "";
      noAlertsMsg.style.display = "block";
      incidentBanner.style.display = "none";
      updateStats([]);
      updateTimeline([]);
      return;
    }

    allAlerts = alerts;
    noAlertsMsg.style.display = "none";
    updateStats(alerts);
    updateTimeline(alerts);

    // Check for active incident (alert within last 15 seconds, medium or high)
    let activeIncident = false;
    let incidentReason = "";

    const now = Date.now();
    for (const alert of alerts) {
      const alertTime = new Date(alert.created_at).getTime();
      if ((now - alertTime) < 15000 && (alert.tier === "high" || alert.tier === "medium")) {
        activeIncident = true;
        incidentReason = alert.summary_text || alert.reasons[0] || "Suspicious activity detected.";
        break;
      }
    }

    if (activeIncident) {
      incidentText.textContent = incidentReason;
      incidentBanner.style.display = "block";
    } else {
      incidentBanner.style.display = "none";
    }

    renderAlerts(currentFilter);
  } catch (err) {
    console.error("Failed to load family alerts:", err);
  }
}

/**
 * Render alert cards with the current filter applied.
 */
function renderAlerts(filter) {
  const alertsList = document.getElementById("family-alerts-list");
  const noAlertsMsg = document.getElementById("no-alerts-msg");
  alertsList.innerHTML = "";

  const filtered = filter === "all"
    ? allAlerts
    : allAlerts.filter(a => a.tier === filter);

  if (filtered.length === 0) {
    noAlertsMsg.style.display = "block";
    return;
  }

  noAlertsMsg.style.display = "none";

  for (const alert of filtered) {
    const card = document.createElement("div");
    card.className = `alert-card risk-${alert.tier}`;

    const badgeClass = alert.tier === "low" ? "badge-low" : (alert.tier === "medium" ? "badge-medium" : "badge-high");
    const reasonsList = alert.reasons.map(r => `<li>• ${r}</li>`).join("");
    const timeStr = new Date(alert.created_at).toLocaleString();

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
        <span class="badge ${badgeClass}">${alert.tier} Risk</span>
        <span style="font-size: 0.85rem; color: var(--text-muted); font-weight: 600;">${timeStr}</span>
      </div>
      <h3 style="font-size: 1.15rem; margin-bottom: 0.4rem; color: var(--text-primary);">${alert.summary_text}</h3>
      <ul style="list-style: none; color: var(--text-secondary); font-size: 0.95rem; margin-top: 0.4rem;">
        ${reasonsList}
      </ul>
      <div style="margin-top: 0.8rem; padding-top: 0.8rem; border-top: 1px solid var(--glass-border); display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 0.85rem; color: var(--text-muted);">Elder: ${alert.elder_id ? alert.elder_id.substring(0, 8) + '...' : 'Unknown'}</span>
        <button class="btn btn-secondary" style="padding: 0.3rem 0.7rem; font-size: 0.8rem;" onclick="viewAlertDetail('${alert.id}')">View Details</button>
      </div>
    `;
    alertsList.appendChild(card);
  }
}

/**
 * Filter alerts by risk tier.
 */
function filterAlerts(tier, btn) {
  currentFilter = tier;

  // Update active filter button style
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active-filter"));
  if (btn) btn.classList.add("active-filter");

  renderAlerts(tier);
}

/**
 * Navigate to alert detail view (or show inline for now).
 */
async function viewAlertDetail(alertId) {
  try {
    const detail = await apiRequest(`/alerts/${alertId}`);
    if (detail) {
      alert(`Alert Detail:\n\nSummary: ${detail.summary_text}\n\nRisk Tier: ${detail.tier}\nReasons: ${detail.reasons.join(", ")}\n\nCreated: ${new Date(detail.created_at).toLocaleString()}`);
    }
  } catch (err) {
    console.error("Failed to fetch alert detail:", err);
  }
}

/**
 * Update stats panel with current alert data.
 */
function updateStats(alerts) {
  document.getElementById("stat-total-alerts").textContent = alerts.length;
  document.getElementById("stat-high-risk").textContent = alerts.filter(a => a.tier === "high").length;
  document.getElementById("stat-blocked").textContent = alerts.filter(a =>
    a.reasons && a.reasons.some(r => r.toLowerCase().includes("transaction") || r.toLowerCase().includes("paused") || r.toLowerCase().includes("blocked"))
  ).length;
}

/**
 * Build a simple timeline view from recent alerts.
 */
function updateTimeline(alerts) {
  const timelineList = document.getElementById("timeline-list");
  const noMsg = document.getElementById("no-timeline-msg");

  // Show the 5 most recent alerts
  const recent = alerts.slice(0, 5);

  if (recent.length === 0) {
    noMsg.style.display = "block";
    timelineList.querySelectorAll(".timeline-item").forEach(el => el.remove());
    return;
  }

  noMsg.style.display = "none";

  // Remove existing items
  timelineList.querySelectorAll(".timeline-item").forEach(el => el.remove());

  for (const a of recent) {
    const item = document.createElement("div");
    item.className = "timeline-item";

    const tierColor = a.tier === "high" ? "var(--risk-high)" : (a.tier === "medium" ? "var(--risk-medium)" : "var(--risk-low)");
    const tierIcon = a.tier === "high" ? "🔴" : (a.tier === "medium" ? "🟡" : "🟢");
    const timeAgo = getTimeAgo(new Date(a.created_at));

    item.style.cssText = `
      display: flex;
      align-items: flex-start;
      gap: 0.8rem;
      padding: 0.8rem 0;
      border-bottom: 1px solid var(--glass-border);
    `;

    item.innerHTML = `
      <span style="font-size: 1.2rem; flex-shrink: 0; margin-top: 0.1rem;">${tierIcon}</span>
      <div style="flex: 1; min-width: 0;">
        <div style="font-size: 0.9rem; font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${a.summary_text}</div>
        <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">${timeAgo}</div>
      </div>
    `;

    timelineList.appendChild(item);
  }
}

/**
 * Helper: relative time string.
 */
function getTimeAgo(date) {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "Just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/**
 * Load list of elders who have authorized this family member.
 */
async function loadLinkedElders() {
  try {
    const elders = await apiRequest(`/consent/linked-elders`);
    const eldersList = document.getElementById("linked-elders-list");
    const noEldersMsg = document.getElementById("no-elders-msg");

    eldersList.innerHTML = "";

    if (!elders || elders.length === 0) {
      noEldersMsg.style.display = "block";
      return;
    }

    noEldersMsg.style.display = "none";

    for (const elder of elders) {
      const div = document.createElement("div");
      div.style.cssText = `
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.8rem 1rem;
        background: var(--bg-tertiary);
        border-radius: 10px;
        border: 1px solid var(--glass-border);
      `;
      div.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.6rem;">
          <span style="font-size: 1.4rem;">👤</span>
          <div>
            <div style="font-weight: 600; font-size: 0.95rem;">${elder.name || 'Elder (' + elder.id.substring(0, 8) + ')'}</div>
            <div style="font-size: 0.8rem; color: ${elder.shield_active ? 'var(--risk-low)' : 'var(--text-muted)'};">
              ${elder.shield_active ? '🛡️ Shield Active' : '⚠️ Shield Paused'}
            </div>
          </div>
        </div>
      `;
      eldersList.appendChild(div);
    }

    // Update shield status indicator
    const anyActive = elders.some(e => e.shield_active);
    document.getElementById("stat-shield-status").textContent = anyActive ? "🟢" : "🔴";
  } catch (err) {
    console.error("Failed to load linked elders:", err);
  }
}

/**
 * Redeem an invite code to link with an elder.
 */
async function redeemInviteCode() {
  const codeInput = document.getElementById("invite-code-input");
  const errorEl = document.getElementById("invite-error");
  const code = codeInput.value.trim();

  errorEl.style.display = "none";

  if (!code || code.length < 4) {
    errorEl.textContent = "Please enter a valid invite code.";
    errorEl.style.display = "block";
    return;
  }

  try {
    const result = await apiRequest("/consent/redeem-invite", {
      method: "POST",
      body: JSON.stringify({ code: code })
    });

    if (result && result.success) {
      codeInput.value = "";
      await loadLinkedElders();
      await loadAlerts();
    } else {
      errorEl.textContent = result.detail || "Failed to redeem invite code.";
      errorEl.style.display = "block";
    }
  } catch (err) {
    errorEl.textContent = err.message || "Invalid or expired invite code.";
    errorEl.style.display = "block";
  }
}

/**
 * Trigger a phone call to the elder (placeholder — would integrate with telephony).
 */
function callElderNow() {
  alert("📞 Initiating call to your family member...\n\nIn production, this would connect via the telephony system (Twilio) to call the elder immediately.");
}

// Startup
init();
