const imageInput = document.getElementById("imageInput");
const dropZone = document.getElementById("dropZone");
const imageStage = document.getElementById("imageStage");
const preview = document.getElementById("preview");
const detectButton = document.getElementById("detectButton");
const resetButton = document.getElementById("resetButton");
const loading = document.getElementById("loading");
const result = document.getElementById("result");
let selectedFile = null;
let previewUrl = null;

function chooseFile(file) {
    if (imageInput.disabled || !file || !file.type.startsWith("image/")) return;
    selectedFile = file;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    imageStage.classList.remove("hidden");
    dropZone.classList.add("hidden");
    resetButton.classList.remove("hidden");
    detectButton.disabled = false;
    result.innerHTML = '<div class="empty-state tall">点击开始检测后显示结果</div>';
}

imageInput.addEventListener("change", () => chooseFile(imageInput.files[0]));
["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
}));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
}));
dropZone.addEventListener("drop", (event) => chooseFile(event.dataTransfer.files[0]));

resetButton.addEventListener("click", () => {
    selectedFile = null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    imageInput.value = "";
    preview.removeAttribute("src");
    imageStage.classList.add("hidden");
    dropZone.classList.remove("hidden");
    resetButton.classList.add("hidden");
    detectButton.disabled = true;
    result.innerHTML = '<div class="empty-state tall">检测结果将在这里显示</div>';
});

detectButton.addEventListener("click", async () => {
    if (!selectedFile) return;
    const formData = new FormData();
    formData.append("file", selectedFile);
    detectButton.disabled = true;
    loading.classList.remove("hidden");
    resetButton.disabled = true;
    imageInput.disabled = true;
    try {
        const response = await fetch("/api/detect/image", { method: "POST", body: formData });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || "检测失败");
        renderDetectionResult(result, data);
    } catch (error) {
        result.innerHTML = `<div class="alert error">${escapeHtml(userErrorMessage(error, "识别失败，请检查网络后重试"))}</div>`;
    } finally {
        detectButton.disabled = false;
        loading.classList.add("hidden");
        resetButton.disabled = false;
        imageInput.disabled = false;
    }
});
