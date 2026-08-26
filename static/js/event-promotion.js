(() => {
  const form = document.getElementById("eventPromotionForm");
  const editorHost = document.getElementById("fullDescriptionEditor");
  const hiddenInput = document.getElementById("fullDescriptionInput");
  const galleryInput = document.querySelector("[data-gallery-input]");
  const galleryPreview = document.querySelector("[data-gallery-preview]");
  const exhibitorRows = document.querySelector("[data-exhibitor-rows]");
  const addExhibitorBtn = document.querySelector("[data-add-exhibitor]");
  const epModal = document.getElementById("eventModal");
  const epNextBtn = document.getElementById("epNextPublishBtn");
  const epTabButtons = epModal
    ? Array.from(epModal.querySelectorAll(".event-promotion-tabs .nav-link"))
    : [];
  const LAST_TAB_INDEX = epTabButtons.length - 1;
  const modalLabel = document.getElementById("eventModalLabel");
  const modalSubtitle = document.getElementById("eventModalSubtitle");

  let quill = null;
  let isEditing = false;

  // ── slug auto-fill ──────────────────────────────────────────────────────
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

  // ── gallery preview (new file selections) ───────────────────────────────
  let galleryPreviewUrls = [];
  function renderGalleryPreviewFromFiles() {
    if (!galleryInput || !galleryPreview) return;
    galleryPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
    galleryPreviewUrls = [];
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
      galleryPreviewUrls.push(url);
      img.src = url;
      wrap.appendChild(img);
      galleryPreview.appendChild(wrap);
    }
  }
  if (galleryInput) {
    galleryInput.addEventListener("change", renderGalleryPreviewFromFiles);
  }

  function renderGalleryPreviewFromUrls(urls) {
    if (!galleryPreview) return;
    galleryPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
    galleryPreviewUrls = [];
    galleryPreview.innerHTML = "";
    (urls || []).forEach((url) => {
      const wrap = document.createElement("div");
      wrap.className = "event-gallery-preview__item";
      const img = document.createElement("img");
      img.alt = "";
      img.loading = "lazy";
      img.src = url;
      wrap.appendChild(img);
      galleryPreview.appendChild(wrap);
    });
  }

  // ── "current file" notes shown next to file inputs when editing ────────
  function populateCurrentFiles(event) {
    document.querySelectorAll("[data-current-file]").forEach((el) => {
      const key = el.getAttribute("data-current-file");
      const url = event ? event[key] : null;
      el.innerHTML = "";
      if (!url) return;
      el.append("Current: ");
      const a = document.createElement("a");
      a.href = url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "view file";
      el.append(a);
      el.append(" (upload a new one to replace it)");
    });
  }

  // ── exhibitor rows ───────────────────────────────────────────────────────
  const EXHIBITOR_FIELD_MAP = {
    exhibitor_business_name: "business_name",
    exhibitor_owner: "owner_name",
    exhibitor_category: "category",
    exhibitor_booth_number: "booth_number",
    exhibitor_lgu_id: "lgu_id",
    exhibitor_products: "products",
    exhibitor_fb_page: "fb_page",
    exhibitor_website: "website",
  };

  function fillExhibitorRow(row, exhibitor) {
    row.querySelectorAll("input, textarea, select").forEach((el) => {
      const key = EXHIBITOR_FIELD_MAP[el.name];
      if (!key) return;
      const value = exhibitor ? exhibitor[key] : null;
      el.value = value === null || value === undefined ? "" : value;
    });
  }

  function populateExhibitors(exhibitors) {
    if (!exhibitorRows) return;
    const rows = Array.from(exhibitorRows.querySelectorAll("[data-exhibitor-row]"));
    rows.forEach((row, i) => {
      if (i > 0) row.remove();
    });
    const first = exhibitorRows.querySelector("[data-exhibitor-row]");
    if (!first) return;
    const list = exhibitors || [];
    if (list.length === 0) {
      fillExhibitorRow(first, null);
      return;
    }
    fillExhibitorRow(first, list[0]);
    for (let i = 1; i < list.length; i += 1) {
      const clone = first.cloneNode(true);
      fillExhibitorRow(clone, list[i]);
      exhibitorRows.appendChild(clone);
    }
  }

  if (exhibitorRows && addExhibitorBtn) {
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
          fillExhibitorRow(row, null);
        }
      }
    });

    addExhibitorBtn.addEventListener("click", () => {
      const first = exhibitorRows.querySelector("[data-exhibitor-row]");
      if (!first) return;
      const clone = first.cloneNode(true);
      fillExhibitorRow(clone, null);
      exhibitorRows.appendChild(clone);
    });
  }

  // ── Next / Publish tab-wizard logic ──────────────────────────────────────
  function updateNextPublishBtn() {
    if (!epNextBtn || !epTabButtons.length) return;
    const activeIdx = epTabButtons.findIndex((btn) =>
      btn.classList.contains("active"),
    );
    if (activeIdx === LAST_TAB_INDEX) {
      epNextBtn.textContent = isEditing ? "Save changes" : "Publish";
      epNextBtn.dataset.action = "publish";
    } else {
      epNextBtn.textContent = "Next";
      epNextBtn.dataset.action = "next";
    }
  }

  if (epModal && epNextBtn && epTabButtons.length) {
    epModal.addEventListener("shown.bs.tab", updateNextPublishBtn);
    epModal.addEventListener("show.bs.modal", () => {
      setTimeout(updateNextPublishBtn, 0);
    });

    epNextBtn.addEventListener("click", () => {
      const action = epNextBtn.dataset.action || "next";
      if (action === "publish") {
        if (form) form.requestSubmit();
      } else {
        const activeIdx = epTabButtons.findIndex((btn) =>
          btn.classList.contains("active"),
        );
        const nextBtn = epTabButtons[activeIdx + 1];
        if (nextBtn) nextBtn.click();
      }
    });

    updateNextPublishBtn();
  }

  // ── rich text editor ─────────────────────────────────────────────────────
  const initQuill = () => {
    if (!form || !editorHost || !hiddenInput || typeof Quill === "undefined")
      return;
    quill = new Quill(editorHost, {
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

  // ── create / edit mode switching ─────────────────────────────────────────
  const TEXT_FIELDS = [
    "title",
    "slug",
    "short_description",
    "category",
    "subcategory",
    "tourism_campaign_type",
    "organizer",
    "contact_person",
    "theme",
    "tagline",
    "start_date",
    "end_date",
    "venue_name",
    "venue_type",
    "barangay",
    "map_pin",
    "virtual_event_link",
    "overview",
    "historical_background",
    "significance",
    "cultural_importance",
    "tourism_impact",
    "expected_visitors",
    "economic_contribution",
    "tourism_office",
    "pavilion_booth_no",
    "pavilion_products",
    "featured_destination",
    "representative",
  ];

  function setFieldValue(name, value) {
    if (!form) return;
    const el = form.elements.namedItem(name);
    if (!el || el.tagName === undefined) return;
    const str = value === null || value === undefined ? "" : String(value);
    if (el.tagName === "SELECT") {
      // <select>.value silently rejects a value with no matching <option>
      // (leaving nothing selected), which would drop the field entirely on
      // submit. Match case-insensitively first (form casing can drift from
      // stored casing), and if a stored value truly isn't one of the
      // options (legacy/imported data), add it as an extra option instead
      // of losing it.
      const options = Array.from(el.options);
      const match = options.find(
        (opt) => opt.value.toLowerCase() === str.toLowerCase(),
      );
      if (match) {
        el.value = match.value;
      } else if (str) {
        const opt = document.createElement("option");
        opt.value = str;
        opt.textContent = str;
        el.appendChild(opt);
        el.value = str;
      } else {
        el.selectedIndex = 0;
      }
      return;
    }
    el.value = str;
  }

  function resetEventForm() {
    if (!form) return;
    form.reset();
    form.action = form.dataset.createAction || form.action;
    if (hiddenInput) hiddenInput.value = "";
    if (quill) {
      try {
        quill.setText("");
      } catch (_) {
        /* ignore */
      }
    }
    populateExhibitors([]);
    populateCurrentFiles(null);
    renderGalleryPreviewFromUrls([]);
    if (modalLabel) modalLabel.textContent = "Post promotion / event";
    if (modalSubtitle)
      modalSubtitle.textContent =
        "Complete all sections. Gallery supports multiple images.";
    if (epTabButtons.length) epTabButtons[0].click();
    isEditing = false;
    updateNextPublishBtn();
  }

  function populateEventForm(event) {
    if (!form) return;
    TEXT_FIELDS.forEach((name) => setFieldValue(name, event[name]));
    setFieldValue(
      "event_status",
      event.event_status === "draft" ? "draft" : "published",
    );
    setFieldValue("visibility", event.visibility === "private" ? "private" : "public");
    if (form.elements.namedItem("lgu_id") && event.lgu_id !== undefined) {
      setFieldValue("lgu_id", event.lgu_id === null ? "" : String(event.lgu_id));
    }
    if (hiddenInput) hiddenInput.value = event.full_description || "";
    if (quill) {
      try {
        quill.root.innerHTML = event.full_description || "";
      } catch (_) {
        /* ignore */
      }
    }
    populateExhibitors(event.exhibitors);
    populateCurrentFiles(event);
    renderGalleryPreviewFromUrls(event.gallery_images);
  }

  document.querySelectorAll("[data-edit-event]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!form) return;
      const id = btn.dataset.eventId;
      const dataUrl = (form.dataset.editDataTemplate || "").replace(
        /\/0\/edit-data$/,
        `/${id}/edit-data`,
      );
      const updateUrl = (form.dataset.updateActionTemplate || "").replace(
        /\/0\/update$/,
        `/${id}/update`,
      );
      let event;
      try {
        const res = await fetch(dataUrl, { headers: { Accept: "application/json" } });
        const body = await res.json();
        if (!res.ok) {
          alert(body.error || "Could not load event for editing.");
          return;
        }
        event = body;
      } catch (_) {
        alert("Could not load event for editing.");
        return;
      }
      resetEventForm();
      populateEventForm(event);
      form.action = updateUrl;
      isEditing = true;
      if (modalLabel) modalLabel.textContent = "Edit promotion / event";
      if (modalSubtitle)
        modalSubtitle.textContent = "Update the sections you need, then save.";
      updateNextPublishBtn();
      new bootstrap.Modal(document.getElementById("eventModal")).show();
    });
  });

  const newEventBtn = document.getElementById("newEventBtn");
  if (newEventBtn) {
    newEventBtn.addEventListener("click", resetEventForm);
  }
})();
