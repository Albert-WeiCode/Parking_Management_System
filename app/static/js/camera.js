const video = document.getElementById("cameraVideo");
const placeholder = document.getElementById("cameraPlaceholder");
const canvas = document.getElementById("captureCanvas");
const startButton = document.getElementById("startCamera");
const captureButton = document.getElementById("captureFrame");
const stopButton = document.getElementById("stopCamera");
const cameraStatus = document.getElementById("cameraStatus");
const cameraLoading = document.getElementById("cameraLoading");
const cameraResult = document.getElementById("cameraResult");
let stream = null;

startButton.addEventListener("click", async () => {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        video.srcObject = stream;
        video.classList.add("active");
        placeholder.classList.add("hidden");
        startButton.classList.add("hidden");
        stopButton.classList.remove("hidden");
        captureButton.disabled = false;
        cameraStatus.textContent = "摄像头已启动";
    } catch (error) {
        cameraResult.innerHTML = `<div class="alert error">无法访问摄像头：${escapeHtml(error.message)}</div>`;
    }
});

stopButton.addEventListener("click", () => {
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    video.classList.remove("active");
    placeholder.classList.remove("hidden");
    startButton.classList.remove("hidden");
    stopButton.classList.add("hidden");
    captureButton.disabled = true;
    cameraStatus.textContent = "摄像头未启动";
});

captureButton.addEventListener("click", () => {
    if (!stream || !video.videoWidth) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    cameraLoading.classList.remove("hidden");
    captureButton.disabled = true;
    canvas.toBlob(async (blob) => {
        const formData = new FormData();
        formData.append("file", blob, "camera-frame.jpg");
        try {
            const response = await fetch("/api/detect/image", { method: "POST", body: formData });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.message || "检测失败");
            renderDetectionResult(cameraResult, data);
        } catch (error) {
            cameraResult.innerHTML = `<div class="alert error">${escapeHtml(error.message)}</div>`;
        } finally {
            cameraLoading.classList.add("hidden");
            captureButton.disabled = false;
        }
    }, "image/jpeg", 0.92);
});

window.addEventListener("beforeunload", () => {
    if (stream) stream.getTracks().forEach((track) => track.stop());
});
