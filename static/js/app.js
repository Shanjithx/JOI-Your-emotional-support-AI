// static/js/app.js
document.addEventListener("DOMContentLoaded", () => {
  const userInput = document.getElementById("userInput");
  const sendBtn = document.getElementById("sendBtn");
  const messagesDiv = document.getElementById("messages");

  function appendMessage(text, cls="assistant") {
    const el = document.createElement("div");
    el.className = `msg ${cls}`;
    el.textContent = text;
    messagesDiv.appendChild(el);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    return el;
  }

  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;
    // append user message
    appendMessage(text, "user");
    userInput.value = "";
    userInput.disabled = true;
    sendBtn.disabled = true;

    // prepare assistant bubble (empty, will be filled as stream arrives)
    const assistantEl = appendMessage("", "assistant");

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      if (!resp.ok) {
        const err = await resp.text();
        assistantEl.textContent = "[Error] " + err;
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let done = false;

      // stream read loop
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value, { stream: !done });
          // append chunk to assistant bubble
          assistantEl.textContent += chunk;
          messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
      }
    } catch (err) {
      assistantEl.textContent = "[Connection error] " + String(err);
    } finally {
      userInput.disabled = false;
      sendBtn.disabled = false;
      userInput.focus();
    }
  }

  // send on button click
  sendBtn.addEventListener("click", sendMessage);

  // enter key also sends
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
});
