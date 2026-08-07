/**
 * Smart Community Platform - Issue List, Report Form, Vote, Comments
 */

/* ================================================================
   ISSUE LIST MANAGER
   ================================================================ */
const IssueList = {
  currentFilters: {},
  currentPage: 1,
  totalPages: 1,
  _container: null,
  _paginationContainer: null,
  _countEl: null,

  init(containerId, paginationId, countId) {
    this._container = document.getElementById(containerId || "issue-list");
    this._paginationContainer = document.getElementById(paginationId || "issue-pagination");
    this._countEl = document.getElementById(countId || "issue-count");
  },

  async load(filters, page) {
    filters = filters || this.currentFilters;
    page = page || 1;
    this.currentFilters = filters;
    this.currentPage = page;

    if (this._container) Loader.showSkeleton(this._container, 6);

    try {
      const data = await IssuesAPI.getList({ ...filters, page, page_size: CONFIG.DEFAULT_PAGE_SIZE });
      this.totalPages = data.total_pages || 1;
      if (this._countEl) {
        this._countEl.textContent = "Showing " + data.issues.length + " of " + data.total + " issues";
      }
      this.renderList(data.issues);
      this.renderPaginationUI();
    } catch (err) {
      if (this._container) {
        this._container.innerHTML =
          '<div class="empty-state"><i class="bi bi-exclamation-triangle"></i><h5>Failed to load issues</h5>' +
          '<p>' + escapeHtml(err.message) + '</p>' +
          '<button class="btn btn-primary" onclick="IssueList.load()">Try Again</button></div>';
      }
    }
  },

  renderList(issues) {
    if (!this._container) return;
    if (!issues || issues.length === 0) {
      this._container.innerHTML =
        '<div class="empty-state"><i class="bi bi-inbox"></i><h5>No issues found</h5>' +
        '<p>Try adjusting your filters or report a new issue.</p></div>';
      return;
    }
    this._container.innerHTML = '<div class="issue-grid">' + issues.map(renderIssueCard).join("") + '</div>';
  },

  renderPaginationUI() {
    if (!this._paginationContainer) return;
    this._paginationContainer.innerHTML = "";
    if (this.totalPages <= 1) return;
    const pagEl = renderPagination(this.currentPage, this.totalPages, (p) => {
      this.load(this.currentFilters, p);
      window.scrollTo({ top: this._container.offsetTop - 80, behavior: "smooth" });
    });
    this._paginationContainer.appendChild(pagEl);
  },

  applyFilter(key, value) {
    if (value === "" || value === null || value === undefined) {
      delete this.currentFilters[key];
    } else {
      this.currentFilters[key] = value;
    }
    this.load(this.currentFilters, 1);
  },

  clearAllFilters() {
    this.currentFilters = {};
    this.load({}, 1);
    const selects = document.querySelectorAll(".filter-select");
    selects.forEach((s) => { s.value = ""; });
    const searchInput = document.getElementById("filter-search");
    if (searchInput) searchInput.value = "";
  }
};

/* ================================================================
   REPORT ISSUE FORM (3-step)
   ================================================================ */
