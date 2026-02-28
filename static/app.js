import React, { useEffect, useMemo, useRef, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";

function formatAnswer(text) {
  return text.split("\n").map((line, idx) =>
    React.createElement("p", { key: idx, className: "answer-line" }, line || "\u00A0")
  );
}

function ToolCard({ tool }) {
  return React.createElement(
    "article",
    { className: "tool-card" },
    React.createElement("h4", null, tool.name),
    React.createElement("p", null, tool.description)
  );
}

function Message({ msg }) {
  const isUser = msg.role === "user";
  return React.createElement(
    "section",
    { className: `msg ${isUser ? "user" : "assistant"}` },
    React.createElement(
      "header",
      { className: "msg-head" },
      React.createElement("span", { className: "avatar" }, isUser ? "You" : "CORA"),
      !isUser && msg.toolsUsed?.length
        ? React.createElement("span", { className: "used-tools" }, `Tools: ${msg.toolsUsed.join(", ")}`)
        : null
    ),
    React.createElement("div", { className: "msg-body" }, isUser ? msg.content : formatAnswer(msg.content)),
    !isUser && msg.steps?.length
      ? React.createElement(
          "div",
          { className: "steps" },
          React.createElement("h5", null, "Investigation Steps"),
          msg.steps.map((step) =>
            React.createElement(
              "details",
              { key: step.number, open: step.number === 1, className: "step-item" },
              React.createElement("summary", null, `Step ${step.number}: ${step.tool}`),
              React.createElement("p", null, `Query: ${step.query}`),
              React.createElement("p", null, `Result: ${step.result_preview}`)
            )
          )
        )
      : null
  );
}

function App() {
  const [mode, setMode] = useState("Mock");
  const [teamOptions, setTeamOptions] = useState(["All Teams"]);
  const [teamFilter, setTeamFilter] = useState("All Teams");
  const [exampleQueries, setExampleQueries] = useState([]);
  const [tools, setTools] = useState([]);
  const [messages, setMessages] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const chatEndRef = useRef(null);

  useEffect(() => {
    async function bootstrap() {
      const [configRes, toolsRes] = await Promise.all([fetch("/api/config"), fetch("/api/tools")]);
      const configData = await configRes.json();
      const toolsData = await toolsRes.json();

      setMode(configData.mode || "Mock");
      setTeamOptions(configData.team_options || ["All Teams"]);
      setTeamFilter((configData.team_options || ["All Teams"])[0]);
      setExampleQueries(configData.example_queries || []);
      setTools(toolsData.tools || []);
    }

    bootstrap().catch(() => setError("Failed to load app configuration."));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const modeBadge = useMemo(() => (mode === "Live" ? "Live data (Azure + GitLab)" : "Mock demo data"), [mode]);

  async function updateMode(nextMode) {
    if (nextMode === mode) return;
    setError("");

    try {
      const res = await fetch("/api/config/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: nextMode }),
      });

      if (!res.ok) throw new Error("Failed to switch mode");

      const data = await res.json();
      setMode(data.mode || nextMode);
      setMessages([]);
    } catch (e) {
      setError("Could not switch data mode.");
    }
  }

  async function runQuery(customPrompt) {
    const activePrompt = (customPrompt ?? prompt).trim();
    if (!activePrompt || loading) return;

    setError("");
    setLoading(true);

    const prefixed = teamFilter !== "All Teams" ? `For ${teamFilter}: ${activePrompt}` : activePrompt;
    setMessages((prev) => [...prev, { role: "user", content: prefixed }]);
    setPrompt("");

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: activePrompt, team_filter: teamFilter }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Query failed");

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer || "No answer returned.",
          toolsUsed: data.tools_used || [],
          steps: data.steps || [],
        },
      ]);
    } catch (e) {
      setError(e.message || "Investigation failed.");
    } finally {
      setLoading(false);
    }
  }

  return React.createElement(
    "div",
    { className: "layout" },
    React.createElement(
      "aside",
      { className: "sidebar" },
      React.createElement("h1", null, "CORA Controls"),
      React.createElement("p", { className: "subtle" }, "Configure your investigation context"),
      React.createElement("h3", null, "Data Mode"),
      React.createElement(
        "div",
        { className: "toggle-group" },
        ["Mock", "Live"].map((m) =>
          React.createElement(
            "button",
            {
              key: m,
              className: `toggle ${mode === m ? "active" : ""}`,
              onClick: () => updateMode(m),
              type: "button",
            },
            m
          )
        )
      ),
      React.createElement("p", { className: "mode-badge" }, modeBadge),
      React.createElement("h3", null, "Team Filter"),
      React.createElement(
        "select",
        {
          className: "team-select",
          value: teamFilter,
          onChange: (e) => setTeamFilter(e.target.value),
        },
        teamOptions.map((team) => React.createElement("option", { key: team, value: team }, team))
      ),
      React.createElement("h3", null, "Example Queries"),
      React.createElement(
        "div",
        { className: "examples" },
        exampleQueries.map((q) =>
          React.createElement(
            "button",
            { key: q, className: "example-btn", type: "button", onClick: () => runQuery(q) },
            q
          )
        )
      ),
      React.createElement("footer", { className: "sidebar-footer" }, `CORA v2.0 • ${mode} Mode`)
    ),
    React.createElement(
      "main",
      { className: "main" },
      React.createElement(
        "header",
        { className: "hero" },
        React.createElement("p", { className: "eyebrow" }, "Cloud Optimization & Resource Advisor"),
        React.createElement("h2", null, "Investigate cloud spend with clarity"),
        React.createElement(
          "p",
          { className: "hero-copy" },
          "Track policy, spending, and deployment signals in one place without changing your backend logic."
        )
      ),
      React.createElement(
        "section",
        { className: "tools-panel" },
        React.createElement("h3", null, "Available Investigation Tools"),
        React.createElement("div", { className: "tools-grid" }, tools.map((tool) => React.createElement(ToolCard, { key: tool.name, tool })))
      ),
      React.createElement(
        "section",
        { className: "chat-panel" },
        React.createElement("h3", null, "Investigation Chat"),
        error ? React.createElement("div", { className: "error" }, error) : null,
        React.createElement(
          "div",
          { className: "chat-log" },
          messages.length
            ? messages.map((msg, i) => React.createElement(Message, { key: `${msg.role}-${i}`, msg }))
            : React.createElement("p", { className: "empty" }, "Ask your first question to start an investigation."),
          loading ? React.createElement("div", { className: "loading" }, "Analyzing data...") : null,
          React.createElement("div", { ref: chatEndRef })
        ),
        React.createElement(
          "form",
          {
            className: "composer",
            onSubmit: (e) => {
              e.preventDefault();
              runQuery();
            },
          },
          React.createElement("input", {
            value: prompt,
            onChange: (e) => setPrompt(e.target.value),
            placeholder: "Start your investigation...",
            disabled: loading,
            maxLength: 1200,
          }),
          React.createElement(
            "button",
            { type: "submit", disabled: loading || !prompt.trim() },
            loading ? "Running..." : "Investigate"
          )
        )
      )
    )
  );
}

createRoot(document.getElementById("root")).render(React.createElement(App));
