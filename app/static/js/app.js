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
            ctx.fillStyle = index === data.length - 1 ? "#c47721" : "#1e7050";
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
    return node.innerHTML;
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
            <dl><div><dt>检测置信度</dt><dd>${detectConfidence.toFixed(1)}%</dd></div><div><dt>字符置信度</dt><dd>${ocrConfidence.toFixed(1)}%</dd></div></dl>
        </article>`;
    }).join("");
    const image = data.result_image ? `<img class="result-image" src="${encodeURI(data.result_image)}" alt="检测结果">` : "";
    container.innerHTML = `${image}<div class="result-list">${items}</div>`;
}
