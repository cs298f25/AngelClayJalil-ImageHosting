/*
 * ImageHost Frontend Script
 * Connects the HTML UI to the Flask backend (S3 private).
 */

const API_KEY_STORAGE = 'imagehost_api_key';
let filesToUpload = []; // This is our "Staging Area"
let currentModalImage = null;

// Helper to make API calls
async function apiFetch(endpoint, options = {}, attempt = 0) {
  const requestOptions = { ...options };
  const headers = {
    'X-API-Key': localStorage.getItem(API_KEY_STORAGE) || '',
    ...(requestOptions.headers || {}),
  };
  const isFormData = requestOptions.body instanceof FormData;
  if (!isFormData) {
    headers['Content-Type'] = 'application/json';
  }
  requestOptions.headers = headers;
  if (!isFormData && requestOptions.body) {
    requestOptions.body = JSON.stringify(requestOptions.body);
  }

  const response = await fetch(endpoint, requestOptions);

  if (response.status === 401 && attempt === 0) {
    console.warn('API key rejected, getting a new one...');
    localStorage.removeItem(API_KEY_STORAGE);
    await initApiKey({ force: true });
    return apiFetch(endpoint, options, attempt + 1);
  }

  if (!response.ok) {
    let errorMessage;
    try {
      const err = await response.json();
      errorMessage = err.error?.message || 'API request failed';
    } catch (e) {
      errorMessage = `Server error: ${response.status} ${response.statusText}`;
    }
    throw new Error(errorMessage);
  }
  
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  return json.data ? json.data : json; 
}

// 1. Get or create a dev API key on load
async function initApiKey({ force = false } = {}) {
  let key = localStorage.getItem(API_KEY_STORAGE);
  if (key && !force) {
    console.log('Using existing API key');
    return key;
  }

  if (force && key) {
    localStorage.removeItem(API_KEY_STORAGE);
  }

  console.log('No API key found, issuing a new one...');
  try {
    const data = await apiFetch('/api/v1/dev/issue-key', {
      method: 'POST',
      body: {},
    });
    if (!data.api_key) {
      throw new Error("Server didn't return an API key.");
    }
    localStorage.setItem(API_KEY_STORAGE, data.api_key);
    console.log('New dev key issued and stored');
    return data.api_key;
  } catch (error) {
    console.error('Failed to issue dev key:', error);
  }
}

// 2. Handle file selection & Preview Generation
function setupFileHandling(dropzone, fileInput, uploadBtn, previewContainer) {
  
  function handleNewFiles(fileList) {
    const incoming = Array.from(fileList);
    filesToUpload = [...filesToUpload, ...incoming];
    renderPreviews(previewContainer, uploadBtn);
    fileInput.value = ''; 
  }

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    handleNewFiles(e.dataTransfer.files);
  });

  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => handleNewFiles(fileInput.files));
}

// 3. Render the staging thumbnails
function renderPreviews(container, uploadBtn) {
  container.innerHTML = ''; 

  if (filesToUpload.length > 0) {
    uploadBtn.disabled = false;
    uploadBtn.textContent = `Upload ${filesToUpload.length} Image(s)`;
  } else {
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Upload Images';
  }

  filesToUpload.forEach((file, index) => {
    const item = document.createElement('div');
    item.className = 'preview-item';

    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    img.alt = file.name;
    img.onload = () => URL.revokeObjectURL(img.src);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'preview-remove';
    removeBtn.innerHTML = '&times;';
    removeBtn.title = 'Remove image';
    
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation(); 
      filesToUpload.splice(index, 1); 
      renderPreviews(container, uploadBtn); 
    });

    item.appendChild(img);
    item.appendChild(removeBtn);
    container.appendChild(item);
  });
}

function resolveUrl(url) {
  if (!url) return '';
  return url.startsWith('http') ? url : `${window.location.origin}${url}`;
}

// 4. Handle the S3 upload process
async function handleUpload(uploadBtn, progressBarEl, resultsEl, linksListEl, previewContainer) {
  if (filesToUpload.length === 0) return;

  uploadBtn.disabled = true;
  progressBarEl.parentElement.classList.add('active');
  resultsEl.hidden = true;
  linksListEl.innerHTML = '';
  
  const totalFiles = filesToUpload.length;
  let filesUploaded = 0;

  for (const file of filesToUpload) {
    try {
      const { presigned_url, iid, key } = await apiFetch('/api/v1/upload/request', {
        method: 'POST',
        body: { filename: file.name, mime_type: file.type },
      });
      const s3Response = await fetch(presigned_url, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': file.type,
        },
      });
      if (!s3Response.ok) {
        throw new Error('S3 upload failed');
      }
      const { url } = await apiFetch('/api/v1/upload/complete', {
        method: 'POST',
        body: { iid, key, filename: file.name, mime_type: file.type },
      });
      
      // --- UPDATE: Pass the file object so we can show a thumbnail ---
      addLinkToResults(url, linksListEl, file);
      
      filesUploaded++;
      progressBarEl.style.width = `${(filesUploaded / totalFiles) * 100}%`;
    } catch (error) {
      console.error('Failed to upload file:', file.name, error);
    }
  }

  uploadBtn.disabled = false;
  uploadBtn.textContent = 'Upload Images';
  resultsEl.hidden = false;
  
  filesToUpload = [];
  renderPreviews(previewContainer, uploadBtn);
  
  console.log('All uploads complete');
  setTimeout(() => {
    document.getElementById('refresh-gallery').click();
    progressBarEl.parentElement.classList.remove('active');
    progressBarEl.style.width = '0%';
  }, 1000);
}

