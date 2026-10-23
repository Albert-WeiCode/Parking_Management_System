const menuButton = document.getElementById("menuButton");
const sidebar = document.getElementById("sidebar");

if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => sidebar.classList.toggle("open"));
    document.addEventListener("click", (event) => {
        if (window.innerWidth <= 820 && sidebar.classList.contains("open") &&
            !sidebar.contains(event.target) && !menuButton.contains(event.target)) {
            sidebar.classList.remove("open");
        }
    });
}

function drawBarChart(id, data) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    const render = () => {
        const ratio = window.devicePixelRatio || 1;
        const width = canvas.clientWidth;
        const height = 250;
        canvas.width = width * ratio;
        canvas.height = height * ratio;
        const ctx = canvas.getContext("2d");
        ctx.scale(ratio, ratio);
        ctx.clearRect(0, 0, width, height);

        const padding = { top: 18, right: 12, bottom: 34, left: 32 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;
        const max = Math.max(1, ...data.map((item) => Number(item.count)));
        const step = chartWidth / Math.max(1, data.length);
        const barWidth = Math.min(42, step * 0.54);

        ctx.strokeStyle = "#e4e8e6";
        ctx.fillStyle = "#77817c";
        ctx.font = '11px "PingFang SC", sans-serif';
        ctx.textAlign = "right";
        for (let line = 0; line <= 4; line += 1) {
            const y = padding.top + chartHeight * line / 4;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.stroke();
            ctx.fillText(String(Math.round(max * (4 - line) / 4)), padding.left - 7, y + 4);
        }

        data.forEach((item, index) => {
            const value = Number(item.count);
            const barHeight = value / max * chartHeight;
            const x = padding.left + step * index + (step - barWidth) / 2;
            const y = padding.top + chartHeight - barHeight;
            ctx.fillStyle = index === data.length - 1 ? "#10b9a5" : "#3978f6";
            ctx.fillRect(x, y, barWidth, barHeight);
            ctx.fillStyle = "#69736f";
            ctx.textAlign = "center";
            ctx.fillText(item.label, x + barWidth / 2, height - 10);
        });
    };
    render();
    window.addEventListener("resize", render);
}

function escapeHtml(value) {
    const node = document.createElement("div");
    node.textContent = value ?? "";
    return node.innerHTML.replace(/"/g, "&quot;");
}

function userErrorMessage(error, fallback = "操作失败，请重试") {
    return /[\u4e00-\u9fff]/.test(error.message || "") ? error.message : fallback;
}

function renderDetectionResult(container, data) {
    if (!data.results || data.results.length === 0) {
        container.innerHTML = '<div class="empty-state tall">当前画面未检测到车牌</div>';
        return;
    }
    const items = data.results.map((item, index) => {
        const detectConfidence = Number(item.detection_confidence || 0) * 100;
        const ocrConfidence = Number(item.ocr_confidence || 0) * 100;
        return `<article class="result-item">
            <header><span>车牌 ${index + 1}</span><strong>${escapeHtml(item.plate_number || "识别失败")}</strong></header>
            <dl><div><dt>车牌颜色</dt><dd>${escapeHtml(item.plate_color || "未知")} (${(Number(item.color_confidence || 0) * 100).toFixed(1)}%)</dd></div><div><dt>检测置信度</dt><dd>${detectConfidence.toFixed(1)}%</dd></div><div><dt>字符置信度</dt><dd>${ocrConfidence.toFixed(1)}%</dd></div></dl>
            <form class="access-form">
                <label>核对车牌号码<input name="plate_number" value="${escapeHtml(item.plate_number || "")}" maxlength="8" required></label>
                <div class="action-row"><button class="button primary small" data-operation="entry" type="submit">确认入场 ↘</button><button class="button secondary small" data-operation="exit" type="submit">确认出场 ↗</button></div>
                <p class="access-message" role="status"></p>
            </form>
        </article>`;
    }).join("");
    const image = data.result_image ? `<img class="result-image" src="${encodeURI(data.result_image)}" alt="检测结果">` : "";
    container.innerHTML = `${image}<div class="result-list">${items}</div>`;
}


// Shared by image and camera recognition results. Registration requires a click.
document.addEventListener("focusin", (event) => {
    if (event.target.closest(".access-form")) {
        const automatic = document.getElementById("autoDetect");
        if (automatic) { automatic.checked = false; automatic.dispatchEvent(new Event("change")); }
    }
});
document.addEventListener("submit", async (event) => {
    const form = event.target.closest(".access-form");
    if (!form) return;
    event.preventDefault();
    const operation = event.submitter?.dataset.operation;
    if (!["entry", "exit"].includes(operation)) return;
    const buttons = form.querySelectorAll("button");
    buttons.forEach((button) => button.disabled = true);
    const message = form.querySelector(".access-message");
    message.textContent = "正在登记…";
    const body = new FormData(form);
    body.append("source", location.pathname.includes("camera") ? "摄像头识别" : "图片识别");
    try {
        const response = await fetch(`/api/records/${operation}`, {method: "POST", headers: {Accept: "application/json"}, body});
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || "登记失败");
        message.className = "access-message success-text";
        message.textContent = data.message;
    } catch (error) {
        message.className = "access-message error-text";
        message.textContent = userErrorMessage(error, "登记失败，请检查网络后重试");
    } finally { buttons.forEach((button) => button.disabled = false); }
});
