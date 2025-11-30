/* ImageHost Frontend Script */

const API_KEY_STORAGE = 'imagehost_api_key';
const USERNAME_STORAGE = 'imagehost_username';

let filesToUpload = [];
let currentModalImage = null;

// --- DOM ELEMENTS ---
// Views
const guestView = document.getElementById('guest-view');
const dashboardView = document.getElementById('dashboard-view');

// Auth UI
const authBtn = document.getElementById('auth-btn');
const currentUserDisplay = document.getElementById('current-user-display');
const authModal = document.getElementById('auth-modal');
const authCloseBtn = document.getElementById('auth-close-btn');
const usernameInput = document.getElementById('username-input');
const passwordInput = document.getElementById('password-input');
const authSubmitBtn = document.getElementById('auth-submit-btn');
const authToggleLink = document.getElementById('auth-toggle-link');
const guestDropzone = document.getElementById('guest-dropzone');

// App UI
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const progressBar = document.querySelector('.progress');
const progressBarFill = document.getElementById('progress-bar');
const uploadResults = document.getElementById('upload-results');
const previewContainer = document.getElementById('file-previews');
const galleryGrid = document.getElementById('gallery-grid');
const refreshBtn = document.getElementById('refresh-gallery');

// Image Modal
const imgModal = document.getElementById('image-modal');
const imgModalClose = document.getElementById('modal-close-btn');
const imgModalImg = document.getElementById('modal-img');
const imgModalLink = document.getElementById('modal-link-input');
const imgModalCopy = document.getElementById('modal-copy-btn');
const imgModalDelete = document.getElementById('modal-delete-btn');

// State
let isRegisterMode = false;

// --- INIT ---
document.addEventListener('DOMContentLoaded', () => {
  checkLoginState();
  setupEventListeners();
});

function checkLoginState() {
  const key = localStorage.getItem(API_KEY_STORAGE);
  const username = localStorage.getItem(USERNAME_STORAGE);

  if (key && username) {
    // Logged In
    guestView.classList.add('hidden');
    dashboardView.classList.remove('hidden');
    
    authBtn.textContent = 'Logout';
    authBtn.classList.remove('primary');
    authBtn.classList.add('ghost');
    
    currentUserDisplay.textContent = `Hi, ${username}`;
    
    // Load data
    refreshGallery();
  } else {
    // Logged Out
    guestView.classList.remove('hidden');
    dashboardView.classList.add('hidden');
    
    authBtn.textContent = 'Login';
    authBtn.classList.remove('ghost');
    authBtn.classList.add('primary');
    
    currentUserDisplay.textContent = '';
  }
}

function setupEventListeners() {
  // Auth Modal Toggling
  authBtn.addEventListener('click', () => {
    if (localStorage.getItem(API_KEY_STORAGE)) {
      // Logic for Logout
      if(confirm('Log out?')) {
        localStorage.removeItem(API_KEY_STORAGE);
        localStorage.removeItem(USERNAME_STORAGE);
        checkLoginState();
      }
    } else {
      // Logic for Login
      openAuthModal(false);
    }
  });

  authCloseBtn.addEventListener('click', () => authModal.classList.remove('open'));
  
  // Guest Interaction
  guestDropzone.addEventListener('click', () => openAuthModal(false));
  guestDropzone.addEventListener('dragover', (e) => { e.preventDefault(); });
  guestDropzone.addEventListener('drop', (e) => { 
    e.preventDefault(); 
    openAuthModal(false); 
  });

  // Auth Toggle (Login vs Register)
  authToggleLink.addEventListener('click', (e) => {
    e.preventDefault();
    isRegisterMode = !isRegisterMode;
    updateAuthModalUI();
  });

  // Auth Submit
  authSubmitBtn.addEventListener('click', handleAuthSubmit);

  // File Handling
  setupFileHandling();
  
  uploadBtn.addEventListener('click', handleUpload);
  refreshBtn.addEventListener('click', refreshGallery);

  // Image Modal
  imgModalClose.addEventListener('click', () => imgModal.classList.remove('open'));
  imgModal.addEventListener('click', (e) => {
    if(e.target === imgModal) imgModal.classList.remove('open');
  });
  
  imgModalCopy.addEventListener('click', () => {
    imgModalLink.select();
    document.execCommand('copy');
    imgModalCopy.textContent = 'Copied!';
    setTimeout(() => imgModalCopy.textContent = 'Copy', 2000);
  });
  
  imgModalDelete.addEventListener('click', handleDeleteImage);
}

