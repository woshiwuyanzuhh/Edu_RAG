/**
 * edu_rag 前端公共工具函数
 */

// Markdown 解析（使用 marked.js CDN）
if (typeof marked !== 'undefined') {
    marked.setOptions({
        breaks: true,
        gfm: true,
    });
}

// 通用的 HTML 转义函数（挂 window）
window.escapeHtml = function (text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};

// 文件大小格式化
window.formatSize = function (bytes) {
    if (!bytes) return '0B';
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
    return (bytes / 1024 / 1024).toFixed(1) + 'MB';
};

// Toast 消息
window.showToast = function (message, type = 'info') {
    const colors = { success: '#198754', error: '#dc3545', info: '#0d6efd', warning: '#ffc107' };
    const div = document.createElement('div');
    div.style.cssText = `
        position:fixed;top:20px;right:20px;z-index:9999;
        background:${colors[type] || colors.info};color:white;
        padding:12px 20px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.2);
        transition:opacity 0.3s;
    `;
    div.textContent = message;
    document.body.appendChild(div);
    setTimeout(() => { div.style.opacity = '0'; setTimeout(() => div.remove(), 300); }, 3000);
};

console.log('edu_rag app.js loaded');
