// ============================================================
// ESCAPE HTML - Prevent XSS
// ============================================================

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// LOAD ALL DATA
// ============================================================

function loadAllData() {
    loadTools();
    loadDocuments();
    loadHITL();
    loadTickets();
}

// Load data when tab changes
document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(button => {
    button.addEventListener('shown.bs.tab', function(e) {
        const target = e.target.getAttribute('data-bs-target');
        switch(target) {
            case '#tools': loadTools(); break;
            case '#documents': loadDocuments(); break;
            case '#hitl': loadHITL(); break;
            case '#tickets': loadTickets(); break;
        }
    });
});

// ============================================================
// TOOLS MANAGEMENT
// ============================================================

async function loadTools() {
    try {
        const response = await fetch('/api/admin/tools');
        const data = await response.json();

        if (data.status === 'error') {
            document.getElementById('tools-container').innerHTML =
                `<div class="alert alert-danger">${escapeHtml(data.error)}</div>`;
            return;
        }

        const tools = data.data?.tools || data.data || [];

        if (tools.length === 0) {
            document.getElementById('tools-container').innerHTML =
                '<div class="text-center text-muted py-3">No tools registered.</div>';
            return;
        }

        const agents = {};
        tools.forEach(t => {
            if (!agents[t.agent_name]) agents[t.agent_name] = [];
            agents[t.agent_name].push(t);
        });

        let html = '';
        for (const [agent, toolList] of Object.entries(agents)) {
            html += `
                <h6 class="mt-3">
                    <i class="fas fa-robot me-1"></i>
                    ${escapeHtml(agent)}
                    <span class="badge bg-secondary">${toolList.length} tools</span>
                </h6>
                <div class="row mb-3">`;

            toolList.forEach(t => {
                html += `
                    <div class="col-md-4 col-lg-3">
                        <div class="form-check form-switch">
                            <input class="form-check-input tool-toggle"
                                   type="checkbox"
                                   data-tool-id="${t.id}"
                                   data-tool="${escapeHtml(t.tool_name)}"
                                   data-agent="${escapeHtml(t.agent_name)}"
                                   ${t.enabled ? 'checked' : ''}>
                            <label class="form-check-label">
                                ${escapeHtml(t.tool_name)}
                                <span class="badge ${t.enabled ? 'bg-success' : 'bg-secondary'}">
                                    ${t.enabled ? 'ON' : 'OFF'}
                                </span>
                            </label>
                        </div>
                    </div>`;
            });

            html += `</div>`;
        }

        document.getElementById('tools-container').innerHTML = html;

        document.querySelectorAll('.tool-toggle').forEach(el => {
            el.addEventListener('change', function() {
                toggleTool(
                    parseInt(this.dataset.tool_id),
                    this.checked
                );
            });
        });

    } catch(e) {
        document.getElementById('tools-container').innerHTML =
            `<div class="alert alert-danger">Error loading tools: ${escapeHtml(e.message)}</div>`;
    }
}

