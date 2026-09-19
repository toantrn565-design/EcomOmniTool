// Core Logic & UI Management for Ecom OmniTool Pro
document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initWebsocket();
    loadAccountsForSelects();
    loadSchedules();
    startStatusPolling();
});

// ==========================================
// 1. UI NAVIGATION & WEBSOCKET
// ==========================================
function initSidebar() {
    const navItems = document.querySelectorAll('.nav-item:not(.disabled)');
    const sections = document.querySelectorAll('.module-section');
    const pageTitle = document.getElementById('pageTitle');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navItems.forEach(nav => nav.classList.remove('active'));
            sections.forEach(sec => sec.classList.remove('active'));
            
            item.classList.add('active');
            const targetId = item.getAttribute('data-target');
            const targetEl = document.getElementById(targetId);
            if (targetEl) targetEl.classList.add('active');
            
            pageTitle.textContent = item.querySelector('span').textContent;
        });
    });
}

function initWebsocket() {
    const wsUrl = `ws://${window.location.host}/ws/logs`;
    const ws = new WebSocket(wsUrl);
    const logOutput = document.getElementById('logOutput');
    
    ws.onmessage = (event) => {
        const p = document.createElement("div");
        p.textContent = event.data;
        logOutput.appendChild(p);
        logOutput.scrollTop = logOutput.scrollHeight;
    };
    
    ws.onclose = () => {
        setTimeout(initWebsocket, 2500);
    };
}

// ==========================================
// 2. MODALS, TOASTS & ACCOUNTS
// ==========================================
function openModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.add('show');
        // Click ngoài backdrop để đóng modal
        el.onclick = (e) => {
            if (e.target === el) closeModal(id);
        };
    }
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('show');
}

// Đóng modal bằng phím Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.show').forEach(m => m.classList.remove('show'));
    }
});

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'fa-info-circle';
    if(type === 'success') icon = 'fa-check-circle';
    if(type === 'error') icon = 'fa-exclamation-circle';
    if(type === 'warning') icon = 'fa-exclamation-triangle';
    
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

async function loadAccountsForSelects() {
    try {
        const res = await fetch("/api/accounts");
        const accounts = await res.json();
        
        const selects = [
            'videoAccountSelect',
            'productAccountSelect',
            'boostAccountSelect',
            'flashsaleAccountSelect',
            'schedAccountSelect',
            'chatAccountSelect'
        ];
        
        selects.forEach(selectId => {
            const el = document.getElementById(selectId);
            if (!el) return;
            el.innerHTML = '';
            
            // Thêm tùy chọn chạy tất cả shop cho các module tự động hóa
            if (['boostAccountSelect', 'flashsaleAccountSelect', 'chatAccountSelect'].includes(selectId) && accounts.length > 1) {
                const allOpt = document.createElement('option');
                allOpt.value = "all";
                allOpt.textContent = `🚀 TẤT CẢ CÁC SHOP (${accounts.length} Shop)`;
                el.appendChild(allOpt);
            }

            accounts.forEach(acc => {
                const opt = document.createElement('option');
                opt.value = acc.id;
                const proxyTag = acc.proxy_server ? ' [Proxy]' : '';
                opt.textContent = `${acc.name} [${(acc.platform || 'SHOPEE').toUpperCase()}]${proxyTag} (${acc.status})`;
                el.appendChild(opt);
            });
        });

        // Cập nhật danh sách shop luân phiên
        const seqList = document.getElementById('sequentialShopsList');
        if (seqList) {
            seqList.innerHTML = '';
            accounts.forEach(acc => {
                if ((acc.platform || 'shopee').toLowerCase() === 'shopee') {
                    const label = document.createElement('label');
                    label.style.display = 'flex';
                    label.style.alignItems = 'center';
                    label.style.gap = '5px';
                    label.style.fontSize = '0.85rem';
                    label.innerHTML = `<input type="checkbox" class="seq-shop-cb" value="${acc.id}" checked> ${acc.name}`;
                    seqList.appendChild(label);
                }
            });
        }

        onVideoAccountChange();
    } catch(e) {
        console.error("Lỗi tải danh sách tài khoản", e);
    }
}

async function openAccountsModal() {
    openModal('accountsModal');
    try {
        const res = await fetch("/api/accounts");
        const accounts = await res.json();
        let html = '';
        accounts.forEach(acc => {
            const platformName = acc.platform ? acc.platform.toUpperCase() : "SHOPEE";
            const proxyBadge = acc.proxy_server ? `<span class="badge" title="${acc.proxy_server}">Proxy On</span>` : '<span class="text-muted" style="font-size: 0.8rem;">Trực tiếp</span>';
            html += `<tr>
                <td style="font-weight: 600;">${acc.name}</td>
                <td><span class="badge">${platformName}</span></td>
                <td>${proxyBadge}</td>
                <td><span class="badge-status ${acc.status === 'Đã kết nối' ? 'badge-active' : 'badge-inactive'}">${acc.status}</span></td>
                <td>
                    <div class="action-btn-group">
                        <button class="btn btn-sm btn-outline" onclick="loginAccount('${acc.id}')" title="Mở trình duyệt đăng nhập"><i class="fa-solid fa-arrow-right-to-bracket"></i> Login</button>
                        <button class="btn btn-sm btn-outline" onclick="checkAccount('${acc.id}')" title="Kiểm tra kết nối"><i class="fa-solid fa-rotate"></i> Kiểm tra</button>
                        <button class="btn btn-sm btn-outline" onclick="openEditAccountModal('${acc.id}')" title="Sửa thông tin"><i class="fa-solid fa-pen-to-square"></i> Sửa</button>
                    </div>
                </td>
            </tr>`;
        });
        if(accounts.length === 0) html = '<tr><td colspan="5" style="text-align:center; padding: 20px;">Chưa có tài khoản. Hãy Thêm Shop Mới.</td></tr>';
        document.getElementById('accountsTableBody').innerHTML = html;
    } catch(e) { console.error("Lỗi tải accounts", e); }
}

