/*
 * Camera-only photo capture for review forms. Replaces the native
 * <input type="file"> chooser (which lets people pick from their gallery)
 * with a live camera feed + "Capture" button, so review photos are always
 * taken on the spot. The hidden file input still carries the captured
 * File objects on submit — nothing else about form submission changes.
 *
 * Usage: a trigger button with data-camera-trigger, data-camera-target
 * (the file input's id) and data-camera-preview (the preview container's
 * id), optionally data-camera-max (default 5).
 */
(() => {
  function initWidget(triggerBtn) {
    const fileInput = document.getElementById(triggerBtn.dataset.cameraTarget);
    const previewEl = document.getElementById(triggerBtn.dataset.cameraPreview);
    const max = parseInt(triggerBtn.dataset.cameraMax, 10) || 5;
    if (!fileInput || !previewEl) return;

    const triggerLabel = triggerBtn.innerHTML;
    let files = [];
    let previewUrls = [];
    let sessionShots = [];
    let sessionUrls = [];
    let stream = null;
    let modalEl, videoEl, canvasEl, captureBtn, doneBtn, thumbsEl, errorEl, countEl, bsModal;

    function syncInput() {
      const dt = new DataTransfer();
      files.forEach((f) => dt.items.add(f));
      fileInput.files = dt.files;
    }

    function updateTrigger() {
      if (files.length >= max) {
        triggerBtn.disabled = true;
        triggerBtn.innerHTML = `<i class="ph ph-camera"></i> Maximum ${max} photos added`;
      } else {
        triggerBtn.disabled = false;
        triggerBtn.innerHTML = triggerLabel;
      }
    }

    function renderPreview() {
      previewUrls.forEach((url) => URL.revokeObjectURL(url));
      previewUrls = [];
      previewEl.innerHTML = "";
      files.forEach((file, idx) => {
        const url = URL.createObjectURL(file);
        previewUrls.push(url);
        const wrap = document.createElement("div");
        wrap.className = "review-image-preview__item";
        const img = document.createElement("img");
        img.src = url;
        img.alt = file.name;
        img.className = "review-image-preview__thumb";
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "review-image-preview__remove";
        remove.setAttribute("aria-label", "Remove photo");
        remove.innerHTML = "&times;";
        remove.addEventListener("click", () => {
          files.splice(idx, 1);
          syncInput();
          renderPreview();
          updateTrigger();
        });
        wrap.appendChild(img);
        wrap.appendChild(remove);
        previewEl.appendChild(wrap);
      });
      updateTrigger();
    }

    function buildModal() {
      modalEl = document.createElement("div");
      modalEl.className = "modal fade";
      modalEl.tabIndex = -1;
      modalEl.setAttribute("aria-hidden", "true");
      modalEl.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title"><i class="ph ph-camera"></i> Take a photo</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <p class="camera-capture-error text-danger small d-none mb-2"></p>
              <div class="camera-capture-viewport">
                <video autoplay playsinline muted></video>
              </div>
              <canvas class="d-none"></canvas>
              <div class="camera-capture-thumbs"></div>
              <p class="small text-muted mt-2 mb-0 camera-capture-count"></p>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-outline-primary camera-capture-shot">
                <i class="ph ph-camera"></i> Capture
              </button>
              <button type="button" class="btn ltcato-btn-pill camera-capture-done">Use photo(s)</button>
            </div>
          </div>
        </div>`;
      document.body.appendChild(modalEl);
      videoEl = modalEl.querySelector("video");
      canvasEl = modalEl.querySelector("canvas");
      captureBtn = modalEl.querySelector(".camera-capture-shot");
      doneBtn = modalEl.querySelector(".camera-capture-done");
      thumbsEl = modalEl.querySelector(".camera-capture-thumbs");
      errorEl = modalEl.querySelector(".camera-capture-error");
      countEl = modalEl.querySelector(".camera-capture-count");
      bsModal = new bootstrap.Modal(modalEl);

      modalEl.addEventListener("shown.bs.modal", startCamera);
      modalEl.addEventListener("hidden.bs.modal", stopCamera);
      captureBtn.addEventListener("click", takeShot);
      doneBtn.addEventListener("click", () => {
        files = files.concat(sessionShots).slice(0, max);
        syncInput();
        renderPreview();
        bsModal.hide();
      });
    }

    function renderSessionThumbs() {
      sessionUrls.forEach((url) => URL.revokeObjectURL(url));
      sessionUrls = [];
      thumbsEl.innerHTML = "";
      sessionShots.forEach((file, idx) => {
        const url = URL.createObjectURL(file);
        sessionUrls.push(url);
        const wrap = document.createElement("div");
        wrap.className = "review-image-preview__item";
        const img = document.createElement("img");
        img.src = url;
        img.className = "review-image-preview__thumb";
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "review-image-preview__remove";
        remove.setAttribute("aria-label", "Discard shot");
        remove.innerHTML = "&times;";
        remove.addEventListener("click", () => {
          sessionShots.splice(idx, 1);
          renderSessionThumbs();
        });
        wrap.appendChild(img);
        wrap.appendChild(remove);
        thumbsEl.appendChild(wrap);
      });
      const remaining = max - files.length - sessionShots.length;
      countEl.textContent = `${files.length + sessionShots.length}/${max} photos`;
      captureBtn.disabled = remaining <= 0;
    }

    function takeShot() {
      if (!videoEl.videoWidth) return;
      canvasEl.width = videoEl.videoWidth;
      canvasEl.height = videoEl.videoHeight;
      canvasEl.getContext("2d").drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
      canvasEl.toBlob(
        (blob) => {
          if (!blob) return;
          sessionShots.push(new File([blob], `review-${Date.now()}.jpg`, { type: "image/jpeg" }));
          renderSessionThumbs();
        },
        "image/jpeg",
        0.85,
      );
    }

    function startCamera() {
      sessionShots = [];
      renderSessionThumbs();
      errorEl.classList.add("d-none");
      captureBtn.disabled = false;
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showError("Your browser doesn't support camera capture.");
        return;
      }
      navigator.mediaDevices
        .getUserMedia({ video: { facingMode: "environment" }, audio: false })
        .then((s) => {
          stream = s;
          videoEl.srcObject = stream;
        })
        .catch(() => {
          showError("Camera access was denied or is unavailable. Please allow camera permission and try again.");
        });
    }

    function showError(message) {
      errorEl.textContent = message;
      errorEl.classList.remove("d-none");
      captureBtn.disabled = true;
    }

    function stopCamera() {
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
        stream = null;
      }
      videoEl.srcObject = null;
    }

    triggerBtn.addEventListener("click", () => {
      if (files.length >= max) return;
      if (!modalEl) buildModal();
      bsModal.show();
    });

    renderPreview();
  }

  function init() {
    document.querySelectorAll("[data-camera-trigger]").forEach(initWidget);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