async function toggleTool(toolId, enabled) {
    try {
        const response = await fetch(`/api/admin/tools/${toolId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });

        const data = await response.json();

        if (data.status === 'success') {
            showSuccess(`Tool ${enabled ? 'enabled' : 'disabled'} successfully`);
            loadTools();
        } else {
            showError(`Failed to update tool: ${escapeHtml(data.error)}`);
            document.querySelector(`.tool-toggle[data-tool-id="${toolId}"]`).checked = !enabled;
        }
    } catch(e) {
        showError(`Error: ${escapeHtml(e.message)}`);
        document.querySelector(`.tool-toggle[data-tool-id="${toolId}"]`).checked = !enabled;
    }
}

// ============================================================
// DOCUMENTS MANAGEMENT
// ============================================================

async function loadDocuments() {
    try {
        const response = await fetch('/api/admin/documents');
        const data = await response.json();

        if (data.status === 'error') {
            document.getElementById('documents-container').innerHTML =
                `<div class="alert alert-danger">${escapeHtml(data.error)}</div>`;
            return;
        }

        const docs = data.data?.documents || data.data || [];

        if (docs.length === 0) {
            document.getElementById('documents-container').innerHTML =
                '<div class="text-center text-muted py-3">No documents. Click "Add Document" to upload one.</div>';
            return;
        }

        let html = `
            <div class="table-responsive">
                <table class="table table-sm table-hover">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Source</th>
                            <th>Status</th>
                            <th>Added</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>`;

        docs.forEach(d => {
            html += `
                <tr>
                    <td><strong>${escapeHtml(d.name)}</strong></td>
                    <td>${escapeHtml(d.source || 'N/A')}</td>
                    <td>
                        <span class="badge ${d.active ? 'bg-success' : 'bg-secondary'}">
                            ${d.active ? 'Active' : 'Inactive'}
                        </span>
                    </td>
                    <td>${d.added_at ? new Date(d.added_at).toLocaleDateString() : 'N/A'}</td>
                    <td>
                        ${d.active ?
                            `<button class="btn btn-sm btn-outline-danger" onclick="deleteDocument(${d.id})">
                                <i class="fas fa-trash"></i>
                            </button>` :
                            `<button class="btn btn-sm btn-outline-success" onclick="activateDocument(${d.id})">
                                <i class="fas fa-check"></i> Activate
                            </button>`
                        }
                    </td>
                </tr>`;
        });

        html += `</tbody></table></div>`;
        document.getElementById('documents-container').innerHTML = html;

    } catch(e) {
        document.getElementById('documents-container').innerHTML =
            `<div class="alert alert-danger">Error loading documents: ${escapeHtml(e.message)}</div>`;
    }
}

function showAddDocumentModal() {
    document.getElementById('doc-name').value = '';
    document.getElementById('doc-content').value = '';
    document.getElementById('doc-source').value = '';
    document.getElementById('doc-active').checked = true;
    new bootstrap.Modal(document.getElementById('addDocumentModal')).show();
}

async function addDocument() {
    const name = document.getElementById('doc-name').value.trim();
    const content = document.getElementById('doc-content').value.trim();
    const source = document.getElementById('doc-source').value.trim();
    const active = document.getElementById('doc-active').checked;

    if (!name || !content) {
        showError('Please fill in both name and content.');
        return;
    }

    try {
        const response = await fetch('/api/admin/documents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, content, source, active })
        });

        const data = await response.json();

        if (data.status === 'success') {
            bootstrap.Modal.getInstance(document.getElementById('addDocumentModal')).hide();
            showSuccess(`Document "${escapeHtml(name)}" added successfully`);
            loadDocuments();
        } else {
            showError(`Failed to add document: ${escapeHtml(data.error)}`);
        }
    } catch(e) {
        showError(`Error: ${escapeHtml(e.message)}`);
    }
}

async function deleteDocument(id) {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
        const response = await fetch(`/api/admin/documents/${id}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.status === 'success') {
            showSuccess('Document deleted successfully');
            loadDocuments();
        } else {
            showError(`Failed to delete: ${escapeHtml(data.error)}`);
        }
    } catch(e) {
        showError(`Error: ${escapeHtml(e.message)}`);
    }
}

