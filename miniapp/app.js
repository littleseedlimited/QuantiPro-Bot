/**
 * QuantiProBot Mini App - Main Application Logic
 */

// Configuration
const API_BASE = window.location.origin + '/api';
let currentUser = null;
let currentFile = null;
let selectedVariables = [];
let currentAnalysisType = null;

// Telegram WebApp SDK
const tg = window.Telegram?.WebApp;

// Initialize app
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize Telegram WebApp
    if (tg) {
        tg.ready();
        tg.expand();

        // Apply Telegram theme
        applyTelegramTheme();

        // Setup back button
        tg.BackButton.onClick(() => {
            const activeScreen = document.querySelector('.screen.active');
            if (activeScreen && activeScreen.id !== 'homeScreen') {
                showScreen('homeScreen');
            }
        });
    }

    // Setup file input
    setupFileUpload();

    // Load user info
    await loadUserInfo();
});

// Apply Telegram theme colors
function applyTelegramTheme() {
    if (!tg?.themeParams) return;

    const root = document.documentElement;
    const theme = tg.themeParams;

    if (theme.bg_color) root.style.setProperty('--tg-theme-bg-color', theme.bg_color);
    if (theme.text_color) root.style.setProperty('--tg-theme-text-color', theme.text_color);
    if (theme.hint_color) root.style.setProperty('--tg-theme-hint-color', theme.hint_color);
    if (theme.link_color) root.style.setProperty('--tg-theme-link-color', theme.link_color);
    if (theme.button_color) root.style.setProperty('--tg-theme-button-color', theme.button_color);
    if (theme.button_text_color) root.style.setProperty('--tg-theme-button-text-color', theme.button_text_color);
    if (theme.secondary_bg_color) root.style.setProperty('--tg-theme-secondary-bg-color', theme.secondary_bg_color);
}

// API Helper
async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    // Add Telegram auth if available
    if (tg?.initData) {
        headers['X-Telegram-Init-Data'] = tg.initData;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || 'Request failed');
    }

    return response.json();
}

// Load user info
async function loadUserInfo() {
    try {
        const user = await apiRequest('/user');
        currentUser = user;

        document.getElementById('userInfo').textContent = user.name;

        if (user.is_new) {
            // Could redirect to signup
            console.log('New user detected');
        }
    } catch (err) {
        console.error('Failed to load user:', err);
    }

    // CHECK FOR MIRRORED SESSION
    try {
        const session = await apiRequest('/session/active');
        if (session.active) {
            console.log("Restoring active session from bot...");
            currentFile = session;

            // Show file info on Home Screen
            const fileInfo = document.getElementById('fileInfo');
            if (fileInfo) {
                fileInfo.innerHTML = `
                    <h3>📄 ${session.file_id}</h3>
                    <p>${session.rows} rows × ${session.columns.length} columns</p>
                    <p class="hint">Synced from Bot • Numeric: ${session.numeric_columns.length} | Categorical: ${session.categorical_columns.length}</p>
                    <button class="btn primary" onclick="showScreen('analysisScreen')" style="margin-top: 10px; width: 100%;">Continue Analysis</button>
                `;
                fileInfo.classList.remove('hidden');
            }
        }
    } catch (err) {
        console.log('No active session to restore');
    }
}

// Screen navigation
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');

    // Update Telegram back button
    if (tg) {
        if (screenId === 'homeScreen') {
            tg.BackButton.hide();
        } else {
            tg.BackButton.show();
        }
    }
}

// Loading overlay
function showLoading(text = 'Processing...') {
    document.getElementById('loadingText').textContent = text;
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

// File Upload
function setupFileUpload() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });
}