const ReportForm = {
  imageFile: null,
  imagePreviewUrl: null,
  currentStep: 1,
  totalSteps: 3,

  init() {
    const form = document.getElementById("report-form");
    if (!form) return;

    form.addEventListener("submit", (e) => this.submit(e));

    // Initialize ImageUploader component
    if (typeof ImageUploader !== "undefined") {
      ImageUploader.init("drop-zone", "image-input", "image-preview-container");
    }

    const pwdFields = form.querySelectorAll("[data-step-btn]");
    pwdFields.forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const dir = btn.dataset.stepBtn;
        if (dir === "next") this.nextStep();
        else if (dir === "prev") this.prevStep();
      });
    });
  },

  open() {
    if (!Auth.requireLogin()) return;
    this.currentStep = 1;
    if (typeof ImageUploader !== "undefined") {
      ImageUploader.removeImage();
    }
    this._updateStepUI();
    const form = document.getElementById("report-form");
    if (form) form.reset();
    const coordsEl = document.getElementById("selected-coords");
    if (coordsEl) coordsEl.textContent = "";

    if (typeof MapManager !== "undefined" && MapManager.map) {
      MapManager.enableLocationPicker();
    }

    const modal = document.getElementById("report-modal");
    if (modal) {
      const bsModal = bootstrap.Modal.getOrCreateInstance(modal);
      bsModal.show();
    }
  },

  close() {
    if (typeof MapManager !== "undefined") MapManager.disableLocationPicker();
    const modal = document.getElementById("report-modal");
    if (modal) {
      const bsModal = bootstrap.Modal.getInstance(modal);
      if (bsModal) bsModal.hide();
    }
  },

  nextStep() {
    if (!this._validateStep(this.currentStep)) return;
    if (this.currentStep < this.totalSteps) {
      this.currentStep++;
      this._updateStepUI();
    }
  },

  prevStep() {
    if (this.currentStep > 1) {
      this.currentStep--;
      this._updateStepUI();
    }
  },

  _updateStepUI() {
    for (let i = 1; i <= this.totalSteps; i++) {
      const panel = document.getElementById("step-" + i);
      if (panel) panel.style.display = i === this.currentStep ? "block" : "none";
      const dot = document.getElementById("step-dot-" + i);
      if (dot) {
        dot.classList.remove("active", "completed");
        if (i < this.currentStep) dot.classList.add("completed");
        else if (i === this.currentStep) dot.classList.add("active");
      }
    }
  },

  _validateStep(step) {
    if (step === 1) {
      const title = document.getElementById("issue-title");
      const desc = document.getElementById("issue-description");
      if (!title || title.value.trim().length < 5) { Toast.warning("Title must be at least 5 characters."); if (title) title.focus(); return false; }
      if (!desc || desc.value.trim().length < 20) { Toast.warning("Description must be at least 20 characters."); if (desc) desc.focus(); return false; }
      return true;
    }
    if (step === 2) {
      const lat = document.getElementById("issue-lat");
      const lng = document.getElementById("issue-lng");
      if (!lat || !lat.value || !lng || !lng.value) {
        Toast.warning("Please click the map to select a location.");
        return false;
      }
      return true;
    }
    return true;
  },

  async submit(e) {
    e.preventDefault();
    if (!this._validateStep(1) || !this._validateStep(2)) return;

    const btn = document.getElementById("report-submit-btn");
    const restore = Loader.setButtonLoading(btn, "Submitting...");

    try {
      let imageUrl = null;
      let tempId = null;

      if (typeof ImageUploader !== "undefined") {
        const imgInfo = ImageUploader.getImageInfo();
        if (imgInfo.file) {
          Toast.info("Uploading image...");
          const uploadResp = await IssuesAPI.uploadImage(imgInfo.file);
          imageUrl = uploadResp.url;
          tempId = uploadResp.temp_id;
        }
      }

      const payload = {
        title: document.getElementById("issue-title").value.trim(),
        description: document.getElementById("issue-description").value.trim(),
        category: document.getElementById("issue-category").value || "other",
        priority: document.getElementById("issue-priority") ? document.getElementById("issue-priority").value || "medium" : "medium",
        location_lat: parseFloat(document.getElementById("issue-lat").value),
        location_lng: parseFloat(document.getElementById("issue-lng").value),
        location_address: document.getElementById("issue-address") ? document.getElementById("issue-address").value : null,
        location_city: document.getElementById("issue-city") ? document.getElementById("issue-city").value : null,
        location_area: document.getElementById("issue-area") ? document.getElementById("issue-area").value : null,
        location_landmark: document.getElementById("issue-landmark") ? document.getElementById("issue-landmark").value : null,
        image_url: imageUrl,
        temp_id: tempId
      };

      const result = await IssuesAPI.create(payload);
      this.close();
      Toast.success("Issue reported successfully!");

      if (typeof MapManager !== "undefined" && MapManager.map) {
        await MapManager.loadMarkers();
      }
      if (typeof IssueList !== "undefined" && IssueList._container) {
        IssueList.load();
      }
    } catch (err) {
      Toast.error(err.message || "Failed to report issue.");
    } finally {
      restore();
    }
  }
};

/* ================================================================
   VOTE HANDLER
   ================================================================ */
async function handleVote(issueUuid, button) {
  if (!Auth.requireLogin()) return;
  button.disabled = true;

  try {
    const data = await IssuesAPI.vote(issueUuid);
    const countEl = button.querySelector(".vote-count") || button.nextElementSibling;
    if (countEl && data.vote_count !== undefined) countEl.textContent = data.vote_count;
    button.classList.add("voted");
    const icon = button.querySelector("i");
    if (icon) { icon.className = "bi bi-hand-thumbs-up-fill"; }
    Toast.success("Vote added!");
  } catch (err) {
    if (err.status === 200 || (err.message && err.message.toLowerCase().includes("removed"))) {
      button.classList.remove("voted");
      const icon = button.querySelector("i");
      if (icon) { icon.className = "bi bi-hand-thumbs-up"; }
      Toast.info("Vote removed.");
    } else {
      Toast.error(err.message || "Vote failed.");
    }
  } finally {
    button.disabled = false;
  }
}

/* ================================================================
   COMMENT MANAGER
   ================================================================ */