async function activateDocument(id) {
    try {
        const response = await fetch(`/api/admin/documents/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: true })
        });

        const data = await response.json();

        if (data.status === 'success') {
            showSuccess('Document activated successfully');
            loadDocuments();
        } else {
            showError(`Failed to activate: ${escapeHtml(data.error)}`);
        }
    } catch(e) {
        showError(`Error: ${escapeHtml(e.message)}`);
    }
}

// ============================================================
// HITL TASKS – UPDATED with outcome controls
// ============================================================

async function loadHITL() {
    try {
        const response = await fetch('/api/admin/hitl');
        const data = await response.json();

        if (data.status === 'error') {
            document.getElementById('hitl-container').innerHTML =
                `<div class="alert alert-danger">${escapeHtml(data.error)}</div>`;
            document.getElementById('hitl-badge').textContent = '0';
            return;
        }

        const tasks = data.data?.tasks || [];
        document.getElementById('hitl-badge').textContent = tasks.length;

        if (tasks.length === 0) {
            document.getElementById('hitl-container').innerHTML =
                '<div class="text-center text-muted py-3">No pending HITL tasks. All good! ✅</div>';
            return;
        }

        let html = '';
        tasks.forEach(t => {
            const statePreview = t.state ? JSON.stringify(t.state, null, 2) : '{}';

            // Determine which outcome buttons to show based on node name
            let outcomeButtons = '';
            if (t.node_name === 'claims_review' || t.node_name === 'underwriting_review') {
                outcomeButtons = `
                    <button class="btn btn-sm btn-success me-1" onclick="resolveHITL(${t.id}, 'approved', 'cleared')">
                        <i class="fas fa-check me-1"></i>Approve (Clear)
                    </button>
                    <button class="btn btn-sm btn-warning me-1" onclick="resolveHITL(${t.id}, 'approved', 'suspicious')">
                        <i class="fas fa-exclamation-triangle me-1"></i>Escalate
                    </button>
                `;
            } else if (t.node_name === 'legal_review') {
                outcomeButtons = `
                    <button class="btn btn-sm btn-success me-1" onclick="resolveHITL(${t.id}, 'approved', 'cleared')">
                        <i class="fas fa-check me-1"></i>Approve (Clear)
                    </button>
                    <button class="btn btn-sm btn-danger me-1" onclick="resolveHITL(${t.id}, 'approved', 'confirmed')">
                        <i class="fas fa-gavel me-1"></i>Confirm Fraud
                    </button>
                `;
            } else {
                // Default: simple approve with no outcome
                outcomeButtons = `
                    <button class="btn btn-sm btn-success me-1" onclick="resolveHITL(${t.id}, 'approved', null)">
                        <i class="fas fa-check me-1"></i>Approve
                    </button>
                `;
            }

            html += `
                <div class="border-bottom py-3">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <strong>${escapeHtml(t.graph_name)}</strong>
                            <span class="badge bg-warning ms-2">Pending</span>
                        </div>
                        <span class="badge ${t.priority === 'urgent' ? 'bg-danger' : t.priority === 'high' ? 'bg-warning' : 'bg-info'}">
                            ${escapeHtml(t.priority || 'medium')}
                        </span>
                    </div>
                    <div class="text-muted small">
                        Run: ${escapeHtml(t.run_id?.substring(0, 12) || 'N/A')}... | Node: ${escapeHtml(t.node_name || 'N/A')}
                        ${t.assigned_to ? `| Assigned: ${escapeHtml(t.assigned_to)}` : ''}
                    </div>
                    <div class="text-muted small">
                        Created: ${t.created_at ? new Date(t.created_at).toLocaleString() : 'N/A'}
                    </div>
                    <div class="mt-2">
                        <details>
                            <summary class="text-muted small">View State</summary>
                            <pre class="small bg-light p-2 rounded mt-1" style="max-height:150px;overflow:auto;">${escapeHtml(statePreview)}</pre>
                        </details>
                    </div>
                    <div class="mt-2">
                        ${outcomeButtons}
                        <button class="btn btn-sm btn-danger" onclick="resolveHITL(${t.id}, 'rejected', null)">
                            <i class="fas fa-times me-1"></i>Reject
                        </button>
                    </div>
                </div>`;
        });

        document.getElementById('hitl-container').innerHTML = html;

    } catch(e) {
        document.getElementById('hitl-container').innerHTML =
            `<div class="alert alert-danger">Error loading HITL tasks: ${escapeHtml(e.message)}</div>`;
        document.getElementById('hitl-badge').textContent = '0';
    }
}

// Updated resolveHITL to accept an outcome parameter
async function resolveHITL(taskId, action, outcome = null) {
    if (!confirm(`Do you want to ${action} this task?`)) return;

    const decision = { action };
    if (outcome) {
        decision.outcome = outcome;
    }

    try {
        const response = await fetch(`/api/admin/hitl/${taskId}/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                decision: decision,
                status: action === 'approved' ? 'resolved' : 'rejected',
                notes: `Admin ${action} this task with outcome: ${outcome || 'N/A'}`
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            showSuccess(`Task #${taskId} ${action} successfully${outcome ? ' with outcome: ' + outcome : ''}`);
            loadHITL();
        } else {
            showError(`Failed to resolve: ${escapeHtml(data.error)}`);
        }
    } catch(e) {
        showError(`Error: ${escapeHtml(e.message)}`);
    }
}

// ============================================================
// TICKETS
// ============================================================

