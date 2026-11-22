"use strict";

const app = {
  documents: [],
  current: null,
  dirty: false,
  saving: false,
  saveTimer: null,
  lightbox: { items: [], index: 0 },
};

const $ = (id) => document.getElementById(id);

/* ---------------------------------------------------------------- load */

async function loadState() {
  setSaveState("Loading…");
  const response = await fetch("/api/state");
  if (!response.ok) {
    setSaveState("Could not load state — is the server running?");
    return;
  }
  const data = await response.json();
  app.documents = data.documents;
  renderSidebar();
  const wanted = decodeURIComponent(location.hash.slice(1));
  const first = app.documents.find((doc) => doc.slug === wanted)
    || app.documents.find((doc) => !doc.reviewed)
    || app.documents[0];
  if (first) select(first.slug, { skipSave: true });
  else {
    $("empty").hidden = false;
    $("doc").hidden = true;
  }
}

/* ------------------------------------------------------------- sidebar */

function renderSidebar() {
  const reviewed = app.documents.filter((doc) => doc.reviewed).length;
  const total = app.documents.length;
  $("progress-bar").style.width = total ? `${(reviewed / total) * 100}%` : "0";
  $("progress-text").textContent = `${reviewed} of ${total} reviewed`;

  const list = $("doc-list");
  list.replaceChildren();
  for (const doc of app.documents) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "doc-item";
    button.classList.toggle("reviewed", Boolean(doc.reviewed));
    button.classList.toggle("has-errors", Boolean(doc.errors && doc.errors.length));
    button.setAttribute("aria-current", String(app.current && app.current.slug === doc.slug));
    button.title = doc.slug;
    button.addEventListener("click", () => select(doc.slug));

    const dot = document.createElement("span");
    dot.className = "dot";
    const name = document.createElement("span");
    name.className = "doc-name";
    name.textContent = doc.slug;
    const count = document.createElement("span");
    count.className = "doc-count";
    count.textContent = doc.errors && doc.errors.length ? "!" : String(doc.chapters.length);

    button.append(dot, name, count);
    list.append(button);
  }
}

/* ------------------------------------------------------------- select */

async function select(slug, options = {}) {
  if (app.current && app.current.slug === slug) return;
  if (app.dirty && !options.skipSave) {
    const saved = await save({ silent: true });
    if (!saved) return;
  }
  app.current = app.documents.find((doc) => doc.slug === slug) || null;
  app.dirty = false;
  if (!app.current) return;
  location.hash = slug;
  $("empty").hidden = true;
  $("doc").hidden = false;
  renderDoc();
}

/* ----------------------------------------------------------- rendering */

function renderDoc() {
  const doc = app.current;
  if (!doc) return;

  $("doc-title").textContent = doc.title || doc.slug;
  const toc = doc.toc_pdf_pages && doc.toc_pdf_pages.length
    ? `contents pp. ${doc.toc_pdf_pages.join(", ")}`
    : "contents pages not recorded";
  const pages = doc.page_count ? `PDF pages 1–${doc.page_count}` : "page count unknown";
  $("doc-meta").textContent = `${doc.slug} · ${doc.chapters.length} chapters · ${toc} · ${pages}`;

  $("status-chip").textContent = doc.reviewed ? "Reviewed" : "Draft";
  $("status-chip").className = `chip ${doc.reviewed ? "reviewed" : "draft"}`;
  $("approve").textContent = doc.reviewed ? "Save reviewed file" : "Approve & mark reviewed";
  $("approve").dataset.shortcut = "⌘↵";

  renderBanner();
  renderToc();
  renderChapters();
  $("notes").value = doc.notes || "";
  $("sha").textContent = `PDF sha256 ${doc.pdf_sha256.slice(0, 12)}…`;
  setSaveState(doc.reviewed ? "Saved and reviewed" : "Draft — not scored until approved");
  $("approve").disabled = false;
}

