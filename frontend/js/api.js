
const API_BASE_URL = "https://YOUR-RENDER-URL.onrender.com";

async function checkBackend() {
    const response = await fetch(`${API_BASE_URL}/health`);

    if (!response.ok) {
        throw new Error("Backend connection failed");
    }

    return await response.json();
}

async function uploadVoiceRecording(audioBlob) {
    const formData = new FormData();

    formData.append("file", audioBlob, "voice.webm");

    const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: "POST",
        body: formData
    });

    if (!response.ok) {
        throw new Error(await response.text());
    }

    return await response.json();
}

window.ALVI_API = {
    checkBackend,
    uploadVoiceRecording
};