async function loginAccount(id) {
    try {
        await fetch(`/api/accounts/${id}/login`, { method: "POST" });
        showToast("Đang mở trình duyệt đăng nhập cho Shop...", "info");
    } catch(e) { showToast("Lỗi mở trình duyệt!", "error"); }
}

async function checkAccount(id) {
    try {
        const res = await fetch(`/api/accounts/${id}/check`);
        const data = await res.json();
        showToast("Trạng thái: " + data.status, data.status === "Đã kết nối" ? "success" : "warning");
        openAccountsModal();
        loadAccountsForSelects();
    } catch(e) { showToast("Lỗi kiểm tra trạng thái!", "error"); }
}

function openEditAccountModal(id = null) {
    openModal('editAccountModal');
    document.getElementById('editAccountId').value = id || '';
    if(!id) {
        document.getElementById('editAccountTitle').textContent = "Thêm Shop Mới";
        document.getElementById('editAccountName').value = "";
        document.getElementById('editAccountVideoFolder').value = "";
        document.getElementById('editAccountPlatform').value = "shopee";
        document.getElementById('editAccountProxyServer').value = "";
        document.getElementById('editAccountProxyUser').value = "";
        document.getElementById('editAccountProxyPass').value = "";
    } else {
        document.getElementById('editAccountTitle').textContent = "Sửa Thông Tin Shop";
        fetch("/api/accounts").then(res => res.json()).then(accounts => {
            const acc = accounts.find(a => a.id === id);
            if(acc) {
                document.getElementById('editAccountName').value = acc.name || '';
                document.getElementById('editAccountVideoFolder').value = acc.video_folder || '';
                document.getElementById('editAccountPlatform').value = acc.platform || 'shopee';
                document.getElementById('editAccountProxyServer').value = acc.proxy_server || '';
                document.getElementById('editAccountProxyUser').value = acc.proxy_username || '';
                document.getElementById('editAccountProxyPass').value = acc.proxy_password || '';
            }
        });
    }
}

async function saveAccount() {
    const id = document.getElementById('editAccountId').value || ('shop_' + Date.now());
    const name = document.getElementById('editAccountName').value.trim();
    const video_folder = document.getElementById('editAccountVideoFolder').value.trim();
    const platform = document.getElementById('editAccountPlatform').value;
    const proxy_server = document.getElementById('editAccountProxyServer').value.trim();
    const proxy_username = document.getElementById('editAccountProxyUser').value.trim();
    const proxy_password = document.getElementById('editAccountProxyPass').value.trim();
    
    if(!name) { showToast("Vui lòng nhập tên Shop!", "warning"); return; }
    
    const accountData = {
        id: id,
        name: name,
        type: "seller",
        platform: platform,
        profile_dir: `profile_${name.toLowerCase().replace(/[^a-z0-9]/g, '')}`,
        video_folder: video_folder,
        proxy_server: proxy_server,
        proxy_username: proxy_username,
        proxy_password: proxy_password,
        status: "Chưa kết nối"
    };
    
    try {
        await fetch("/api/accounts", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(accountData)
        });
        showToast("Đã lưu thông tin Shop thành công!", "success");
        closeModal('editAccountModal');
        openAccountsModal();
        loadAccountsForSelects();
    } catch(e) { showToast("Lỗi lưu Shop!", "error"); }
}

async function openSettingsModal() {
    openModal('settingsModal');
    try {
        const res = await fetch("/api/settings");
        const settings = await res.json();
        document.getElementById('settingGeminiApiKey').value = settings.gemini_api_key || '';
        document.getElementById('settingCaptionSuffix').value = settings.default_caption_suffix || '';
        document.getElementById('settingDelay').value = settings.delay_between_posts || 60;
        const modeSelect = document.getElementById('settingTaggingMode');
        if(modeSelect) modeSelect.value = settings.product_tagging_mode || "manual";
    } catch(e) { console.error("Lỗi tải settings", e); }
}

async function saveSettings() {
    const data = {
        gemini_api_key: document.getElementById('settingGeminiApiKey').value.trim(),
        default_caption_suffix: document.getElementById('settingCaptionSuffix').value,
        delay_between_posts: parseInt(document.getElementById('settingDelay').value) || 60,
        product_tagging_mode: document.getElementById('settingTaggingMode').value || "manual"
    };
    try {
        await fetch("/api/settings", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(data)
        });
        showToast("Đã lưu cài đặt chung!", "success");
        closeModal('settingsModal');
    } catch(e) { showToast("Lỗi lưu cài đặt!", "error"); }
}


// ==========================================
// 3. MODULE VIDEO POSTER
// ==========================================
async function onVideoAccountChange() {
    const accId = document.getElementById('videoAccountSelect').value;
    if(!accId) return;
    try {
        const res = await fetch("/api/accounts");
        const accounts = await res.json();
        const current = accounts.find(a => a.id === accId);
        if(current && current.video_folder) {
            document.getElementById('quickVideoFolder').value = current.video_folder;
        } else {
            document.getElementById('quickVideoFolder').value = "";
        }
    } catch(e) {}
}

function toggleSequentialMode() {
    const toggle = document.getElementById('sequentialModeToggle');
    const list = document.getElementById('sequentialShopsList');
    list.style.display = toggle.checked ? 'flex' : 'none';
}

