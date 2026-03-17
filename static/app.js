import React, { useState, useEffect, useRef, useMemo } from 'https://esm.sh/react@18';
import { createRoot } from 'https://esm.sh/react-dom@18/client';

const SCENARIOS = {
  '1': 'Scenario 1 — VM Destroy Failure & Orphaned Resources',
  '2': 'Scenario 2 — Tagging Issue & Cost Misattribution',
  '3': 'Scenario 3 — Autoscaler Not Scaling Down',
  '4': 'Scenario 4 — Forgotten POC Environment',
  '5': 'Scenario 5 — App-Level Misconfiguration'
};

const TEAMS = ["All teams", "ci-team", "release-team", "cloudops-team"];

function Rail({ dark, toggleTheme }) {
  return (
    <nav id="rail">
      <svg className="rl-logo" viewBox="0 0 26 26" fill="none">
        <rect width="26" height="26" rx="6" fill="#166534" />
        <rect x="5" y="16" width="3.5" height="6" rx="1.1" fill="#4ADE80" />
        <rect x="10.5" y="12" width="3.5" height="10" rx="1.1" fill="#4ADE80" opacity=".7" />
        <rect x="16" y="8" width="3.5" height="14" rx="1.1" fill="#4ADE80" opacity=".42" />
        <path d="M6.75 15.5L12.25 11.5L17.75 7.5" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="17.75" cy="7.5" r="1.6" fill="white" />
      </svg>
      <div className="rl-sep"></div>
      <div className="rl-icon on" title="Investigation">
        <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
      </div>
      <div className="rl-icon" title="History">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
      </div>
      <div className="rl-icon" title="Settings">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
      </div>
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
        setMode(newMode);
        onNewInvestigation();
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
        body: JSON.stringify({ scenario_id: `scenario_${s}` })
      });
      if (res.ok) {
        setScenario(s);
        onNewInvestigation();
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
              <rect width="32" height="32" rx="8" fill="#166534" />
              <rect x="6" y="19" width="4" height="7" rx="1.3" fill="#4ADE80" />
              <rect x="12.5" y="14.5" width="4" height="11.5" rx="1.3" fill="#4ADE80" opacity=".7" />
              <rect x="19" y="10" width="4" height="16" rx="1.3" fill="#4ADE80" opacity=".42" />
              <path d="M8 18.5L14.5 14L21 9.5" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="21" cy="9.5" r="2" fill="white" />
            </svg>
            <div>
              <div className="logo-name">CORA</div>
              <div className="logo-sub">Cloud Operations &<br />Resource Advisor</div>
            </div>
          </div>
        </div>

        <div className="cfg-sec">
          <div className="cfg-lbl">Data source</div>
          <div className="mode-row">
            <button className={`mode-btn ${!isMock ? 'on' : ''}`} onClick={() => handleModeChange('Live')}>
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
              <span className="st-name">{isMock ? 'Mock mode' : 'Live mode — Azure connected'}</span>
            </div>
            <div className="st-sub">
              {isMock ? `Scenario ${scenario} of 5 active` : 'GitLab + Cost Management API'}
            </div>
          </div>
        </div>

        <button className="new-btn" onClick={onNewInvestigation}>
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
        <h1 className="wlc-title">Investigate cloud cost anomalies.</h1>
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

function ChatMessage({ m }) {
  const isUsr = m.role === 'user';

  const formattedHtml = { __html: m.content || "" };

  return (
    <div className={`mrow ${isUsr ? 'usr' : ''}`}>
      <div className={`mavt ${isUsr ? 'user' : 'agent'}`}>{isUsr ? 'U' : 'CR'}</div>
      <div className={`mbbl ${isUsr ? 'usr' : 'agt'}`}>
        {isUsr ? (
          m.content
        ) : (
          <>
            <div dangerouslySetInnerHTML={formattedHtml} />
            {m.toolsUsed?.length > 0 && (
              <div className="chips">
                {m.toolsUsed.map((t, i) => (
                  <span key={i} className={`chip ${t.includes('cost') ? 'cost' : t.includes('pipe') ? 'pipe' : t.includes('docs') || t.includes('historical') ? 'docs' : 'tag'}`}>
                    <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
                    {t.replace('_tool', '').replace('data_api', 'Cost API').replace('historical', 'Docs')}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ChatMain({ mode, scenario, messages, loading, onSendMsg, ctxOpen, setCtxOpen }) {
  const isMock = mode === 'Mock';
  const [inp, setInp] = useState("");
  const chatRef = useRef(null);

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
        <span className="tb-title">Cloud cost investigation</span>
        <span className="tb-div"></span>
        <span className="tb-sub">{isMock ? `Mock mode · Scenario ${scenario}` : 'Live mode · Azure + GitLab'}</span>
        <span className={`tb-badge ${isMock ? 'mock' : 'live'}`}>{isMock ? 'MOCK' : 'LIVE'}</span>
        <div className="tb-right">
          <span className="tb-conn"><span className="conn-dot"></span>Connected</span>
          <button className="tb-icon-btn" onClick={() => setCtxOpen(!ctxOpen)} title="Toggle context panel">
            <svg viewBox="0 0 24 24" stroke="currentColor" fill="none">
              <polyline points={ctxOpen ? "15 18 9 12 15 6" : "9 18 15 12 9 6"} />
            </svg>
          </button>
        </div>
      </header>

      {isMock && (
        <div id="mock-banner">
          <span className="bnr-pill">MOCK</span>
          <span className="bnr-text">{SCENARIOS[scenario]}</span>
        </div>
      )}

      {messages.length === 0 ? (
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
                {messages.map((m, i) => <ChatMessage key={i} m={m} />)}
                {loading && <TypingIndicator />}
              </div>
            </div>
          </div>
          <div id="input-bar">
            <div className="inp-wrap">
              <input
                type="text"
                placeholder="Ask CORA about your cloud costs..."
                value={inp}
                onChange={(e) => setInp(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
              />
              <span className="inp-hint">Enter ↵ · Shift+Enter for new line</span>
            </div>
            <button className="send-btn" onClick={handleSubmit}>
              <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
            </button>
          </div>
        </div>
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
                  <div className="anomaly-title">{contextData.title}</div>
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
  const [mode, setMode] = useState('Mock');
  const [scenario, setScenario] = useState('1');
  const [teamFilter, setTeamFilter] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ctxOpen, setCtxOpen] = useState(true);
  const [contextData, setContextData] = useState(null);

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
        // We can keep the tools in state or just use them if needed. 
        // The API provides available tools, which informs tool chips rendering.
      } catch (e) {
        console.error("Failed to fetch initial config", e);
      }
    }
    init();
  }, []);

  const handleNewInvestigation = () => {
    setMessages([]);
    setContextData(null);
  };

  const handleSendMsg = async (query) => {
    if (!query.trim()) return;

    const formattedQuery = teamFilter ? `For ${teamFilter}: ${query.trim()}` : query.trim();

    setMessages(prev => [...prev, { role: 'user', content: formattedQuery }]);
    setLoading(true);

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: query.trim(),
          team_filter: teamFilter,
          scenario_id: `scenario_${scenario}`
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Query failed");

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer || "No response received.",
        toolsUsed: data.tools_used || [],
        steps: data.steps || []
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

  return (
    <div id="app">
      <Rail dark={dark} toggleTheme={() => setDark(!dark)} />
      <ConfigPanel
        mode={mode}
        setMode={setMode}
        scenario={scenario}
        setScenario={setScenario}
        teamFilter={teamFilter}
        setTeamFilter={setTeamFilter}
        onNewInvestigation={handleNewInvestigation}
      />
      <ChatMain
        mode={mode}
        scenario={scenario}
        messages={messages}
        loading={loading}
        onSendMsg={handleSendMsg}
        ctxOpen={ctxOpen}
        setCtxOpen={setCtxOpen}
      />
      <ContextPanel open={ctxOpen} contextData={contextData} />
    </div>
  );
}

const root = createRoot(document.getElementById('root'));
root.render(<CoraApp />);
