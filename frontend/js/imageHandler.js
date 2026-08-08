/**
 * Smart Community Platform - Image Handling System
 * Client-side validation, drag-and-drop upload, preview, gallery lightbox,
 * progressive image loading, and Canvas client-side compression.
 */

const ImageUploader = {
  currentFile: null,
  currentTempId: null,
  currentPreviewUrl: null,
  dropZoneEl: null,
  fileInputEl: null,
  previewContainerEl: null,

  init(dropZoneId = "drop-zone", inputId = "image-input", previewId = "image-preview-container") {
    this.dropZoneEl = document.getElementById(dropZoneId);
    this.fileInputEl = document.getElementById(inputId);
    this.previewContainerEl = document.getElementById(previewId);

    if (!this.dropZoneEl || !this.fileInputEl) return this;

    this.setupDragAndDrop(this.dropZoneEl);
    this.setupClickToBrowse(this.dropZoneEl, this.fileInputEl);

    return this;
  },

  setupDragAndDrop(dropZone) {
    ["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      }, false);
    });

    ["dragenter", "dragover"].forEach(eventName => {
      dropZone.addEventListener(eventName, () => dropZone.classList.add("dragover"), false);
    });

    ["dragleave", "drop"].forEach(eventName => {
      dropZone.addEventListener(eventName, () => dropZone.classList.remove("dragover"), false);
    });

    dropZone.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files && files.length > 0) {
        this.handleFileSelection(files[0]);
      }
    }, false);
  },

  setupClickToBrowse(dropZone, fileInput) {
    dropZone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        this.handleFileSelection(e.target.files[0]);
      }
    });
  },

  async handleFileSelection(file) {
    if (!file) return;

    // Step 1: Validate file type
    const allowedTypes = (CONFIG.ALLOWED_IMAGE_TYPES || ["image/jpeg", "image/png", "image/webp"]).map(t => t.toLowerCase());
    const fileExt = file.name.split('.').pop().toLowerCase();
    const mimeType = file.type.toLowerCase();

    const isAllowedExt = ["jpg", "jpeg", "png", "webp"].includes(fileExt);
    const isAllowedMime = allowedTypes.includes(mimeType) || mimeType.startsWith("image/");

    if (!isAllowedExt || !isAllowedMime) {
      this.showError("Please select a JPG, PNG, or WEBP image.");
      return;
    }

    // Step 2: Validate & Compress if necessary
    const maxSize = (CONFIG.MAX_IMAGE_SIZE_MB || 5) * 1024 * 1024;
    let finalFile = file;

    if (file.size > maxSize) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
      Toast.info(`Image is ${sizeMB}MB. Compressing client-side...`);
      finalFile = await compressImageClientSide(file, 2);

      if (finalFile.size > maxSize) {
        this.showError(`Image is ${sizeMB}MB. Maximum allowed is ${CONFIG.MAX_IMAGE_SIZE_MB || 5}MB.`);
        return;
      }
    }

    this.currentFile = finalFile;
    this.currentTempId = null;

    // Step 3: Instant Preview via FileReader
    const reader = new FileReader();
    reader.onload = (e) => {
      this.currentPreviewUrl = e.target.result;
      this.showPreview(e.target.result, finalFile);
    };
    reader.readAsDataURL(finalFile);
  },

  showPreview(dataUrl, file) {
    if (this.dropZoneEl) this.dropZoneEl.style.display = "none";

    const previewImg = document.getElementById("preview-img");
    if (previewImg) previewImg.src = dataUrl;

    if (this.previewContainerEl) {
      this.previewContainerEl.style.display = "block";
      this.previewContainerEl.classList.add("has-file");
    }

    const fileInfoEl = document.getElementById("file-info");
    const fileNameEl = document.getElementById("file-name");
    const fileSizeEl = document.getElementById("file-size");

    if (fileInfoEl && fileNameEl && fileSizeEl) {
      fileNameEl.textContent = file.name;
      fileSizeEl.textContent = this.formatFileSize(file.size);
      fileInfoEl.style.display = "flex";
    }

    const errorEl = document.getElementById("upload-error");
    if (errorEl) errorEl.style.display = "none";
  },

  removeImage() {
    this.currentFile = null;
    this.currentTempId = null;
    this.currentPreviewUrl = null;

    if (this.dropZoneEl) {
      this.dropZoneEl.style.display = "block";
      this.dropZoneEl.classList.remove("error", "has-file");
    }
    if (this.previewContainerEl) {
      this.previewContainerEl.style.display = "none";
    }

    const fileInfoEl = document.getElementById("file-info");
    if (fileInfoEl) fileInfoEl.style.display = "none";

    if (this.fileInputEl) this.fileInputEl.value = "";
  },

  showError(message) {
    const errorEl = document.getElementById("upload-error");
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.style.display = "block";
      setTimeout(() => { errorEl.style.display = "none"; }, 4000);
    }
    if (this.dropZoneEl) {
      this.dropZoneEl.classList.add("error");
      setTimeout(() => { this.dropZoneEl.classList.remove("error"); }, 600);
    }
    Toast.error(message);
  },

  getImageInfo() {
    return {
      file: this.currentFile,
      tempId: this.currentTempId,
      hasImage: !!this.currentFile || !!this.currentTempId
    };
  },

  formatFileSize(bytes) {
    if (bytes < 1024) return bytes + " bytes";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }
};