async function saveQuickFolder() {
    const accId = document.getElementById('videoAccountSelect').value;
    const folder = document.getElementById('quickVideoFolder').value.trim();
    if(!accId || !folder) { showToast("Chọn Shop và nhập đường dẫn Folder!", "warning"); return; }
    try {
        const res = await fetch("/api/accounts");
        const accounts = await res.json();
        const current = accounts.find(a => a.id === accId);
        if(current) {
            current.video_folder = folder;
            await fetch("/api/accounts", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(current)
            });
            showToast("Đã lưu folder video thành công!", "success");
            loadVideos();
        }
    } catch(e) { showToast("Lỗi lưu folder!", "error"); }
}

async function loadVideos() {
    const accId = document.getElementById('videoAccountSelect').value;
    if(!accId) { showToast("Vui lòng chọn Shop trước!", "warning"); return; }
    try {
        const res = await fetch(`/api/videos?account_id=${accId}`);
        const videos = await res.json();
        const tbody = document.getElementById('videoTableBody');
        tbody.innerHTML = '';
        if(videos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Không tìm thấy file .mp4 nào trong thư mục.</td></tr>';
            return;
        }
        videos.forEach(v => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><input type="checkbox" class="video-cb" value="${v.file_name}" checked></td>
                <td><strong>${v.file_name}</strong></td>
                <td><span class="badge">${v.status || 'Sẵn sàng'}</span></td>
                <td><input type="text" class="form-control caption-input" value="${v.caption || ''}"></td>
                <td><input type="text" class="form-control prod-input" value="${v.products || ''}" placeholder="Từ khóa/Mã SP"></td>
            `;
            tbody.appendChild(tr);
        });
        showToast(`Đã quét thấy ${videos.length} video!`, "success");
    } catch(e) { showToast("Lỗi khi quét thư mục video!", "error"); }
}

async function startVideoUpload() {
    const isSeq = document.getElementById('sequentialModeToggle').checked;
    let payload = {};
    if (isSeq) {
        const checkedShops = Array.from(document.querySelectorAll('.seq-shop-cb:checked')).map(cb => cb.value);
        if(checkedShops.length === 0) { showToast("Chọn ít nhất 1 Shop để chạy!", "warning"); return; }
        payload = { account_ids: checkedShops };
    } else {
        const accId = document.getElementById('videoAccountSelect').value;
        if(!accId) { showToast("Chọn Shop để đăng!", "warning"); return; }
        payload = { account_id: accId };
    }
    try {
        await fetch("/api/uploader/start", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });
        showToast("Đã bắt đầu chiến dịch đăng video!", "success");
    } catch(e) { showToast("Lỗi khởi chạy video uploader!", "error"); }
}

async function stopVideoUpload() {
    try {
        await fetch("/api/uploader/stop", { method: "POST" });
        showToast("Đã gửi lệnh dừng đăng video.", "info");
    } catch(e) {}
}


// ==========================================
// 4. MODULE PRODUCT COPIER
// ==========================================
async function scrapeSingleOrBulk() {
    const rawUrls = document.getElementById('scrapeUrls').value.trim();
    if(!rawUrls) { showToast("Vui lòng nhập link sản phẩm!", "warning"); return; }
    const urls = rawUrls.split("\n").map(u => u.trim()).filter(u => u);
    showToast(`Bắt đầu cào ${urls.length} sản phẩm...`, "info");
    try {
        const res = await fetch("/api/scrape-bulk", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ urls: urls })
        });
        const data = await res.json();
        showToast(`Đã cào thành công ${data.length} sản phẩm!`, "success");
    } catch(e) { showToast("Lỗi cào dữ liệu!", "error"); }
}

async function extractShopLinks() {
    const rawUrls = document.getElementById('scrapeUrls').value.trim();
    if(!rawUrls) { showToast("Vui lòng nhập link Shop Shopee/TikTok!", "warning"); return; }
    showToast("Đang quét toàn bộ sản phẩm của Shop...", "info");
    try {
        const res = await fetch("/api/extract-shop", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ url: rawUrls.split("\n")[0].trim() })
        });
        const data = await res.json();
        document.getElementById('scrapeUrls').value = data.urls.join("\n");
        showToast(`Tìm thấy ${data.urls.length} link sản phẩm!`, "success");
    } catch(e) { showToast("Lỗi quét shop!", "error"); }
}


// ==========================================
// 5. MODULE AUTO BOOST 4H (ĐẨY SẢN PHẨM)
// ==========================================
let boostProductsData = [];
let selectedBoostProductNames = [];

function onBoostAccountChanged() {
    boostProductsData = [];
    selectedBoostProductNames = [];
    renderBoostProductTable([]);
    updateBoostSelectedCounter();
}

function toggleBoostMode() {
    const mode = document.getElementById('boostMode').value;
    const box = document.getElementById('boostProductSelectionBox');
    if (mode === 'selected') {
        box.style.display = 'block';
        if (boostProductsData.length === 0) {
            fetchBoostShopProducts();
        }
    } else {
        box.style.display = 'block'; // vẫn hiện để user có thể xem và đẩy tức thì 1 sản phẩm
    }
}

async function fetchBoostShopProducts() {
    const accountId = document.getElementById('boostAccountSelect').value;
    if (!accountId) { showToast("Vui lòng chọn Shop Shopee!", "warning"); return; }
    
    const tbody = document.getElementById('boostProductTableBody');
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 25px;"><i class="fa-solid fa-spinner fa-spin" style="font-size: 1.5rem; color: var(--primary);"></i><div class="mt-2">Đang kết nối Kênh Người Bán để quét sản phẩm...</div></td></tr>`;
    
    showToast("Đang quét danh sách sản phẩm từ Shop Shopee...", "info");
    
    try {
        const res = await fetch(`/api/boost/products?account_id=${encodeURIComponent(accountId)}`);
        if (!res.ok) throw new Error("Không thể tải danh sách sản phẩm");
        const data = await res.json();
        boostProductsData = Array.isArray(data) ? data : [];
        
        if (boostProductsData.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 25px;">Không tìm thấy sản phẩm nào hoặc Shop chưa có sản phẩm.</td></tr>`;
            showToast("Không tìm thấy sản phẩm trong Shop!", "warning");
            return;
        }
        
        showToast(`Đã tải thành công ${boostProductsData.length} sản phẩm!`, "success");
        renderBoostProductTable(boostProductsData);
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--danger); padding: 25px;"><i class="fa-solid fa-triangle-exclamation"></i> Lỗi tải danh sách sản phẩm từ Shop.</td></tr>`;
        showToast("Lỗi kết nối hoặc Shop chưa đăng nhập!", "error");
    }
}

function renderBoostProductTable(products) {
    const tbody = document.getElementById('boostProductTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (products.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">Không có sản phẩm phù hợp từ khóa tìm kiếm.</td></tr>`;
        return;
    }
    
    products.forEach((prod, index) => {
        const tr = document.createElement('tr');
        const isChecked = selectedBoostProductNames.includes(prod.name);
        const imgTag = prod.image ? `<img src="${prod.image}" style="width: 44px; height: 44px; object-fit: cover; border-radius: 6px; border: 1px solid var(--border-color);">` : `<div style="width: 44px; height: 44px; background: rgba(255,255,255,0.05); border-radius: 6px; display:flex; align-items:center; justify-content:center;"><i class="fa-solid fa-image text-muted"></i></div>`;
        const statusBadge = prod.is_boosted 
            ? `<span class="badge-status badge-active" style="font-size: 0.75rem;">Đang đẩy</span>` 
            : `<span class="badge-status" style="background: rgba(100,116,139,0.2); color: #94a3b8; font-size: 0.75rem;">Có thể đẩy</span>`;
        
        tr.innerHTML = `
            <td style="text-align: center;">
                <input type="checkbox" class="boost-checkbox" ${isChecked ? 'checked' : ''} onchange="toggleBoostSelect('${encodeURIComponent(prod.name)}', this.checked)">
            </td>
            <td>${imgTag}</td>
            <td>
                <div style="font-weight: 500; font-size: 0.88rem; line-height: 1.3; max-width: 360px;">${prod.name}</div>
                <div class="text-muted" style="font-size: 0.75rem; margin-top: 2px;">ID: ${prod.id || (index+1)}</div>
            </td>
            <td>
                <div style="font-size: 0.85rem; color: #10b981; font-weight: 600;">${prod.price || '---'}</div>
                <div class="text-muted" style="font-size: 0.75rem;">Kho: ${prod.stock || '---'}</div>
            </td>
            <td>${statusBadge}</td>
            <td style="text-align: center;">
                <button class="btn btn-outline btn-sm" onclick="instantBoostSingle('${encodeURIComponent(prod.name)}')" title="Đẩy ngay sản phẩm này">
                    <i class="fa-solid fa-bolt" style="color: #f59e0b;"></i> Đẩy ngay
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterBoostProductList() {
    const query = (document.getElementById('boostProductSearchInput').value || '').toLowerCase().trim();
    if (!query) {
        renderBoostProductTable(boostProductsData);
        return;
    }
    const filtered = boostProductsData.filter(p => (p.name || '').toLowerCase().includes(query) || (p.id || '').toLowerCase().includes(query));
    renderBoostProductTable(filtered);
}

function toggleBoostSelect(encodedName, isChecked) {
    const name = decodeURIComponent(encodedName);
    if (isChecked) {
        if (selectedBoostProductNames.length >= 5) {
            showToast("Shopee chỉ cho phép đẩy tối đa 5 sản phẩm mỗi lần!", "warning");
            renderBoostProductTable(boostProductsData);
            return;
        }
        if (!selectedBoostProductNames.includes(name)) {
            selectedBoostProductNames.push(name);
        }
    } else {
        selectedBoostProductNames = selectedBoostProductNames.filter(n => n !== name);
    }
    updateBoostSelectedCounter();
}

function clearBoostSelection() {
    selectedBoostProductNames = [];
    updateBoostSelectedCounter();
    renderBoostProductTable(boostProductsData);
}

function updateBoostSelectedCounter() {
    const countEl = document.getElementById('boostSelectedCount');
    if (countEl) countEl.textContent = selectedBoostProductNames.length;
}

async function instantBoostSingle(encodedName) {
    const accountId = document.getElementById('boostAccountSelect').value;
    const name = decodeURIComponent(encodedName);
    if (!accountId) { showToast("Vui lòng chọn Shop!", "warning"); return; }
    
    showToast(`Đang kích hoạt đẩy ngay: ${name.substring(0, 30)}...`, "info");
    try {
        const res = await fetch("/api/boost/instant", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ account_id: accountId, product_name: name })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(`Đã đẩy thành công sản phẩm: ${name.substring(0, 30)}!`, "success");
        } else {
            showToast(data.error || "Không thể đẩy sản phẩm lúc này", "warning");
        }
    } catch (e) { showToast("Lỗi kết nối khi đẩy sản phẩm!", "error"); }
}

async function startAutoBoost() {
    const accountId = document.getElementById('boostAccountSelect').value;
    const mode = document.getElementById('boostMode').value;
    if (!accountId) { showToast("Vui lòng chọn Shop Shopee!", "warning"); return; }
    
    const payload = {
        account_id: accountId,
        mode: mode,
        product_ids: mode === 'selected' ? selectedBoostProductNames : null
    };
    
    if (mode === 'selected' && selectedBoostProductNames.length === 0) {
        showToast("Vui lòng tích chọn ít nhất 1 sản phẩm bên dưới để đẩy!", "warning");
        return;
    }
    
    try {
        const res = await fetch("/api/boost/start", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            showToast("Đã kích hoạt tự động đẩy sản phẩm 4h!", "success");
            updateBoostUI(true, 4 * 3600);
        } else {
            showToast(data.detail || "Lỗi bật đẩy sản phẩm", "error");
        }
    } catch(e) { showToast("Lỗi kết nối server!", "error"); }
}

async function startAutoBoostAll() {
    showToast("Đang kích hoạt đẩy sản phẩm cho TẤT CẢ các Shop...", "info");
    try {
        const res = await fetch("/api/boost/start", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                account_id: "all",
                mode: "smart",
                product_ids: null
            })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message || "Đã kích hoạt đẩy sản phẩm cho tất cả Shop!", "success");
            updateBoostUI(true, 4 * 3600);
        } else {
            showToast(data.detail || "Lỗi kích hoạt!", "error");
        }
    } catch(e) { showToast("Lỗi kết nối server!", "error"); }
}

async function stopAutoBoost() {
    try {
        await fetch("/api/boost/stop", { method: "POST" });
        showToast("Đã dừng tự động đẩy sản phẩm.", "info");
        updateBoostUI(false, 0);
    } catch(e) {}
}

function updateBoostUI(isRunning, remainingSec) {
    const badge = document.getElementById('boostStatusBadge');
    const timer = document.getElementById('boostCountdown');
    if (!badge || !timer) return;
    
    if (isRunning) {
        badge.className = "badge-status badge-active";
        badge.textContent = "Đang chạy 24/7";
        if (remainingSec > 0) {
            const h = Math.floor(remainingSec / 3600).toString().padStart(2, '0');
            const m = Math.floor((remainingSec % 3600) / 60).toString().padStart(2, '0');
            const s = (remainingSec % 60).toString().padStart(2, '0');
            timer.textContent = `${h}:${m}:${s}`;
        } else {
            timer.textContent = "Đang đẩy...";
        }
    } else {
        badge.className = "badge-status badge-inactive";
        badge.textContent = "Đang dừng";
        timer.textContent = "--:--:--";
    }
}


// ==========================================
// 6. MODULE AUTO FLASH SALE (TỰ ĐỘNG TẠO FLASH SALE)
// ==========================================
let flashsaleProductsData = [];
let selectedFlashSaleProductNames = [];

function onFlashSaleAccountChanged() {
    flashsaleProductsData = [];
    selectedFlashSaleProductNames = [];
    renderFlashSaleProductTable([]);
    updateFlashSaleSelectedCounter();
}

function toggleFlashSaleMode() {
    const mode = document.getElementById('fsSelectionMode').value;
    const box = document.getElementById('fsProductSelectionBox');
    if (mode === 'custom') {
        box.style.display = 'block';
        if (flashsaleProductsData.length === 0) {
            fetchFlashSaleShopProducts();
        }
    } else {
        box.style.display = 'block';
    }
}

async function fetchFlashSaleShopProducts() {
    const accountId = document.getElementById('flashsaleAccountSelect').value;
    if (!accountId) { showToast("Vui lòng chọn Shop!", "warning"); return; }
    
    // Nếu Auto Boost đã tải sản phẩm cho shop này rồi, dùng ngay
    const boostAccId = document.getElementById('boostAccountSelect').value;
    if (boostAccId === accountId && boostProductsData.length > 0) {
        flashsaleProductsData = [...boostProductsData];
        renderFlashSaleProductTable(flashsaleProductsData);
        showToast(`Đã nạp ${flashsaleProductsData.length} sản phẩm của Shop!`, "success");
        return;
    }

    const tbody = document.getElementById('fsProductTableBody');
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 25px;"><i class="fa-solid fa-spinner fa-spin" style="font-size: 1.5rem; color: #f59e0b;"></i><div class="mt-2">Đang kết nối Kênh Người Bán để quét sản phẩm cho Flash Sale...</div></td></tr>`;
    
    showToast("Đang quét danh sách sản phẩm của Shop...", "info");
    
    try {
        const res = await fetch(`/api/flashsale/products?account_id=${encodeURIComponent(accountId)}`);
        if (!res.ok) throw new Error("Không thể tải danh sách sản phẩm");
        const data = await res.json();
        flashsaleProductsData = Array.isArray(data) ? data : [];
        boostProductsData = [...flashsaleProductsData]; // Đồng bộ sang boost
        
        if (flashsaleProductsData.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 25px;">Không tìm thấy sản phẩm nào.</td></tr>`;
            showToast("Không tìm thấy sản phẩm trong Shop!", "warning");
            return;
        }
        
        showToast(`Đã tải thành công ${flashsaleProductsData.length} sản phẩm!`, "success");
        renderFlashSaleProductTable(flashsaleProductsData);
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--danger); padding: 25px;"><i class="fa-solid fa-triangle-exclamation"></i> Lỗi tải danh sách sản phẩm.</td></tr>`;
        showToast("Lỗi kết nối hoặc Shop chưa đăng nhập!", "error");
    }
}

function renderFlashSaleProductTable(products) {
    const tbody = document.getElementById('fsProductTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (products.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">Không có sản phẩm phù hợp.</td></tr>`;
        return;
    }
    
    products.forEach((prod, index) => {
        const tr = document.createElement('tr');
        const isChecked = selectedFlashSaleProductNames.includes(prod.name);
        const imgTag = prod.image ? `<img src="${prod.image}" style="width: 44px; height: 44px; object-fit: cover; border-radius: 6px; border: 1px solid var(--border-color);">` : `<div style="width: 44px; height: 44px; background: rgba(255,255,255,0.05); border-radius: 6px; display:flex; align-items:center; justify-content:center;"><i class="fa-solid fa-image text-muted"></i></div>`;
        
        tr.innerHTML = `
            <td style="text-align: center;">
                <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleFlashSaleSelect('${encodeURIComponent(prod.name)}', this.checked)">
            </td>
            <td>${imgTag}</td>
            <td>
                <div style="font-weight: 500; font-size: 0.88rem; line-height: 1.3; max-width: 400px;">${prod.name}</div>
                <div class="text-muted" style="font-size: 0.75rem; margin-top: 2px;">ID: ${prod.id || (index+1)}</div>
            </td>
            <td>
                <div style="font-size: 0.85rem; color: #10b981; font-weight: 600;">${prod.price || '---'}</div>
                <div class="text-muted" style="font-size: 0.75rem;">Kho: ${prod.stock || '---'}</div>
            </td>
            <td>
                <span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; font-size: 0.75rem;">Sẵn sàng FS</span>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterFlashSaleProductList() {
    const query = (document.getElementById('fsProductSearchInput').value || '').toLowerCase().trim();
    if (!query) {
        renderFlashSaleProductTable(flashsaleProductsData);
        return;
    }
    const filtered = flashsaleProductsData.filter(p => (p.name || '').toLowerCase().includes(query) || (p.id || '').toLowerCase().includes(query));
    renderFlashSaleProductTable(filtered);
}

function toggleFlashSaleSelect(encodedName, isChecked) {
    const name = decodeURIComponent(encodedName);
    if (isChecked) {
        if (!selectedFlashSaleProductNames.includes(name)) {
            selectedFlashSaleProductNames.push(name);
        }
    } else {
        selectedFlashSaleProductNames = selectedFlashSaleProductNames.filter(n => n !== name);
    }
    updateFlashSaleSelectedCounter();
}

function selectAllFlashSale(selectAll) {
    if (selectAll) {
        selectedFlashSaleProductNames = flashsaleProductsData.map(p => p.name);
    } else {
        selectedFlashSaleProductNames = [];
    }
    updateFlashSaleSelectedCounter();
    renderFlashSaleProductTable(flashsaleProductsData);
}

function updateFlashSaleSelectedCounter() {
    const countEl = document.getElementById('fsSelectedCount');
    if (countEl) countEl.textContent = selectedFlashSaleProductNames.length;
}

async function triggerAutoFlashSale() {
    const accountId = document.getElementById('flashsaleAccountSelect').value;
    const discount = parseInt(document.getElementById('fsDiscountPercent').value) || 10;
    const stock = parseInt(document.getElementById('fsStockPerItem').value) || 10;
    const mode = document.getElementById('fsSelectionMode').value;
    
    if(!accountId) { showToast("Vui lòng chọn Shop!", "warning"); return; }
    
    const selectedProds = (mode === 'custom' && selectedFlashSaleProductNames.length > 0) ? selectedFlashSaleProductNames : null;
    
    if (mode === 'custom' && (!selectedProds || selectedProds.length === 0)) {
        showToast("Vui lòng chọn ít nhất 1 sản phẩm tham gia Flash Sale!", "warning");
        return;
    }
    
    showToast("Đang quét khung giờ và tạo Flash Sale...", "info");
    
    try {
        const res = await fetch("/api/flashsale/trigger", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                account_id: accountId,
                discount_percent: discount,
                stock_per_item: stock,
                target_product_count: selectedProds ? selectedProds.length : 10,
                selected_products: selectedProds
            })
        });
        if(res.ok) {
            showToast("Tiến trình tạo Flash Sale tự động đã khởi chạy!", "success");
        } else {
            showToast("Lỗi kích hoạt Flash Sale!", "error");
        }
    } catch(e) { showToast("Lỗi kết nối server!", "error"); }
}


// ==========================================
// 7. MODULE CRON SCHEDULER (HẸN GIỜ VÀNG)
// ==========================================
async function loadSchedules() {
    try {
        const res = await fetch("/api/schedules");
        const list = await res.json();
        const tbody = document.getElementById('scheduleTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (list.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Chưa có lịch hẹn nào.</td></tr>';
            return;
        }
        list.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${item.task_type.toUpperCase()}</strong></td>
                <td>${item.account_id}</td>
                <td><span class="badge">${item.target_time}</span></td>
                <td><span class="badge-status badge-active">${item.status}</span></td>
                <td><button class="btn-icon" onclick="deleteCronSchedule('${item.id}')"><i class="fa-solid fa-trash"></i></button></td>
            `;
            tbody.appendChild(tr);
        });
    } catch(e) {}
}

async function addCronSchedule() {
    const task_type = document.getElementById('schedTaskType').value;
    const target_time = document.getElementById('schedTime').value;
    const account_id = document.getElementById('schedAccountSelect').value;
    
    if (!account_id || !target_time) { showToast("Chọn Shop và thời gian hẹn!", "warning"); return; }
    
    try {
        await fetch("/api/schedules/add", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                task_type: task_type,
                account_id: account_id,
                target_time: target_time
            })
        });
        showToast("Đã thêm lịch hẹn Khung Giờ Vàng thành công!", "success");
        loadSchedules();
    } catch(e) { showToast("Lỗi thêm lịch hẹn!", "error"); }
}

