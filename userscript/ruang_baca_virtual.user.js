// ==UserScript==
// @name         Ruang Baca Virtual Downloader
// @namespace    http://tampermonkey.net/
// @version      3.1
// @description  Unduh materi modul dari Ruang Baca Virtual (RBV) UT langsung dari browser tanpa terblokir firewall.
// @author       deoffuscated (enhanced for UT-RBV)
// @match        https://pustaka.ut.ac.id/*
// @grant        none
// @license      MIT
// ==/UserScript==

(function () {
    'use strict';

    const DEFAULT_SETTINGS = {
        concurrency: 3, // Safe concurrency for F5 WAF
        maxPage: 1000
    };

    let currentSettings = { ...DEFAULT_SETTINGS };

    try {
        const savedSettings = localStorage.getItem('rbv-scraper-settings');
        if (savedSettings) {
            currentSettings = { ...DEFAULT_SETTINGS, ...JSON.parse(savedSettings) };
        }
    } catch (e) {}

    const existingWrapper = document.getElementById('rbv-scraper-wrapper');
    if (existingWrapper) existingWrapper.remove();

    const existingStyle = document.getElementById('rbv-scraper-style');
    if (existingStyle) existingStyle.remove();

    const navLinks = document.querySelectorAll('nav.sidebar-nav a');
    if (navLinks.length === 0) return;

    const style = document.createElement('style');
    style.id = 'rbv-scraper-style';
    style.innerHTML = `
        :root {
            --rbv-primary: #1a56db;
            --rbv-primary-hover: #1e40af;
            --rbv-accent: #f59e0b;
            --rbv-surface: rgba(255, 255, 255, 0.92);
            --rbv-surface-hover: rgba(255, 255, 255, 0.98);
            --rbv-text-main: #1e293b;
            --rbv-text-muted: #64748b;
            --rbv-border: rgba(255, 255, 255, 0.6);
            --rbv-shadow: 0 10px 40px -10px rgba(26, 86, 219, 0.25);
            --rbv-blur: blur(20px);
        }

        .header-watermark-container,
        #wm-overlay,
        .rbv-watermark-overlay {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
            z-index: -9999 !important;
        }

        #rbv-scraper-wrapper {
            position: fixed;
            z-index: 999999;
            bottom: 30px;
            left: 30px;
            font-family: 'Inter', -apple-system, system-ui, sans-serif;
        }

        #rbv-widget-trigger {
            position: absolute;
            bottom: 0;
            left: 0;
            z-index: 1;
            width: 54px;
            height: 54px;
            border-radius: 50%;
            background: #ffffff;
            border: 2px solid #1a56db;
            box-shadow: 0 0 0 0 rgba(26, 86, 219, 0.4), var(--rbv-shadow);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            padding: 8px;
            box-sizing: border-box;
            animation: rbv-pulse 2s infinite;
        }

        @keyframes rbv-pulse {
            0% { box-shadow: 0 0 0 0 rgba(26, 86, 219, 0.4), var(--rbv-shadow); }
            70% { box-shadow: 0 0 0 15px rgba(26, 86, 219, 0), var(--rbv-shadow); }
            100% { box-shadow: 0 0 0 0 rgba(26, 86, 219, 0), var(--rbv-shadow); }
        }

        #rbv-widget-trigger:hover {
            transform: scale(1.08) translateY(-4px);
            animation: none;
        }

        #rbv-widget-trigger img {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }

        #rbv-widget-trigger.is-open {
            transform: scale(0.4) !important;
            opacity: 0;
            pointer-events: none;
            animation: none;
        }

        #rbv-main-panel {
            position: absolute;
            bottom: 0;
            left: 0;
            z-index: 2;
            background: var(--rbv-surface);
            backdrop-filter: var(--rbv-blur);
            -webkit-backdrop-filter: var(--rbv-blur);
            border: 1px solid var(--rbv-border);
            box-shadow: var(--rbv-shadow), 0 0 0 1px rgba(255,255,255,0.5) inset;
            border-radius: 20px;
            width: 350px;
            display: flex;
            flex-direction: column;
            max-height: 75vh;
            overflow: hidden;
            transform-origin: 24px calc(100% - 24px);
            transform: scale(0.4);
            opacity: 0;
            pointer-events: none;
            transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
        }

        #rbv-main-panel.active {
            transform: scale(1);
            opacity: 1;
            pointer-events: auto;
        }

        .rbv-header {
            padding: 16px 20px;
            border-bottom: 1px solid rgba(0,0,0,0.06);
            background: linear-gradient(180deg, rgba(255,255,255,0.8) 0%, rgba(255,255,255,0.4) 100%);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }

        .rbv-title {
            font-weight: 800;
            color: var(--rbv-primary);
            font-size: 15px;
            margin: 0;
        }

        .rbv-header-actions {
            display: flex;
            gap: 6px;
            align-items: center;
        }

        .rbv-action-btn {
            background: rgba(0,0,0,0.05);
            border: none;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: 0.2s;
            color: var(--rbv-text-muted);
            padding: 0;
        }

        .rbv-action-btn:hover {
            background: rgba(26, 86, 219, 0.15);
            color: var(--rbv-primary);
        }

        .rbv-content {
            padding: 12px 16px;
            overflow-y: auto;
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .rbv-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 11px 14px;
            background: rgba(255,255,255,0.7);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.8);
            cursor: pointer;
            transition: all 0.2s ease;
            color: var(--rbv-text-main);
            font-weight: 600;
            font-size: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.02);
        }

        .rbv-item:hover {
            background: #fff;
            transform: translateY(-2px);
            color: var(--rbv-primary);
            border-color: rgba(26, 86, 219, 0.3);
            box-shadow: 0 6px 15px rgba(26, 86, 219, 0.08);
        }

        .rbv-item-icon {
            background: rgba(26, 86, 219, 0.1);
            color: var(--rbv-primary);
            width: 26px;
            height: 26px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: 0.3s;
            flex-shrink: 0;
        }

        .rbv-item:hover .rbv-item-icon {
            background: var(--rbv-primary);
            color: white;
        }

        .rbv-item svg {
            width: 14px;
            height: 14px;
            stroke: currentColor;
            stroke-width: 2.5;
            fill: none;
        }

        .rbv-progress-section {
            padding: 14px 20px;
            background: rgba(255,255,255,0.8);
            border-top: 1px solid rgba(0,0,0,0.05);
            display: none;
            flex-shrink: 0;
        }

        .rbv-prog-labels {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: var(--rbv-text-muted);
            margin-bottom: 8px;
            font-weight: 600;
        }

        .rbv-prog-status {
            color: var(--rbv-primary);
            font-weight: 700;
        }

        .rbv-prog-track {
            width: 100%;
            height: 6px;
            background: rgba(0,0,0,0.08);
            border-radius: 4px;
            overflow: hidden;
        }

        .rbv-prog-bar {
            height: 100%;
            background: linear-gradient(90deg, var(--rbv-primary), #3b82f6);
            width: 0%;
            transition: width 0.3s ease;
        }

        .rbv-footer-action {
            padding: 14px 20px;
            background: rgba(255,255,255,0.85);
            border-top: 1px solid rgba(0,0,0,0.05);
            flex-shrink: 0;
        }

        .btn-download-all {
            width: 100%;
            padding: 12px 16px;
            border: none;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--rbv-primary) 0%, var(--rbv-primary-hover) 100%);
            color: white;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            box-shadow: 0 4px 15px rgba(26, 86, 219, 0.3);
            transition: all 0.2s ease;
        }

        .btn-download-all:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(26, 86, 219, 0.4);
        }

        .btn-download-all:disabled {
            background: #cbd5e1;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
            color: #64748b;
        }

        .rbv-modal-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(248, 250, 252, 0.6);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            z-index: 100;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
            border-radius: inherit;
        }

        .rbv-modal-overlay.show {
            opacity: 1;
            pointer-events: auto;
        }

        .rbv-modal-box {
            background: rgba(255, 255, 255, 0.98);
            width: 88%;
            padding: 22px 18px;
            border-radius: 16px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.12);
            border: 1px solid rgba(26, 86, 219, 0.15);
            text-align: center;
            box-sizing: border-box;
        }

        .rbv-modal-title {
            font-size: 15px;
            font-weight: 800;
            color: var(--rbv-text-main);
            margin-bottom: 8px;
        }

        .rbv-modal-text {
            font-size: 12px;
            color: var(--rbv-text-muted);
            margin-bottom: 18px;
            line-height: 1.5;
            white-space: pre-wrap;
        }

        .rbv-modal-actions {
            display: flex;
            gap: 8px;
            justify-content: center;
        }

        .rbv-btn {
            flex: 1;
            padding: 9px 0;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
        }

        .rbv-btn-cancel {
            background: #f1f5f9;
            color: var(--rbv-text-muted);
        }

        .rbv-btn-confirm {
            background: var(--rbv-primary);
            color: white;
        }

        .rbv-spinner {
            animation: rbv-spin 1s linear infinite;
        }

        @keyframes rbv-spin {
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);

    // Watermark cleaner
    const cleanWatermark = () => {
        document.querySelectorAll('.header-watermark-container, #wm-overlay, .rbv-watermark-overlay').forEach(el => el.remove());
    };
    cleanWatermark();
    new MutationObserver(cleanWatermark).observe(document.body, { childList: true, subtree: true });

    // Build UI Elements
    const wrapper = document.createElement('div');
    wrapper.id = 'rbv-scraper-wrapper';

    const trigger = document.createElement('div');
    trigger.id = 'rbv-widget-trigger';
    trigger.innerHTML = `<img src="https://suopmkm.ut.ac.id/uo/statics/logo.png" alt="RBV Logo">`;

    const panel = document.createElement('div');
    panel.id = 'rbv-main-panel';
    panel.innerHTML = `
        <div class="rbv-header">
            <h3 class="rbv-title">RBV In-Browser Downloader</h3>
            <button class="rbv-action-btn" id="rbv-btn-min" title="Tutup">
                <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2.5" fill="none"><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            </button>
        </div>
        <div class="rbv-content" id="rbv-list-container"></div>
        <div class="rbv-progress-section" id="rbv-prog-container">
            <div class="rbv-prog-labels">
                <span id="rbv-prog-status" class="rbv-prog-status">Menyiapkan...</span>
                <span id="rbv-prog-percent">0%</span>
            </div>
            <div class="rbv-prog-track">
                <div class="rbv-prog-bar" id="rbv-prog-fill"></div>
            </div>
        </div>
        <div class="rbv-footer-action">
            <button class="btn-download-all" id="btn-dl-all">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                <span>Download Semua Modul</span>
            </button>
        </div>
        <div class="rbv-modal-overlay" id="rbv-custom-modal">
            <div class="rbv-modal-box">
                <div class="rbv-modal-title" id="rbv-modal-title">Konfirmasi</div>
                <div class="rbv-modal-text" id="rbv-modal-text">Pesan...</div>
                <div class="rbv-modal-actions">
                    <button class="rbv-btn rbv-btn-cancel" id="rbv-modal-cancel">Batal</button>
                    <button class="rbv-btn rbv-btn-confirm" id="rbv-modal-ok">Lanjutkan</button>
                </div>
            </div>
        </div>
    `;

    wrapper.appendChild(panel);
    wrapper.appendChild(trigger);
    document.body.appendChild(wrapper);

    let isOpen = false;
    function togglePanel() {
        isOpen = !isOpen;
        if (isOpen) {
            panel.classList.add('active');
            trigger.classList.add('is-open');
        } else {
            panel.classList.remove('active');
            trigger.classList.remove('is-open');
        }
    }

    trigger.addEventListener('click', togglePanel);
    document.getElementById('rbv-btn-min').addEventListener('click', togglePanel);

    // Modal logic
    let confirmCallback = null;
    const modalOverlay = document.getElementById('rbv-custom-modal');
    const modalTitle = document.getElementById('rbv-modal-title');
    const modalText = document.getElementById('rbv-modal-text');
    const btnCancel = document.getElementById('rbv-modal-cancel');
    const btnOk = document.getElementById('rbv-modal-ok');

    function showDialog(title, message, onConfirm) {
        modalTitle.innerText = title;
        modalText.innerText = message;
        confirmCallback = onConfirm;
        modalOverlay.classList.add('show');
    }

    function hideDialog() {
        modalOverlay.classList.remove('show');
        confirmCallback = null;
    }

    btnCancel.onclick = hideDialog;
    btnOk.onclick = () => {
        if (confirmCallback) confirmCallback();
        hideDialog();
    };

    // Scan navLinks
    const listContainer = document.getElementById('rbv-list-container');
    const allModules = [];
    let globalCourseName = "Materi UT-RBV";

    const iconDownload = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`;
    const iconSpinner = `<svg class="rbv-spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line></svg>`;

    navLinks.forEach((link, index) => {
        const href = link.getAttribute('href');
        if (!href || href.includes('javascript:')) return;

        const urlParams = new URLSearchParams(href.split('?')[1]);
        const subfolder = urlParams.get('subfolder');
        let docName = urlParams.get('doc');
        let label = link.innerText.trim() || docName;

        if (subfolder && docName) {
            const docId = docName.replace('.pdf', '');
            const itemData = { subfolder, docId, label };
            allModules.push(itemData);

            if (globalCourseName === "Materi UT-RBV") {
                globalCourseName = subfolder.replace(/\/$/, '');
            }

            const btn = document.createElement('div');
            btn.className = 'rbv-item';
            btn.innerHTML = `<span>${label}</span><div class="rbv-item-icon" id="icon-${docId}">${iconDownload}</div>`;
            btn.onclick = () => {
                showDialog("Unduh Modul", `Mulai unduh modul "${label}"?`, () => startDownload([itemData]));
            };
            listContainer.appendChild(btn);
        }
    });

    document.getElementById('btn-dl-all').addEventListener('click', () => {
        if (allModules.length > 0) {
            showDialog('Unduh Semua Modul', `Proses ini akan mengunduh ${allModules.length} modul.\nLanjutkan?`, () => startDownload(allModules));
        }
    });

    const baseUrl = `${window.location.origin}/reader/services/view.php`;

    function setProgress(msg, percent) {
        const progContainer = document.getElementById('rbv-prog-container');
        const statusEl = document.getElementById('rbv-prog-status');
        const pctEl = document.getElementById('rbv-prog-percent');
        const barEl = document.getElementById('rbv-prog-fill');

        progContainer.style.display = 'block';
        statusEl.innerText = msg;
        const safePct = Math.min(100, Math.max(0, percent));
        pctEl.innerText = Math.round(safePct) + '%';
        barEl.style.width = safePct + '%';
    }

    async function fetchImage(mod, pageNum) {
        const imgUrl = `${baseUrl}?doc=${mod.docId}&format=jpg&subfolder=${mod.subfolder}&page=${pageNum}`;
        try {
            const response = await fetch(imgUrl);
            if (!response.ok) return null;
            const blob = await response.blob();
            if (blob.size < 500) return null; // End of section or rejected
            return URL.createObjectURL(blob);
        } catch (e) {
            return null;
        }
    }

    async function startDownload(modulesList) {
        const btnAll = document.getElementById('btn-dl-all');
        btnAll.disabled = true;
        btnAll.innerHTML = `${iconSpinner} <span>Mengunduh...</span>`;

        let combinedHtml = "";
        const totalModules = modulesList.length;
        let pageTitle = globalCourseName;

        if (modulesList.length === 1) {
            pageTitle += ` - ${modulesList[0].label}`;
        }

        const activeConcurrency = currentSettings.concurrency; // 3 concurrent requests (safe)
        const activeMaxPage = currentSettings.maxPage;

        for (let mIdx = 0; mIdx < totalModules; mIdx++) {
            const mod = modulesList[mIdx];
            const validImages = [];
            let page = 1;
            let consecutiveErrors = 0;

            const itemIcon = document.getElementById(`icon-${mod.docId}`);
            if (itemIcon) itemIcon.innerHTML = iconSpinner;

            setProgress(`Membaca ${mod.label}...`, (mIdx / totalModules) * 100);

            while (page <= activeMaxPage) {
                const promises = [];
                for (let i = 0; i < activeConcurrency; i++) {
                    let targetPage = page + i;
                    if (targetPage <= activeMaxPage) {
                        promises.push(fetchImage(mod, targetPage));
                    }
                }

                if (promises.length === 0) break;

                const results = await Promise.all(promises);
                let batchHasData = false;

                for (let res of results) {
                    if (res) {
                        validImages.push(res);
                        batchHasData = true;
                        consecutiveErrors = 0;
                    } else {
                        consecutiveErrors++;
                    }
                }

                if (!batchHasData || consecutiveErrors >= activeConcurrency) break;
                page += activeConcurrency;
                setProgress(`${mod.label} (${validImages.length} hal)`, (mIdx / totalModules) * 100);

                // Small human delay between batches
                await new Promise(r => setTimeout(r, 200));
            }

            if (validImages.length > 0) {
                combinedHtml += `<div class="mod-section"><h2>${mod.label}</h2>`;
                validImages.forEach(blobUrl => {
                    combinedHtml += `<img src="${blobUrl}" loading="lazy" />`;
                });
                combinedHtml += `</div><div class="page-break"></div>`;
            }

            if (itemIcon) itemIcon.innerHTML = iconDownload;
        }

        setProgress("Selesai! Menyiapkan PDF...", 100);

        setTimeout(() => {
            generatePrintWindow(combinedHtml, pageTitle);
            document.getElementById('rbv-prog-container').style.display = 'none';
            btnAll.disabled = false;
            btnAll.innerHTML = `${iconDownload} <span>Download Semua Modul</span>`;
        }, 800);
    }

    function generatePrintWindow(content, title) {
        const html = `
            <!DOCTYPE html>
            <html>
            <head>
                <title>${title}</title>
                <style>
                    body { background: #f8fafc; margin: 0; padding: 30px 20px; font-family: 'Inter', system-ui, sans-serif; color: #1e293b; display: flex; flex-direction: column; align-items: center; }
                    .doc-container { max-width: 900px; width: 100%; }
                    .info-card { background: white; padding: 20px 25px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #e2e8f0; position: sticky; top: 20px; z-index: 100; }
                    .info-text h1 { margin: 0 0 5px 0; font-size: 18px; color: #0f172a; font-weight: 800; }
                    .info-text p { margin: 0; font-size: 13px; color: #64748b; }
                    .btn-print { background: #1a56db; color: white; border: none; padding: 12px 24px; border-radius: 10px; font-weight: 700; cursor: pointer; font-size: 14px; transition: 0.2s; box-shadow: 0 4px 12px rgba(26, 86, 219, 0.2); }
                    .btn-print:hover { background: #1e40af; transform: translateY(-2px); }
                    .mod-section { background: white; box-shadow: 0 10px 30px rgba(0,0,0,0.05); margin-bottom: 40px; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }
                    .mod-section h2 { background: #f1f5f9; padding: 15px 20px; margin: 0; font-size: 15px; border-bottom: 1px solid #e2e8f0; text-align: left; color: #475569; font-weight: 700; }
                    img { width: 100%; height: auto; display: block; margin: 0 auto; border-bottom: 1px solid #e2e8f0; }
                    img:last-child { border-bottom: none; }
                    @page { margin: 0; size: auto; }
                    @media print { body { background: white; padding: 0; margin: 0; } .info-card { display: none; } .mod-section { box-shadow: none; margin: 0; border: none; border-radius: 0; } .mod-section h2 { display: none; } .page-break { page-break-after: always; } img { page-break-inside: avoid; margin: 0; width: 100%; max-width: 100%; border: none; } }
                </style>
            </head>
            <body>
                <div class="doc-container">
                    <div class="info-card">
                        <div class="info-text">
                            <h1>${title}</h1>
                            <p>Klik tombol Simpan PDF atau tekan Ctrl+P untuk menyimpan sebagai file PDF utuh.</p>
                        </div>
                        <button class="btn-print" onclick="window.print()">Simpan PDF</button>
                    </div>
                    ${content}
                </div>
            </body>
            </html>
        `;

        const win = window.open('', '_blank');
        if (!win) {
            alert('Pop-up diblokir browser. Izinkan pop-up di browser Anda agar file PDF bisa dibuka.');
            return;
        }
        win.document.write(html);
        win.document.close();
    }
})();