const ImageGallery = {
  containerEl: null,
  images: [],
  currentIndex: 0,
  options: {},

  init(containerId, images = [], options = {}) {
    this.containerEl = document.getElementById(containerId);
    this.images = Array.isArray(images) ? images.filter(Boolean) : (images ? [images] : []);
    this.options = options;
    this.currentIndex = 0;

    if (!this.containerEl) return;
    this.render();
  },

  render() {
    if (!this.containerEl) return;

    if (this.images.length === 0) {
      this.containerEl.innerHTML = `
        <div class="gallery-placeholder">
          <i class="bi bi-card-image" style="font-size:3rem"></i>
          <p class="mt-2 mb-0">No photos uploaded for this issue</p>
        </div>
      `;
      if (this.options.editable) {
        this.containerEl.innerHTML += `
          <div class="mt-2 text-center">
            <button class="btn btn-outline-primary btn-sm" onclick="ImageGallery.triggerAddImage()">
              <i class="bi bi-plus-lg me-1"></i>Add Photo
            </button>
            <input type="file" id="gallery-add-input" accept=".jpg,.jpeg,.png,.webp" style="display:none" onchange="ImageGallery.handleUploadAdd(this)">
          </div>
        `;
      }
      return;
    }

    const rawUrl = this.images[this.currentIndex] || this.images[0];
    const currentUrl = (typeof formatImageUrl === "function") ? formatImageUrl(rawUrl) : rawUrl;
    const editable = !!this.options.editable;

    let thumbsHtml = this.images.map((url, idx) => {
      const formattedThumbUrl = (typeof formatImageUrl === "function") ? formatImageUrl(url) : url;
      return `
      <div class="position-relative d-inline-block">
        <img src="${formattedThumbUrl}" class="gallery-thumb ${idx === this.currentIndex ? 'active' : ''}" 
             alt="Thumbnail ${idx + 1}" onclick="ImageGallery.showImage(${idx})"
             onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1584467735871-8e85353a8413?auto=format&fit=crop&w=400&q=80'">
        ${editable ? `<button class="btn btn-danger btn-sm gallery-thumb-del" onclick="ImageGallery.removeImageButton('${url}', event)"><i class="bi bi-x"></i></button>` : ''}
      </div>
    `;
    }).join("");

    if (editable && this.images.length < (CONFIG.MAX_IMAGES_PER_ISSUE || 5)) {
      thumbsHtml += `
        <div class="gallery-thumb-add" onclick="ImageGallery.triggerAddImage()">
          <i class="bi bi-plus-lg"></i>
          <input type="file" id="gallery-add-input" accept=".jpg,.jpeg,.png,.webp" style="display:none" onchange="ImageGallery.handleUploadAdd(this)">
        </div>
      `;
    }

    this.containerEl.innerHTML = `
      <div class="issue-gallery">
        <div class="position-relative">
          <img src="${currentUrl}" alt="Issue photo" class="gallery-primary" id="gallery-primary-img" 
               onclick="ImageGallery.openFullscreen('${currentUrl}')"
               onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1584467735871-8e85353a8413?auto=format&fit=crop&w=800&q=80'">
          <span class="gallery-counter">${this.currentIndex + 1} / ${this.images.length}</span>
        </div>
        <div class="gallery-thumbnails mt-2">
          ${thumbsHtml}
        </div>
      </div>
    `;

    const primaryImg = document.getElementById("gallery-primary-img");
    if (primaryImg) {
      loadImageProgressively(primaryImg, currentUrl);
    }
  },

  showImage(index) {
    if (index < 0 || index >= this.images.length) return;
    this.currentIndex = index;
    this.render();
  },

  openFullscreen(imageUrl) {
    const overlay = document.createElement("div");
    overlay.className = "fullscreen-overlay";
    overlay.innerHTML = `
      <span class="fullscreen-close" onclick="this.parentElement.remove()"><i class="bi bi-x-lg"></i></span>
      <img src="${imageUrl}" alt="Fullscreen image">
      <div class="fullscreen-counter">${this.currentIndex + 1} / ${this.images.length}</div>
    `;

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) overlay.remove();
    });

    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        overlay.remove();
        document.removeEventListener("keydown", handleKeyDown);
      }
    };
    document.addEventListener("keydown", handleKeyDown);

    document.body.appendChild(overlay);
  },

  triggerAddImage() {
    const input = document.getElementById("gallery-add-input");
    if (input) input.click();
  },

  async handleUploadAdd(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const issueUuid = this.options.issueUuid;
    if (!issueUuid) return;

    const restore = Loader.setButtonLoading(input.parentElement, "Uploading...");
    try {
      const result = await IssuesAPI.addImage(issueUuid, file);
      Toast.success("Photo added successfully!");
      if (result.image_urls) {
        this.images = result.image_urls;
        this.currentIndex = this.images.length - 1;
        this.render();
      } else {
        setTimeout(() => location.reload(), 800);
      }
    } catch (err) {
      Toast.error(err.message || "Failed to upload image.");
    } finally {
      if (restore) restore();
    }
  },

  async removeImageButton(imageUrl, event) {
    if (event) event.stopPropagation();

    const confirmed = await Modal.confirm("Remove Image", "Are you sure you want to remove this photo from the issue?", "Remove", true);
    if (!confirmed) return;

    const issueUuid = this.options.issueUuid;
    if (!issueUuid) return;

    try {
      const response = await API.delete(`/upload/issue/${issueUuid}/image`, { image_url: imageUrl });
      Toast.success("Image removed.");
      this.images = this.images.filter(u => u !== imageUrl);
      if (this.currentIndex >= this.images.length) {
        this.currentIndex = Math.max(0, this.images.length - 1);
      }
      this.render();
    } catch (err) {
      Toast.error(err.message || "Failed to remove image.");
    }
  }
};


