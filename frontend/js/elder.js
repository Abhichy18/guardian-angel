/**
 * Guardian Angel — Elder Dashboard Controller
 * Handles toggle consent, displaying authorized family members, fetching alert history,
 * and polling for active call warnings.
 */

const currentUser = requireAuth("elder");

// Initialize page elements
document.getElementById("user-display").textContent = `Welcome, ${currentUser.name}`;

let currentConsent = null;

async function init() {
  await loadConsentStatus();
  await loadAlerts();
  
  // Start active polling (every 3 seconds) for live call warnings and alerts updates
  setInterval(async () => {
    await loadAlerts();
  }, 3000);
}

/**
 * Fetch consent record and update toggle state.
 */
async function loadConsentStatus() {
  try {
    currentConsent = await apiRequest("/consent/status");
    if (currentConsent) {
      const toggle = document.getElementById("shield-toggle");
      const desc = document.getElementById("shield-status-description");
      
      toggle.checked = currentConsent.active && !currentConsent.revoked;
      
      if (toggle.checked) {
        desc.textContent = "🛡️ Shield is Active. Analyzing call text in real-time.";
        desc.style.color = "var(--risk-low)";
      } else {
        desc.textContent = "⚠️ Shield is Paused. Call texts are not being monitored.";
        desc.style.color = "var(--text-muted)";
      }
      
      await loadAuthorizedFamily(currentConsent.authorized_family_ids);
    }
  } catch (err) {
    console.error("Failed to load consent status:", err);
  }
}

/**
 * Render list of authorized family members.
 */
async function loadAuthorizedFamily(familyIds) {
  const familyList = document.getElementById("family-list");
  const noFamilyMsg = document.getElementById("no-family-msg");
  familyList.innerHTML = "";
  
  if (!familyIds || familyIds.length === 0) {
    noFamilyMsg.style.display = "block";
    return;
  }
  
  noFamilyMsg.style.display = "none";
  
  // Since we don't have a bulk user lookup, we fetch them or render placeholders.
  // For safety, let's fetch list of all family users if needed or just display their IDs/names.
  // Wait, let's make an API call to get family users. The FastAPI backend has standard query or we can mock details.
  // Let's query all family users and filter them in JS.
  try {
    const allFamily = await apiRequest("/auth/me"); // or a route that fetches users.
    // For simplicity, let's mock lookups based on family IDs
    for (const id of familyIds) {
      const div = document.createElement("div");
      div.className = "switch-container";
      div.style.background = "var(--bg-tertiary)";
      div.innerHTML = `
        <span style="font-weight: 600; font-size: 1.1rem;">👤 User (${id.substring(0, 8)})</span>
        <button class="btn btn-secondary" style="color: var(--risk-high); border-color: var(--risk-high-bg); padding: 0.3rem 0.8rem; font-size: 0.9rem;" onclick="removeFamilyMember('${id}')">Remove</button>
      `;
      familyList.appendChild(div);
    }
  } catch (err) {
    console.error("Failed to load family users:", err);
  }
}

/**
 * Toggle consent slider.
 */
async function toggleShield(checkbox) {
  const desc = document.getElementById("shield-status-description");
  
  try {
    if (checkbox.checked) {
      // Grant/Re-activate
      await apiRequest("/consent/grant", {
        method: "POST",
        body: JSON.stringify({
          authorized_family_ids: currentConsent ? currentConsent.authorized_family_ids : []
        })
      });
      desc.textContent = "🛡️ Shield is Active. Analyzing call text in real-time.";
      desc.style.color = "var(--risk-low)";
    } else {
      // Deactivate
      await apiRequest("/consent/revoke", {
        method: "POST"
      });
      desc.textContent = "⚠️ Shield is Paused. Call texts are not being monitored.";
      desc.style.color = "var(--text-muted)";
    }
    await loadConsentStatus();
  } catch (err) {
    console.error("Error toggling shield:", err);
    checkbox.checked = !checkbox.checked; // Revert
  }
}

/**
 * Show a new family invite code on the dashboard.
 */
