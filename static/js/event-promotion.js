(() => {
  const slugSource = document.querySelector("[data-slug-source]");
  const slugTarget = document.querySelector("[data-slug-target]");
  if (slugSource && slugTarget) {
    const slugify = (t) =>
      t
        .toLowerCase()
        .replace(/[^\w\s-]/g, "")
        .trim()
        .replace(/[-\s]+/g, "-")
        .slice(0, 80);
    let slugTouched = false;
    slugTarget.addEventListener("input", () => {
      slugTouched = slugTarget.value.trim().length > 0;
    });
    slugSource.addEventListener("input", () => {
      if (!slugTouched) slugTarget.value = slugify(slugSource.value);
    });
  }

  const galleryInput = document.querySelector("[data-gallery-input]");
  const galleryPreview = document.querySelector("[data-gallery-preview]");
  if (galleryInput && galleryPreview) {
    galleryInput.addEventListener("change", () => {
      galleryPreview.innerHTML = "";
      const files = galleryInput.files || [];
      for (let i = 0; i < files.length; i += 1) {
        const f = files[i];
        if (!f.type.startsWith("image/")) continue;
        const wrap = document.createElement("div");
        wrap.className = "event-gallery-preview__item";
        const img = document.createElement("img");
        img.alt = f.name;
        img.loading = "lazy";
        const url = URL.createObjectURL(f);
        img.src = url;
        wrap.appendChild(img);
        galleryPreview.appendChild(wrap);
      }
    });
  }

  const exhibitorRows = document.querySelector("[data-exhibitor-rows]");
  const addBtn = document.querySelector("[data-add-exhibitor]");
  if (exhibitorRows && addBtn) {
    exhibitorRows.addEventListener("click", (e) => {
      const removeBtn = e.target.closest("[data-remove-exhibitor]");
      if (removeBtn) {
        const row = removeBtn.closest("[data-exhibitor-row]");
        const inputs = Array.from(
          row.querySelectorAll("input, textarea"),
        ).filter((el) => {
          if (el.type === "checkbox" || el.type === "radio") return el.checked;
          return el.value.trim() !== "";
        });
        const hasInputs = inputs.length > 0;

        if (hasInputs) {
          if (
            !confirm(
              "This exhibitor has filled data. Are you sure you want to remove it?",
            )
          ) {
            return;
          }
        }

        if (exhibitorRows.querySelectorAll("[data-exhibitor-row]").length > 1) {
          row.remove();
        } else {
          row.querySelectorAll("input, textarea, select").forEach((el) => {
            if (el.type === "checkbox" || el.type === "radio")
              el.checked = false;
            else el.value = "";
          });
        }
      }
    });

    addBtn.addEventListener("click", () => {
      const first = exhibitorRows.querySelector("[data-exhibitor-row]");
      if (!first) return;
      const clone = first.cloneNode(true);
      clone.querySelectorAll("input, textarea, select").forEach((el) => {
        if (el.type === "checkbox" || el.type === "radio") el.checked = false;
        else el.value = "";
      });
      exhibitorRows.appendChild(clone);
    });
  }

  // ── Next / Publish tab-wizard logic ──────────────────────────────────────
  const epModal = document.getElementById("eventModal");
  const epNextBtn = document.getElementById("epNextPublishBtn");
  const epTabButtons = epModal
    ? Array.from(epModal.querySelectorAll(".event-promotion-tabs .nav-link"))
    : [];
  const LAST_TAB_INDEX = epTabButtons.length - 1;

  function updateNextPublishBtn() {
    if (!epNextBtn || !epTabButtons.length) return;
    const activeIdx = epTabButtons.findIndex((btn) =>
      btn.classList.contains("active"),
    );
    if (activeIdx === LAST_TAB_INDEX) {
      epNextBtn.textContent = "Publish";
      epNextBtn.dataset.action = "publish";
    } else {
      epNextBtn.textContent = "Next";
      epNextBtn.dataset.action = "next";
    }
  }

  if (epModal && epNextBtn && epTabButtons.length) {
    // Update label whenever a tab becomes active
    epModal.addEventListener("shown.bs.tab", updateNextPublishBtn);
    // Also update on modal show (reset to first tab)
    epModal.addEventListener("show.bs.modal", () => {
      setTimeout(updateNextPublishBtn, 0);
    });

    epNextBtn.addEventListener("click", () => {
      const action = epNextBtn.dataset.action || "next";
      if (action === "publish") {
        // Trigger form submission
        const epForm = document.getElementById("eventPromotionForm");
        if (epForm) epForm.requestSubmit();
      } else {
        // Navigate to the next tab
        const activeIdx = epTabButtons.findIndex((btn) =>
          btn.classList.contains("active"),
        );
        const nextBtn = epTabButtons[activeIdx + 1];
        if (nextBtn) nextBtn.click();
      }
    });

    // Initialise label on page load
    updateNextPublishBtn();
  }
  // ──────────────────────────────────────────────────────────────────────────

  const form = document.getElementById("eventPromotionForm");
  const editorHost = document.getElementById("fullDescriptionEditor");
  const hiddenInput = document.getElementById("fullDescriptionInput");

  const initQuill = () => {
    if (!form || !editorHost || !hiddenInput || typeof Quill === "undefined")
      return;
    const quill = new Quill(editorHost, {
      theme: "snow",
      placeholder:
        "Write the full event story, program notes, and visitor information…",
      modules: {
        toolbar: [
          [{ header: [1, 2, 3, false] }],
          ["bold", "italic", "underline", "strike"],
          [{ list: "ordered" }, { list: "bullet" }],
          [{ align: [] }],
          ["link", "blockquote", "code-block"],
          ["clean"],
        ],
      },
    });
    if (hiddenInput.value) {
      try {
        quill.root.innerHTML = hiddenInput.value;
      } catch (_) {
        /* ignore */
      }
    }
    form.addEventListener("submit", () => {
      hiddenInput.value = quill.root.innerHTML;
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initQuill);
  } else {
    initQuill();
  }
})();