async function loadTickets() {
    try {
        const response = await fetch('/api/admin/tickets');
        const data = await response.json();

        if (data.status === 'error') {
            document.getElementById('tickets-container').innerHTML =
                `<div class="alert alert-danger">${escapeHtml(data.error)}</div>`;
            document.getElementById('ticket-badge').textContent = '0';
            return;
        }

        const tickets = data.data?.tickets || [];
        document.getElementById('ticket-badge').textContent = tickets.length;

        if (tickets.length === 0) {
            document.getElementById('tickets-container').innerHTML =
                '<div class="text-center text-muted py-3">No open tickets. System is healthy! ✅</div>';
            return;
        }

        let html = '';
        tickets.forEach(t => {
            const statePreview = t.state ? JSON.stringify(t.state, null, 2) : 'No state';
            html += `
                <div class="border-bottom py-3">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <strong>${escapeHtml(t.graph_name)}</strong>
                            <span class="badge ${t.status === 'open' ? 'bg-danger' : 'bg-warning'} ms-2">
                                ${escapeHtml(t.status)}
                            </span>
                        </div>
                        <span class="badge ${t.severity === 'critical' ? 'bg-danger' : t.severity === 'high' ? 'bg-warning' : 'bg-info'}">
                            ${escapeHtml(t.severity || 'medium')}
                        </span>
                    </div>
                    <div class="text-danger small">Error: ${escapeHtml(t.error_message)}</div>
                    <div class="text-muted small">
                        Run: ${escapeHtml(t.run_id?.substring(0, 12) || 'N/A')}... | Node: ${escapeHtml(t.node_name || 'N/A')}
                        ${t.assigned_to ? `| Assigned: ${escapeHtml(t.assigned_to)}` : ''}
                    </div>
                    ${t.state ? `
                        <details>
                            <summary class="text-muted small">View State</summary>
                            <pre class="small bg-light p-2 rounded mt-1" style="max-height:100px;overflow:auto;">${escapeHtml(statePreview)}</pre>
                        </details>
                    ` : ''}
                    <button class="btn btn-sm btn-primary mt-2" onclick="resolveTicket(${t.id})">
                        <i class="fas fa-check me-1"></i>Resolve Ticket
                    </button>
                </div>`;
        });

        document.getElementById('tickets-container').innerHTML = html;

    } catch(e) {
        document.getElementById('tickets-container').innerHTML =
            `<div class="alert alert-danger">Error loading tickets: ${escapeHtml(e.message)}</div>`;
        document.getElementById('ticket-badge').textContent = '0';
    }
}

async function resolveTicket(ticketId) {
    const notes = prompt('Enter resolution notes:');
    if (notes === null) return;

    try {
        const response = await fetch(`/api/admin/tickets/${ticketId}/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: 'resolved',
                resolution_notes: notes || 'Resolved by admin'
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            showSuccess(`Ticket #${ticketId} resolved successfully`);
            loadTickets();
        } else {
            showError(`Failed to resolve: ${escapeHtml(data.error)}`);
        }
    } catch(e) {
        showError(`Error: ${escapeHtml(e.message)}`);
    }
}

// ============================================================
// UI HELPERS
// ============================================================

function showSuccess(message) {
    const container = document.getElementById('alert-container');
    if (!container) return;
    container.innerHTML = `
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            <i class="fas fa-check-circle me-2"></i>${escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    setTimeout(() => {
        const alert = container.querySelector('.alert');
        if (alert) alert.remove();
    }, 5000);
}

function showError(message) {
    const container = document.getElementById('alert-container');
    if (!container) return;
    container.innerHTML = `
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            <i class="fas fa-exclamation-circle me-2"></i>${escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    setTimeout(() => {
        const alert = container.querySelector('.alert');
        if (alert) alert.remove();
    }, 5000);
}

// ============================================================
// AUTO-REFRESH (every 30 seconds) - only counts, not full reload
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
    loadAllData();
});

setInterval(() => {
    const hitlTab = document.getElementById('hitl-tab');
    const ticketsTab = document.getElementById('tickets-tab');

    if (hitlTab && hitlTab.classList.contains('active')) {
        fetch('/api/admin/hitl')
            .then(r => r.json())
            .then(data => {
                const count = data.data?.tasks?.length || 0;
                document.getElementById('hitl-badge').textContent = count;
            })
            .catch(() => {});
    }
    if (ticketsTab && ticketsTab.classList.contains('active')) {
        fetch('/api/admin/tickets')
            .then(r => r.json())
            .then(data => {
                const count = data.data?.tickets?.length || 0;
                document.getElementById('ticket-badge').textContent = count;
            })
            .catch(() => {});
    }
}, 30000);