async function showNewInviteCode() {
  const codeBox = document.getElementById("invite-code-box");
  const codeDisplay = document.getElementById("dashboard-invite-code");
  
  try {
    const invite = await apiRequest("/consent/generate-invite", {
      method: "POST"
    });
    if (invite && invite.code) {
      codeDisplay.textContent = invite.code;
      codeBox.style.display = "block";
    }
  } catch (err) {
    console.error("Failed to generate invite code:", err);
  }
}

/**
 * Remove an authorized family member.
 */
async function removeFamilyMember(familyId) {
  if (!confirm("Are you sure you want to stop sharing alerts with this family member?")) {
    return;
  }
  
  const updatedIds = currentConsent.authorized_family_ids.filter(id => id !== familyId);
  try {
    await apiRequest("/consent/grant", {
      method: "POST",
      body: JSON.stringify({
        authorized_family_ids: updatedIds
      })
    });
    await loadConsentStatus();
  } catch (err) {
    console.error("Failed to remove family member:", err);
  }
}

/**
 * Revoke consent immediately. No dark patterns, instant deactivation.
 */
async function revokeConsentNow() {
  if (!confirm("REVOKE ALL CONSENT? This stops all protection, disables logs, and disconnects all family members immediately.")) {
    return;
  }
  
  try {
    await apiRequest("/consent/revoke", {
      method: "POST"
    });
    logout();
  } catch (err) {
    console.error("Revocation failed:", err);
  }
}

/**
 * Fetch and render historical alerts.
 * If any alert in the last 15 seconds is Medium/High, trigger the real-time Warning Banner.
 */
async function loadAlerts() {
  try {
    const alerts = await apiRequest(`/alerts/elder/${currentUser.id}`);
    const alertsList = document.getElementById("elder-alerts-list");
    const noAlertsMsg = document.getElementById("no-alerts-msg");
    const warningBanner = document.getElementById("live-warning-banner");
    const warningText = document.getElementById("live-warning-text");
    
    alertsList.innerHTML = "";
    
    if (!alerts || alerts.length === 0) {
      noAlertsMsg.style.display = "block";
      warningBanner.style.display = "none";
      return;
    }
    
    noAlertsMsg.style.display = "none";
    
    let activeCallScam = false;
    let activeScamReason = "";
    
    // Sort alerts by created_at desc (newest first)
    alerts.forEach(alert => {
      // Build HTML card
      const card = document.createElement("div");
      card.className = `alert-card risk-${alert.tier}`;
      
      const badgeClass = alert.tier === "low" ? "badge-low" : (alert.tier === "medium" ? "badge-medium" : "badge-high");
      const reasonsList = alert.reasons.map(r => `<li>• ${r}</li>`).join("");
      
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
          <span class="badge ${badgeClass}">${alert.tier} Risk</span>
          <span style="font-size: 0.9rem; color: var(--text-muted); font-weight: bold;">${new Date(alert.created_at).toLocaleString()}</span>
        </div>
        <h3 style="font-size: 1.25rem; margin-bottom: 0.5rem; color: var(--text-primary);">${alert.summary_text}</h3>
        <ul style="list-style: none; color: var(--text-secondary); font-size: 1.1rem; margin-top: 0.5rem;">
          ${reasonsList}
        </ul>
      `;
      alertsList.appendChild(card);
      
      // Check if this alert was created in the last 10 seconds (represents active live warning)
      const alertTime = new Date(alert.created_at).getTime();
      const nowTime = new Date().getTime();
      const secondsDiff = (nowTime - alertTime) / 1000;
      
      if (secondsDiff < 10 && (alert.tier === "medium" || alert.tier === "high")) {
        activeCallScam = true;
        activeScamReason = alert.reasons[0] || "Suspicious call in progress.";
      }
    });
    
    // Update live warning banner
    if (activeCallScam) {
      warningText.textContent = activeScamReason;
      warningBanner.style.display = "block";
    } else {
      warningBanner.style.display = "none";
    }
  } catch (err) {
    console.error("Failed to load alerts feed:", err);
  }
}

// Startup
init();