async function deleteCronSchedule(id) {
    try {
        await fetch(`/api/schedules/${id}`, { method: "DELETE" });
        showToast("Đã xóa lịch hẹn.", "info");
        loadSchedules();
    } catch(e) {}
}

async function toggleScheduler(active) {
    try {
        const res = await fetch(`/api/schedules/toggle?active=${active}`, { method: "POST" });
        const data = await res.json();
        showToast(data.message, active ? "success" : "info");
    } catch(e) {}
}


// ==========================================
// 8. MODULE AI SALES CHATBOT
// ==========================================
async function toggleAIChat(action) {
    const accountId = document.getElementById('chatAccountSelect').value;
    const apiKey = document.getElementById('chatApiKey').value.trim();
    if(!accountId) { showToast("Chọn Shop để bật AI Chat!", "warning"); return; }
    
    try {
        const res = await fetch("/api/chat/toggle", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                account_id: accountId,
                action: action,
                api_key: apiKey
            })
        });
        const data = await res.json();
        showToast(data.message, action === 'start' ? "success" : "info");
        const badge = document.getElementById('chatStatusBadge');
        if (badge) {
            badge.className = action === 'start' ? "badge-status badge-active" : "badge-status badge-inactive";
            badge.textContent = action === 'start' ? "Đang lắng nghe 24/7" : "Chưa bật";
        }
        loadChatHistory();
    } catch(e) { showToast("Lỗi điều khiển AI Chat!", "error"); }
}

