document.addEventListener('DOMContentLoaded', () => {
    // --- Navigation Logic ---
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = item.getAttribute('data-target');

            // Update nav state
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Update views
            views.forEach(view => {
                view.classList.remove('active');
                if (view.id === targetId) {
                    view.classList.add('active');
                    // Trigger specific fetches when tab is opened
                    if (targetId === 'history') fetchHistory();
                    if (targetId === 'settings') fetchConfig();
                }
            });
        });
    });

    // --- State and Formatting Utilities ---
    let currentConfig = {};
    let isPulsing = false;

    function formatBytes(bytes, decimals = 2) {
        if (!+bytes) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
    }

    function formatDate(dateStr) {
        const d = new Date(dateStr);
        return d.toLocaleString(undefined, {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    }

    function showToast(msg = "Settings saved successfully!", isError = false) {
        const toast = document.getElementById('toast');
        const icon = toast.querySelector('i');
        document.getElementById('toast-msg').innerText = msg;

        if (isError) {
            toast.style.borderColor = 'rgba(239, 68, 68, 0.3)';
            icon.className = 'fa-solid fa-triangle-exclamation';
            icon.style.color = '#ef4444';
        } else {
            toast.style.borderColor = 'rgba(16, 185, 129, 0.3)';
            icon.className = 'fa-solid fa-check-circle';
            icon.style.color = '#10b981';
        }

        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3000);
    }

    function getIconForMedia(type) {
        if (type === 'audio') return 'fa-music';
        if (type === 'tv') return 'fa-tv';
        return 'fa-film';
    }

    // --- API Calls & UI Updates ---

    // Stats Update
    async function fetchStats() {
        if (document.getElementById('dashboard').classList.contains('active')) {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();

                if (data.dry_run) {
                    document.getElementById('dry-run-banner').style.display = 'flex';
                } else {
                    document.getElementById('dry-run-banner').style.display = 'none';
                }

                // Top cards
                document.getElementById('cpu-val').innerText = `${data.cpu_usage.toFixed(1)}%`;
                document.getElementById('cpu-bar').style.width = `${data.cpu_usage}%`;

                document.getElementById('gpu-val').innerText = `${data.gpu_usage}%`;
                document.getElementById('gpu-bar').style.width = `${data.gpu_usage}%`;

                document.getElementById('disk-val').innerText = `${data.disk_usage.toFixed(1)}%`;
                document.getElementById('disk-bar').style.width = `${data.disk_usage}%`;

                document.getElementById('mem-val').innerText = `${data.memory_usage.toFixed(1)}%`;
                document.getElementById('mem-bar').style.width = `${data.memory_usage}%`;

                document.getElementById('queue-val').innerText = data.queue_size;
                document.getElementById('saved-val').innerText = formatBytes(data.total_saved_bytes || 0);

                // Lifetime stats
                document.getElementById('total-conv').innerText = data.total_conversions || 0;
                document.getElementById('success-conv').innerText = data.successful_conversions || 0;
                document.getElementById('failed-conv').innerText = data.failed_conversions || 0;

                // Currently converting list
                const convertingList = document.getElementById('converting-list');
                const items = data.currently_converting || [];

                if (items.length === 0) {
                    convertingList.innerHTML = `
                        <div class="empty-state">
                            <i class="fa-solid fa-mug-hot"></i>
                            <p>No active conversions right now</p>
                        </div>
                    `;
                } else {
                    convertingList.innerHTML = items.map(item => `
                        <div class="converting-item">
                            <div class="item-icon"><i class="fa-solid ${getIconForMedia(item.type)}"></i></div>
                            <div class="item-details">
                                <div class="item-name" title="${item.file}">${item.file}</div>
                                <div class="item-meta">Type: <span class="badge type-${item.type}">${item.type}</span></div>
                            </div>
                            <div class="item-status" style="width: 150px; text-align: right;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 0.85rem;">
                                    <span><i class="fa-solid fa-gear fa-spin" style="margin-right: 4px;"></i> Converting</span>
                                    <span>${item.progress || 0}%</span>
                                </div>
                                <div class="stat-prog" style="height: 6px; margin-top: 4px;"><div class="stat-bar primary-bg" style="width: ${item.progress || 0}%"></div></div>
                            </div>
                        </div>
                    `).join('');
                }
            } catch (err) {
                console.error("Failed to fetch stats:", err);
            }
        }
    }

    // History Update
    async function fetchHistory() {
        try {
            const res = await fetch('/api/history');
            const data = await res.json();
            const tbody = document.getElementById('history-body');

            if (data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" class="text-center"><div class="empty-state" style="padding: 2rem"><i class="fa-solid fa-folder-open"></i><p>No conversion history yet</p></div></td></tr>`;
                return;
            }

            tbody.innerHTML = data.map(item => {
                const isSuccess = item.status === 'success' || item.status.includes('success');
                const savedBytes = item.original_size - item.new_size;
                const savedFormatted = savedBytes > 0 ? formatBytes(savedBytes) : '0 B';

                return `
                <tr>
                    <td><strong title="${item.file_name}">${item.file_name.length > 30 ? item.file_name.substring(0, 30) + '...' : item.file_name}</strong></td>
                    <td><span class="badge type-${item.media_type}">${item.media_type}</span></td>
                    <td><span class="badge ${isSuccess ? 'success' : 'error'}">${item.status}</span></td>
                    <td>${formatBytes(item.original_size)}</td>
                    <td>${formatBytes(item.new_size)}</td>
                    <td class="${savedBytes > 0 ? 'text-success' : ''}">${isSuccess ? savedFormatted : '-'}</td>
                    <td>${formatDate(item.timestamp)}</td>
                </tr>
            `}).join('');

        } catch (err) {
            console.error("Failed to fetch history:", err);
            document.getElementById('history-body').innerHTML = `<tr><td colspan="7" class="text-center text-error">Failed to load history</td></tr>`;
        }
    }

    // Config Update (Settings Panel)
    async function fetchConfig() {
        try {
            const res = await fetch('/api/config');
            currentConfig = await res.json();
            renderSettingsForm(currentConfig);
        } catch (err) {
            console.error("Failed to fetch config:", err);
        }
    }

    const OPTIONS_SCHEMA = {
        video_codec: [
            { val: "libx265", lbl: "CPU (x265 / HEVC)" },
            { val: "libx264", lbl: "CPU (x264 / AVC)" },
            { val: "hevc_nvenc", lbl: "Nvidia GPU (HEVC)" },
            { val: "hevc_amf", lbl: "AMD GPU (HEVC)" },
            { val: "hevc_qsv", lbl: "Intel GPU (QuickSync HEVC)" }
        ],
        audio_codec_video: [
            { val: "aac", lbl: "AAC (Standard)" },
            { val: "ac3", lbl: "AC-3 (Dolby Digital)" },
            { val: "libopus", lbl: "Opus (High Efficiency)" },
            { val: "copy", lbl: "Copy Original (No re-encode)" }
        ],
        audio_codec_music: [
            { val: "libmp3lame", lbl: "MP3" },
            { val: "libopus", lbl: "Opus" },
            { val: "flac", lbl: "FLAC (Lossless)" },
            { val: "aac", lbl: "AAC" }
        ],
        ffmpeg_preset: [
            { val: "ultrafast", lbl: "Ultrafast (Lowest Quality, Fast Encode)" },
            { val: "superfast", lbl: "Superfast" },
            { val: "veryfast", lbl: "Veryfast" },
            { val: "faster", lbl: "Faster" },
            { val: "fast", lbl: "Fast" },
            { val: "medium", lbl: "Medium (Balanced)" },
            { val: "slow", lbl: "Slow" },
            { val: "slower", lbl: "Slower (High Quality, Slow Encode)" },
            { val: "veryslow", lbl: "Veryslow (Highest Quality)" }
        ],
        music_bitrate: ["128k", "192k", "256k", "320k"],
        tv_resolution: ["720x480", "1280x720", "1920x1080", "3840x2160"],
        movie_resolution: ["1280x720", "1920x1080", "2560x1440", "3840x2160"]
    };

    function renderSettingsForm(config) {
        const form = document.getElementById('settings-form');
        form.innerHTML = '';

        // Configuration options grouped by type implicitly by UI rendering
        for (const [key, value] of Object.entries(config)) {
            const title = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

            const group = document.createElement('div');
            group.className = 'form-group';

            if (typeof value === 'boolean') {
                group.innerHTML = `
                    <label class="checkbox-label" for="setting-${key}">
                        <input type="checkbox" id="setting-${key}" name="${key}" ${value ? 'checked' : ''}>
                        <span style="font-size: 0.95rem; color: var(--text-primary); font-weight: 500">${title}</span>
                    </label>
                `;
            } else if (Array.isArray(value)) {
                group.innerHTML = `
                    <label for="setting-${key}">${title} (comma-separated)</label>
                    <input type="text" id="setting-${key}" name="${key}" value="${value.join(', ')}">
                `;
            } else if (OPTIONS_SCHEMA[key]) {
                const optionsHTML = OPTIONS_SCHEMA[key].map(opt => {
                    const val = typeof opt === 'string' ? opt : opt.val;
                    const lbl = typeof opt === 'string' ? opt : opt.lbl;
                    return `<option value="${val}" ${value === val ? 'selected' : ''}>${lbl}</option>`;
                }).join('');

                group.innerHTML = `
                    <label for="setting-${key}">${title}</label>
                    <select id="setting-${key}" name="${key}">
                        ${optionsHTML}
                    </select>
                `;
            } else if (key === 'ffmpeg_crf') {
                group.innerHTML = `
                    <label for="setting-${key}">${title} (0-51, lower = better quality)</label>
                    <input type="number" id="setting-${key}" name="${key}" value="${value}" min="0" max="51">
                `;
            } else if (key === 'parent_directory') {
                group.innerHTML = `
                    <label for="setting-${key}">${title}</label>
                    <div class="input-with-button">
                        <input type="text" id="setting-${key}" name="${key}" value="${value}">
                        <button type="button" class="btn-icon" onclick="openFolderBrowser()"><i class="fa-solid fa-folder-open"></i> Browse...</button>
                    </div>
                `;
            } else if (typeof value === 'number') {
                group.innerHTML = `
                    <label for="setting-${key}">${title}</label>
                    <input type="number" id="setting-${key}" name="${key}" value="${value}">
                `;
            } else {
                group.innerHTML = `
                    <label for="setting-${key}">${title}</label>
                    <input type="text" id="setting-${key}" name="${key}" value="${value}">
                `;
            }
            form.appendChild(group);
        }
    }

    // Save Settings
    document.getElementById('save-settings').addEventListener('click', async (e) => {
        e.preventDefault();
        const form = document.getElementById('settings-form');
        const formData = new FormData(form);
        const newConfig = { ...currentConfig };

        for (const [key, originalValue] of Object.entries(newConfig)) {
            const input = form.querySelector(`[name="${key}"]`);
            if (!input) continue;

            if (typeof originalValue === 'boolean') {
                newConfig[key] = input.checked;
            } else if (Array.isArray(originalValue)) {
                newConfig[key] = input.value.split(',').map(s => s.trim()).filter(Boolean);
            } else if (typeof originalValue === 'number') {
                newConfig[key] = Number(input.value) || 0;
            } else {
                newConfig[key] = input.value;
            }
        }

        try {
            const origText = document.getElementById('save-settings').innerHTML;
            document.getElementById('save-settings').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newConfig)
            });

            if (res.ok) {
                showToast("Settings updated successfully!");
                currentConfig = newConfig;
            } else {
                throw new Error("Server returned " + res.status);
            }
            document.getElementById('save-settings').innerHTML = origText;
        } catch (err) {
            showToast("Failed to save settings: " + err.message, true);
            document.getElementById('save-settings').innerHTML = '<i class="fa-solid fa-save"></i> Save Changes';
        }
    });

    document.getElementById('refresh-history').addEventListener('click', fetchHistory);

    // --- Folder Browser Logic ---
    let currentBrowserPath = "";

    window.openFolderBrowser = function () {
        const modal = document.getElementById('folder-modal');
        const currentSetting = document.getElementById('setting-parent_directory').value;
        modal.classList.add('show');
        fetchFolderContent(currentSetting);
    };

    document.getElementById('close-modal').addEventListener('click', () => {
        document.getElementById('folder-modal').classList.remove('show');
    });

    document.getElementById('folder-up').addEventListener('click', () => {
        // Fetch passing parent path
        if (currentBrowserPath) {
            // Let the backend calculate the parent, just ask for current path, backend returns parent
            const lastSlash = currentBrowserPath.lastIndexOf(currentBrowserPath.includes('\\') ? '\\' : '/');
            if (lastSlash > 0) {
                fetchFolderContent(currentBrowserPath.substring(0, lastSlash));
            } else if (lastSlash === 0) {
                fetchFolderContent('/');
            }
        }
    });

    document.getElementById('select-folder-btn').addEventListener('click', () => {
        if (currentBrowserPath) {
            document.getElementById('setting-parent_directory').value = currentBrowserPath;
            document.getElementById('folder-modal').classList.remove('show');
        }
    });

    window.fetchFolderContent = async function (path = "") {
        const listContainer = document.getElementById('folder-list');
        const pathText = document.getElementById('folder-path-text');

        listContainer.innerHTML = '<div class="text-center" style="padding: 2rem"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading...</div>';

        try {
            const res = await fetch(`/api/folders?path=${encodeURIComponent(path)}`);
            const data = await res.json();

            if (data.error) {
                listContainer.innerHTML = `<div class="text-center text-error" style="padding: 2rem"><i class="fa-solid fa-triangle-exclamation"></i> ${data.error}</div>`;
                return;
            }

            currentBrowserPath = data.current_path;
            pathText.innerText = currentBrowserPath;

            if (data.folders.length === 0) {
                listContainer.innerHTML = '<div class="text-center" style="padding: 2rem; color: var(--text-muted)">No subfolders</div>';
            } else {
                listContainer.innerHTML = data.folders.map(f => `
                    <div class="folder-item" onclick="fetchFolderContent('${f.path.replace(/\\/g, '\\\\')}')">
                        <i class="fa-solid fa-folder"></i> <span>${f.name}</span>
                    </div>
                `).join('');
            }
        } catch (err) {
            listContainer.innerHTML = `<div class="text-center text-error" style="padding: 2rem">Failed to load directory</div>`;
        }
    }

    // Initial setups
    fetchStats();
    setInterval(fetchStats, 2000);
});
