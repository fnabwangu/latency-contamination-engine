const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));

class CandidateCard extends HTMLElement {
  connectedCallback() {
    const candidate = JSON.parse(this.dataset.candidate);
    this.innerHTML = `<article class="candidate-card ${candidate.state === 'BLOCKED' ? 'blocked' : ''}">
      <div class="card-head"><h3>${escapeHtml(candidate.name)}</h3><span class="badge">${escapeHtml(candidate.state)}</span></div>
      <div class="id">${escapeHtml(candidate.candidate_id)} · ${escapeHtml(candidate.candidate_type)}</div>
      <dl><dt>Thesis</dt><dd>${escapeHtml(candidate.thesis)}</dd><dt>Why now</dt><dd>${escapeHtml(candidate.catalyst)}</dd><dt>Horizon</dt><dd>${escapeHtml(candidate.horizon)}</dd><dt>Confidence</dt><dd>${candidate.confidence == null ? 'Unscored' : escapeHtml(candidate.confidence)}</dd><dt>Dissent</dt><dd>${escapeHtml(candidate.dissent || 'No material dissent recorded')}</dd></dl>
      <div class="actions"><button data-action="inspect" data-id="${escapeHtml(candidate.candidate_id)}">Inspect</button><button data-action="BACK_BURNER" data-id="${escapeHtml(candidate.candidate_id)}">Park</button><button data-action="DISCARDED" data-id="${escapeHtml(candidate.candidate_id)}">Discard</button></div>
    </article>`;
  }
}
customElements.define('candidate-card', CandidateCard);

class CandidateShelves extends HTMLElement {
  set candidates(value) {
    this.items = value;
    this.render();
  }
  render() {
    const shelves = { 'Decision queue': this.items.filter((item) => !['BACK_BURNER', 'DISCARDED', 'ARCHIVED'].includes(item.state)), 'Back burner': this.items.filter((item) => item.state === 'BACK_BURNER'), Archive: this.items.filter((item) => ['DISCARDED', 'ARCHIVED', 'COMPLETED'].includes(item.state)) };
    this.innerHTML = `<nav class="shelves" aria-label="Candidate shelves">${Object.keys(shelves).map((name, index) => `<button class="shelf-tab ${index === 0 ? 'active' : ''}" data-shelf="${escapeHtml(name)}">${escapeHtml(name)} <span>${shelves[name].length}</span></button>`).join('')}</nav><div class="shelf-content"></div>`;
    this.shelves = shelves;
    this.querySelectorAll('.shelf-tab').forEach((tab) => tab.addEventListener('click', () => { this.querySelectorAll('.shelf-tab').forEach((item) => item.classList.remove('active')); tab.classList.add('active'); this.renderShelf(tab.dataset.shelf); }));
    this.renderShelf('Decision queue');
  }
  renderShelf(name) {
    const content = this.querySelector('.shelf-content');
    const items = this.shelves[name] || [];
    content.innerHTML = items.length ? `<div class="cards">${items.slice(0, 3).map((item) => `<candidate-card data-candidate='${escapeHtml(JSON.stringify(item))}'></candidate-card>`).join('')}</div>` : '<div class="empty">Nothing in this shelf.</div>';
  }
}
customElements.define('candidate-shelves', CandidateShelves);

class AuditPanel extends HTMLElement {
  async inspect(candidateId) {
    this.hidden = false;
    this.innerHTML = '<div class="audit-panel"><button class="close" aria-label="Close audit">Close</button><p>Loading audit...</p></div>';
    this.querySelector('.close').addEventListener('click', () => { this.hidden = true; });
    try {
      const audit = await fetch(`/candidates/${encodeURIComponent(candidateId)}/audit`).then((response) => response.json());
      this.innerHTML = `<div class="audit-panel"><button class="close" aria-label="Close audit">Close</button><div class="eyebrow">Level 2 audit</div><h2>${escapeHtml(audit.candidate.name)}</h2><p>${escapeHtml(audit.candidate.thesis)}</p><h3>Lifecycle</h3><ul>${audit.lifecycle.map((event) => `<li><strong>${escapeHtml(event.to_state)}</strong> ${escapeHtml(event.reason)}</li>`).join('') || '<li>No lifecycle events</li>'}</ul><h3>Gate evaluations</h3><p>${audit.gates.length} recorded evaluations</p><h3>LCAEs</h3><p>${audit.lcaes.length} collective-action diagnostics</p></div>`;
      this.querySelector('.close').addEventListener('click', () => { this.hidden = true; });
    } catch { this.innerHTML = '<div class="audit-panel"><button class="close">Close</button><p>Audit unavailable.</p></div>'; this.querySelector('.close').addEventListener('click', () => { this.hidden = true; }); }
  }
}
customElements.define('audit-panel', AuditPanel);

const app = {
  async load() {
    const [health, queue] = await Promise.all([fetch('/health').then((response) => response.json()), fetch('/queue').then((response) => response.json())]);
    document.querySelector('#run').textContent = `Run ${health.run_id.slice(0, 12)} · live`;
    document.querySelector('#count').textContent = `${Math.min(queue.length, 3)} of 3 shown`;
    document.querySelector('candidate-shelves').candidates = queue;
  },
  async disposition(id, action) {
    await fetch(`/candidates/${encodeURIComponent(id)}/disposition`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ disposition: action, reason: 'human meeting-surface action' }) });
    await this.load();
  }
};

document.addEventListener('click', (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  if (button.dataset.action === 'inspect') document.querySelector('audit-panel').inspect(button.dataset.id);
  else app.disposition(button.dataset.id, button.dataset.action);
});
app.load().catch(() => { document.querySelector('#run').textContent = 'Coordinator unavailable'; document.querySelector('candidate-shelves').innerHTML = '<div class="empty">The Coordinator could not be reached. Server state remains authoritative.</div>'; });
