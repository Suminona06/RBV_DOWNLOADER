// UT-RBV Downloader Web Client

let currentBook = null;
let activeTaskId = null;
let pollInterval = null;

// Elements
const inspectForm = document.getElementById("inspectForm");
const bookCodeInput = document.getElementById("bookCode");
const cookieInput = document.getElementById("cookieInput");
const usernameInput = document.getElementById("usernameInput");
const passwordInput = document.getElementById("passwordInput");
const compressSelect = document.getElementById("compressLevel");
const mergeSelect = document.getElementById("mergeMode");

const btnInspect = document.getElementById("btnInspect");
const emptyState = document.getElementById("emptyState");
const bookBanner = document.getElementById("bookBanner");
const displayBookTitle = document.getElementById("displayBookTitle");
const displayBookMeta = document.getElementById("displayBookMeta");
const modulesList = document.getElementById("modulesList");
const moduleActions = document.getElementById("moduleActions");
const downloadFooter = document.getElementById("downloadFooter");
const btnStartDownload = document.getElementById("btnStartDownload");

const btnSelectAll = document.getElementById("btnSelectAll");
const btnDeselectAll = document.getElementById("btnDeselectAll");

const progressCard = document.getElementById("progressCard");
const progressTitle = document.getElementById("progressTitle");
const progressSubtitle = document.getElementById("progressSubtitle");
const progressPercentage = document.getElementById("progressPercentage");
const progressBarFill = document.getElementById("progressBarFill");
const terminalLog = document.getElementById("terminalLog");
const downloadResult = document.getElementById("downloadResult");
const resultButtons = document.getElementById("resultButtons");

// 1. Inspect Book Event
inspectForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const code = bookCodeInput.value.trim().toUpperCase();
    if (!code) return;

    btnInspect.disabled = true;
    btnInspect.querySelector(".btn-text").textContent = "Memeriksa...";

    try {
        const payload = {
            code: code,
            cookie: cookieInput.value.trim() || null,
            username: usernameInput.value.trim() || null,
            password: passwordInput.value || null,
        };

        const res = await fetch("/api/inspect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Gagal mengambil metadata buku.");
        }

        currentBook = data;
        renderBookDetails(data);
    } catch (err) {
        alert("Error: " + err.message);
    } finally {
        btnInspect.disabled = false;
        btnInspect.querySelector(".btn-text").textContent = "Periksa Buku";
    }
});

// 2. Render Book Modules
function renderBookDetails(book) {
    emptyState.classList.add("hidden");
    bookBanner.classList.remove("hidden");
    modulesList.classList.remove("hidden");
    moduleActions.classList.remove("hidden");
    downloadFooter.classList.remove("hidden");

    displayBookTitle.textContent = `${book.code} - ${book.title}`;
    displayBookMeta.textContent = `Total: ${book.sections.length} Bagian / Modul • Estimasi ${book.total_pages || '?'} Halaman`;

    modulesList.innerHTML = "";
    book.sections.forEach((sec, idx) => {
        const item = document.createElement("div");
        item.className = "module-item";

        const left = document.createElement("div");
        left.className = "module-item-left";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.id = `mod_${sec.doc_id}`;
        checkbox.value = sec.doc_id;
        checkbox.checked = true; // default all checked

        const label = document.createElement("label");
        label.htmlFor = `mod_${sec.doc_id}`;
        label.textContent = sec.title;

        left.appendChild(checkbox);
        left.appendChild(label);

        const badge = document.createElement("span");
        badge.className = "module-badge";
        badge.textContent = sec.total_pages > 0 ? `${sec.total_pages} hlm` : sec.doc_id;

        item.appendChild(left);
        item.appendChild(badge);
        modulesList.appendChild(item);
    });
}

// 3. Selection Helpers
btnSelectAll.addEventListener("click", () => {
    document.querySelectorAll(".module-item input[type='checkbox']").forEach(cb => cb.checked = true);
});

btnDeselectAll.addEventListener("click", () => {
    document.querySelectorAll(".module-item input[type='checkbox']").forEach(cb => cb.checked = false);
});

// 4. Start Download Event
btnStartDownload.addEventListener("click", async () => {
    if (!currentBook) return;

    const selectedDocIds = Array.from(
        document.querySelectorAll(".module-item input[type='checkbox']:checked")
    ).map(cb => cb.value);

    if (selectedDocIds.length === 0) {
        alert("Pilih minimal satu modul untuk diunduh!");
        return;
    }

    const payload = {
        code: currentBook.code,
        doc_ids: selectedDocIds,
        merge: mergeSelect.value === "true",
        compress: compressSelect.value,
        cookie: cookieInput.value.trim() || null,
        username: usernameInput.value.trim() || null,
        password: passwordInput.value || null,
    };

    btnStartDownload.disabled = true;
    progressCard.classList.remove("hidden");
    downloadResult.classList.add("hidden");
    resultButtons.innerHTML = "";
    appendLog(`Memulai antrean unduhan untuk buku ${currentBook.code}...`);

    try {
        const res = await fetch("/api/download", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Gagal memulai tugas unduhan.");
        }

        activeTaskId = data.task_id;
        startPollingProgress(activeTaskId);
    } catch (err) {
        alert("Gagal mengunduh: " + err.message);
        btnStartDownload.disabled = false;
    }
});

// 5. Polling Progress
function startPollingProgress(taskId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/progress/${taskId}`);
            if (!res.ok) return;

            const state = await res.json();
            updateProgressUI(state);

            if (state.status === "completed") {
                clearInterval(pollInterval);
                btnStartDownload.disabled = false;
                onDownloadCompleted(state);
            } else if (state.status === "failed") {
                clearInterval(pollInterval);
                btnStartDownload.disabled = false;
                progressTitle.textContent = "Pengunduhan Gagal";
                appendLog(`[ERROR] ${state.error_message || 'Terjadi kesalahan sistem.'}`);
            }
        } catch (e) {
            console.error("Gagal memeriksa progres:", e);
        }
    }, 600);
}

function updateProgressUI(state) {
    const percent = Math.min(100, Math.round(state.percentage || 0));
    progressPercentage.textContent = `${percent}%`;
    progressBarFill.style.width = `${percent}%`;

    progressTitle.textContent = state.current_stage || "Sedang Mengunduh Aset...";
    progressSubtitle.textContent = `Progres: ${state.completed_pages || 0} dari ${state.total_pages || '?'} halaman`;

    if (state.latest_log) {
        appendLog(state.latest_log);
    }
}

function appendLog(text) {
    const line = document.createElement("div");
    line.className = "log-line";
    const time = new Date().toLocaleTimeString();
    line.textContent = `[${time}] ${text}`;
    terminalLog.appendChild(line);
    terminalLog.scrollTop = terminalLog.scrollHeight;
}

function onDownloadCompleted(state) {
    progressTitle.textContent = "Selesai!";
    progressSubtitle.textContent = "Seluruh dokumen telah berhasil disusun ke dalam file PDF.";
    downloadResult.classList.remove("hidden");

    resultButtons.innerHTML = "";
    (state.generated_files || []).forEach(file => {
        const btn = document.createElement("a");
        btn.href = `/api/files/${encodeURIComponent(file.filename)}`;
        btn.download = file.filename;
        btn.className = "btn btn-success";
        btn.textContent = `Unduh ${file.filename}`;
        resultButtons.appendChild(btn);
    });
}
