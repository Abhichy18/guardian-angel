/**
 * Guardian Angel — Onboarding JS Logic
 * Orchestrates step transitions, PIN-consent confirmation, and family invite code generation.
 */

// Verify user role
const currentUser = requireAuth("elder");

let currentStep = 1;

function goToStep(step) {
  currentStep = step;
  
  // Hide all panels
  document.getElementById("step-1-panel").style.display = "none";
  document.getElementById("step-2-panel").style.display = "none";
  document.getElementById("step-3-panel").style.display = "none";
  
  // Show target panel
  document.getElementById(`step-${step}-panel`).style.display = "block";
  
  // Update step nodes indicator
  for (let i = 1; i <= 3; i++) {
    const node = document.getElementById(`node-${i}`);
    if (i <= step) {
      node.classList.add("active");
    } else {
      node.classList.remove("active");
    }
  }
}

/**
 * Step 2: Confirm consent using PIN verification.
 */
async function confirmConsent(event) {
  event.preventDefault();
  const pinInput = document.getElementById("confirm-pin").value;
  const errorDiv = document.getElementById("consent-error");
  errorDiv.style.display = "none";
  
  try {
    // 1. Authenticate with PIN to confirm consent signal
    const loginData = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        name: currentUser.name,
        pin: pinInput
      })
    });
    
    if (loginData) {
      // 2. Grant initial consent in DB
      await apiRequest("/consent/grant", {
        method: "POST",
        body: JSON.stringify({
          authorized_family_ids: []
        })
      });
      
      // 3. Generate invite code
      await generateNewCode();
      
      // 4. Move to step 3
      goToStep(3);
    }
  } catch (err) {
    errorDiv.textContent = err.message || "Invalid PIN. Please try again.";
    errorDiv.style.display = "block";
  }
}

/**
 * Step 3: Fetch a new family invite code from the server.
 */
async function generateNewCode() {
  const codeDisplay = document.getElementById("code-display");
  codeDisplay.textContent = "------";
  
  try {
    const response = await apiRequest("/consent/generate-invite", {
      method: "POST"
    });
    
    if (response && response.code) {
      codeDisplay.textContent = response.code;
    }
  } catch (err) {
    console.error("Failed to generate invite code:", err);
    alert("Could not generate invite code. Please try again.");
  }
}

function finishOnboarding() {
  window.location.href = "/elder-dashboard";
}
