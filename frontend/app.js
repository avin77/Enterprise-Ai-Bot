import { connectVoiceSocket, sendChatText } from "./api_client.js";

const logEl = document.getElementById("log");
const tokenEl = document.getElementById("token");
const textEl = document.getElementById("textInput");
const connectBtn = document.getElementById("connect");
const startMicBtn = document.getElementById("startMic");
const stopMicBtn = document.getElementById("stopMic");
const sendTextBtn = document.getElementById("sendText");

let socket = null;
let mediaRecorder = null;
let mediaStream = null;

function log(message) {
  logEl.value += `${message}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

function currentToken() {
  return tokenEl.value.trim();
}

function ensureSocket() {
  if (socket && socket.readyState === WebSocket.OPEN) {
    return socket;
  }
  socket = connectVoiceSocket(currentToken(), {
    onOpen: () => log("ws connected"),
    onClose: () => log("ws closed"),
    onError: () => log("ws error"),
    onMessage: (msg) => log(`ws << ${JSON.stringify(msg)}`),
  });
  return socket;
}

async function blobToBase64(blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return btoa(binary);
}

connectBtn.addEventListener("click", () => {
  ensureSocket();
});

sendTextBtn.addEventListener("click", async () => {
  const text = textEl.value.trim();
  if (!text) {
    return;
  }
  try {
    const data = await sendChatText(text, currentToken());
    log(`chat << ${JSON.stringify(data)}`);
  } catch (error) {
    log(`chat error: ${error.message}`);
  }
});

startMicBtn.addEventListener("click", async () => {
  try {
    const ws = ensureSocket();
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(mediaStream, { mimeType: "audio/webm" });
    mediaRecorder.ondataavailable = async (event) => {
      if (!event.data || event.data.size === 0 || ws.readyState !== WebSocket.OPEN) {
        return;
      }
      const audioBase64 = await blobToBase64(event.data);
      ws.send(JSON.stringify({ type: "audio_chunk", audio_base64: audioBase64 }));
    };
    mediaRecorder.start(900);
    log("mic streaming started");
  } catch (error) {
    log(`mic error: ${error.message}`);
  }
});

stopMicBtn.addEventListener("click", () => {
  if (mediaRecorder) {
    mediaRecorder.stop();
    mediaRecorder = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "end" }));
  }
  log("mic streaming stopped");
});

