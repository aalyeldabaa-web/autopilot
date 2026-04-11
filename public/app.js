// Autopilot - Social Media Automation System
// GitHub Repo Configuration
const GITHUB_CONFIG = {
  owner: 'aalyeldabaa-web',
  repo: 'autopilot',
  branch: 'main',
  postsFile: 'posts.json'
};

let posts = [];
let currentEditId = null;

// Initialize app
async function init() {
  await loadPostsFromGitHub();
  updateStats();
  renderPosts();
  setupEventListeners();
  
  const now = new Date();
  now.setHours(now.getHours() + 1);
  const dateStr = now.toISOString().split('T')[0];
  const timeStr = now.toTimeString().slice(0, 5);
  
  document.getElementById('schedule-date').value = dateStr;
  document.getElementById('schedule-time').value = timeStr;
}

function setupEventListeners() {
  document.getElementById('post-content').addEventListener('input', updateCharCounter);
  document.getElementById('edit-content').addEventListener('input', updateEditCharCounter);
  setInterval(saveDraftsLocally, 30000);
}

function updateCharCounter() {
  const content = document.getElementById('post-content').value;
  const counter = document.getElementById('char-counter');
  const length = content.length;
  
  counter.textContent = `${length.toLocaleString()} characters`;
  
  if (length > 3000) {
    counter.classList.add('error');
    counter.classList.remove('warning');
  } else if (length > 2000) {
    counter.classList.add('warning');
    counter.classList.remove('error');
  } else {
    counter.classList.remove('warning', 'error');
  }
}

function updateEditCharCounter() {
  const content = document.getElementById('edit-content').value;
  const counter = document.getElementById('edit-char-counter');
  const length = content.length;
  counter.textContent = `${length.toLocaleString()} characters`;
}

// Base64 encoding/decoding (CSP-safe)
function base64Encode(str) {
  return btoa(unescape(encodeURIComponent(str)));
}

function base64Decode(str) {
  return decodeURIComponent(escape(atob(str)));
}

async function loadPostsFromGitHub() {
  try {
    const token = localStorage.getItem('github_token');
    if (!token) {
      console.warn('No GitHub token found - using local storage only');
      loadPostsLocally();
      return;
    }

    const url = `https://api.github.com/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/${GITHUB_CONFIG.postsFile}`;
    
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github.v3+json'
      }
    });

    if (response.status === 404) {
      await createPostsFile(token);
      posts = [];
      return;
    }

    if (!response.ok) {
      throw new Error(`GitHub API error: ${response.status}`);
    }

    const data = await response.json();
    const content = base64Decode(data.content.replace(/\n/g, ''));
    posts = JSON.parse(content);
    
    localStorage.setItem('posts_sha', data.sha);
    saveDraftsLocally();
    
  } catch (error) {
    console.error('Failed to load from GitHub:', error);
    loadPostsLocally();
  }
}

async function createPostsFile(token) {
  const url = `https://api.github.com/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/${GITHUB_CONFIG.postsFile}`;
  
  const initialData = JSON.stringify([], null, 2);
  const content = base64Encode(initialData);
  
  const response = await fetch(url, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/vnd.github.v3+json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      message: 'Initialize Autopilot posts database',
      content: content,
      branch: GITHUB_CONFIG.branch
    })
  });
  
  if (!response.ok) {
    throw new Error('Failed to create posts file');
  }
  
  const data = await response.json();
  localStorage.setItem('posts_sha', data.content.sha);
}

function loadPostsLocally() {
  const saved = localStorage.getItem('autopilot_posts');
  if (saved) {
    posts = JSON.parse(saved);
  } else {
    posts = [];
  }
}

function saveDraftsLocally() {
  localStorage.setItem('autopilot_posts', JSON.stringify(posts));
}

async function savePostsToGitHub() {
  try {
    const token = localStorage.getItem('github_token');
    if (!token) {
      console.warn('No GitHub token - saving locally only');
      saveDraftsLocally();
      return;
    }

    const sha = localStorage.getItem('posts_sha');
    const url = `https://api.github.com/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/${GITHUB_CONFIG.postsFile}`;
    
    const content = base64Encode(JSON.stringify(posts, null, 2));
    
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: `Update posts - ${new Date().toISOString()}`,
        content: content,
        sha: sha,
        branch: GITHUB_CONFIG.branch
      })
    });

    if (!response.ok) {
      throw new Error(`GitHub API error: ${response.status}`);
    }

    const data = await response.json();
    localStorage.setItem('posts_sha', data.content.sha);
    saveDraftsLocally();
    
    return true;
  } catch (error) {
    console.error('Failed to save to GitHub:', error);
    saveDraftsLocally();
    return false;
  }
}

function updateStats() {
  const now = new Date();
  
  const queued = posts.filter(p => !p.published).length;
  const published = posts.filter(p => p.published).length;
  const total = posts.length;
  
  const next24h = posts.filter(p => {
    if (p.published) return false;
    const postDate = new Date(p.scheduledTime);
    const diff = postDate - now;
    return diff > 0 && diff < 24 * 60 * 60 * 1000;
  }).length;
  
  document.getElementById('stat-queued').textContent = queued;
  document.getElementById('stat-next24').textContent = next24h;
  document.getElementById('stat-published').textContent = published;
  document.getElementById('stat-total').textContent = total;
}

