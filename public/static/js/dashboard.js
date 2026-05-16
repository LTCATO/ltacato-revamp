document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("dashboardSidebar");
  const toggle = document.getElementById("sidebarToggle");

  if (toggle && sidebar) {
    toggle.addEventListener("click", () => {
      sidebar.classList.toggle("is-open");
    });

    document.addEventListener("click", (event) => {
      if (
        window.innerWidth <= 991 &&
        sidebar.classList.contains("is-open") &&
        !sidebar.contains(event.target) &&
        !toggle.contains(event.target)
      ) {
        sidebar.classList.remove("is-open");
      }
    });
  }

  document.querySelectorAll(".dashboard-demo-fill").forEach((btn) => {
    btn.addEventListener("click", () => {
      const email = document.getElementById("dashboard-email");
      const password = document.getElementById("dashboard-password");
      if (email) email.value = btn.dataset.demoEmail || "";
      if (password) password.value = btn.dataset.demoPassword || "";
    });
  });
});