// 5. Handle refreshing the gallery
async function refreshGallery(gridEl) {
  gridEl.innerHTML = '<p class="grid-item-placeholder">Loading...</p>';
  try {
    const { items } = await apiFetch('/api/v1/me/images');
    gridEl.innerHTML = '';
    if (!items || items.length === 0) {
      gridEl.innerHTML = '<p class="grid-item-placeholder">No images uploaded yet.</p>';
      return;
    }
    items.forEach((item) => {
      const el = document.createElement('div');
      el.className = 'grid-item';
      const viewUrl = resolveUrl(item.url);
      el.innerHTML = `<img src="${viewUrl}" alt="${item.filename}" loading="lazy">`;
      el.addEventListener('click', () => showImageModal(item));
      gridEl.appendChild(el);
    });
  } catch (error) {
    console.error('Failed to refresh gallery:', error);
    gridEl.innerHTML = '<p class="grid-item-placeholder" style="color: red;">Failed to load images.</p>';
  }
}

// 6. UI Helpers (UPDATED FOR THUMBNAILS)
function addLinkToResults(url, listEl, file) {
  const item = document.createElement('li');
  item.className = 'link-item';
  const fullUrl = resolveUrl(url);
  
  // --- Create Thumbnail ---
  const img = document.createElement('img');
  img.className = 'link-thumb';
  img.src = URL.createObjectURL(file); // Use the local file for instant preview
  img.alt = file.name;
  
  // --- Create Input & Button container ---
  // We use HTML string for the inputs, but append the image via JS
  const controlsDiv = document.createElement('div');
  controlsDiv.style.flex = '1';
  controlsDiv.style.display = 'flex';
  controlsDiv.style.gap = '0.5rem';
  
  controlsDiv.innerHTML = `
    <input class="link-url" type="text" value="${fullUrl}" readonly style="width: 100%">
    <button class="button copy-btn">Copy</button>
  `;

  // Append elements
  item.appendChild(img);
  item.appendChild(controlsDiv);
  
  // Add Copy Logic
  controlsDiv.querySelector('.copy-btn').addEventListener('click', (e) => {
    const button = e.target;
    const input = controlsDiv.querySelector('.link-url');
    button.textContent = 'Copied!';
    input.focus();
    input.select();
    try {
      document.execCommand('copy');
    } catch (err) {
      console.error('Fallback: Oops, unable to copy', err);
    }
    setTimeout(() => {
      button.textContent = 'Copy';
    }, 2000);
  });
  
  listEl.prepend(item);
}

// 7. Function to show the image modal
function showImageModal(item) {
  const modal = document.getElementById('image-modal');
  const modalImg = document.getElementById('modal-img');
  const modalLinkInput = document.getElementById('modal-link-input');
  
  currentModalImage = item; 
  
  modalImg.src = resolveUrl(item.url);
  modalImg.alt = item.filename;
  modalLinkInput.value = resolveUrl(item.url);
  
  modal.style.display = 'flex';
}

// 8. Delete Image Logic
async function handleDeleteImage() {
  if (!currentModalImage) return; 
  
  const iid = currentModalImage.id;
  const filename = currentModalImage.filename;

  if (!confirm(`Are you sure you want to delete this image: ${filename}?`)) {
    return;
  }
  
  try {
    await apiFetch(`/api/v1/image/${iid}`, {
      method: 'DELETE',
    });
    closeModal(); 
    document.getElementById('refresh-gallery').click(); 
  } catch (error) {
    console.error('Failed to delete image:', error);
    alert(`Error: ${error.message}`);
  }
}

function closeModal() {
  const modal = document.getElementById('image-modal');
  modal.style.display = 'none';
  currentModalImage = null; 
}

// --- Main execution ---
document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const uploadBtn = document.getElementById('upload-btn');
  const progressBar = document.getElementById('progress-bar');
  const uploadResults = document.getElementById('upload-results');
  const linksList = document.getElementById('links-list');
  const galleryGrid = document.getElementById('gallery-grid');
  const refreshBtn = document.getElementById('refresh-gallery');
  const modal = document.getElementById('image-modal');
  const modalCloseBtn = document.getElementById('modal-close-btn');
  const modalCopyBtn = document.getElementById('modal-copy-btn');
  const modalLinkInput = document.getElementById('modal-link-input');
  const modalDeleteBtn = document.getElementById('modal-delete-btn'); 
  const previewContainer = document.getElementById('file-previews');

  if (!dropzone) return;

  setupFileHandling(dropzone, fileInput, uploadBtn, previewContainer);
  
  uploadBtn.addEventListener('click', () =>
    handleUpload(uploadBtn, progressBar, uploadResults, linksList, previewContainer)
  );
  
  refreshBtn.addEventListener('click', () => refreshGallery(galleryGrid));

  modalCloseBtn.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  modalCopyBtn.addEventListener('click', (e) => {
    e.target.textContent = 'Copied!';
    modalLinkInput.focus();
    modalLinkInput.select();
    try { document.execCommand('copy'); } catch (err) {}
    setTimeout(() => { e.target.textContent = 'Copy'; }, 2000);
  });
  
  modalDeleteBtn.addEventListener('click', handleDeleteImage);

  initApiKey().then(() => {
    refreshGallery(galleryGrid);
  });
});