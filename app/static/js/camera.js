const video = document.getElementById("cameraVideo");
const placeholder = document.getElementById("cameraPlaceholder");
const canvas = document.getElementById("captureCanvas");
const startButton = document.getElementById("startCamera");
const captureButton = document.getElementById("captureFrame");
const stopButton = document.getElementById("stopCamera");
const cameraStatus = document.getElementById("cameraStatus");
const cameraLoading = document.getElementById("cameraLoading");
const cameraResult = document.getElementById("cameraResult");
const autoDetect = document.getElementById("autoDetect");
let stream = null;
let busy = false;
let timer = null;
let controller = null;
let generation = 0;

function scheduleDetection() {
    clearTimeout(timer);
    if (autoDetect.checked && stream && !busy) timer = setTimeout(captureFrame, 1000);
}

function stopCamera() {
    generation += 1;
    clearTimeout(timer);
    if (controller) controller.abort();
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    video.classList.remove("active");
    placeholder.classList.remove("hidden");
    startButton.classList.remove("hidden");
    stopButton.classList.add("hidden");
    captureButton.disabled = true;
    cameraLoading.classList.add("hidden");
    cameraStatus.textContent = "摄像头未启动";
}

startButton.addEventListener("click", async () => {
    startButton.disabled = true;
    try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("请使用安全连接或本机地址访问摄像头");
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        video.srcObject = stream;
        await video.play();
        video.classList.add("active");
        placeholder.classList.add("hidden");
        startButton.classList.add("hidden");
        stopButton.classList.remove("hidden");
        captureButton.disabled = busy;
        cameraStatus.textContent = "摄像头已启动";
        scheduleDetection();
    } catch (error) {
        stopCamera();
        cameraResult.innerHTML = `<div class="alert error">无法访问摄像头：${escapeHtml(userErrorMessage(error, "请检查摄像头权限、设备连接及网络"))}</div>`;
    } finally {
        startButton.disabled = false;
    }
});

async function captureFrame() {
    if (!stream || busy) return;
    if (!video.videoWidth) { scheduleDetection(); return; }
    clearTimeout(timer);
    const currentGeneration = generation;
    busy = true;
    controller = new AbortController();
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    cameraLoading.classList.remove("hidden");
    captureButton.disabled = true;
    let failed = false;
    try {
        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
        if (!blob) throw new Error("无法截取摄像头画面，请重试");
        if (currentGeneration !== generation) return;
        const formData = new FormData();
        formData.append("file", blob, "camera-frame.jpg");
        const response = await fetch("/api/detect/image", { method: "POST", body: formData, signal: controller.signal });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || "检测失败");
        if (currentGeneration === generation && !cameraResult.contains(document.activeElement)) renderDetectionResult(cameraResult, data);
    } catch (error) {
        if (error.name !== "AbortError" && currentGeneration === generation) {
            failed = true;
            autoDetect.checked = false;
            cameraResult.innerHTML = `<div class="alert error">${escapeHtml(userErrorMessage(error, "请检查摄像头权限、设备连接及网络"))}</div>`;
        }
    } finally {
        busy = false;
        cameraLoading.classList.add("hidden");
        captureButton.disabled = !stream;
        if (!failed) scheduleDetection();
    }
}

stopButton.addEventListener("click", stopCamera);
captureButton.addEventListener("click", captureFrame);
autoDetect.addEventListener("change", scheduleDetection);
window.addEventListener("pagehide", stopCamera);
