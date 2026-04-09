import React, { useState, useEffect, useRef, useMemo } from 'https://esm.sh/react@18';
import { createRoot } from 'https://esm.sh/react-dom@18/client';

function toTitleCase(str) {
  if (!str) return str;
  return str.replace(/\w\S*/g, txt =>
    txt.charAt(0).toUpperCase() + txt.substr(1)
  );
}

const SCENARIOS = {
  'scenario_1_vm_destroy': 'Scenario 1 — VM Destroy Failure & Orphaned Resources',
  'scenario_2_tagging': 'Scenario 2 — Tagging Issue & Cost Misattribution',
  'scenario_3_autoscaler': 'Scenario 3 — Autoscaler Not Scaling Down',
  'scenario_4_forgotten_poc': 'Scenario 4 — Forgotten POC Environment',
  'scenario_5_app_misconfig': 'Scenario 5 — App-Level Misconfiguration',
  'scenario_legacy_mock': 'Legacy Mock — Generic Hard-Coded Dataset'
};

const TEAMS = ["All teams", "ci-team", "release-team", "cloudops-team"];

function Rail({ dark, toggleTheme, activeNav, setActiveNav, settingsOpen, setSettingsOpen }) {
  return (
    <nav id="rail">
      <svg className="rl-logo" viewBox="0 0 26 26" fill="none">
        <rect width="26" height="26" rx="6" fill="#009999" />
        <rect x="5" y="16" width="3.5" height="6" rx="1.1" fill="#4DCCCC" />
        <rect x="10.5" y="12" width="3.5" height="10" rx="1.1" fill="#4DCCCC" opacity=".7" />
        <rect x="16" y="8" width="3.5" height="14" rx="1.1" fill="#4DCCCC" opacity=".42" />
        <path d="M6.75 15.5L12.25 11.5L17.75 7.5" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="17.75" cy="7.5" r="1.6" fill="white" />
      </svg>
      <div className="rl-sep"></div>
      <button
        className={`rl-icon ${activeNav === 'chat' ? 'on' : ''}`}
        title="Investigation"
        onClick={() => { setActiveNav('chat'); setSettingsOpen(false); }}
      >
        <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
      </button>
      <button className={`rl-icon ${activeNav === 'history' ? 'on' : ''}`} title="History" onClick={() => setActiveNav('history')}>
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
      </button>
      <button
        className={`rl-icon ${settingsOpen ? 'on' : ''}`}
        title="Settings"
        onClick={() => setSettingsOpen(!settingsOpen)}
      >
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
      </button>
      <div className="rl-spacer"></div>
      <button className="rl-btn" onClick={toggleTheme} title="Toggle theme">
        {!dark ? (
          <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" /><line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" /></svg>
        ) : (
          <svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg>
        )}
      </button>
    </nav>
  );
}