function loadImageProgressively(imgElement, fullUrl) {
  if (!imgElement || !fullUrl) return;

  const formattedUrl = (typeof formatImageUrl === "function") ? formatImageUrl(fullUrl) : fullUrl;

  if (formattedUrl.includes("cloudinary.com")) {
    const parts = formattedUrl.split("/upload/");
    if (parts.length === 2) {
      const blurUrl = `${parts[0]}/upload/w_20,e_blur:2000/${parts[1]}`;
      imgElement.src = blurUrl;
      imgElement.classList.add("loading");
    }
  }

  const highResImg = new Image();
  highResImg.src = formattedUrl;
  highResImg.onload = () => {
    imgElement.src = formattedUrl;
    imgElement.classList.remove("loading");
    imgElement.classList.add("loaded");
  };
  highResImg.onerror = () => {
    imgElement.classList.remove("loading");
    imgElement.src = formattedUrl;
  };
}


function lazyLoadImages() {
  if (!("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        const dataSrc = img.getAttribute("data-src");
        if (dataSrc) {
          loadImageProgressively(img, dataSrc);
          img.removeAttribute("data-src");
        }
        obs.unobserve(img);
      }
    });
  });

  document.querySelectorAll(".lazy-image[data-src]").forEach(img => observer.observe(img));
}


async function compressImageClientSide(file, maxSizeMB = 2) {
  if (!file || !file.type.startsWith("image/")) return file;
  if (file.size <= maxSizeMB * 1024 * 1024) return file;

  return new Promise((resolve) => {
    const img = new Image();
    const reader = new FileReader();

    reader.onload = (e) => {
      img.src = e.target.result;
    };

    img.onload = () => {
      const maxW = 1920;
      const maxH = 1080;
      let width = img.width;
      let height = img.height;

      if (width > maxW || height > maxH) {
        if (width / height > maxW / maxH) {
          height = Math.round((height * maxW) / width);
          width = maxW;
        } else {
          width = Math.round((width * maxH) / height);
          height = maxH;
        }
      }

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, width, height);

      canvas.toBlob(
        (blob) => {
          if (!blob) {
            resolve(file);
            return;
          }
          const compressedFile = new File([blob], file.name, {
            type: "image/jpeg",
            lastModified: Date.now()
          });
          resolve(compressedFile);
        },
        "image/jpeg",
        0.85
      );
    };

    img.onerror = () => resolve(file);
    reader.readAsDataURL(file);
  });
}
