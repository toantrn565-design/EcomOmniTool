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
        const text = event.data || "";
        const p = document.createElement("div");
        p.style.marginBottom = "3px";
        p.style.lineHeight = "1.5";
        p.style.wordBreak = "break-word";
        
        if (text.includes("✅") || text.includes("thành công") || text.includes("Success")) {
            p.style.color = "#4ade80";
        } else if (text.includes("❌") || text.includes("Lỗi") || text.includes("Error") || text.includes("thất bại")) {
            p.style.color = "#f87171";
        } else if (text.includes("⚠️") || text.includes("cảnh báo") || text.includes("Warning")) {
            p.style.color = "#fbbf24";
        } else if (text.includes("🚀") || text.includes("🔍") || text.includes("⚡") || text.includes("Bắt đầu")) {
            p.style.color = "#38bdf8";
        } else {
            p.style.color = "#cbd5e1";
        }
        
        p.textContent = text;
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
        onBoostAccountChanged();
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

function toggleAuthModeFields() {
    const mode = document.getElementById('editAccountAuthMode').value;
    const platform = document.getElementById('editAccountPlatform').value;
    const shopeeBox = document.getElementById('shopeeApiFields');
    const tiktokBox = document.getElementById('tiktokApiFields');
    const mcpBox = document.getElementById('mcpFields');
    
    if (shopeeBox) shopeeBox.style.display = (mode === 'api' && platform === 'shopee') ? 'block' : 'none';
    if (tiktokBox) tiktokBox.style.display = (mode === 'api' && platform === 'tiktok') ? 'block' : 'none';
    if (mcpBox) mcpBox.style.display = (mode === 'mcp') ? 'block' : 'none';
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
        document.getElementById('editAccountAuthMode').value = "browser";
        if (document.getElementById('editAccountStatus')) {
            document.getElementById('editAccountStatus').value = "Đã kết nối";
        }
        
        document.getElementById('editShopeePartnerId').value = "";
        document.getElementById('editShopeeShopId').value = "";
        document.getElementById('editShopeePartnerKey').value = "";
        document.getElementById('editShopeeAccessToken').value = "";
        
        document.getElementById('editTikTokAppKey').value = "";
        document.getElementById('editTikTokShopCipher').value = "";
        document.getElementById('editTikTokAppSecret').value = "";
        document.getElementById('editTikTokAccessToken').value = "";
        
        document.getElementById('editMcpUrl').value = "";
        document.getElementById('editMcpToken').value = "";
        toggleAuthModeFields();
    } else {
        document.getElementById('editAccountTitle').textContent = "Sửa Thông Tin Shop";
        fetch("/api/accounts").then(res => res.json()).then(accounts => {
            const acc = accounts.find(a => a.id === id);
            if(acc) {
                document.getElementById('editAccountName').value = acc.name || '';
                document.getElementById('editAccountVideoFolder').value = acc.video_folder || '';
                document.getElementById('editAccountPlatform').value = acc.platform || 'shopee';
                if (document.getElementById('editAccountStatus')) {
                    document.getElementById('editAccountStatus').value = acc.status || 'Đã kết nối';
                }
                document.getElementById('editAccountProxyServer').value = acc.proxy_server || '';
                document.getElementById('editAccountProxyUser').value = acc.proxy_username || '';
                document.getElementById('editAccountProxyPass').value = acc.proxy_password || '';
                document.getElementById('editAccountAuthMode').value = acc.auth_mode || 'browser';
                
                document.getElementById('editShopeePartnerId').value = acc.shopee_partner_id || '';
                document.getElementById('editShopeeShopId').value = acc.shopee_shop_id || '';
                document.getElementById('editShopeePartnerKey').value = acc.shopee_partner_key || '';
                document.getElementById('editShopeeAccessToken').value = acc.shopee_access_token || '';
                
                document.getElementById('editTikTokAppKey').value = acc.tiktok_app_key || '';
                document.getElementById('editTikTokShopCipher').value = acc.tiktok_shop_cipher || '';
                document.getElementById('editTikTokAppSecret').value = acc.tiktok_app_secret || '';
                document.getElementById('editTikTokAccessToken').value = acc.tiktok_access_token || '';
                
                document.getElementById('editMcpUrl').value = acc.mcp_url || '';
                document.getElementById('editMcpToken').value = acc.mcp_token || '';
                toggleAuthModeFields();
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
    const auth_mode = document.getElementById('editAccountAuthMode').value;
    const statusEl = document.getElementById('editAccountStatus');
    const status = statusEl ? statusEl.value : (auth_mode === 'api' ? 'Đã kết nối (API)' : 'Đã kết nối');
    
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
        status: status,
        auth_mode: auth_mode,
        shopee_partner_id: document.getElementById('editShopeePartnerId').value.trim(),
        shopee_shop_id: document.getElementById('editShopeeShopId').value.trim(),
        shopee_partner_key: document.getElementById('editShopeePartnerKey').value.trim(),
        shopee_access_token: document.getElementById('editShopeeAccessToken').value.trim(),
        tiktok_app_key: document.getElementById('editTikTokAppKey').value.trim(),
        tiktok_shop_cipher: document.getElementById('editTikTokShopCipher').value.trim(),
        tiktok_app_secret: document.getElementById('editTikTokAppSecret').value.trim(),
        tiktok_access_token: document.getElementById('editTikTokAccessToken').value.trim(),
        mcp_url: document.getElementById('editMcpUrl').value.trim(),
        mcp_token: document.getElementById('editMcpToken').value.trim()
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
// 5. MODULE AUTO BOOST (PIPELINE 4 NHÓM XOAY VÒNG CHUẨN GOSELLER)
// ==========================================
let boostProductsData = [];
let selectedBoostProductNames = [];
let currentBoostGroups = [
    { id: "group_1", name: "Đẩy nhóm số 1", products: [] },
    { id: "group_2", name: "Đẩy nhóm số 2", products: [] },
    { id: "group_3", name: "Đẩy nhóm số 3", products: [] },
    { id: "group_4", name: "Đẩy nhóm số 4", products: [] }
];
let activeModalGroupId = null;
let modalTempSelectedProducts = [];
let isBoostRunningLocally = false;
let localBoostRemainingSec = 0;
let localActiveGroupIndex = 0;

function switchBoostModeView(mode) {
    const pView = document.getElementById('boostPipelineView');
    const qView = document.getElementById('boostQuickView');
    const btnP = document.getElementById('btnTabPipeline');
    const btnQ = document.getElementById('btnTabQuick');
    
    if (mode === 'pipeline') {
        if (pView) pView.style.display = 'block';
        if (qView) qView.style.display = 'none';
        if (btnP) { btnP.className = 'btn btn-primary btn-sm w-50'; }
        if (btnQ) { btnQ.className = 'btn btn-outline btn-sm w-50'; }
    } else {
        if (pView) pView.style.display = 'none';
        if (qView) qView.style.display = 'block';
        if (btnP) { btnP.className = 'btn btn-outline btn-sm w-50'; }
        if (btnQ) { btnQ.className = 'btn btn-primary btn-sm w-50'; }
        if (boostProductsData.length === 0) fetchBoostShopProducts();
    }
}

async function onBoostAccountChanged() {
    const accSelect = document.getElementById('boostAccountSelect');
    if (!accSelect) return;
    const shopName = accSelect.options[accSelect.selectedIndex]?.text || "Shop";
    const shopNameEl = document.getElementById('boostPipelineShopName');
    if (shopNameEl) shopNameEl.textContent = shopName.split('[')[0].trim();
    
    selectedBoostProductNames = [];
    renderBoostProductTable([]);
    await loadBoostGroupsFromServer();
}

async function loadBoostGroupsFromServer() {
    const accountId = document.getElementById('boostAccountSelect')?.value;
    if (!accountId) return;
    try {
        const res = await fetch(`/api/boost/groups?account_id=${encodeURIComponent(accountId)}`);
        if (res.ok) {
            const data = await res.json();
            currentBoostGroups = data.groups && data.groups.length > 0 ? data.groups : [
                { id: "group_1", name: "Đẩy nhóm số 1", products: [] },
                { id: "group_2", name: "Đẩy nhóm số 2", products: [] },
                { id: "group_3", name: "Đẩy nhóm số 3", products: [] },
                { id: "group_4", name: "Đẩy nhóm số 4", products: [] }
            ];
            localActiveGroupIndex = data.current_group_index || 0;
            renderBoostPipeline();
        }
    } catch(e) {
        renderBoostPipeline();
    }
}

function renderBoostPipeline() {
    const container = document.getElementById('boostPipelineContainer');
    if (!container) return;
    container.innerHTML = '';
    
    currentBoostGroups.forEach((group, idx) => {
        const isCurrentRunning = isBoostRunningLocally && idx === localActiveGroupIndex;
        const card = document.createElement('div');
        card.className = `boost-group-card ${isCurrentRunning ? 'active-running' : ''}`;
        card.id = `boost_card_${group.id}`;
        
        // Header
        const header = document.createElement('div');
        header.className = 'boost-group-header';
        header.innerHTML = `
            <div class="boost-group-title">
                <span class="group-idx-badge">${idx + 1}</span>
                <span style="font-weight: 700;">${group.name || `Đẩy nhóm số ${idx + 1}`}</span>
                ${isCurrentRunning ? '<span class="badge-status badge-active" style="font-size: 0.72rem; padding: 2px 8px; margin-left: 6px;"><span class="pulse-dot-green"></span> ĐANG ĐẨY</span>' : ''}
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                <button class="btn btn-outline btn-sm" onclick="openGroupProductModal('${group.id}')" style="font-size: 0.8rem; padding: 4px 10px;">
                    <i class="fa-solid fa-plus"></i> Chọn 5 SP (${(group.products || []).length}/5)
                </button>
                <button class="btn btn-outline btn-sm text-danger" onclick="deleteBoostGroup('${group.id}')" title="Xóa nhóm này" style="padding: 4px 8px;">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
        `;
        card.appendChild(header);
        
        // Products Row (5 slots)
        const prodsRow = document.createElement('div');
        prodsRow.className = 'boost-products-row';
        
        const prods = group.products || [];
        for (let s = 0; s < 5; s++) {
            const slot = document.createElement('div');
            if (s < prods.length && prods[s]) {
                const p = prods[s];
                slot.className = 'boost-product-slot filled-slot';
                const imgSrc = p.image || '';
                const fallbackImg = `<div style="width: 100%; height: 100%; display:flex; align-items:center; justify-content:center; background: rgba(255,255,255,0.05);"><i class="fa-solid fa-box text-muted"></i></div>`;
                slot.innerHTML = `
                    ${imgSrc ? `<img src="${imgSrc}">` : fallbackImg}
                    <div class="slot-overlay">
                        <div class="slot-pname" title="${p.name}">${p.name}</div>
                        <button class="slot-remove-btn" onclick="removeProductFromGroup('${group.id}', ${s}); event.stopPropagation();" title="Bỏ sản phẩm">&times;</button>
                    </div>
                `;
            } else {
                slot.className = 'boost-product-slot empty-slot';
                slot.innerHTML = `<i class="fa-solid fa-plus"></i><span>Slot #${s + 1}</span>`;
                slot.onclick = () => openGroupProductModal(group.id);
            }
            prodsRow.appendChild(slot);
        }
        card.appendChild(prodsRow);
        container.appendChild(card);
        
        // Connector
        if (idx < currentBoostGroups.length - 1) {
            const conn = document.createElement('div');
            conn.className = 'pipeline-connector';
            const isConnActive = isCurrentRunning;
            conn.innerHTML = `
                <div class="pipeline-connector-badge ${isConnActive ? 'active-badge' : ''}">
                    ${isConnActive ? `<span class="pulse-dot-green"></span> Đang chạy (Chờ 4h)` : `⏳ Chờ 4 tiếng`}
                </div>
            `;
            container.appendChild(conn);
        }
    });
}

function updateBoostPipelineActiveState(isRunning, activeIndex) {
    const cards = document.querySelectorAll('.boost-group-card');
    cards.forEach((card, idx) => {
        if (isRunning && idx === activeIndex) {
            card.classList.add('active-running');
        } else {
            card.classList.remove('active-running');
        }
    });

    const connectors = document.querySelectorAll('.pipeline-connector-badge');
    connectors.forEach((conn, idx) => {
        if (isRunning && idx === activeIndex) {
            conn.classList.add('active-badge');
            conn.innerHTML = `<span class="pulse-dot-green"></span> Đang chạy (Chờ 4h)`;
        } else {
            conn.classList.remove('active-badge');
            conn.innerHTML = `⏳ Chờ 4 tiếng`;
        }
    });
}

async function openGroupProductModal(groupId) {
    activeModalGroupId = groupId;
    const group = currentBoostGroups.find(g => g.id === groupId);
    const titleEl = document.getElementById('groupModalTitle');
    if (titleEl && group) {
        titleEl.innerHTML = `<i class="fa-solid fa-boxes-stacked" style="color: #ec4899;"></i> Chọn 5 SP Cho ${group.name || 'Nhóm'}`;
    }
    
    // Copy existing products to temp list
    modalTempSelectedProducts = group && group.products ? [...group.products] : [];
    updateGroupModalSelectedCount();
    
    openModal('boostGroupProductModal');
    
    if (boostProductsData.length === 0) {
        await fetchBoostShopProducts();
    }
    renderGroupProductModalTable(boostProductsData);
}

function closeGroupProductModal() {
    closeModal('boostGroupProductModal');
    activeModalGroupId = null;
}

function renderGroupProductModalTable(products) {
    const tbody = document.getElementById('groupProductModalTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (products.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 25px;">Chưa có dữ liệu sản phẩm. Vui lòng bấm 'Tải Danh Mục Sản Phẩm Shop'.</td></tr>`;
        return;
    }
    
    products.forEach((prod, idx) => {
        const isChecked = modalTempSelectedProducts.some(p => p.name === prod.name);
        const tr = document.createElement('tr');
        const imgTag = prod.image ? `<img src="${prod.image}" style="width: 44px; height: 44px; object-fit: cover; border-radius: 6px; border: 1px solid var(--border-color);">` : `<div style="width: 44px; height: 44px; background: rgba(255,255,255,0.05); border-radius: 6px; display:flex; align-items:center; justify-content:center;"><i class="fa-solid fa-image text-muted"></i></div>`;
        
        tr.innerHTML = `
            <td style="text-align: center;">
                <input type="checkbox" class="group-prod-cb" ${isChecked ? 'checked' : ''} onchange="toggleGroupProductSelect(${idx}, this.checked)">
            </td>
            <td>${imgTag}</td>
            <td>
                <div style="font-weight: 600; font-size: 0.88rem; line-height: 1.3;">${prod.name}</div>
                <div class="text-muted" style="font-size: 0.75rem;">ID: ${prod.id || (idx+1)}</div>
            </td>
            <td>
                <div style="color: #10b981; font-weight: 600; font-size: 0.85rem;">${prod.price || 'Sẵn sàng'}</div>
                <div class="text-muted" style="font-size: 0.75rem;">Kho: ${prod.stock || 'Còn hàng'}</div>
            </td>
            <td>
                <span class="badge-status" style="background: rgba(100,116,139,0.2); color: #94a3b8; font-size: 0.75rem;">Có thể đẩy</span>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterGroupProductModalList() {
    const q = (document.getElementById('groupProductModalSearch')?.value || '').toLowerCase().trim();
    if (!q) {
        renderGroupProductModalTable(boostProductsData);
        return;
    }
    const filtered = boostProductsData.filter(p => (p.name || '').toLowerCase().includes(q));
    renderGroupProductModalTable(filtered);
}

function toggleGroupProductSelect(productIndex, isChecked) {
    const prod = boostProductsData[productIndex];
    if (!prod) return;
    
    if (isChecked) {
        if (modalTempSelectedProducts.length >= 5) {
            showToast("Mỗi nhóm chỉ được chọn tối đa 5 sản phẩm!", "warning");
            renderGroupProductModalTable(boostProductsData);
            return;
        }
        if (!modalTempSelectedProducts.some(p => p.name === prod.name)) {
            modalTempSelectedProducts.push({
                id: prod.id || `p_${Date.now()}`,
                name: prod.name,
                image: prod.image || '',
                price: prod.price || '',
                stock: prod.stock || ''
            });
        }
    } else {
        modalTempSelectedProducts = modalTempSelectedProducts.filter(p => p.name !== prod.name);
    }
    updateGroupModalSelectedCount();
}

function updateGroupModalSelectedCount() {
    const countEl = document.getElementById('groupModalSelectedCount');
    if (countEl) countEl.textContent = modalTempSelectedProducts.length;
}

function confirmGroupProductSelection() {
    if (!activeModalGroupId) return;
    const group = currentBoostGroups.find(g => g.id === activeModalGroupId);
    if (group) {
        group.products = [...modalTempSelectedProducts];
        showToast(`Đã cập nhật ${group.products.length} sản phẩm cho ${group.name}!`, "success");
        renderBoostPipeline();
        saveBoostGroupsToServer();
    }
    closeGroupProductModal();
}

function removeProductFromGroup(groupId, productIndex) {
    const group = currentBoostGroups.find(g => g.id === groupId);
    if (group && group.products) {
        group.products.splice(productIndex, 1);
        renderBoostPipeline();
        saveBoostGroupsToServer();
    }
}

function addNewBoostGroup() {
    const newIdx = currentBoostGroups.length + 1;
    currentBoostGroups.push({
        id: `group_${Date.now()}`,
        name: `Đẩy nhóm số ${newIdx}`,
        products: []
    });
    renderBoostPipeline();
    showToast(`Đã thêm Nhóm số ${newIdx}!`, "info");
    saveBoostGroupsToServer();
}

function deleteBoostGroup(groupId) {
    if (currentBoostGroups.length <= 1) {
        showToast("Cần giữ ít nhất 1 nhóm đẩy!", "warning");
        return;
    }
    currentBoostGroups = currentBoostGroups.filter(g => g.id !== groupId);
    currentBoostGroups.forEach((g, i) => {
        g.name = `Đẩy nhóm số ${i + 1}`;
    });
    renderBoostPipeline();
    saveBoostGroupsToServer();
    showToast("Đã xóa nhóm đẩy.", "info");
}

function clearAllBoostGroups() {
    currentBoostGroups = [
        { id: "group_1", name: "Đẩy nhóm số 1", products: [] },
        { id: "group_2", name: "Đẩy nhóm số 2", products: [] },
        { id: "group_3", name: "Đẩy nhóm số 3", products: [] },
        { id: "group_4", name: "Đẩy nhóm số 4", products: [] }
    ];
    renderBoostPipeline();
    saveBoostGroupsToServer();
    showToast("Đã thiết lập lại 4 nhóm mặc định.", "info");
}

async function saveBoostGroupsToServer() {
    const accountId = document.getElementById('boostAccountSelect')?.value;
    if (!accountId) return;
    try {
        const res = await fetch("/api/boost/groups/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                account_id: accountId,
                groups: currentBoostGroups
            })
        });
        if (res.ok) {
            showToast("Đã lưu cấu hình các nhóm đẩy!", "success");
        }
    } catch(e) {}
}

async function startBoostPipeline() {
    const accountId = document.getElementById('boostAccountSelect')?.value;
    if (!accountId) { showToast("Vui lòng chọn Shop!", "warning"); return; }
    
    const totalProds = currentBoostGroups.reduce((sum, g) => sum + (g.products?.length || 0), 0);
    if (totalProds === 0) {
        showToast("Vui lòng chọn sản phẩm cho ít nhất 1 nhóm trước khi bắt đầu!", "warning");
        return;
    }
    
    try {
        const res = await fetch("/api/boost/groups/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                account_id: accountId,
                start_group_index: 0
            })
        });
        const data = await res.json();
        if (res.ok) {
            showToast("Đã kích hoạt tự động đẩy xoay vòng 4 nhóm 24/7!", "success");
            updateBoostUI(true, 4 * 3600);
        } else {
            showToast(data.detail || "Lỗi kích hoạt tiến trình!", "error");
        }
    } catch(e) {
        showToast("Lỗi kết nối server!", "error");
    }
}

async function stopBoostPipeline() {
    const accountId = document.getElementById('boostAccountSelect')?.value;
    try {
        await fetch(`/api/boost/groups/stop?account_id=${encodeURIComponent(accountId)}`, { method: "POST" });
        showToast("Đã dừng tự động đẩy nhóm.", "info");
        updateBoostUI(false, 0);
    } catch(e) {}
}

async function fetchBoostShopProducts() {
    const accountId = document.getElementById('boostAccountSelect')?.value;
    if (!accountId) { showToast("Vui lòng chọn Shop Shopee!", "warning"); return; }
    
    const tbody = document.getElementById('boostProductTableBody');
    const btn = document.getElementById('btnScanBoost');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang kết nối Shop...`;
    }

    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 30px;">
            <i class="fa-solid fa-spinner fa-spin" style="font-size: 2rem; color: var(--primary);"></i>
            <div class="mt-3" style="font-weight: 600; font-size: 1rem;">Đang kết nối Kênh Người Bán để quét sản phẩm...</div>
            <div class="text-muted" style="font-size: 0.85rem; margin-top: 6px;">Playwright đang kết nối Shopee Seller Center (khoảng 5-10 giây)...</div>
        </td></tr>`;
    }
    
    showToast("Đang quét danh sách sản phẩm từ Shop Shopee...", "info");
    
    try {
        const res = await fetch(`/api/boost/products?account_id=${encodeURIComponent(accountId)}`);
        if (!res.ok) throw new Error("Không thể tải danh sách sản phẩm");
        const data = await res.json();
        boostProductsData = Array.isArray(data) ? data : [];
        
        if (boostProductsData.length === 0) {
            if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 25px;">Không tìm thấy sản phẩm nào hoặc Shop chưa có sản phẩm.</td></tr>`;
            showToast("Không tìm thấy sản phẩm trong Shop!", "warning");
            return;
        }
        
        showToast(`Đã tải thành công ${boostProductsData.length} sản phẩm!`, "success");
        renderBoostProductTable(boostProductsData);
    } catch (e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--danger); padding: 25px;"><i class="fa-solid fa-triangle-exclamation"></i> Lỗi tải danh sách sản phẩm từ Shop. Vui lòng bấm Quản lý Shop -> Login trước.</td></tr>`;
        showToast("Lỗi kết nối hoặc Shop chưa đăng nhập!", "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Tải Danh Mục Sản Phẩm Shop`;
        }
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
    const query = (document.getElementById('boostProductSearchInput')?.value || '').toLowerCase().trim();
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
    const accountId = document.getElementById('boostAccountSelect')?.value;
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

async function startQuickBoost() {
    const accountId = document.getElementById('boostAccountSelect')?.value;
    if (!accountId) { showToast("Vui lòng chọn Shop Shopee!", "warning"); return; }
    if (selectedBoostProductNames.length === 0) {
        showToast("Vui lòng tích chọn ít nhất 1 sản phẩm bên dưới để đẩy!", "warning");
        return;
    }
    
    try {
        const res = await fetch("/api/boost/start", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                account_id: accountId,
                mode: "selected",
                product_ids: selectedBoostProductNames
            })
        });
        const data = await res.json();
        if (res.ok) {
            showToast("Đã kích hoạt tự động đẩy 5 sản phẩm đã chọn!", "success");
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
    const btn = document.getElementById('btnScanFlashSale');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang kết nối Shop...`;
    }

    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 30px;">
        <i class="fa-solid fa-spinner fa-spin" style="font-size: 2rem; color: #f59e0b;"></i>
        <div class="mt-3" style="font-weight: 600; font-size: 1rem;">Đang kết nối Kênh Người Bán để quét sản phẩm cho Flash Sale...</div>
        <div class="text-muted" style="font-size: 0.85rem; margin-top: 6px;">Playwright đang quét danh mục sản phẩm (khoảng 5-10 giây)...</div>
    </td></tr>`;
    
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
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--danger); padding: 25px;"><i class="fa-solid fa-triangle-exclamation"></i> Lỗi tải danh sách sản phẩm. Vui lòng bấm Quản lý Shop -> Login trước.</td></tr>`;
        showToast("Lỗi kết nối hoặc Shop chưa đăng nhập!", "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Quét / Tải Sản Phẩm Shop`;
        }
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
let localBoostRemainingSec = 0;
let isBoostRunningLocally = false;

function updateBoostUI(isRunning, remainingSec, runningCount = 0, runningAccounts = [], activeGroupIndex = 0, activeGroupName = "") {
    isBoostRunningLocally = isRunning;
    if (remainingSec > 0) localBoostRemainingSec = remainingSec;
    if (typeof activeGroupIndex === 'number') localActiveGroupIndex = activeGroupIndex;
    
    const badge = document.getElementById('boostStatusBadge');
    const timerWrapper = document.getElementById('boostCountdownWrapper');
    const timer = document.getElementById('boostCountdown');
    const navDot = document.getElementById('navDotBoost');
    const liveInfoBox = document.getElementById('boostLiveInfoBox');
    const liveDetail = document.getElementById('boostLiveDetail');
    const activeNameEl = document.getElementById('boostGroupActiveName');
    
    if (isRunning) {
        if (badge) {
            badge.className = "badge-status badge-active";
            badge.innerHTML = `<span class="pulse-dot-green"></span> Đang Hoạt Động (${runningCount > 1 ? `${runningCount} Shop` : 'Tự Động 4h'})`;
        }
        if (timerWrapper) timerWrapper.style.display = "inline-flex";
        if (navDot) navDot.style.display = "inline-block";
        if (liveInfoBox) liveInfoBox.style.display = "block";
        
        const gName = activeGroupName || (currentBoostGroups[localActiveGroupIndex]?.name || `Nhóm ${localActiveGroupIndex + 1}`);
        if (activeNameEl) activeNameEl.textContent = gName;
        if (liveDetail) {
            liveDetail.textContent = `Đang đẩy ${gName}, đếm ngược 4 tiếng để tự động đổi nhóm tiếp theo...`;
        }
        
        if (timer) {
            if (localBoostRemainingSec > 0) {
                const h = Math.floor(localBoostRemainingSec / 3600).toString().padStart(2, '0');
                const m = Math.floor((localBoostRemainingSec % 3600) / 60).toString().padStart(2, '0');
                const s = (localBoostRemainingSec % 60).toString().padStart(2, '0');
                timer.textContent = `${h}:${m}:${s}`;
            } else {
                timer.textContent = "Đang đẩy...";
            }
        }
    } else {
        if (badge) {
            badge.className = "badge-status badge-inactive";
            badge.textContent = "⚪ Đang dừng";
        }
        if (timerWrapper) timerWrapper.style.display = "none";
        if (navDot) navDot.style.display = "none";
        if (liveInfoBox) liveInfoBox.style.display = "none";
        if (timer) timer.textContent = "--:--:--";
    }
    
    updateBoostPipelineActiveState(isRunning, localActiveGroupIndex);
}

function updateFlashSaleUI(isRunning, currentShopName = "", statusMessage = "") {
    const badge = document.getElementById('flashsaleStatusBadge');
    const navDot = document.getElementById('navDotFlashSale');
    const liveInfoBox = document.getElementById('flashsaleLiveInfoBox');
    const liveDetail = document.getElementById('flashsaleLiveDetail');
    
    if (isRunning) {
        if (badge) {
            badge.className = "badge-status badge-active";
            badge.innerHTML = `<span class="pulse-dot-amber"></span> Đang tạo Flash Sale`;
        }
        if (navDot) navDot.style.display = "inline-block";
        if (liveInfoBox) liveInfoBox.style.display = "block";
        if (liveDetail) {
            liveDetail.textContent = statusMessage || (currentShopName ? `Đang tạo chiến dịch Flash Sale cho Shop ${currentShopName}...` : 'Đang thực thi...');
        }
    } else {
        if (badge) {
            badge.className = "badge-status badge-inactive";
            badge.textContent = "⚪ Sẵn sàng";
        }
        if (navDot) navDot.style.display = "none";
        if (liveInfoBox) liveInfoBox.style.display = "none";
    }
}

function updatePosterUI(isRunning, totalVideos = 0, completedVideos = 0, currentVideo = "") {
    const badge = document.getElementById('posterStatusBadge');
    const progressBadge = document.getElementById('posterProgressBadge');
    const progressText = document.getElementById('posterProgressText');
    const navDot = document.getElementById('navDotPoster');
    const liveInfoBox = document.getElementById('posterLiveInfoBox');
    const liveDetail = document.getElementById('posterLiveDetail');
    
    if (isRunning) {
        if (badge) {
            badge.className = "badge-status badge-active";
            badge.innerHTML = `<span class="pulse-dot-green"></span> Đang đăng video`;
        }
        if (navDot) navDot.style.display = "inline-block";
        if (progressBadge) progressBadge.style.display = "inline-flex";
        if (progressText) progressText.textContent = `${completedVideos}/${totalVideos} video`;
        if (liveInfoBox) liveInfoBox.style.display = "block";
        if (liveDetail) {
            liveDetail.textContent = currentVideo ? `Đang đăng file: ${currentVideo} (${completedVideos}/${totalVideos})` : `Đang tiến hành đăng video...`;
        }
    } else {
        if (badge) {
            badge.className = "badge-status badge-inactive";
            badge.textContent = "⚪ Sẵn sàng";
        }
        if (navDot) navDot.style.display = "none";
        if (progressBadge) progressBadge.style.display = "none";
        if (liveInfoBox) liveInfoBox.style.display = "none";
    }
}

function updateChatUI(isRunning, runningCount = 0) {
    const chatBadge = document.getElementById('chatStatusBadge');
    const navDot = document.getElementById('navDotChat');
    
    if (isRunning) {
        if (chatBadge) {
            chatBadge.className = "badge-status badge-active";
            chatBadge.innerHTML = `<span class="pulse-dot-green"></span> Đang trực 24/7 (${runningCount > 1 ? `${runningCount} Shop` : 'Online'})`;
        }
        if (navDot) navDot.style.display = "inline-block";
    } else {
        if (chatBadge) {
            chatBadge.className = "badge-status badge-inactive";
            chatBadge.textContent = "⚪ Chưa bật";
        }
        if (navDot) navDot.style.display = "none";
    }
}

function updateGlobalHeaderBadge(runningList) {
    const globalBadge = document.getElementById('globalActivityBadge');
    const globalDot = document.getElementById('globalActivityDot');
    const globalText = document.getElementById('globalActivityText');
    if (!globalBadge || !globalDot || !globalText) return;
    
    if (runningList && runningList.length > 0) {
        globalBadge.className = "global-activity-badge";
        globalDot.className = "pulse-dot-green";
        globalText.textContent = `⚡ Đang chạy: ${runningList.join(', ')}`;
    } else {
        globalBadge.className = "global-activity-badge idle";
        globalDot.className = "pulse-dot-gray";
        globalText.textContent = "⚪ Hệ thống sẵn sàng";
    }
}

function startStatusPolling() {
    // 1. Đồng hồ đếm ngược từng giây độc lập trên client
    setInterval(() => {
        if (isBoostRunningLocally && localBoostRemainingSec > 0) {
            localBoostRemainingSec--;
            const timer = document.getElementById('boostCountdown');
            if (timer) {
                const h = Math.floor(localBoostRemainingSec / 3600).toString().padStart(2, '0');
                const m = Math.floor((localBoostRemainingSec % 3600) / 60).toString().padStart(2, '0');
                const s = (localBoostRemainingSec % 60).toString().padStart(2, '0');
                timer.textContent = `${h}:${m}:${s}`;
            }
        }
    }, 1000);

    // 2. Định kỳ 2.5s truy vấn trạng thái thực tế từ Backend
    const pollAllStatuses = async () => {
        try {
            const [boostRes, fsRes, upRes, chatRes] = await Promise.allSettled([
                fetch("/api/boost/status").then(r => r.json()),
                fetch("/api/flashsale/status").then(r => r.json()),
                fetch("/api/uploader/status").then(r => r.json()),
                fetch("/api/chat/status").then(r => r.json())
            ]);
            
            const runningTasks = [];
            
            // Auto Boost
            if (boostRes.status === "fulfilled" && boostRes.value) {
                const b = boostRes.value;
                updateBoostUI(b.is_running, b.remaining_seconds, b.running_count, b.running_accounts, b.active_group_index, b.active_group_name);
                if (b.is_running) runningTasks.push(`Auto Boost 4h${b.running_count > 1 ? ` (${b.running_count} Shop)` : ''}`);
            }
            
            // Auto Flash Sale
            if (fsRes.status === "fulfilled" && fsRes.value) {
                const fs = fsRes.value;
                updateFlashSaleUI(fs.is_running, fs.current_shop_name, fs.status_message);
                if (fs.is_running) runningTasks.push(`Flash Sale${fs.current_shop_name ? ` (${fs.current_shop_name})` : ''}`);
            }
            
            // Video Poster
            if (upRes.status === "fulfilled" && upRes.value) {
                const up = upRes.value;
                updatePosterUI(up.is_running, up.total_videos, up.completed_videos, up.current_video);
                if (up.is_running) runningTasks.push("Đăng Video");
            }
            
            // AI Chatbot
            if (chatRes.status === "fulfilled" && chatRes.value) {
                const ch = chatRes.value;
                updateChatUI(ch.is_running, ch.running_count);
                if (ch.is_running) runningTasks.push("AI Chatbot");
            }
            
            // Cập nhật Header Badge
            updateGlobalHeaderBadge(runningTasks);
            
            // Cập nhật Chat History
            chatPollCounter++;
            if (chatPollCounter % 3 === 0) {
                loadChatHistory();
            }
        } catch(e) {}
    };

    // Chạy ngay lần đầu và đặt interval 2.5s
    pollAllStatuses();
    setInterval(pollAllStatuses, 2500);
}