// --- AUTH LOGIC ---

function openAuthModal(register = false) {
  isRegisterMode = register;
  updateAuthModalUI();
  authModal.classList.add('open');
  usernameInput.focus();
}

function updateAuthModalUI() {
  const title = document.getElementById('auth-title');
  const toggleText = document.getElementById('auth-toggle-text');
  
  if (isRegisterMode) {
    title.textContent = 'Create Account';
    authSubmitBtn.textContent = 'Register';
    toggleText.textContent = 'Already have an account?';
    authToggleLink.textContent = 'Login';
  } else {
    title.textContent = 'Welcome Back';
    authSubmitBtn.textContent = 'Login';
    toggleText.textContent = 'Need an account?';
    authToggleLink.textContent = 'Register';
  }
}

async function handleAuthSubmit() {
  const username = usernameInput.value.trim();
  const password = passwordInput.value.trim();
  
  if (!username || !password) return alert('Please fill in fields');

  const endpoint = isRegisterMode ? '/api/v1/register' : '/api/v1/login';
  
  try {
    authSubmitBtn.disabled = true;
    authSubmitBtn.textContent = 'Processing...';

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.error?.message || 'Error');

    const payload = data.data ? data.data : data;
    
    localStorage.setItem(API_KEY_STORAGE, payload.api_key);
    localStorage.setItem(USERNAME_STORAGE, payload.username);
    
    authModal.classList.remove('open');
    usernameInput.value = '';
    passwordInput.value = '';
    
    checkLoginState();
    
  } catch (err) {
    alert(err.message);
  } finally {
    authSubmitBtn.disabled = false;
    updateAuthModalUI();
  }
}

// --- UPLOAD LOGIC ---

function setupFileHandling() {
  function handleFiles(list) {
    filesToUpload = [...filesToUpload, ...Array.from(list)];
    renderPreviews();
    fileInput.value = '';
  }

  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => handleFiles(fileInput.files));
  
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    handleFiles(e.dataTransfer.files);
  });
}

function renderPreviews() {
  previewContainer.innerHTML = '';
  filesToUpload.forEach((file, idx) => {
    const div = document.createElement('div');
    div.className = 'preview-item';
    
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    
    const btn = document.createElement('button');
    btn.className = 'preview-remove';
    btn.innerHTML = '&times;';
    btn.onclick = (e) => {
      e.stopPropagation();
      filesToUpload.splice(idx, 1);
      renderPreviews();
    };
    
    div.appendChild(img);
    div.appendChild(btn);
    previewContainer.appendChild(div);
  });
  
  if (filesToUpload.length > 0) {
    uploadBtn.disabled = false;
    uploadBtn.textContent = `Upload ${filesToUpload.length} Files`;
  } else {
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Upload Images';
  }
}