async function handleFileUpload(file) {
    showLoading('Uploading file...');

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData,
            headers: tg?.initData ? { 'X-Telegram-Init-Data': tg.initData } : {}
        });

        if (!response.ok) throw new Error('Upload failed');

        currentFile = await response.json();

        // Show file info
        const fileInfo = document.getElementById('fileInfo');
        fileInfo.innerHTML = `
            <h3>📄 ${file.name}</h3>
            <p>${currentFile.rows} rows × ${currentFile.columns.length} columns</p>
            <p class="hint">Numeric: ${currentFile.numeric_columns.length} | Categorical: ${currentFile.categorical_columns.length}</p>
        `;
        fileInfo.classList.remove('hidden');

        // Show success feedback
        if (tg) tg.HapticFeedback.notificationOccurred('success');

        // Navigate to analysis screen
        setTimeout(() => showScreen('analysisScreen'), 500);

    } catch (err) {
        alert('Failed to upload file: ' + err.message);
        if (tg) tg.HapticFeedback.notificationOccurred('error');
    } finally {
        hideLoading();
    }
}

// Variable Selection UI
function showVariableSelect(analysisType) {
    currentAnalysisType = analysisType;
    selectedVariables = [];

    const screen = document.getElementById('variableScreen');
    const container = document.getElementById('variableList');
    container.innerHTML = '';

    // Header
    const titleMap = {
        'crosstab': 'Select Row & Column',
        'correlation': 'Select Variables (2+)',
        'regression': 'Select Target & Predictors',
        'visual': 'Select Variable(s)'
    };
    document.getElementById('variableTitle').textContent = titleMap[analysisType] || 'Select Variables';

    // UI GENERATION
    if (analysisType === 'crosstab') {
        // CROSSTAB: Specific Row/Col Selectors
        renderCrosstabSelectors(container);
    }
    else if (analysisType === 'regression') {
        // REGRESSION: Target vs Predictors
        renderRegressionSelectors(container);
    }
    else {
        // STANDARD: Checkbox List
        renderCheckboxList(container, analysisType);
    }

    // Options for Visuals
    if (analysisType === 'visual') {
        renderVisualOptions(container);
    }

    showScreen('variableScreen');
}