function renderBanner() {
  const doc = app.current;
  const banner = $("banner");
  banner.replaceChildren();
  const errors = doc.errors || [];
  const warnings = doc.warnings || [];

  if (errors.length) {
    banner.hidden = false;
    banner.className = "banner error";
    banner.append(strong("This file is invalid and cannot be saved"));
    banner.append(listOf(errors));
    return;
  }
  if (warnings.length) {
    banner.hidden = false;
    banner.className = "banner warning";
    banner.append(strong(`${warnings.length} consistency warning${warnings.length === 1 ? "" : "s"}`));
    banner.append(listOf(warnings));
    const hint = document.createElement("p");
    hint.className = "hint";
    hint.textContent =
      "Clear a warning by correcting the file or explaining it in Notes (the check looks for "
      + "\"offset\", \"same page\", or \"artwork\"/\"text layer\").";
    banner.append(hint);
    return;
  }
  banner.hidden = false;
  banner.className = "banner ok";
  banner.append(strong("No consistency warnings"));
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent = doc.reviewed
    ? "This document is scored by the report."
    : "Check the contents pages and every chapter start, then approve.";
  banner.append(hint);
}

function strong(text) {
  const node = document.createElement("strong");
  node.textContent = text;
  return node;
}

function listOf(items) {
  const list = document.createElement("ul");
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = item;
    list.append(li);
  }
  return list;
}

function renderToc() {
  const doc = app.current;
  const wrap = $("toc-images");
  wrap.replaceChildren();
  const tocPages = doc.toc_pdf_pages || [];
  if (!doc.images.toc.length) {
    const missing = document.createElement("p");
    missing.className = "hint";
    missing.textContent = "No contents-page image — is the source PDF available?";
    wrap.append(missing);
    return;
  }
  doc.images.toc.forEach((url, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.title = "Click to enlarge";
    const image = document.createElement("img");
    image.src = url;
    image.alt = `Contents page ${tocPages[index] ?? index + 1}`;
    image.loading = "lazy";
    const tag = document.createElement("span");
    tag.className = "page-tag";
    tag.textContent = `p. ${tocPages[index] ?? "?"}`;
    button.append(image, tag);
    button.addEventListener("click", () => openLightbox(imageItems(), index));
    wrap.append(button);
  });
}

function renderChapters() {
  const doc = app.current;
  const list = $("chapter-list");
  list.replaceChildren();
  $("chapter-count").textContent = `${doc.chapters.length}`;

  doc.chapters.forEach((chapter, index) => {
    list.append(chapterRow(chapter, index));
  });

  if (!doc.chapters.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "No chapters yet — add the first one.";
    list.append(empty);
  }
}

function chapterRow(chapter, index) {
  const documents = app.current;
  const page = Number(chapter.pdf_page);
  const url = documents.images.pages[String(page)];

  const row = document.createElement("div");
  row.className = "chapter";

  const thumb = document.createElement("button");
  thumb.type = "button";
  thumb.className = "thumb";
  thumb.title = "Open the start page";
  if (url) {
    const image = document.createElement("img");
    image.src = url;
    image.alt = `Start of ${chapter.title || "chapter"}`;
    image.loading = "lazy";
    thumb.append(image);
    const tag = document.createElement("span");
    tag.className = "page-tag";
    tag.textContent = String(page);
    thumb.append(tag);
    thumb.addEventListener("click", () => {
      const items = imageItems();
      const found = items.findIndex((item) => item.url === url);
      openLightbox(items, found >= 0 ? found : 0);
    });
  } else {
    const none = document.createElement("span");
    none.className = "none";
    none.textContent = page ? "no image" : "no page";
    thumb.append(none);
    thumb.disabled = true;
  }

  const fields = document.createElement("div");
  fields.className = "fields";

  const title = document.createElement("input");
  title.className = "title-input";
  title.value = chapter.title || "";
  title.placeholder = "Chapter title as printed in the contents";
  title.setAttribute("aria-label", `Chapter ${index + 1} title`);
  title.addEventListener("input", () => {
    chapter.title = title.value;
    markDirty();
  });

  const pages = document.createElement("div");
  pages.className = "pages";

  const printedLabel = document.createElement("label");
  printedLabel.textContent = "printed";
  const printed = document.createElement("input");
  printed.value = chapter.printed_page ?? "";
  printed.placeholder = "—";
  printed.setAttribute("aria-label", `Chapter ${index + 1} printed page`);
  printed.addEventListener("input", () => {
    chapter.printed_page = printed.value.trim() || null;
    markDirty();
  });
  printedLabel.append(printed);

  const pdfLabel = document.createElement("label");
  pdfLabel.textContent = "PDF";
  const pdf = document.createElement("input");
  pdf.type = "number";
  pdf.min = "1";
  pdf.value = Number.isFinite(page) && page > 0 ? String(page) : "";
  pdf.addEventListener("input", () => {
    chapter.pdf_page = pdf.value === "" ? null : Number(pdf.value);
    const next = documents.images.pages[String(chapter.pdf_page)];
    if (next && thumb.querySelector("img")) thumb.querySelector("img").src = next;
    markDirty();
  });
  pdfLabel.append(pdf);

  pages.append(printedLabel, pdfLabel);

  const note = document.createElement("p");
  note.className = "hint";
  note.textContent = `Chapter ${index + 1} of ${documents.chapters.length}`;

  fields.append(title, pages);
  if (!url && page) {
    const warn = document.createElement("p");
    warn.className = "hint";
    warn.textContent = "No rendered image for this page yet — save to render it.";
    fields.append(warn);
  }

  const actions = document.createElement("div");
  actions.className = "row-actions";
  actions.append(
    rowButton("↑", "Move up", () => moveChapter(index, -1), index === 0),
    rowButton("↓", "Move down", () => moveChapter(index, 1), index === documents.chapters.length - 1),
    rowButton("×", "Remove chapter", () => removeChapter(index), false, "remove"),
  );

  row.append(thumb, fields, actions);
  return row;
}