async function handleUpload() {
  if (filesToUpload.length === 0) return;
  
  uploadBtn.disabled = true;
  progressBar.classList.add('active');
  uploadResults.classList.add('hidden');
  uploadResults.innerHTML = '';
  
  let completed = 0;
  
  for (const file of filesToUpload) {
    try {
      // 1. Get Presigned URL
      const reqRes = await apiFetch('/api/v1/upload/request', {
        method: 'POST',
        body: { filename: file.name, mime_type: file.type }
      });
      
      // 2. Upload to S3
      await fetch(reqRes.presigned_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type }
      });
      
      // 3. Finalize
      const finalRes = await apiFetch('/api/v1/upload/complete', {
        method: 'POST',
        body: { 
          iid: reqRes.iid, 
          key: reqRes.key, 
          filename: file.name, 
          mime_type: file.type 
        }
      });
      
      addResultLink(finalRes.url, file);
      completed++;
      progressBarFill.style.width = `${(completed / filesToUpload.length) * 100}%`;
      
    } catch (err) {
      console.error(err);
    }
  }
  
  filesToUpload = [];
  renderPreviews();
  uploadResults.classList.remove('hidden');
  
  setTimeout(() => {
    progressBar.classList.remove('active');
    progressBarFill.style.width = '0';
    refreshGallery();
  }, 1000);
}

function addResultLink(url, file) {
  const fullUrl = url.startsWith('http') ? url : window.location.origin + url;
  const div = document.createElement('div');
  div.className = 'link-item';
  
  const img = document.createElement('img');
  img.className = 'link-thumb';
  img.src = URL.createObjectURL(file);
  
  const input = document.createElement('input');
  input.className = 'link-url';
  input.readOnly = true;
  input.value = fullUrl;
  
  const btn = document.createElement('button');
  btn.className = 'button ghost';
  btn.textContent = 'Copy';
  btn.onclick = () => {
    input.select();
    document.execCommand('copy');
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 1500);
  };
  
  div.appendChild(img);
  div.appendChild(input);
  div.appendChild(btn);
  uploadResults.prepend(div);
}

// --- GALLERY ---

async function refreshGallery() {
  galleryGrid.innerHTML = '<div class="grid-item-placeholder">Loading...</div>';
  try {
    const data = await apiFetch('/api/v1/me/images');
    galleryGrid.innerHTML = '';
    
    if (!data.items || data.items.length === 0) {
      galleryGrid.innerHTML = '<div class="grid-item-placeholder">No images yet. Upload some!</div>';
      return;
    }
    
    data.items.forEach(item => {
      const div = document.createElement('div');
      div.className = 'grid-item';
      
      const img = document.createElement('img');
      const url = item.url.startsWith('http') ? item.url : window.location.origin + item.url;
      img.src = url;
      img.loading = 'lazy';
      
      div.onclick = () => openImageModal(item, url);
      
      div.appendChild(img);
      galleryGrid.appendChild(div);
    });
    
  } catch (err) {
    galleryGrid.innerHTML = '<div class="grid-item-placeholder">Failed to load gallery.</div>';
  }
}

function openImageModal(item, url) {
  currentModalImage = item;
  imgModalImg.src = url;
  imgModalLink.value = url;
  imgModal.classList.add('open');
}

async function handleDeleteImage() {
  if (!currentModalImage || !confirm('Delete this image?')) return;
  
  try {
    await apiFetch(`/api/v1/image/${currentModalImage.id}`, { method: 'DELETE' });
    imgModal.classList.remove('open');
    refreshGallery();
  } catch (err) {
    alert('Failed to delete');
  }
}

// --- API HELPER ---

async function apiFetch(endpoint, opts = {}) {
  const key = localStorage.getItem(API_KEY_STORAGE);
  if (!key) throw new Error('Not Logged In');
  
  opts.headers = { 
    ...opts.headers,
    'X-API-Key': key,
    'Content-Type': 'application/json'
  };
  
  if (opts.body && typeof opts.body !== 'string') {
    opts.body = JSON.stringify(opts.body);
  }
  
  const res = await fetch(endpoint, opts);
  const json = await res.json();
  
  if (res.status === 401) {
    localStorage.removeItem(API_KEY_STORAGE);
    localStorage.removeItem(USERNAME_STORAGE);
    checkLoginState();
    throw new Error('Session Expired');
  }
  
  if (!res.ok) throw new Error(json.error?.message || 'Error');
  
  return json.data ? json.data : json;
}