async function toggleAIChatAll(action) {
    const apiKey = document.getElementById('chatApiKey').value.trim();
    showToast("Đang kích hoạt AI Chatbot cho TẤT CẢ các Shop...", "info");
    try {
        const res = await fetch("/api/chat/toggle", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                account_id: "all",
                action: action,
                api_key: apiKey
            })
        });
        const data = await res.json();
        showToast(data.message, action === 'start' ? "success" : "info");
        const badge = document.getElementById('chatStatusBadge');
        if (badge) {
            badge.className = action === 'start' ? "badge-status badge-active" : "badge-status badge-inactive";
            badge.textContent = action === 'start' ? "Đang lắng nghe tất cả Shop" : "Chưa bật";
        }
        loadChatHistory();
    } catch(e) { showToast("Lỗi kết nối server!", "error"); }
}

async function sendTestChat() {
    const msgInput = document.getElementById('chatTestInput');
    const msg = msgInput ? msgInput.value.trim() : '';
    const accountId = document.getElementById('chatAccountSelect').value || 'all';
    const apiKey = document.getElementById('chatApiKey').value.trim();
    const resultBox = document.getElementById('testChatResultBox');
    
    if (!msg) { showToast("Vui lòng nhập câu hỏi test!", "warning"); return; }
    
    if (resultBox) {
        resultBox.innerHTML = `<div style="color: #f59e0b;"><i class="fa-solid fa-spinner fa-spin"></i> AI đang suy nghĩ câu trả lời tư vấn tối ưu...</div>`;
    }
    
    try {
        const res = await fetch("/api/chat/test", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                account_id: accountId,
                customer_message: msg,
                api_key: apiKey
            })
        });
        const data = await res.json();
        if (res.ok && data.reply) {
            if (resultBox) {
                resultBox.innerHTML = `
                    <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 4px;"><strong>[${data.shop_name}]</strong> Phản hồi câu hỏi: <em>"${data.customer_message}"</em></div>
                    <div style="background: rgba(99, 102, 241, 0.2); padding: 10px 14px; border-radius: 8px; border: 1px solid rgba(99, 102, 241, 0.4); color: #fff; font-size: 0.9rem; line-height: 1.45;">
                        <i class="fa-solid fa-robot" style="color: #a855f7; margin-right: 6px;"></i> ${data.reply}
                    </div>
                `;
            }
            showToast("AI đã trả lời test thành công và lưu vào lịch sử!", "success");
            loadChatHistory();
        } else {
            showToast("Lỗi chạy test AI!", "error");
        }
    } catch(e) { showToast("Lỗi kết nối server!", "error"); }
}

