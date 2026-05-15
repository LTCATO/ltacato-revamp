function initPasswordToggles() {
  document.querySelectorAll("[data-password-toggle]").forEach((btn) => {
    const inputId = btn.getAttribute("data-password-toggle");
    const input = document.getElementById(inputId);
    if (!input) return;

    btn.addEventListener("click", () => {
      const isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";
      btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
      const icon = btn.querySelector("i");
      if (icon) {
        icon.className = isHidden ? "ph ph-eye-slash" : "ph ph-eye";
      }
    });
  });
}

function initPasswordMeter() {
  const passwordInput = document.getElementById("register-password");
  const meter = document.getElementById("passwordMeter");
  if (!passwordInput || !meter) return;

  const bar = meter.querySelector(".auth-password-meter__bar");
  if (!bar) return;

  const scorePassword = (value) => {
    let score = 0;
    if (value.length >= 8) score += 1;
    if (value.length >= 12) score += 1;
    if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
    if (/\d/.test(value)) score += 1;
    if (/[^a-zA-Z0-9]/.test(value)) score += 1;
    return Math.min(score, 4);
  };

  passwordInput.addEventListener("input", () => {
    const score = scorePassword(passwordInput.value);
    meter.dataset.strength = String(score);
    bar.style.width = `${(score / 4) * 100}%`;
  });
}

function initRegisterValidation() {
  const form = document.getElementById("touristRegisterForm");
  if (!form) return;

  const password = document.getElementById("register-password");
  const confirm = document.getElementById("register-confirm");
  const mismatch = document.getElementById("passwordMismatch");

  const checkMatch = () => {
    if (!password || !confirm || !mismatch) return true;
    const matches = !confirm.value || password.value === confirm.value;
    mismatch.classList.toggle("d-none", matches);
    confirm.setCustomValidity(matches ? "" : "Passwords do not match");
    return matches;
  };

  if (confirm) {
    confirm.addEventListener("input", checkMatch);
  }
  if (password) {
    password.addEventListener("input", checkMatch);
  }

  form.addEventListener("submit", (event) => {
    if (!checkMatch()) {
      event.preventDefault();
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initPasswordToggles();
  initPasswordMeter();
  initRegisterValidation();
});
