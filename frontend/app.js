const API_TIMEOUT = 30000; // 30 秒超时

const api = {
  async request(path, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);

    try {
      const r = await fetch(path, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {}),
        },
      });

      clearTimeout(timeoutId);

      if (!r.ok) {
        // 尝试读取错误详情，否则使用默认错误消息
        let detail = `HTTP ${r.status}`;
        try {
          const errBody = await r.json();
          detail = errBody.detail || detail;
        } catch (_) {
          // 忽略非 JSON 错误体
        }
        throw new Error(detail);
      }

      const ct = r.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        return r.json();
      }
      return r.text();
    } finally {
      clearTimeout(timeoutId);
    }
  },

  async get(path) {
    return this.request(path, { method: 'GET' });
  },

  async post(path, data) {
    return this.request(path, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
};

const state = { tasks: [], loading: false };

function showToast(message, type = 'error') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.className = 'toast show ' + type;
  setTimeout(() => {
    toast.className = 'toast';
  }, 4000);
}

async function init() {
  try {
    const health = await api.get('/api/health');
    console.log('TaskPilot AI', health);
    loadTasks();
  } catch (e) {
    console.error('Health check failed', e);
    showToast('后端服务不可用，请确认服务器已启动');
  }
}

async function loadTasks() {
  try {
    const tasks = await api.get('/api/tasks');
    renderHistory(tasks);
  } catch (e) {
    console.error('Failed to load tasks', e);
    showToast('加载任务列表失败: ' + e.message);
  }
}

function renderHistory(tasks) {
  const list = document.getElementById('history-list');
  list.innerHTML = '';
  if (!tasks.length) {
    const li = document.createElement('li');
    li.textContent = '暂无历史任务';
    list.appendChild(li);
    return;
  }
  tasks.forEach(t => {
    const li = document.createElement('li');
    li.textContent = '#' + t.id.slice(0, 8) + ' ' + t.status;
    li.addEventListener('click', () => loadTaskDetail(t.id));
    list.appendChild(li);
  });
}

async function loadTaskDetail(id) {
  try {
    const task = await api.get('/api/tasks/' + encodeURIComponent(id));
    renderStatus(task);
    renderReport(task);
  } catch (e) {
    console.error('Failed to load task detail', e);
    showToast('加载任务详情失败: ' + e.message);
  }
}

function renderStatus(task) {
  const el = document.getElementById('status-content');
  if (!el) return;
  el.innerHTML = '<p>状态: <strong>' + task.status + '</strong></p>';
  if (task.error) {
    const div = document.createElement('div');
    div.className = 'error';
    div.textContent = '异常: ' + task.error;
    el.appendChild(div);
  }
}

function renderReport(task) {
  const el = document.getElementById('report-content');
  if (!el) return;
  el.textContent = task.final_report || '暂无报告';
}

document.getElementById('task-form').addEventListener('submit', async function (e) {
  e.preventDefault();
  const input = document.getElementById('task-input');
  const btn = e.target.querySelector('button[type=submit]');
  const statusEl = document.getElementById('status-content');

  if (!input.value.trim()) {
    showToast('请输入任务描述');
    return;
  }

  btn.disabled = true;
  btn.textContent = '执行中...';
  statusEl.innerHTML = '<p>状态: <strong>提交中...</strong></p>';

  try {
    const task = await api.post('/api/tasks', { user_task: input.value });
    renderStatus(task);
    loadTasks();
    showToast('任务已创建，正在后台执行，请刷新查看状态', 'success');
  } catch (err) {
    statusEl.innerHTML =
      '<div class="error">创建任务失败: ' + err.message + '</div>';
    showToast('创建任务失败: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '运行任务';
  }
});

init();
