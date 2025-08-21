document.addEventListener("DOMContentLoaded", () => {
  const loginBox = document.getElementById("loginBox");
  const chatBox = document.getElementById("chatBox");
  const loginForm = document.getElementById("loginForm");
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const loginError = document.getElementById("loginError");
  const userInput = document.getElementById("userInput");
  const sendBtn = document.getElementById("sendBtn");
  const logoutBtn = document.getElementById("logoutBtn");
  const messagesDiv = document.getElementById("messages");

  function appendMessage(text, cls = "assistant") {
    const el = document.createElement("div");
    el.className = `msg ${cls}`;
    if (cls === "assistant") {
      el.innerHTML = DOMPurify.sanitize(marked.parse(text));
    } else {
      el.textContent = text;
    }
    messagesDiv.appendChild(el);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    return el;
  }

  async function login() {
    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();
    if (!username || !password) {
      loginError.textContent = "Please enter both username and password";
      loginError.style.display = "block";
      return;
    }

    try {
      const resp = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await resp.json();
      if (data.success) {
        loginBox.style.display = "none";
        chatBox.style.display = "block";
        userInput.focus();
        if (data.new_user && data.first_message) {
          appendMessage(data.first_message, "assistant");
        } else {
          appendMessage("JOI - EVERYTHING YOU WANT TO SEE, EVERYTHING YOU WANT TO HEAR\nWelcome back! You can update your profile anytime with commands like 'update my nickname to Alex' or 'my mood is happy'. How can I assist you today?", "assistant");
        }
      } else {
        loginError.textContent = data.error || "Login failed";
        loginError.style.display = "block";
      }
    } catch (err) {
      loginError.textContent = "Connection error";
      loginError.style.display = "block";
    }
  }

  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;
    appendMessage(text, "user");
    userInput.value = "";
    userInput.disabled = true;
    sendBtn.disabled = true;

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
      let accumulatedText = "";

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value, { stream: !done });
          accumulatedText += chunk;
          assistantEl.innerHTML = DOMPurify.sanitize(marked.parse(accumulatedText));
          messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
      }
    } catch (err) {
      assistantAssistantEl.textContent = "[Connection error] " + String(err);
    } finally {
      userInput.disabled = false;
      sendBtn.disabled = false;
      userInput.focus();
    }
  }

  async function logout() {
    try {
      await fetch("/api/logout", { method: "POST" });
      loginBox.style.display = "block";
      chatBox.style.display = "none";
      messagesDiv.innerHTML = "";
      usernameInput.value = "";
      passwordInput.value = "";
      loginError.style.display = "none";
    } catch (err) {
      loginError.textContent = "Logout failed";
      loginError.style.display = "block";
    }
  }

  loginForm.addEventListener("submit", (e) => {
    e.preventDefault();
    login();
  });

  sendBtn.addEventListener("click", sendMessage);

  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  logoutBtn.addEventListener("click", logout);
});