const CommentManager = {
  renderComments(comments, container, issueUuid) {
    if (!container) return;
    if (!comments || comments.length === 0) {
      container.innerHTML = '<p class="text-muted text-center py-3">No comments yet. Be the first to comment!</p>';
      return;
    }
    const pinned = comments.filter((c) => c.is_pinned);
    const normal = comments.filter((c) => !c.is_pinned);
    container.innerHTML = pinned.map((c) => this.renderComment(c, issueUuid, true)).join("") + normal.map((c) => this.renderComment(c, issueUuid, false)).join("");
  },

  renderComment(comment, issueUuid, isPinned) {
    const isOwn = Auth.user && comment.user && Auth.user.uuid === comment.user.uuid;
    const isAuth = comment.comment_type === "authority_update";
    const roleClass = isAuth ? "comment-authority" : "";
    const pinnedBadge = isPinned ? '<span class="badge bg-warning text-dark ms-2"><i class="bi bi-pin-fill"></i> Pinned</span>' : "";

    let actions = "";
    if (isOwn) {
      actions += '<button class="btn btn-sm btn-link text-danger p-0 ms-3" onclick="CommentManager.deleteComment(\'' + issueUuid + "','" + comment.uuid + '\', this)"><i class="bi bi-trash"></i></button>';
    }

    const replies = (comment.replies || []).map((r) => this.renderComment(r, issueUuid, false)).join("");

    return (
      '<div class="comment-item ' + roleClass + '" data-comment-uuid="' + comment.uuid + '">' +
      '<div class="comment-header">' +
      renderUserAvatar(comment.user, 32) +
      '<div class="comment-meta">' +
      '<strong>' + escapeHtml(comment.user ? comment.user.name : "Unknown") + '</strong>' +
      (isAuth ? ' <span class="badge bg-primary">Authority</span>' : '') +
      pinnedBadge +
      '<span class="text-muted small ms-2">' + renderTimeAgo(comment.created_at) + '</span>' +
      (comment.is_edited ? '<span class="text-muted small ms-1">(edited)</span>' : '') +
      '</div>' +
      '<div class="comment-actions">' + actions + '</div>' +
      '</div>' +
      '<div class="comment-body">' + escapeHtml(comment.content) + '</div>' +
      (replies ? '<div class="comment-replies">' + replies + '</div>' : '') +
      '</div>'
    );
  },

  async submitComment(issueUuid, content, parentId) {
    if (!content || content.trim().length < 2) { Toast.warning("Comment must be at least 2 characters."); return null; }
    try {
      const data = await IssuesAPI.addComment(issueUuid, {
        content: content.trim(),
        parent_id: parentId || null
      });
      Toast.success("Comment added!");
      return data;
    } catch (err) {
      Toast.error(err.message || "Failed to add comment.");
      return null;
    }
  },

  async deleteComment(issueUuid, commentUuid, btn) {
    const confirmed = await Modal.confirm("Delete Comment", "Are you sure you want to delete this comment?", "Delete", true);
    if (!confirmed) return;
    try {
      await IssuesAPI.deleteComment(issueUuid, commentUuid);
      const el = btn.closest(".comment-item");
      if (el) { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }
      Toast.success("Comment deleted.");
    } catch (err) {
      Toast.error(err.message || "Failed to delete comment.");
    }
  }
};

/* ================================================================
   AI ASSISTANT HELPER
   ================================================================ */
const AIAssistant = {
  debounceTimer: null,

  async classifyText(title, description) {
    if (!title || title.length < 3 || !description || description.length < 5) return null;
    try {
      const res = await API.post("/api/ai/classify-text", { title, description, use_ml: true });
      return res;
    } catch (e) {
      console.warn("AI text classification preview failed:", e);
      return null;
    }
  },

  async analyzeImageFile(file) {
    if (!file) return null;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await API.postForm("/api/ai/analyze-image", formData);
      return res;
    } catch (e) {
      console.warn("AI image analysis preview failed:", e);
      return null;
    }
  },

  attachLiveSuggestions(modalEl) {
    if (!modalEl) return;
    const titleInput = modalEl.querySelector('#issue-title, [name="title"]');
    const descInput = modalEl.querySelector('#issue-desc, [name="description"]');
    const catSelect = modalEl.querySelector('#issue-category, [name="category"]');
    const aiCard = modalEl.querySelector('#ai-suggestion-box');

    if (!titleInput || !descInput || !catSelect) return;

    const runSuggestion = () => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(async () => {
        const title = titleInput.value.trim();
        const desc = descInput.value.trim();
        if (title.length >= 4 && desc.length >= 8) {
          if (aiCard) {
            aiCard.innerHTML = '<span class="ai-thinking"><i class="bi bi-arrow-repeat"></i> AI Analyzing issue report...</span>';
            aiCard.style.display = 'block';
          }
          const res = await this.classifyText(title, desc);
          if (res && res.category && aiCard) {
            const confidencePct = Math.round((res.category_confidence || 0.8) * 100);
            aiCard.innerHTML = `
              <div class="ai-suggestion-header">
                <span class="ai-badge"><i class="bi bi-robot"></i> Smart AI Suggestion</span>
                <span>Category: <strong>${res.category}</strong> (${confidencePct}% confidence)</span>
              </div>
              <div style="font-size: 0.8rem; color: #555;">Urgency level predicted as <strong>${res.urgency}</strong>. Auto-tagging applied upon submission.</div>
            `;
            if (!catSelect.value || catSelect.value === 'other') {
              catSelect.value = res.category;
            }
          }
        }
      }, 600);
    };

    titleInput.addEventListener('input', runSuggestion);
    descInput.addEventListener('input', runSuggestion);
  }
};