function rowButton(label, title, handler, disabled, extraClass) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.title = title;
  button.disabled = Boolean(disabled);
  if (extraClass) button.classList.add(extraClass);
  button.addEventListener("click", handler);
  return button;
}

function imageItems() {
  const doc = app.current;
  const items = [];
  doc.images.toc.forEach((url, index) => {
    items.push({ url, caption: `Contents — PDF page ${doc.toc_pdf_pages[index] ?? "?"}` });
  });
  doc.chapters.forEach((chapter, index) => {
    const url = doc.images.pages[String(Number(chapter.pdf_page))];
    if (url) {
      items.push({
        url,
        caption: `${chapter.title || `Chapter ${index + 1}`} — PDF page ${chapter.pdf_page}`,
      });
    }
  });
  return items;
}

/* -------------------------------------------------------------- edits */

function moveChapter(index, delta) {
  const chapters = app.current.chapters;
  const target = index + delta;
  if (target < 0 || target >= chapters.length) return;
  [chapters[index], chapters[target]] = [chapters[target], chapters[index]];
  markDirty();
  renderChapters();
}

function removeChapter(index) {
  app.current.chapters.splice(index, 1);
  markDirty();
  renderChapters();
}

function addChapter() {
  const chapters = app.current.chapters;
  const last = chapters.length ? Number(chapters[chapters.length - 1].pdf_page) : 0;
  chapters.push({
    title: "",
    printed_page: null,
    pdf_page: Number.isFinite(last) && last > 0 ? last + 1 : 1,
  });
  markDirty();
  renderChapters();
  const inputs = $("chapter-list").querySelectorAll(".title-input");
  if (inputs.length) inputs[inputs.length - 1].focus();
}

function markDirty() {
  app.dirty = true;
  setSaveState("Unsaved changes…");
  scheduleSave();
}

function scheduleSave() {
  clearTimeout(app.saveTimer);
  app.saveTimer = setTimeout(() => save({ silent: true }), 1400);
}

/* --------------------------------------------------------------- save */

function payloadChapters() {
  return app.current.chapters.map((chapter) => ({
    title: String(chapter.title ?? ""),
    printed_page: chapter.printed_page ?? null,
    pdf_page: Number(chapter.pdf_page),
  }));
}

function clientError() {
  const bad = app.current.chapters.some((chapter) => {
    const page = Number(chapter.pdf_page);
    return !Number.isInteger(page) || page < 1;
  });
  if (bad) return "Every chapter needs a whole PDF page number of 1 or more.";
  if (!app.current.chapters.length) return "A gold file needs at least one chapter.";
  return null;
}