function renderPosts() {
  const container = document.getElementById('post-list');
  const emptyState = document.getElementById('empty-state');
  
  if (posts.length === 0) {
    container.style.display = 'none';
    emptyState.style.display = 'block';
    return;
  }
  
  container.style.display = 'flex';
  emptyState.style.display = 'none';
  
  const sortedPosts = [...posts].sort((a, b) => {
    if (a.published && !b.published) return 1;
    if (!a.published && b.published) return -1;
    return new Date(a.scheduledTime) - new Date(b.scheduledTime);
  });
  
  container.innerHTML = sortedPosts.map(post => {
    const scheduledDate = new Date(post.scheduledTime);
    const formattedDate = scheduledDate.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
    
    const platformBadges = post.platforms.map(platform => {
      const className = platform.includes('linkedin') ? 'linkedin' : 'facebook';
      const label = {
        'linkedin_personal': 'LinkedIn Personal',
        'linkedin_company': 'Ajax LinkedIn',
        'facebook_personal': 'Facebook Personal',
        'facebook_page': 'Ajax Facebook'
      }[platform];
      
      return `<span class="post-platform ${className}">${label}</span>`;
    }).join('');
    
    const publishedClass = post.published ? 'published' : '';
    
    return `
      <div class="post-card ${publishedClass}">
        <div class="post-header">
          <div class="post-meta">
            <div class="post-platforms">${platformBadges}</div>
            <div class="post-datetime">${formattedDate}</div>
          </div>
          <div class="post-actions">
            <button class="icon-btn" onclick="editPost('${post.id}')" title="Edit">✏️</button>
          </div>
        </div>
        <div class="post-content">${escapeHtml(post.content)}</div>
      </div>
    `;
  }).join('');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function openScheduleModal() {
  document.getElementById('schedule-modal').classList.add('active');
  document.getElementById('post-content').focus();
}

function closeScheduleModal() {
  document.getElementById('schedule-modal').classList.remove('active');
  clearScheduleForm();
}

function clearScheduleForm() {
  document.getElementById('post-content').value = '';
  document.querySelectorAll('#schedule-modal input[type="checkbox"]').forEach(cb => {
    cb.checked = false;
  });
  updateCharCounter();
}

async function schedulePost() {
  const content = document.getElementById('post-content').value.trim();
  const date = document.getElementById('schedule-date').value;
  const time = document.getElementById('schedule-time').value;
  
  const platforms = [];
  document.querySelectorAll('#schedule-modal input[type="checkbox"]:checked').forEach(cb => {
    platforms.push(cb.value);
  });
  
  if (!content) {
    alert('Please enter post content');
    return;
  }
  
  if (platforms.length === 0) {
    alert('Please select at least one platform');
    return;
  }
  
  if (!date || !time) {
    alert('Please set schedule date and time');
    return;
  }
  
  const scheduledTime = `${date}T${time}:00`;
  
  const post = {
    id: Date.now().toString(),
    content,
    platforms,
    scheduledTime,
    published: false,
    createdAt: new Date().toISOString()
  };
  
  posts.push(post);
  
  await savePostsToGitHub();
  updateStats();
  renderPosts();
  closeScheduleModal();
  
  alert(`✅ Post scheduled for ${new Date(scheduledTime).toLocaleString()}`);
}

function editPost(id) {
  const post = posts.find(p => p.id == id);
  if (!post) return;
  
  currentEditId = id;
  
  document.getElementById('edit-content').value = post.content;
  
  const dt = new Date(post.scheduledTime);
  document.getElementById('edit-date').value = dt.toISOString().split('T')[0];
  document.getElementById('edit-time').value = dt.toTimeString().slice(0, 5);
  
  document.querySelectorAll('#edit-modal input[type="checkbox"]').forEach(cb => {
    cb.checked = post.platforms.includes(cb.value);
  });
  
  updateEditCharCounter();
  document.getElementById('edit-modal').classList.add('active');
}

function closeEditModal() {
  document.getElementById('edit-modal').classList.remove('active');
  currentEditId = null;
}

async function saveEditedPost() {
  if (!currentEditId) return;
  
  const post = posts.find(p => p.id == currentEditId);
  if (!post) return;
  
  post.content = document.getElementById('edit-content').value.trim();
  
  const date = document.getElementById('edit-date').value;
  const time = document.getElementById('edit-time').value;
  post.scheduledTime = `${date}T${time}:00`;
  
  post.platforms = [];
  document.querySelectorAll('#edit-modal input[type="checkbox"]:checked').forEach(cb => {
    post.platforms.push(cb.value);
  });
  
  if (!post.content) {
    alert('Please enter post content');
    return;
  }
  
  if (post.platforms.length === 0) {
    alert('Please select at least one platform');
    return;
  }
  
  await savePostsToGitHub();
  updateStats();
  renderPosts();
  closeEditModal();
  
  alert('✅ Post updated');
}

async function deletePost() {
  if (!currentEditId) return;
  
  if (!confirm('Are you sure you want to delete this post?')) {
    return;
  }
  
  posts = posts.filter(p => p.id !== currentEditId);
  
  await savePostsToGitHub();
  updateStats();
  renderPosts();
  closeEditModal();
  
  alert('✅ Post deleted');
}

async function refreshPosts() {
  await loadPostsFromGitHub();
  updateStats();
  renderPosts();
  alert('✅ Posts refreshed from GitHub');
}

function setupGitHubToken() {
  const token = prompt('Enter your GitHub Personal Access Token:\n\nThis will be stored locally and used to sync posts to your repository.');
  if (token) {
    localStorage.setItem('github_token', token);
    alert('✅ GitHub token saved! Autopilot will now sync with your repository.');
    init();
  }
}

window.addEventListener('DOMContentLoaded', () => {
  const token = localStorage.getItem('github_token');
  if (!token) {
    const setup = confirm('Autopilot needs a GitHub token to sync posts.\n\nDo you want to set it up now?');
    if (setup) {
      setupGitHubToken();
    }
  }
  init();
});