function ConfigPanel({ mode, setMode, scenario, setScenario, teamFilter, setTeamFilter, onNewInvestigation }) {
  const configReady = mode === 'Mock' || mode === 'Live';
  const isMock = mode === 'Mock';

  const handleModeChange = async (newMode) => {
    if (newMode === mode) return;
    try {
      const res = await fetch('/api/config/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode })
      });
      if (res.ok) {
        onNewInvestigation({ reason: 'Mode switched', detail: `${mode} → ${newMode}` });
        setMode(newMode);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleScenarioChange = async (s) => {
    if (s === scenario) return;
    try {
      const res = await fetch('/api/config/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: s })
      });
      if (res.ok) {
        onNewInvestigation({ reason: 'Scenario changed', detail: `${SCENARIOS[scenario] || scenario} → ${SCENARIOS[s] || s}` });
        setScenario(s);
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <aside id="cfg">
      <div className="cfg-inner">
        <div className="cfg-logo">
          <div className="logo-row">
            <svg className="logo-mark" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="#009999" />
              <rect x="6" y="19" width="4" height="7" rx="1.3" fill="#4DCCCC" />
              <rect x="12.5" y="14.5" width="4" height="11.5" rx="1.3" fill="#4DCCCC" opacity=".7" />
              <rect x="19" y="10" width="4" height="16" rx="1.3" fill="#4DCCCC" opacity=".42" />
              <path d="M8 18.5L14.5 14L21 9.5" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="21" cy="9.5" r="2" fill="white" />
            </svg>
            <div>
              <div className="logo-name">CORA</div>
              <div className="logo-sub">FinOps Intelligence</div>
            </div>
          </div>
        </div>

        <div className="cfg-sec">
          <div className="cfg-lbl">Data source</div>
          <div className="mode-row">
            <button className={`mode-btn ${configReady && !isMock ? 'on' : ''}`} onClick={() => handleModeChange('Live')}>
              <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="3" fill="currentColor" /></svg>Live
            </button>
            <button className={`mode-btn ${isMock ? 'on' : ''}`} onClick={() => handleModeChange('Mock')}>
              <svg viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" /></svg>Mock
            </button>
          </div>
        </div>

        {isMock && (
          <div className="cfg-sec">
            <div className="cfg-lbl">Scenario</div>
            <select className="cfg-sel" value={scenario} onChange={(e) => handleScenarioChange(e.target.value)}>
              {Object.entries(SCENARIOS).map(([id, label]) => (
                <option key={id} value={id}>{label}</option>
              ))}
            </select>
          </div>
        )}

        <div className="cfg-sec">
          <div className="cfg-lbl">Team filter</div>
          <select className="cfg-sel" value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)}>
            {TEAMS.map((t) => (
              <option key={t} value={t === "All teams" ? "" : t}>{t}</option>
            ))}
          </select>
        </div>

        <div className="cfg-sec">
          <div className="cfg-lbl">Status</div>
          <div className="status-card">
            <div className="st-row">
              <span className="st-dot"></span>
              <span className="st-name">
                {!configReady ? 'Choose a mode to begin' : (isMock ? 'Mock mode' : 'Live mode — Azure connected')}
              </span>
            </div>
            <div className="st-sub">
              {!configReady
                ? 'Select Live or Mock from the toggle above'
                : (isMock ? `${SCENARIOS[scenario] || scenario} active (${Object.keys(SCENARIOS).length} total)` : 'GitLab + Cost Management API')}
            </div>
          </div>
        </div>

        <button className="new-btn" onClick={() => onNewInvestigation({ reason: 'New investigation' })}>
          <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
          New investigation
        </button>
      </div>
    </aside>
  );
}

function WelcomeScreen({ onSelectStarter }) {
  const starters = [
    "Why has our cloud spend increased this month?",
    "Which team is responsible for the cost spike?",
    "Are there any orphaned or idle resources?",
    "Which pipelines may have caused cost changes?"
  ];
  const [inp, setInp] = useState("");

  return (
    <div id="screen-welcome" style={{ display: 'flex' }}>
      <div className="wlc-body">
        <div className="wlc-mark">
          <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
        </div>
        <h1 className="wlc-title">{toTitleCase('Investigate cloud cost anomalies.')}</h1>
        <p className="wlc-sub">Ask CORA anything about your Azure spend. Get root cause analysis, anomaly detection, and actionable remediation — instantly.</p>
        <div className="starters">
          {starters.map((s, i) => (
            <button key={i} className="starter" onClick={() => onSelectStarter(s)}>{s}</button>
          ))}
        </div>
      </div>
      <div className="wlc-input-bar">
        <div className="inp-wrap">
          <input
            type="text"
            placeholder="Ask CORA about your cloud costs..."
            value={inp}
            onChange={(e) => setInp(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                onSelectStarter(inp);
                setInp('');
              }
            }}
          />
          <span className="inp-hint">Enter ↵</span>
        </div>
        <button className="send-btn" onClick={() => { onSelectStarter(inp); setInp(''); }}>
          <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
        </button>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="mrow typing-row">
      <div className="mavt agent">CR</div>
      <div className="typing-bbl"><span></span><span></span><span></span></div>
    </div>
  );
}

function parseMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
    .replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>(\n|$))+/g, (match) => `<ul>${match}</ul>`)
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^(.+)/, '<p>$1</p>');
}

