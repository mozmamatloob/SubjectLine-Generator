const API_BASE = "http://127.0.0.1:8000";

async function generateLines() {
    const prompt   = document.getElementById('prompt').value.trim();
    const tone     = document.getElementById('tone').value;
    const audience = document.getElementById('audience').value;
    const industry = document.getElementById('industry').value;
    const container = document.getElementById('results-container');

    if (!prompt) { alert("Please enter a prompt!"); return; }

    container.innerHTML = `
        <div class="placeholder-state">
            <i class="fas fa-spinner fa-spin"></i>
            <h3>Generating subject lines…</h3>
            <p>Asking Gemini AI, please wait a moment.</p>
        </div>`;

    try {
        const res = await fetch(`${API_BASE}/generate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt, tone, audience, industry })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Server error");
        }

        const data = await res.json();
        container.innerHTML = ""; 

        data.results.forEach((item, index) => createResultCard(item, index));

    } catch (err) {
        container.innerHTML = `
            <div class="placeholder-state">
                <i class="fas fa-exclamation-circle" style="color:#ef4444"></i>
                <h3>Something went wrong</h3>
                <p>${err.message}</p>
            </div>`;
    }
}

function createResultCard(item, index) {
    const container = document.getElementById('results-container');

    let scoreClass = 'medium-score';
    if (item.score >= 80) scoreClass = 'good-score';
    else if (item.score < 50) scoreClass = 'bad-score';

    const scoreColor = item.score >= 80 ? '#10b981' : (item.score < 50 ? '#ef4444' : '#f59e0b');

    const spamHtml = item.is_spam
        ? `<div class="badge badge-spam"><i class="fas fa-exclamation-triangle"></i> <span>Spam: "${item.spam_words_found.join(', ')}"</span></div>`
        : `<div class="badge badge-safe"><i class="fas fa-check-circle"></i> <span>Clean (No Spam Words)</span></div>`;

    const mobileClass = item.mobile_status === "ok" ? "badge-mobile-ok" : "badge-mobile";

    const cardHTML = `
        <div class="result-card ${scoreClass}" style="animation-delay: ${index * 0.1}s">
            <div class="card-header">
                <div class="subject-text">${item.subject}</div>
                <i class="fas fa-copy copy-icon" onclick="copyToClipboard(this, '${item.subject.replace(/'/g, "\\'")}')" title="Copy"></i>
            </div>
            <div class="analysis-grid">
                <div class="badge badge-score" style="border: 1px solid ${scoreColor}; color: ${scoreColor}">
                    Score: ${item.score}/100
                </div>
                ${spamHtml}
                <div class="badge ${mobileClass}">
                    <i class="fas fa-mobile-alt"></i> <span>${item.char_count} chars</span>
                    <small>${item.mobile_message}</small>
                </div>
            </div>
        </div>`;

    container.innerHTML += cardHTML;
}

function copyToClipboard(iconElement, text) {
    navigator.clipboard.writeText(text).then(() => {
        const originalClass = iconElement.className;
        iconElement.className = "fas fa-check copy-icon";
        iconElement.style.color = "#10b981";
        setTimeout(() => {
            iconElement.className = originalClass;
            iconElement.style.color = "";
        }, 2000);
    });
}