async function openChatBrowser() {
    const select = document.getElementById('chatAccountSelect');
    const accountId = select ? select.value : '';
    if (!accountId || accountId === 'all') {
        const accounts = await (await fetch("/api/accounts")).json();
        if (accounts.length > 0) {
            openSpecificChatBrowser(accounts[0].id);
        } else {
            showToast("Chưa có tài khoản Shop nào!", "warning");
        }
        return;
    }
    openSpecificChatBrowser(accountId);
}

async function openSpecificChatBrowser(accountId) {
    showToast("Đang mở Kênh Chat Shopee trên trình duyệt...", "info");
    try {
        const res = await fetch("/api/chat/open", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ account_id: accountId, product_name: "" })
        });
        const data = await res.json();
        showToast(data.message || "Đã mở trình duyệt Chat!", "success");
    } catch(e) { showToast("Lỗi kết nối server!", "error"); }
}

async function loadChatHistory() {
    try {
        const res = await fetch("/api/chat/history");
        if (!res.ok) return;
        const records = await res.json();
        const tbody = document.getElementById('chatHistoryTableBody');
        if (!tbody) return;
        
        if (!records || records.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 25px;"><i class="fa-solid fa-comment-dots" style="font-size: 1.8rem; margin-bottom: 6px; display: block; opacity: 0.5;"></i>Chưa có tin nhắn mới nào được ghi nhận. Bạn có thể bấm nút "Test AI" ở trên để kiểm tra hoặc đợi khách nhắn tin.</td></tr>`;
            return;
        }
        
        tbody.innerHTML = '';
        records.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span style="font-family: monospace; font-size: 0.8rem; color: #94a3b8;">${r.time}</span></td>
                <td><strong style="color: var(--primary); font-size: 0.85rem;">${r.shop_name}</strong></td>
                <td><div style="background: rgba(255,255,255,0.06); padding: 8px 12px; border-radius: 8px; font-size: 0.85rem; line-height: 1.4; color: #e2e8f0; border-left: 3px solid #38bdf8;">${r.customer_message}</div></td>
                <td><div style="background: rgba(99, 102, 241, 0.15); padding: 8px 12px; border-radius: 8px; font-size: 0.85rem; line-height: 1.4; color: #fff; border: 1px solid rgba(99, 102, 241, 0.3);"><i class="fa-solid fa-robot" style="color: #a855f7; margin-right: 6px;"></i>${r.ai_reply}</div></td>
                <td style="text-align: center;"><span class="badge-status badge-active" style="font-size: 0.75rem;">${r.status || 'Đã gửi'}</span></td>
            `;
            tbody.appendChild(tr);
        });
    } catch(e) {}
}

async function openCurrentShopBrowser(selectId) {
    const select = document.getElementById(selectId);
    let accountId = select ? select.value : '';
    if (!accountId || accountId === 'all') {
        const accounts = await (await fetch("/api/accounts")).json();
        if (accounts.length > 0) {
            accountId = accounts[0].id;
        } else {
            showToast("Vui lòng chọn Shop cần mở trình duyệt!", "warning");
            return;
        }
    }
    showToast("Đang mở trình duyệt Kênh Người Bán Shopee...", "info");
    try {
        const res = await fetch("/api/shop/open", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ account_id: accountId, product_name: "" })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message || "Trình duyệt Kênh Người Bán đã mở!", "success");
        } else {
            showToast("Lỗi mở trình duyệt!", "error");
        }
    } catch (e) {
        showToast("Lỗi kết nối server!", "error");
    }
}


// ==========================================
// 9. MODULE AI CONTENT REWRITER
// ==========================================
async function runAIRewrite() {
    const title = document.getElementById('rawTitle').value.trim();
    const desc = document.getElementById('rawDesc').value.trim();
    if(!title || !desc) { showToast("Nhập Tiêu đề và Mô tả gốc!", "warning"); return; }
    
    showToast("AI đang tối ưu nội dung chuẩn SEO...", "info");
    try {
        const res = await fetch("/api/ai/rewrite", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ title: title, description: desc })
        });
        const data = await res.json();
        if(data.status === "success" && data.data) {
            document.getElementById('rewrittenTitle').value = data.data.title || "";
            document.getElementById('rewrittenDesc').value = data.data.description || "";
            showToast("Đã tối ưu xong tiêu đề và bài mô tả mới!", "success");
        }
    } catch(e) { showToast("Lỗi AI tối ưu nội dung!", "error"); }
}

function copyRewrittenContent() {
    const title = document.getElementById('rewrittenTitle').value;
    const desc = document.getElementById('rewrittenDesc').value;
    if(!title && !desc) return;
    navigator.clipboard.writeText(`${title}\n\n${desc}`);
    showToast("Đã sao chép nội dung mới vào Clipboard!", "success");
}


// ==========================================
// 10. MODULE IMAGE STYLER (ĐÓNG KHUNG 1:1)
// ==========================================
async function processImageFraming() {
    const imgPath = document.getElementById('frameImgPath').value.trim();
    const frameType = document.getElementById('frameType').value;
    const badgeText = document.getElementById('frameBadgeText').value.trim();
    const discountTag = document.getElementById('frameDiscountTag').value.trim();
    
    if (!imgPath) { showToast("Vui lòng nhập đường dẫn file ảnh!", "warning"); return; }
    
    showToast("Đang xử lý đóng khung tỷ lệ 1:1...", "info");
    try {
        const res = await fetch("/api/image/frame", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                image_url_or_path: imgPath,
                frame_type: frameType,
                badge_text: badgeText,
                discount_tag: discountTag
            })
        });
        const data = await res.json();
        if (res.ok && data.framed_url) {
            const preview = document.getElementById('framedImagePreview');
            preview.innerHTML = `<img src="${data.framed_url}?t=${Date.now()}" style="max-height: 240px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">`;
            showToast("Đóng khung ảnh thành công!", "success");
        } else {
            showToast("Lỗi xử lý ảnh!", "error");
        }
    } catch(e) { showToast("Lỗi kết nối server!", "error"); }
}


// ==========================================
// 11. POLLING SYSTEM STATUS & REALTIME CHAT
// ==========================================
let chatPollCounter = 0;
function startStatusPolling() {
    setInterval(async () => {
        try {
            // Check boost status
            const resBoost = await fetch("/api/boost/status");
            const dataBoost = await resBoost.json();
            updateBoostUI(dataBoost.is_running, dataBoost.remaining_seconds);
            
            // Check chat status
            const resChat = await fetch("/api/chat/status");
            const dataChat = await resChat.json();
            const chatBadge = document.getElementById('chatStatusBadge');
            if (chatBadge) {
                chatBadge.className = dataChat.is_running ? "badge-status badge-active" : "badge-status badge-inactive";
                chatBadge.textContent = dataChat.is_running ? "Đang lắng nghe 24/7" : "Chưa bật";
            }
            
            chatPollCounter++;
            if (chatPollCounter % 3 === 0) {
                loadChatHistory();
            }
        } catch(e) {}
    }, 1000);
}