function renderCrosstabSelectors(container) {
    const cols = currentFile.columns; // Allow all columns for crosstab

    container.innerHTML = `
        <div class="form-group">
            <label>Row Variable (Group By)</label>
            <select id="crosstabRow" class="form-select" onchange="updateCrosstabSelection()">
                <option value="">Select Row...</option>
                ${cols.map(c => `<option value="${c}">${c}</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label>Column Variable (Compare)</label>
            <select id="crosstabCol" class="form-select" onchange="updateCrosstabSelection()">
                <option value="">Select Column...</option>
                ${cols.map(c => `<option value="${c}">${c}</option>`).join('')}
            </select>
        </div>
        <div class="hint-box">
             💡 Select two categorical variables to see their relationship.
        </div>
    `;
}

function updateCrosstabSelection() {
    const r = document.getElementById('crosstabRow').value;
    const c = document.getElementById('crosstabCol').value;
    selectedVariables = [];
    if (r) selectedVariables.push(r);
    if (c) selectedVariables.push(c);
}

function renderVisualOptions(container) {
    // Add Chart Options
    const optsDiv = document.createElement('div');
    optsDiv.className = 'visual-options';
    optsDiv.style.marginTop = '20px';
    optsDiv.style.borderTop = '1px solid var(--card-border)';
    optsDiv.style.paddingTop = '15px';

    optsDiv.innerHTML = `
        <label style="display:flex; align-items:center; gap:10px; cursor:pointer;">
             <input type="checkbox" id="chkDataLabels" style="width:18px; height:18px;">
             <span>Show Data Labels (Values/%)</span>
        </label>
        ${window.currentVisualType === 'pie' ? `
        <label style="display:flex; align-items:center; gap:10px; cursor:pointer; margin-top:10px;">
             <input type="checkbox" id="chkLegend" checked style="width:18px; height:18px;">
             <span>Show Legend</span>
        </label>` : ''}
    `;
    container.appendChild(optsDiv);
}

function renderRegressionSelectors(container) {
    const numeric = currentFile.numeric_columns;

    container.innerHTML = `
        <div class="form-group">
            <label>Target Variable (Y) - What you want to predict</label>
            <select id="regTarget" class="form-select" onchange="updateRegressionSelection()">
                <option value="">Select Target...</option>
                ${numeric.map(c => `<option value="${c}">${c}</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label>Predictors (X) - Factors influencing Y</label>
            <div id="regPredictors" class="checkbox-group">
                 ${numeric.map(c => `
                    <div class="variable-item" onclick="toggleRegPredictor(this, '${c}')">
                        <div class="variable-checkbox"></div>
                        <span>${c}</span>
                    </div>
                 `).join('')}
            </div>
        </div>
    `;
}

let regTarget = null;
let regPredictors = [];

function toggleRegPredictor(el, col) {
    el.classList.toggle('selected');
    if (regPredictors.includes(col)) regPredictors = regPredictors.filter(c => c !== col);
    else regPredictors.push(col);
    updateRegressionSelection();
}

function updateRegressionSelection() {
    const target = document.getElementById('regTarget').value;
    selectedVariables = target ? [target, ...regPredictors] : [];
}

function renderCheckboxList(container, analysisType) {
    const columns = (analysisType === 'correlation' || analysisType === 'histogram' || analysisType === 'boxplot')
        ? currentFile.numeric_columns
        : currentFile.columns;

    columns.forEach(col => {
        const item = document.createElement('div');
        item.className = 'variable-item';
        item.innerHTML = `
            <div class="variable-checkbox"></div>
            <span>${col}</span>
        `;
        item.addEventListener('click', () => toggleVariable(item, col));
        container.appendChild(item);
    });
}


function toggleVariable(element, variable) {
    element.classList.toggle('selected'); // UI Toggle

    // Logic Toggle
    if (selectedVariables.includes(variable)) {
        selectedVariables = selectedVariables.filter(v => v !== variable);
    } else {
        selectedVariables.push(variable);
    }

    if (tg) tg.HapticFeedback.selectionChanged();
}

// Run Analysis
async function runAnalysis(type) {
    if (!currentFile) {
        alert('Please upload a file first');
        return;
    }

    showLoading('Running analysis...');

    try {
        const payload = {
            file_id: currentFile.file_id,
            analysis_type: type,
            variables: selectedVariables.length > 0 ? selectedVariables : null
        };

        if (type === 'visual' && window.currentVisualType) {
            const opts = { chart_type: window.currentVisualType };
            // Capture UI options
            const chkLabels = document.getElementById('chkDataLabels');
            const chkLegend = document.getElementById('chkLegend');

            if (chkLabels && chkLabels.checked) opts.data_labels = true;
            if (chkLegend && chkLegend.checked) opts.legend = true;

            payload.options = opts;
        }

        const result = await apiRequest(`/analyze/${type}`, {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        displayResults(result, type);
        if (tg) tg.HapticFeedback.notificationOccurred('success');

    } catch (err) {
        alert('Analysis failed: ' + err.message);
        if (tg) tg.HapticFeedback.notificationOccurred('error');
    } finally {
        hideLoading();
    }
}

async function executeAnalysis() {
    if (selectedVariables.length < 2 && currentAnalysisType !== 'descriptive') {
        alert('Please select at least 2 variables');
        return;
    }

    await runAnalysis(currentAnalysisType);
}

function displayResults(result, type) {
    const container = document.getElementById('resultsContainer');
    window.lastResult = result; // Store for export

    if (result.image_path) {
        container.innerHTML = `<img src="${result.image_path}" alt="Results">`;
    } else if (type === 'crosstab' && result.data && result.data.counts) {
        // Render crosstab as HTML table
        container.innerHTML = renderCrosstabTable(result.data);
    } else if (result.formatted) {
        // Clean up markdown artifacts
        let html = result.formatted
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/_(.*?)_/g, '<em>$1</em>')
            .replace(/📍|🎯|📏|▫️|📊/g, '')
            .replace(/\n/g, '<br>');
        container.innerHTML = `<div class="results-text">${html}</div>`;
    } else {
        container.innerHTML = `<pre>${JSON.stringify(result.data, null, 2)}</pre>`;
    }

    showScreen('resultsScreen');
}

// Render crosstab as styled HTML table
function renderCrosstabTable(data) {
    const counts = data.counts;
    const rowVar = data.row_var || 'Row';
    const colVar = data.col_var || 'Column';
    const n = data.n_observations || 'N/A';

    // Get unique row and column keys
    const rowKeys = Object.keys(counts);
    const colKeys = rowKeys.length > 0 ? Object.keys(counts[rowKeys[0]]) : [];

    let html = `
        <div class="crosstab-header">
            <h3>🎯 Crosstab: ${rowVar} × ${colVar}</h3>
            <p>Total N: ${n}</p>
        </div>
        <table class="crosstab-table">
            <thead>
                <tr>
                    <th>${rowVar} \\ ${colVar}</th>
                    ${colKeys.map(c => `<th>${c}</th>`).join('')}
                </tr>
            </thead>
            <tbody>
                ${rowKeys.map(r => `
                    <tr>
                        <td><strong>${r}</strong></td>
                        ${colKeys.map(c => `<td>${counts[r][c] || 0}</td>`).join('')}
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    return html;
}

// Helper: Get dynamic example based on uploaded data
function getDynamicExample(type) {
    if (!currentFile) return "";

    // Pick random variables
    const num = currentFile.numeric_columns;
    const cat = currentFile.categorical_columns;
    const cols = currentFile.columns;

    const rand = (arr) => arr.length > 0 ? arr[Math.floor(Math.random() * arr.length)] : "[Var]";
    const rand2 = (arr) => {
        if (arr.length < 2) return ["[Var1]", "[Var2]"];
        const s = arr.sort(() => 0.5 - Math.random()).slice(0, 2);
        return s;
    };

    switch (type) {
        case 't_test':
            if (num.length > 0 && cat.length > 0) return `e.g. Compare ${rand(num)} by ${rand(cat)}`;
            return "e.g. Compare Interest by Group";
        case 'anova':
            if (num.length > 0 && cat.length > 0) return `e.g. Compare ${rand(num)} across ${rand(cat)} groups`;
            return "e.g. Compare Income across 3+ Groups";
        case 'chi_square':
            if (cat.length > 1) { const [c1, c2] = rand2(cat); return `e.g. Association between ${c1} & ${c2}`; }
            return "e.g. Association between Gender & Preference";
        case 'correlation':
            if (num.length > 1) { const [n1, n2] = rand2(num); return `e.g. Relationship of ${n1} & ${n2}`; }
            return "e.g. Relationship between Age & Income";
        case 'regression':
            if (num.length > 1) { const [n1, n2] = rand2(num); return `e.g. Predict ${n1} based on ${n2}`; }
            return "e.g. Predict Outcome based on Predictors";
        case 'histogram':
            return `e.g. Distribution of ${rand(num)}`;
        case 'scatter':
            if (num.length > 1) { const [n1, n2] = rand2(num); return `e.g. ${n1} vs ${n2}`; }
            return "e.g. Age vs Income";
        case 'boxplot':
            if (num.length > 0 && cat.length > 0) return `e.g. ${rand(num)} by ${rand(cat)}`;
            return "e.g. Salary by Department";
        default:
            return "";
    }
}

// Test Options
function showTestOptions() {
    const tests = [
        { id: 't_test', name: 'T-Test', icon: '📊' },
        { id: 'anova', name: 'ANOVA', icon: '📈' },
        { id: 'chi_square', name: 'Chi-Square', icon: '🎲' },
        { id: 'mannwhitney', name: 'Mann-Whitney U', icon: '📉' }
    ];

    const container = document.getElementById('resultsContainer');
    container.innerHTML = tests.map(t => `
        <button class="analysis-card" onclick="selectTest('${t.id}')">
            <span class="card-icon">${t.icon}</span>
            <span class="card-title">${t.name}</span>
            <span class="card-desc">${getDynamicExample(t.id)}</span>
        </button>
    `).join('');

    showScreen('resultsScreen');
}

function selectTest(testId) {
    currentAnalysisType = 'hypothesis';
    showVariableSelect('hypothesis');
}

// Visual Options
function showVisualOptions() {
    const visuals = [
        { id: 'histogram', name: 'Histogram', icon: '📊' },
        { id: 'scatter', name: 'Scatter Plot', icon: '🔵' },
        { id: 'boxplot', name: 'Box Plot', icon: '📦' },
        { id: 'heatmap', name: 'Correlation Heatmap', icon: '🟥' }
    ];

    const container = document.getElementById('resultsContainer');
    container.innerHTML = `
        <div class="analysis-grid">
            ${visuals.map(v => `
                <button class="analysis-card" onclick="createVisual('${v.id}')">
                    <span class="card-icon">${v.icon}</span>
                    <span class="card-title">${v.name}</span>
                    <span class="card-desc">${getDynamicExample(v.id)}</span>
                </button>
            `).join('')}
        </div>
    `;

    showScreen('resultsScreen');
}


function createVisual(visualType) {
    window.currentVisualType = visualType;
    showVariableSelect('visual');
}

// Sample Size Calculator
async function calculateSampleSize() {
    showLoading('Calculating...');

    try {
        const result = await apiRequest('/sampling/calculate', {
            method: 'POST',
            body: JSON.stringify({
                method: 'simple_random',
                confidence_level: parseFloat(document.getElementById('confidenceLevel').value),
                margin_of_error: parseFloat(document.getElementById('marginError').value),
                population_size: parseInt(document.getElementById('populationSize').value) || null
            })
        });

        const resultCard = document.getElementById('samplingResult');
        resultCard.innerHTML = `
            <div class="result-value">${result.sample_size}</div>
            <div class="result-label">Required Sample Size</div>
        `;
        resultCard.classList.remove('hidden');

        if (tg) tg.HapticFeedback.notificationOccurred('success');

    } catch (err) {
        alert('Calculation failed: ' + err.message);
    } finally {
        hideLoading();
    }
}

// Projects
async function loadProjects() {
    showLoading('Loading projects...');

    try {
        const result = await apiRequest('/projects');

        const list = document.getElementById('projectsList');

        if (result.projects.length === 0) {
            list.innerHTML = '<p class="hint">No saved projects yet.</p>';
        } else {
            list.innerHTML = result.projects.map(p => `
                <div class="project-item" onclick="loadProject(${p.id})">
                    <div class="project-info">
                        <h3>${p.title}</h3>
                        <span>${p.created}</span>
                    </div>
                    <div class="project-actions">
                        <button class="icon-btn danger" onclick="event.stopPropagation(); deleteProject(${p.id})">🗑️</button>
                    </div>
                </div>
            `).join('');
        }

        showScreen('projectsScreen');

    } catch (err) {
        alert('Failed to load projects: ' + err.message);
    } finally {
        hideLoading();
    }
}

async function loadProject(projectId) {
    showLoading('Loading project...');

    try {
        const project = await apiRequest(`/projects/${projectId}`);

        // Restore context
        if (project.file_path) {
            currentFile = { file_id: project.file_path.split('/').pop(), ...project.context };
        }

        if (tg) tg.HapticFeedback.notificationOccurred('success');
        showScreen('analysisScreen');

    } catch (err) {
        alert('Failed to load project: ' + err.message);
    } finally {
        hideLoading();
    }
}

async function saveProject() {
    if (!currentFile) {
        alert('No analysis to save');
        return;
    }

    const title = prompt('Project name:', 'My Analysis');
    if (!title) return;

    showLoading('Saving project...');

    try {
        await apiRequest('/projects', {
            method: 'POST',
            body: JSON.stringify({
                title: title,
                file_path: currentFile.file_path,
                context_data: {
                    columns: currentFile.columns,
                    numeric_columns: currentFile.numeric_columns
                }
            })
        });

        alert('Project saved successfully!');
        if (tg) tg.HapticFeedback.notificationOccurred('success');

    } catch (err) {
        alert('Failed to save project: ' + err.message);
    } finally {
        hideLoading();
    }
}

async function deleteProject(projectId) {
    if (!confirm('Delete this project?')) return;

    showLoading('Deleting...');

    try {
        await apiRequest(`/projects/${projectId}`, { method: 'DELETE' });
        await loadProjects();
        if (tg) tg.HapticFeedback.notificationOccurred('success');
    } catch (err) {
        alert('Failed to delete project: ' + err.message);
    } finally {
        hideLoading();
    }
}

// Export results as CSV download
function exportResults(format = 'csv') {
    if (!window.lastResult) {
        alert('No results to export');
        return;
    }

    if (format === 'excel') {
        exportToExcel();
        return;
    }

    let csvContent = '';
    const data = window.lastResult.data;

    // Handle crosstab format
    if (data && data.counts) {
        const counts = data.counts;
        const rowKeys = Object.keys(counts);
        const colKeys = rowKeys.length > 0 ? Object.keys(counts[rowKeys[0]]) : [];

        csvContent = `${data.row_var || 'Row'},${colKeys.join(',')}\n`;
        rowKeys.forEach(r => {
            csvContent += `${r},${colKeys.map(c => counts[r][c] || 0).join(',')}\n`;
        });
    } else if (typeof data === 'object') {
        // Generic object export
        csvContent = JSON.stringify(data, null, 2);
    } else {
        csvContent = String(data);
    }

    // Trigger download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `quantiprobot_results_${Date.now()}.csv`;
    link.click();

    if (tg) tg.HapticFeedback.notificationOccurred('success');
}

function exportToExcel() {
    // Simple HTML Table export
    const container = document.getElementById('resultsContainer');
    // Prefer table if exists
    const table = container.querySelector('table');

    let content = "";
    if (table) {
        content = table.outerHTML;
    } else if (window.lastResult && window.lastResult.formatted) {
        content = window.lastResult.formatted;
    } else {
        alert("No tabular data to export to Excel.");
        return;
    }

    const template = `
        <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
        <head><!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>Analysis Results</x:Name><x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]--></head>
        <body>${content}</body></html>`;

    const blob = new Blob([template], { type: 'application/vnd.ms-excel' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `analysis_report_${Date.now()}.xls`;
    link.click();

    if (tg) tg.HapticFeedback.notificationOccurred('success');
}

// Save current project
async function saveProject() {
    if (!currentFile) {
        alert('No file loaded to save');
        return;
    }

    const title = prompt('Enter project name:', `Analysis ${new Date().toLocaleDateString()}`);
    if (!title) return;

    showLoading('Saving project...');

    try {
        await apiRequest('/projects', {
            method: 'POST',
            body: JSON.stringify({
                title: title,
                file_path: currentFile.file_path || currentFile.file_id,
                context_data: {
                    columns: currentFile.columns,
                    rows: currentFile.rows,
                    lastAnalysis: currentAnalysisType
                }
            })
        });

        alert('Project saved successfully!');
        if (tg) tg.HapticFeedback.notificationOccurred('success');
    } catch (err) {
        alert('Failed to save project: ' + err.message);
    } finally {
        hideLoading();
    }
}

// AI Chat
async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    const container = document.getElementById('chatContainer');

    // Add user message
    container.innerHTML += `<div class="chat-message user">${message}</div>`;
    input.value = '';
    container.scrollTop = container.scrollHeight;

    showLoading('AI is thinking...');

    try {
        const result = await apiRequest('/ai/chat', {
            method: 'POST',
            body: JSON.stringify({
                message: message,
                file_id: currentFile?.file_id
            })
        });

        container.innerHTML += `<div class="chat-message assistant">${result.response}</div>`;
        container.scrollTop = container.scrollHeight;

    } catch (err) {
        container.innerHTML += `<div class="chat-message assistant">Sorry, I couldn't process that request.</div>`;
    } finally {
        hideLoading();
    }
}

// Enter key for chat
document.getElementById('chatInput')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendChatMessage();
});
