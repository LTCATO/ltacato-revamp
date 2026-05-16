function setSiteHeaderOffset() {
  const header = document.getElementById("siteHeader");
  if (!header) return;
  document.documentElement.style.setProperty(
    "--site-header-offset",
    `${header.offsetHeight}px`
  );
}

function initHeroVideo() {
  const video = document.getElementById("heroVideo");
  const toggle = document.getElementById("heroSoundToggle");
  if (!video) return;

  video.addEventListener("error", () => {
    video.style.display = "none";
  });

  if (!toggle) return;

  const icon = toggle.querySelector(".hero-sound-toggle__icon");
  const label = toggle.querySelector(".hero-sound-toggle__label");

  const setMutedUi = (muted) => {
    toggle.classList.toggle("is-unmuted", !muted);
    toggle.setAttribute("aria-pressed", String(!muted));
    toggle.setAttribute("aria-label", muted ? "Unmute video" : "Mute video");
    toggle.title = muted ? "Unmute video" : "Mute video";

    if (icon) {
      icon.className = muted
        ? "ph ph-speaker-slash hero-sound-toggle__icon"
        : "ph ph-speaker-high hero-sound-toggle__icon";
    }
    if (label) {
      label.textContent = muted ? "Sound off" : "Sound on";
    }
  };

  setMutedUi(video.muted);

  toggle.addEventListener("click", async () => {
    const willUnmute = video.muted;

    if (willUnmute) {
      video.muted = false;
      try {
        await video.play();
        setMutedUi(false);
      } catch {
        video.muted = true;
        setMutedUi(true);
      }
      return;
    }

    video.muted = true;
    setMutedUi(true);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setSiteHeaderOffset();
  initHeroVideo();

  const navCollapse = document.getElementById("ltcatoNav");
  if (navCollapse) {
    navCollapse.addEventListener("shown.bs.collapse", setSiteHeaderOffset);
    navCollapse.addEventListener("hidden.bs.collapse", setSiteHeaderOffset);
  }
});

window.addEventListener("resize", setSiteHeaderOffset);