async function save(options = {}) {
  const { silent = false, reviewed = app.current.reviewed } = options;
  const problem = clientError();
  if (problem) {
    if (!silent) showTransientError(problem);
    return false;
  }
  if (reviewed && !reviewerName()) {
    if (!silent) showTransientError("Add your name under “Reviewed by” before approving.");
    $("reviewer").focus();
    return false;
  }
  if (app.saving) return false;
  app.saving = true;
  setSaveState("Saving…");
  try {
    const response = await fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        slug: app.current.slug,
        chapters: payloadChapters(),
        notes: $("notes").value,
        reviewed,
        annotator: reviewerName(),
      }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      showTransientError((result.errors || ["save failed"]).join(" · "));
      return false;
    }
    const document_ = result.document;
    app.current = document_;
    const index = app.documents.findIndex((doc) => doc.slug === document_.slug);
    if (index >= 0) app.documents[index] = document_;
    app.dirty = false;
    renderSidebar();
    $("status-chip").textContent = document_.reviewed ? "Reviewed" : "Draft";
    $("status-chip").className = `chip ${document_.reviewed ? "reviewed" : "draft"}`;
    $("approve").textContent = document_.reviewed
      ? "Save reviewed file"
      : "Approve & mark reviewed";
    renderBanner();
    setSaveState(document_.reviewed ? "Saved and reviewed" : "Draft saved");
    if (!silent) renderDoc();
    return true;
  } finally {
    app.saving = false;
  }
}

async function approve() {
  const doc = app.current;
  if (!doc) return;
  if (doc.warnings && doc.warnings.length) {
    const proceed = window.confirm(
      `${doc.warnings.length} consistency warning${doc.warnings.length === 1 ? "" : "s"} remain. `
      + "Mark this document reviewed anyway?",
    );
    if (!proceed) return;
  }
  const saved = await save({ reviewed: true });
  if (!saved) return;
  const next = app.documents.find((item) => !item.reviewed);
  if (next) select(next.slug, { skipSave: true });
}

/* ------------------------------------------------------------ display */

function reviewerName() {
  return $("reviewer").value.trim();
}

function setSaveState(text) {
  $("save-state").textContent = text;
}

function showTransientError(message) {
  const banner = $("banner");
  banner.hidden = false;
  banner.className = "banner error";
  banner.replaceChildren(strong("Not saved"), (() => {
    const p = document.createElement("p");
    p.textContent = message;
    return p;
  })());
}

/* ------------------------------------------------------------ lightbox */

function openLightbox(items, index) {
  if (!items.length) return;
  app.lightbox.items = items;
  app.lightbox.index = Math.max(0, Math.min(index, items.length - 1));
  updateLightbox();
  $("lightbox").hidden = false;
  $("lb-close").focus();
}

function updateLightbox() {
  const { items, index } = app.lightbox;
  const item = items[index];
  if (!item) return;
  $("lb-image").src = item.url;
  $("lb-caption").textContent = `${item.caption} — ${index + 1} of ${items.length}`;
  $("lb-prev").disabled = index <= 0;
  $("lb-next").disabled = index >= items.length - 1;
}

function closeLightbox() {
  $("lightbox").hidden = true;
}

/* --------------------------------------------------------------- boot */

function boot() {
  const stored = localStorage.getItem("gold-reviewer") || "";
  $("reviewer").value = stored;
  $("reviewer").addEventListener("input", () => {
    localStorage.setItem("gold-reviewer", reviewerName());
  });

  $("notes").addEventListener("input", markDirty);
  $("save").addEventListener("click", () => save({ silent: false }));
  $("approve").addEventListener("click", approve);
  $("add-chapter").addEventListener("click", addChapter);
  $("lb-close").addEventListener("click", closeLightbox);
  $("lb-prev").addEventListener("click", () => {
    app.lightbox.index -= 1;
    updateLightbox();
  });
  $("lb-next").addEventListener("click", () => {
    app.lightbox.index += 1;
    updateLightbox();
  });
  $("lightbox").addEventListener("click", (event) => {
    if (event.target === $("lightbox")) closeLightbox();
  });

  document.addEventListener("keydown", (event) => {
    if (!$("lightbox").hidden) {
      if (event.key === "Escape") closeLightbox();
      if (event.key === "ArrowLeft" && app.lightbox.index > 0) {
        app.lightbox.index -= 1;
        updateLightbox();
      }
      if (event.key === "ArrowRight" && app.lightbox.index < app.lightbox.items.length - 1) {
        app.lightbox.index += 1;
        updateLightbox();
      }
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      save({ silent: false });
    }
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      approve();
    }
  });

  window.addEventListener("beforeunload", (event) => {
    if (app.dirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  loadState();
}

boot();
