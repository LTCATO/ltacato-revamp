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

const STRENGTH_LABELS = ["Very weak", "Weak", "Fair", "Good", "Strong"];

function scorePassword(value) {
  let score = 0;
  if (value.length >= 8) score += 1;
  if (value.length >= 12) score += 1;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
  if (/\d/.test(value)) score += 1;
  if (/[^a-zA-Z0-9]/.test(value)) score += 1;
  return Math.min(score, 4);
}

function initPasswordMeter() {
  const passwordInput = document.getElementById("register-password");
  const meter = document.getElementById("passwordMeter");
  if (!passwordInput || !meter) return;

  const bar = meter.querySelector(".auth-password-meter__bar");
  const label = document.getElementById("passwordMeterLabel");
  if (!bar) return;

  const update = () => {
    const value = passwordInput.value;
    const score = scorePassword(value);
    meter.dataset.strength = String(score);
    bar.style.width = `${(score / 4) * 100}%`;
    if (label) {
      label.textContent = value ? STRENGTH_LABELS[score] : "";
    }
  };

  passwordInput.addEventListener("input", update);
  update();
}

function generateStrongPassword(length = 16) {
  const upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
  const lower = "abcdefghijkmnpqrstuvwxyz";
  const digits = "23456789";
  const symbols = "!@#$%^&*()-_=+";
  const all = upper + lower + digits + symbols;

  const randomChar = (charset) => {
    const bytes = new Uint32Array(1);
    crypto.getRandomValues(bytes);
    return charset[bytes[0] % charset.length];
  };

  const chars = [randomChar(upper), randomChar(lower), randomChar(digits), randomChar(symbols)];
  for (let i = chars.length; i < length; i += 1) {
    chars.push(randomChar(all));
  }

  for (let i = chars.length - 1; i > 0; i -= 1) {
    const bytes = new Uint32Array(1);
    crypto.getRandomValues(bytes);
    const j = bytes[0] % (i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }

  return chars.join("");
}

function revealPassword(input) {
  if (!input) return;
  input.type = "text";
  const toggle = document.querySelector(`[data-password-toggle="${input.id}"]`);
  if (toggle) {
    toggle.setAttribute("aria-label", "Hide password");
    const icon = toggle.querySelector("i");
    if (icon) icon.className = "ph ph-eye-slash";
  }
}

function initPasswordSuggestion() {
  const btn = document.getElementById("suggestPasswordBtn");
  const passwordInput = document.getElementById("register-password");
  const confirmInput = document.getElementById("register-confirm");
  if (!btn || !passwordInput) return;

  btn.addEventListener("click", () => {
    const generated = generateStrongPassword();

    passwordInput.value = generated;
    revealPassword(passwordInput);
    passwordInput.dispatchEvent(new Event("input", { bubbles: true }));

    if (confirmInput) {
      confirmInput.value = generated;
      revealPassword(confirmInput);
      confirmInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
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
  initPasswordSuggestion();
  initRegisterValidation();
});