function ChatMessage({ m, setExpandedMsg }) {
  const isUsr = m.role === 'user';
  const [activeTool, setActiveTool] = useState(null);
  const steps = m.steps || [];
  const filteredSteps = activeTool ? steps.filter((s) => s.tool === activeTool) : steps;

  const agentHtml = useMemo(() => {
    if (isUsr) return '';
    const raw = m.content || '';
    // If content already contains HTML tags (from backend), use as-is
    if (raw.includes('<h3>') || raw.includes('<p>') || raw.includes('<strong>')) {
      return raw;
    }
    return parseMarkdown(raw);
  }, [m.content, isUsr]);

  const messageContent = agentHtml;

  return (
    <div className={`mrow ${isUsr ? 'usr' : ''}`}>
      <div className={`mavt ${isUsr ? 'user' : 'agent'}`}>{isUsr ? 'U' : 'CR'}</div>
      {isUsr ? (
        <div className="mbbl usr">
          {m.content}
        </div>
      ) : (
        <div className="msg-agent">
          <div className="mbbl agt">
            <>
              <div dangerouslySetInnerHTML={{ __html: agentHtml }} />
              {m.toolsUsed?.length > 0 && (
                <div className="chips">
                  {m.toolsUsed.map((t, i) => (
                    <button
                      type="button"
                      key={i}
                      onClick={() => setActiveTool(activeTool === t ? null : t)}
                      className={`chip ${t.includes('cost') ? 'cost' : t.includes('pipe') ? 'pipe' : t.includes('docs') || t.includes('historical') ? 'docs' : 'tag'} ${activeTool === t ? 'active' : ''}`}
                      title="Toggle tool details"
                    >
                      <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
                      {t.replace('_tool', '').replace('data_api', 'Cost API').replace('historical', 'Docs')}
                    </button>
                  ))}
                </div>
              )}
              {m.sources?.length > 0 && (
                <div className="sources">
                  <div className="sources-title">Sources</div>
                  <div className="sources-list">
                    {m.sources.map((s, i) => (
                      <span key={i} className="source-pill">{s}</span>
                    ))}
                  </div>
                </div>
              )}
              {filteredSteps.length > 0 && (
                <div className="tool-details">
                  <div className="tool-details-title">
                    Tool details{activeTool ? `: ${activeTool}` : ''}
                    {activeTool && (
                      <button type="button" className="tool-details-clear" onClick={() => setActiveTool(null)}>
                        Show all
                      </button>
                    )}
                  </div>
                  {filteredSteps.map((step) => (
                    <details key={step.number} className="tool-step" open={filteredSteps.length === 1}>
                      <summary>{step.tool}</summary>
                      <div className="tool-step-body">
                        <div className="tool-step-row"><span>Query</span><code>{step.query}</code></div>
                        <div className="tool-step-row"><span>Result</span><pre><code>{step.result_preview}</code></pre></div>
                        {step.sources?.length > 0 && (
                          <div className="tool-step-row">
                            <span>Sources</span>
                            <div className="sources-list">
                              {step.sources.map((s, i) => (
                                <span key={i} className="source-pill">{s}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </details>
                  ))}
                </div>
              )}
            </>
          </div>
          <button
            className="msg-expand-btn"
            onClick={() => setExpandedMsg(messageContent)}
            title="Expand response"
          >
            <svg viewBox="0 0 24 24" width="11" height="11"
                 fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round">
              <polyline points="15 3 21 3 21 9"/>
              <polyline points="9 21 3 21 3 15"/>
              <line x1="21" y1="3" x2="14" y2="10"/>
              <line x1="3" y1="21" x2="10" y2="14"/>
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}

function HistoryView({ investigations, onDeleteInvestigation, onClearHistory, onExportInvestigation }) {
  if (!investigations.length) {
    return (
      <div id="screen-history">
        <div className="history-empty">
          <div className="history-empty-title">{toTitleCase('No investigations yet')}</div>
          <div className="history-empty-sub">Run a query to start tracking history.</div>
        </div>
      </div>
    );
  }

  return (
    <div id="screen-history">
      <div className="history-header">
        <div className="history-title">Past investigations</div>
        <div className="history-actions">
          <div className="history-count">{investigations.length} total</div>
          <button className="hist-btn danger" onClick={onClearHistory}>Clear history</button>
        </div>
      </div>
      <div className="history-list">
        {investigations.map((inv) => (
          <div className="history-card" key={inv.id}>
            <div className="history-row">
              <div className="hist-card-title">{toTitleCase(inv.title)}</div>
              <div className="hist-card-time">{inv.startedAt}</div>
            </div>
            <div className="hist-card-meta">
              <span>{inv.mode}</span>
              <span>{inv.mode === 'Mock' ? (SCENARIOS[inv.scenario] || `Scenario ${inv.scenario}`) : 'Live'}</span>
              <span>{inv.teamFilter || 'All teams'}</span>
            </div>
            <div className="history-tags">
              <span className="history-tag">Started: {inv.startReason}</span>
              {inv.startDetail ? <span className="history-tag">{inv.startDetail}</span> : null}
              <span className="history-tag">Ended: {inv.endReason}</span>
              {inv.endDetail ? <span className="history-tag">{inv.endDetail}</span> : null}
            </div>
            <div className="hist-actions">
              <button className="hist-btn" onClick={() => onExportInvestigation(inv, 'md')}>Download MD</button>
              <button className="hist-btn" onClick={() => onExportInvestigation(inv, 'doc')}>Download DOC</button>
              <button className="hist-btn" onClick={() => onExportInvestigation(inv, 'pdf')}>Print PDF</button>
              <button className="hist-btn danger" onClick={() => onDeleteInvestigation(inv.id)}>Delete</button>
            </div>
            {inv.toolsUsed?.length > 0 && (
              <div className="chips">
                {inv.toolsUsed.map((t, i) => (
                  <span key={i} className={`chip ${t.includes('cost') ? 'cost' : t.includes('pipe') ? 'pipe' : t.includes('docs') || t.includes('historical') ? 'docs' : 'tag'}`}>
                    <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
                    {t.replace('_tool', '').replace('data_api', 'Cost API').replace('historical', 'Docs')}
                  </span>
                ))}
              </div>
            )}
            <details className="history-details">
              <summary>View transcript</summary>
              <div className="history-transcript">
                {inv.messages.map((m, idx) => (
                  <div className={`history-line ${m.role}`} key={idx}>
                    <span className="history-role">{m.role === 'user' ? 'User' : 'CORA'}</span>
                    <span className="history-text">
                      {m.role === 'assistant'
                        ? <span dangerouslySetInnerHTML={{ __html: parseMarkdown(m.content || '') }} />
                        : m.content}
                      {m.sources?.length ? (
                        <div className="history-sources">
                          {m.sources.map((s, i) => (
                            <span key={i} className="source-pill">{s}</span>
                          ))}
                        </div>
                      ) : null}
                    </span>
                  </div>
                ))}
              </div>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}

function SettingsPanel({ mode }) {
  const isMock = mode === 'Mock';
  const [responseDetail, setResponseDetail] = useState('balanced');
  const [reindexing, setReindexing] = useState(false);
  const [reindexMsg, setReindexMsg] = useState(null);
  const [kbData, setKbData] = useState({ document_count: null, chunk_count: null, last_updated: null });
  const [toolsExpanded, setToolsExpanded] = useState(false);

  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then(data => {
        if (data.knowledge_base) setKbData(data.knowledge_base);
      })
      .catch(() => { });
  }, []);

  const handleDetailChange = async (val) => {
    setResponseDetail(val);
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ response_detail: val })
      });
    } catch (e) {
      console.error('Failed to update response detail', e);
    }
  };

  const handleReindex = async () => {
    setReindexing(true);
    setReindexMsg(null);
    try {
      const res = await fetch('/api/reindex', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (res.ok) {
        setReindexMsg({ text: 'Index updated', ok: true });
      } else {
        setReindexMsg({ text: 'Failed — check console', ok: false });
      }
    } catch (e) {
      console.error(e);
      setReindexMsg({ text: 'Failed — check console', ok: false });
    }
    setReindexing(false);
    setTimeout(() => setReindexMsg(null), 3000);
  };

  const detailHints = {
    concise: 'Key findings only, minimal explanation.',
    balanced: 'Structured summary with root cause and recommendations.',
    detailed: 'Full reasoning chain, evidence, and remediation steps.'
  };

  const connectionStatus = isMock ? 'Simulated' : 'Connected';

  return (
    <main id="cmain">
      <header id="topbar">
        <span className="tb-title">{toTitleCase('Settings')}</span>
      </header>
      <div className="sett-scroll">
        <div className="sett-body">

          {/* Section 1 — Agent configuration */}
          <div className="sett-section">
            <h2 className="sett-heading">{toTitleCase('Agent configuration')}</h2>
            <p className="sett-desc">Controls how CORA reasons and structures its responses.</p>
            <div className="sett-field-label">Response detail</div>
            <div className="mode-row" style={{ marginBottom: 8 }}>
              {['concise', 'balanced', 'detailed'].map(v => (
                <button key={v} className={`mode-btn ${responseDetail === v ? 'on' : ''}`} onClick={() => handleDetailChange(v)}>
                  {v.charAt(0).toUpperCase() + v.slice(1)}
                </button>
              ))}
            </div>
            <div className="sett-hint">{detailHints[responseDetail]}</div>
          </div>

          <div className="sett-divider"></div>

          {/* Section 2 — Data connections */}
          <div className="sett-section">
            <h2 className="sett-heading">{toTitleCase('Data connections')}</h2>
            <p className="sett-desc">Live integration status for connected data providers.</p>
            <div className="sett-conn-grid">
              {/* Azure Cost Management */}
              <div className="sett-conn-card">
                <div className="sett-conn-top">
                  <span className="sett-conn-name">Azure Cost Management</span>
                  <span className="sett-conn-pill connected">
                    <span className="sett-conn-dot"></span>{connectionStatus}
                  </span>
                </div>
                <div className="sett-conn-sub">Cost billing API · Azure subscription</div>
                <div className="sett-conn-time">Last synced: just now</div>
              </div>
              {/* GitLab Pipeline */}
              <div className="sett-conn-card">
                <div className="sett-conn-top">
                  <span className="sett-conn-name">GitLab Pipeline</span>
                  <span className="sett-conn-pill connected">
                    <span className="sett-conn-dot"></span>{connectionStatus}
                  </span>
                </div>
                <div className="sett-conn-sub">Pipeline metadata · CI/CD integration</div>
                <div className="sett-conn-time">Last synced: just now</div>
              </div>
            </div>
          </div>

          <div className="sett-divider"></div>

          {/* Section 3 — Knowledge base */}
          <div className="sett-section">
            <h2 className="sett-heading">{toTitleCase('Knowledge base')}</h2>
            <p className="sett-desc">RAG document index used for historical policy and governance lookups.</p>
            <div className="sett-conn-card">
              <div className="sett-conn-top">
                <span className="sett-conn-name" style={{ fontWeight: 600 }}>Document index</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {reindexing && <span className="sett-spinner"></span>}
                  {reindexMsg && <span style={{ fontSize: 'var(--text-xs)', color: reindexMsg.ok ? 'var(--g600)' : '#DC2626' }}>{reindexMsg.text}</span>}
                  <button className="hist-btn" onClick={handleReindex} disabled={reindexing}>Re-index</button>
                </div>
              </div>
              <div className="sett-kb-stats">
                <div className="sett-stat-chip">
                  <span className="sett-stat-label">Documents indexed</span>
                  <span className="sett-stat-value">{kbData.document_count ?? '—'}</span>
                </div>
                <div className="sett-stat-chip">
                  <span className="sett-stat-label">Chunks</span>
                  <span className="sett-stat-value">{kbData.chunk_count ?? '—'}</span>
                </div>
                <div className="sett-stat-chip">
                  <span className="sett-stat-label">Last updated</span>
                  <span className="sett-stat-value">{kbData.last_updated ?? '—'}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="sett-divider"></div>

          {/* Section 4 — About CORA */}
          <div className="sett-section">
            <h2 className="sett-heading">{toTitleCase('About CORA')}</h2>
            <div className="about-wrap">
              <div className="about-subheading">User guide</div>
              <div className="about-guide">
                <div className="about-guide-item">
                  <div className="about-guide-ico">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <div className="about-guide-body">
                    <div className="about-guide-title">Starting an investigation</div>
                    <div className="about-guide-desc">Type a natural language question about your cloud costs into the input bar and press Enter. CORA will automatically select the relevant tools to investigate and return a structured analysis.</div>
                  </div>
                </div>
                <div className="about-guide-item">
                  <div className="about-guide-ico">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <rect x="1" y="6" width="22" height="12" rx="6" ry="6" fill="none" stroke="currentColor" strokeWidth="1.8" />
                      <circle cx="16" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
                    </svg>
                  </div>
                  <div className="about-guide-body">
                    <div className="about-guide-title">Live vs Mock mode</div>
                    <div className="about-guide-desc">Live mode connects to your real Azure Cost Management and GitLab pipeline data. Mock mode uses one of five synthetic scenarios to demonstrate investigation capabilities without real credentials.</div>
                  </div>
                </div>
                <div className="about-guide-item">
                  <div className="about-guide-ico">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
                      <line x1="9" y1="4" x2="9" y2="20" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                    </svg>
                  </div>
                  <div className="about-guide-body">
                    <div className="about-guide-title">Investigation context panel</div>
                    <div className="about-guide-desc">The right panel populates automatically as CORA investigates. It shows the detected anomaly, cost impact, which tools were called, and the affected resources — updated with each response.</div>
                  </div>
                </div>
                <div className="about-guide-item last">
                  <div className="about-guide-ico">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      <polyline points="7 10 12 15 17 10" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      <line x1="12" y1="15" x2="12" y2="3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                    </svg>
                  </div>
                  <div className="about-guide-body">
                    <div className="about-guide-title">Exporting investigations</div>
                    <div className="about-guide-desc">Past investigations are saved automatically. Access them from the history icon in the left rail. Each investigation can be exported as Markdown, Word document, or PDF for reporting purposes.</div>
                  </div>
                </div>
              </div>

              <button
                type="button"
                className="about-tools-toggle"
                onClick={() => setToolsExpanded(!toolsExpanded)}
              >
                <span className="about-subheading" style={{ marginBottom: 0 }}>Integrated tools</span>
                <span className={`about-chevron ${toolsExpanded ? 'open' : ''}`} aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <polyline points="6 9 12 15 18 9" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              </button>

              {toolsExpanded && (
                <div className="about-tools-list">
                  <div className="about-tool-card">
                    <div className="about-tool-top">
                      <span className="about-tool-pill cost">cost_api</span>
                      <span className="about-tool-title">Azure Cost Management API</span>
                    </div>
                    <div className="about-tool-desc">Retrieves real-time billing data from Azure Cost Management. Returns team-level spend breakdowns, budget status, resource-level costs, and anomaly detection signals for the selected time window.</div>
                  </div>

                  <div className="about-tool-card">
                    <div className="about-tool-top">
                      <span className="about-tool-pill pipe">pipeline_tool</span>
                      <span className="about-tool-title">GitLab Pipeline Tool</span>
                    </div>
                    <div className="about-tool-desc">Queries GitLab CI/CD pipeline metadata to correlate deployment activity with cost changes. Identifies failed destroy jobs, resource provisioning events, and pipeline-level cost causation.</div>
                  </div>

                  <div className="about-tool-card">
                    <div className="about-tool-top">
                      <span className="about-tool-pill docs">historical_tool</span>
                      <span className="about-tool-title">Historical Knowledge Base</span>
                    </div>
                    <div className="about-tool-desc">Performs semantic search over indexed enterprise FinOps documentation, governance policies, and past investigation reports using RAG. Provides policy context and precedent for cost decisions.</div>
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>
      </div>
    </main>
  );
}

function ChatMain({ mode, scenario, messages, loading, onSendMsg, ctxOpen, setCtxOpen, view, investigations, onDeleteInvestigation, onClearHistory, onExportInvestigation, setExpandedMsg }) {
  const configReady = mode === 'Mock' || mode === 'Live';
  const isMock = mode === 'Mock';
  const [inp, setInp] = useState("");
  const chatRef = useRef(null);
  const scenarioLabelRaw = SCENARIOS[scenario] || scenario;
  const scenarioLabel = toTitleCase((scenarioLabelRaw || '').replace(/^Scenario\s*\d+\s*[—-]\s*/i, ''));

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSubmit = () => {
    if (!inp.trim() || loading) return;
    onSendMsg(inp);
    setInp("");
  }

  return (
    <main id="cmain">
      <header id="topbar">
        <span className="tb-title">{toTitleCase('Cloud cost investigation')}</span>
        <span className="tb-div"></span>
        <span className={`topbar-mode-pill ${isMock ? 'mock' : 'live'}`}>{configReady ? (isMock ? 'Mock' : 'Live') : 'Select mode'}</span>
        <span className="topbar-scenario-label">{configReady ? (isMock ? scenarioLabel : 'Azure + GitLab') : 'Choose Live or Mock to begin'}</span>
        <div className="tb-right">
          <span className="tb-conn"><span className="conn-dot"></span>Connected</span>
          <button className="tb-icon-btn" onClick={() => setCtxOpen((prev) => !prev)} title="Toggle context panel">
            <svg viewBox="0 0 24 24" stroke="currentColor" fill="none">
              <polyline points={ctxOpen ? "15 18 9 12 15 6" : "9 18 15 12 9 6"} />
            </svg>
          </button>
        </div>
      </header>

      {configReady && isMock && (
        <div id="mock-banner">
          <span className="bnr-pill">MOCK</span>
          <span className="bnr-text">{toTitleCase(SCENARIOS[scenario] || scenario)}</span>
        </div>
      )}

      {view === 'history' ? (
        <HistoryView
          investigations={investigations}
          onDeleteInvestigation={onDeleteInvestigation}
          onClearHistory={onClearHistory}
          onExportInvestigation={onExportInvestigation}
        />
      ) : (
        messages.length === 0 ? (
          <WelcomeScreen onSelectStarter={onSendMsg} />
        ) : (
          <div id="screen-chat" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div id="chat-wrap">
              <div id="chat-area" ref={chatRef}>
                <div id="chat-spacer">
                  <div className="ce-mark">
                    <svg viewBox="0 0 32 32" fill="none">
                      <rect x="5" y="18" width="4" height="8" rx="1.3" fill="white" />
                      <rect x="12" y="13" width="4" height="13" rx="1.3" fill="white" opacity=".75" />
                      <rect x="19" y="8" width="4" height="18" rx="1.3" fill="white" opacity=".45" />
                      <path d="M7 17.5L14 12.5L21 8" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      <circle cx="21" cy="8" r="2.2" fill="white" />
                    </svg>
                  </div>
                  <div className="ce-name">CORA</div>
                  <div className="ce-sub">Select a scenario and send a message to begin your investigation.</div>
                </div>
                <div className="chat-inner">
                  {messages.map((m, i) => <ChatMessage key={i} m={m} setExpandedMsg={setExpandedMsg} />)}
                  {loading && <TypingIndicator />}
                </div>
              </div>
            </div>
            <div id="input-bar">
              <div className="inp-wrap">
                <input
                  type="text"
                  placeholder={configReady ? "Ask CORA about your cloud costs..." : "Waiting for backend configuration..."}
                  value={inp}
                  onChange={(e) => setInp(e.target.value)}
                  disabled={!configReady}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit();
                    }
                  }}
                />
                <span className="inp-hint">Enter ↵ · Shift+Enter for new line</span>
              </div>
              <button className="send-btn" onClick={handleSubmit} disabled={!configReady}>
                <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
              </button>
            </div>
          </div>
        )
      )}
    </main>
  );
}

function ContextPanel({ open, contextData }) {
  const hasData = !!contextData;
  return (
    <aside id="ctx" className={open ? '' : 'closed'}>
      <div className="ctx-inner">
        <div className="ctx-hdr">
          <span className="ctx-hdr-lbl">Investigation context</span>
        </div>
        <div id="ctx-body" style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
          {!hasData ? (
            <div className="ctx-empty">
              <div className="ctx-empty-ico">
                <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
              </div>
              <p>Start an investigation to see anomaly context, cost impact, and tool activity here.</p>
            </div>
          ) : (
            <>
              {contextData.title && (
                <div className="ctx-sec">
                  <div className="ctx-sec-lbl">Anomaly</div>
                  <div className="anomaly-title">{toTitleCase(contextData.title)}</div>
                  <div className="anomaly-meta">
                    <span className={`sev-badge ${contextData.sev || 'medium'}`}>
                      <span className="sev-dot"></span>{(contextData.sev || 'medium').toUpperCase()}
                    </span>
                    <span className="anomaly-team">{contextData.team || 'Multiple teams'}</span>
                  </div>
                  <div className="metrics-row">
                    <div className="metric-card">
                      <div className="metric-lbl">Cost impact</div>
                      <div className="metric-val">{contextData.impact || '-'}</div>
                      <div className="metric-sub">{contextData.pct || '-'}</div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-lbl">Duration</div>
                      <div className="metric-val neutral">{contextData.days || '-'}</div>
                      <div className="metric-sub">{contextData.since ? `since ${contextData.since}` : '-'}</div>
                    </div>
                  </div>
                  {contextData.cause && (
                    <div className="anomaly-cause">{contextData.cause}</div>
                  )}
                </div>
              )}
              {contextData.tools && contextData.tools.length > 0 && (
                <div className="ctx-sec">
                  <div className="ctx-sec-lbl">Tool activity</div>
                  <div className="tool-log">
                    {contextData.tools.map((t, i) => (
                      <div className="tl-row" key={i}>
                        <span className="tl-dot"></span>
                        <div className="tl-body">
                          <div className="tl-name">{t.n}</div>
                          <div className="tl-detail">{t.d}</div>
                        </div>
                        <span className="tl-time">{t.t}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {contextData.res && contextData.res.length > 0 && (
                <div className="ctx-sec">
                  <div className="ctx-sec-lbl">Affected resources</div>
                  <div className="res-list">
                    {contextData.res.map((r, i) => (
                      <div className="res-row" key={i}>
                        <div className="res-ico">
                          <svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" /></svg>
                        </div>
                        <span className="res-name">{r.n}</span>
                        <span className="res-cost">{r.c}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </aside>
  );
}

function CoraApp() {
  const [dark, setDark] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mode, setMode] = useState(null);
  const [scenario, setScenario] = useState('scenario_1_vm_destroy');
  const [teamFilter, setTeamFilter] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ctxOpen, setCtxOpen] = useState(true);
  const [contextData, setContextData] = useState(null);
  const [expandedMsg, setExpandedMsg] = useState(null);
  const [activeNav, setActiveNav] = useState('chat');
  const [investigations, setInvestigations] = useState([]);
  const [currentStartAt, setCurrentStartAt] = useState(() => new Date().toLocaleString());
  const [currentStartReason, setCurrentStartReason] = useState('Session start');
  const [currentStartDetail, setCurrentStartDetail] = useState('');

  useEffect(() => {
    document.body.classList.toggle('dark', dark);
  }, [dark]);

  useEffect(() => {
    async function init() {
      try {
        const [configRes, toolsRes] = await Promise.all([
          fetch('/api/config'),
          fetch('/api/tools')
        ]);
        const config = await configRes.json();
        const tools = await toolsRes.json();
        if (config.mode) setMode(config.mode);
        if (config.scenario_id) setScenario(config.scenario_id);
        // We can keep the tools in state or just use them if needed. 
        // The API provides available tools, which informs tool chips rendering.
      } catch (e) {
        console.error("Failed to fetch initial config", e);
      }
    }
    init();
  }, []);

  const archiveCurrentInvestigation = (endReason, endDetail) => {
    if (!messages.length) {
      setCurrentStartAt(new Date().toLocaleString());
      setCurrentStartReason(endReason || 'Session start');
      setCurrentStartDetail(endDetail || '');
      return;
    }

    const firstUser = messages.find((m) => m.role === 'user');
    const toolsUsed = Array.from(new Set(messages.flatMap((m) => m.toolsUsed || [])));

    setInvestigations((prev) => [
      {
        id: `inv_${Date.now()}`,
        title: firstUser ? firstUser.content.slice(0, 80) : 'Investigation',
        startedAt: currentStartAt,
        endedAt: new Date().toLocaleString(),
        mode,
        scenario,
        teamFilter,
        startReason: currentStartReason,
        startDetail: currentStartDetail,
        endReason: endReason || 'New investigation',
        endDetail: endDetail || '',
        messages,
        toolsUsed
      },
      ...prev
    ]);

    setCurrentStartAt(new Date().toLocaleString());
    setCurrentStartReason(endReason || 'Session start');
    setCurrentStartDetail(endDetail || '');
  };

  const handleSendMsg = async (query) => {
    if (!query.trim() || (mode !== 'Mock' && mode !== 'Live')) return;

    const formattedQuery = teamFilter ? `For ${teamFilter}: ${query.trim()}` : query.trim();
    const chatHistory = messages.map((m) => ({
      role: m.role,
      content: m.content
    }));

    setMessages(prev => [...prev, { role: 'user', content: formattedQuery }]);
    setLoading(true);

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: query.trim(),
          team_filter: teamFilter,
          scenario_id: mode === 'Mock' ? scenario : '',
          chat_history: chatHistory
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Query failed");

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer || "No response received.",
        toolsUsed: data.tools_used || [],
        steps: data.steps || [],
        sources: data.sources || []
      }]);

      if (data.anomaly_context) {
        setContextData(data.anomaly_context);
      } else {
        // Create mock context data fallback based on scenario response size/timing for realism
        setContextData({
          title: "Cost analysis complete",
          sev: "medium",
          impact: "Pending",
          pct: "Review response",
          days: "Last 30d",
          since: new Date().toLocaleDateString(),
          team: teamFilter || "Multiple teams",
          tools: data.tools_used?.map((t, idx) => ({ t: 'now', n: t, d: 'Tool executed' })) || [],
          res: []
        });
      }
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, { role: 'assistant', content: `**Error**: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleInvestigationReset = ({ reason, detail } = {}) => {
    archiveCurrentInvestigation(reason || 'New investigation', detail || '');
    setMessages([]);
    setContextData(null);
    setActiveNav('chat');
  };

  const handleDeleteInvestigation = (id) => {
    const ok = window.confirm('Delete this investigation? This cannot be undone.');
    if (!ok) return;
    setInvestigations((prev) => prev.filter((inv) => inv.id !== id));
  };

  const handleClearHistory = () => {
    const ok = window.confirm('Clear all investigation history? This cannot be undone.');
    if (!ok) return;
    setInvestigations([]);
  };

  const buildExportMarkdown = (inv) => {
    const header = [
      `# Investigation: ${inv.title}`,
      ``,
      `- Started: ${inv.startedAt}`,
      `- Ended: ${inv.endedAt || ''}`,
      `- Mode: ${inv.mode}`,
      `- Scenario: ${inv.mode === 'Mock' ? (SCENARIOS[inv.scenario] || `Scenario ${inv.scenario}`) : 'Live'}`,
      `- Team: ${inv.teamFilter || 'All teams'}`,
      `- Started reason: ${inv.startReason}${inv.startDetail ? ` (${inv.startDetail})` : ''}`,
      `- End reason: ${inv.endReason}${inv.endDetail ? ` (${inv.endDetail})` : ''}`,
      ``,
      `## Transcript`
    ];

    const lines = inv.messages.flatMap((m) => {
      const role = m.role === 'user' ? 'User' : 'CORA';
      const text = (m.content || '').replace(/\n/g, '\n');
      const out = [`**${role}:** ${text}`];
      if (m.sources?.length) {
        out.push(`Sources: ${m.sources.join(', ')}`);
      }
      return out;
    });

    return header.concat(lines).join('\n');
  };

  const buildExportHtml = (inv) => {
    const esc = (str) => (str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#39;');

    const transcript = inv.messages.map((m) => {
      const role = m.role === 'user' ? 'User' : 'CORA';
      const body = m.role === 'assistant'
        ? parseMarkdown(esc(m.content || ''))
        : `<p>${esc(m.content || '')}</p>`;
      const sources = m.sources?.length
        ? `<div class="sources">Sources: ${m.sources.map((s) => `<span>${esc(s)}</span>`).join(' ')}</div>`
        : '';
      return `<div class="msg"><div class="role">${role}</div><div class="body">${body}${sources}</div></div>`;
    }).join('');

    return `<!doctype html>\n<html><head><meta charset="utf-8"><title>${esc(inv.title)}</title>\n` +
      `<style>\n` +
      `body{font-family:Arial, sans-serif;padding:24px;color:#111;}\n` +
      `h1{font-size:20px;margin:0 0 8px;}\n` +
      `.meta{font-size:12px;color:#444;margin-bottom:16px;}\n` +
      `.msg{margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #eee;}\n` +
      `.role{font-weight:bold;font-size:12px;margin-bottom:4px;}\n` +
      `.body p{margin:0 0 6px;}\n` +
      `.sources{font-size:11px;color:#555;}\n` +
      `.sources span{display:inline-block;margin-right:6px;padding:1px 6px;border:1px solid #ddd;border-radius:10px;}\n` +
      `</style></head><body>\n` +
      `<h1>${esc(inv.title)}</h1>\n` +
      `<div class="meta">Started: ${esc(inv.startedAt)} · Ended: ${esc(inv.endedAt || '')} · Mode: ${esc(inv.mode)} · Scenario: ${esc(inv.mode === 'Mock' ? (SCENARIOS[inv.scenario] || `Scenario ${inv.scenario}`) : 'Live')} · Team: ${esc(inv.teamFilter || 'All teams')}</div>\n` +
      `<h2>Transcript</h2>\n${transcript}\n</body></html>`;
  };

  const downloadBlob = (content, filename, type) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const handleExportInvestigation = (inv, format) => {
    const safeTitle = inv.title.replace(/[^a-z0-9\-]+/gi, '_').slice(0, 60) || 'investigation';
    if (format === 'md') {
      downloadBlob(buildExportMarkdown(inv), `${safeTitle}.md`, 'text/markdown;charset=utf-8');
      return;
    }
    if (format === 'doc') {
      const html = buildExportHtml(inv);
      downloadBlob(html, `${safeTitle}.doc`, 'application/msword;charset=utf-8');
      return;
    }
    if (format === 'pdf') {
      const html = buildExportHtml(inv);
      const win = window.open('', '_blank');
      if (!win) return;
      win.document.write(html);
      win.document.close();
      win.focus();
      setTimeout(() => win.print(), 300);
      return;
    }
  };

  return (
    <div id="app">
      <Rail
        dark={dark}
        toggleTheme={() => setDark(!dark)}
        activeNav={activeNav}
        setActiveNav={setActiveNav}
        settingsOpen={settingsOpen}
        setSettingsOpen={setSettingsOpen}
      />
      <ConfigPanel
        mode={mode}
        setMode={setMode}
        scenario={scenario}
        setScenario={setScenario}
        teamFilter={teamFilter}
        setTeamFilter={setTeamFilter}
        onNewInvestigation={handleInvestigationReset}
      />
      {settingsOpen ? (
        <SettingsPanel mode={mode} />
      ) : (
        <ChatMain
          mode={mode}
          scenario={scenario}
          messages={messages}
          loading={loading}
          onSendMsg={handleSendMsg}
          ctxOpen={ctxOpen}
          setCtxOpen={setCtxOpen}
          view={activeNav}
          investigations={investigations}
          onDeleteInvestigation={handleDeleteInvestigation}
          onClearHistory={handleClearHistory}
          onExportInvestigation={handleExportInvestigation}
          setExpandedMsg={setExpandedMsg}
        />
      )}
      <ContextPanel open={ctxOpen} contextData={contextData} />
      {expandedMsg !== null && (
        <div
          className="msg-modal-overlay"
          onClick={() => setExpandedMsg(null)}
        >
          <div
            className="msg-modal-card"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="msg-modal-close"
              onClick={() => setExpandedMsg(null)}
            >
              <svg viewBox="0 0 24 24" width="13" height="13"
                   fill="none" stroke="currentColor"
                   strokeWidth="2" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
            <div
              className="msg-modal-content"
              dangerouslySetInnerHTML={{ __html: expandedMsg }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

const root = createRoot(document.getElementById('root'));
root.render(<CoraApp />);
