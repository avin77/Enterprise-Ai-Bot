const baseHttp = `${window.location.protocol}//${window.location.host}`;
const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
const baseWs = `${wsProtocol}://${window.location.host}`;

export async function sendChatText(text, token) {
  const response = await fetch(`${baseHttp}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new Error(`chat failed: ${response.status}`);
  }
  return response.json();
}

export function connectVoiceSocket(token, handlers) {
  const socket = new WebSocket(`${baseWs}/ws?token=${encodeURIComponent(token)}`);
  socket.addEventListener("open", () => handlers.onOpen?.());
  socket.addEventListener("close", () => handlers.onClose?.());
  socket.addEventListener("error", (event) => handlers.onError?.(event));
  socket.addEventListener("message", (event) => {
    handlers.onMessage?.(JSON.parse(event.data));
  });
  return socket;
}

