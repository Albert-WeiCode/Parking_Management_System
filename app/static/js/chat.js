const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

function addMessage(role, text) {
    const item = document.createElement("div");
    item.className = `message ${role}`;
    const label = document.createElement("span");
    label.className = "message-label";
    label.textContent = role === "user" ? "你" : "AI 助手";
    const content = document.createElement("p");
    content.textContent = text;
    item.append(label, content);
    chatMessages.appendChild(item);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return content;
}

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    addMessage("user", message);
    chatInput.value = "";
    const pending = addMessage("assistant", "正在思考...");
    const button = chatForm.querySelector("button");
    button.disabled = true;
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || "问答服务暂不可用");
        pending.textContent = data.answer || "模型没有返回内容";
    } catch (error) {
        pending.textContent = error.message;
    } finally {
        button.disabled = false;
        chatInput.focus();
    }
});
