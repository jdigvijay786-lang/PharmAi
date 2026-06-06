from flask import Flask, request, Response, stream_with_context
import json

try:
    import ollama
    OLLAMA_OK = True
except ImportError:
    OLLAMA_OK = False

app = Flask(__name__)
MODEL = "llama3.2"

SYSTEM_PROMPT = (
    "You are PharmAI, an expert AI assistant for pharmacy students. "
    "Help with drug mechanisms, pharmacokinetics, drug classes, interactions, "
    "side effects, dosage calculations, brand and generic names, patient counseling, "
    "prescription abbreviations like OD BD TDS QID PRN, and disease treatments. "
    "Use plain sentences. Always mention generic and brand names. Be clear and educational."
)

DIAGRAM_PROMPT = (
    "You are PharmAI, a pharmacy AI that creates study diagrams. "
    "Respond ONLY with valid Mermaid.js syntax. No explanation, no markdown fences, no extra text. "
    "Use short labels that pharmacy students can revise from. "
    "For flowchart/graph nodes, every node must use a compact id plus bracket text, like A[Drug Ingested]. "
    "Never write node names with spaces directly. Always put each connection on a new line. "
    "Avoid parentheses inside flowchart or graph node labels; use commas or hyphens instead. "
    "For pie charts, use Mermaid pie syntax with quoted labels and numeric values. "
    "For mind maps, use mindmap syntax with indented concepts. "
    "For timelines, use Mermaid timeline syntax with sections when useful. "
    "For sequence diagrams, use only participants, arrows, notes, loops, alt/else/end blocks, titles, and activation commands; never include numbered lists or prose lines. "
    "For class charts, use classDiagram syntax with simple class names and relationships. "
    "Return only raw Mermaid code beginning with the diagram type. "
    "Example:\n"
    "flowchart TD\n"
    "    A[Drug Ingested] --> B[Absorption]\n"
    "    B --> C[Distribution]\n"
    "    C --> D[Metabolism]\n"
    "    D --> E[Excretion]"
)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>PharmAI</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
:root {
  --bg:#0d1117; --surface:#161b22; --surface2:#1c2333; --border:#30363d;
  --accent:#3fb68b; --accent2:#58d4a4; --accent-dim:#1a3d30;
  --user-bg:#1a2744; --user-border:#2d4a8a;
  --text:#e6edf3; --muted:#8b949e; --red:#f85149; --yellow:#e3b341;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;
  height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* Header */
header{display:flex;align-items:center;justify-content:space-between;
  padding:12px 24px;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0}
.logo{display:flex;align-items:center;gap:10px}
.logo-icon{width:36px;height:36px;background:var(--accent-dim);border:1.5px solid var(--accent);
  border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}
.logo-text{font-size:20px;font-weight:500;color:var(--accent2)}
.logo-sub{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace}
.hbtns{display:flex;gap:8px;align-items:center}
.badge{font-family:'DM Mono',monospace;font-size:10px;padding:3px 8px;
  border-radius:20px;border:1px solid var(--border);color:var(--muted)}
.ibtn{background:none;border:1px solid var(--border);color:var(--muted);border-radius:8px;
  width:34px;height:34px;cursor:pointer;font-size:15px;display:flex;align-items:center;
  justify-content:center;transition:all .15s}
.ibtn:hover{border-color:var(--accent);color:var(--accent)}
.ibtn.on{background:var(--accent-dim);border-color:var(--accent);color:var(--accent2)}

/* Tabs */
.tabs{display:flex;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0}
.tab{padding:10px 22px;font-size:13px;font-family:'DM Mono',monospace;cursor:pointer;
  color:var(--muted);border-bottom:2px solid transparent;transition:all .15s;
  display:flex;align-items:center;gap:6px;background:none;border-top:none;border-left:none;border-right:none}
.tab:hover{color:var(--text)}
.tab.active{color:var(--accent2);border-bottom-color:var(--accent)}

/* Status */
#status{display:none;padding:7px 24px;font-family:'DM Mono',monospace;font-size:12px;flex-shrink:0}

/* Speaking bar */
#spkbar{display:none;background:var(--accent-dim);border-top:1px solid var(--accent);
  padding:6px 24px;font-family:'DM Mono',monospace;font-size:11px;color:var(--accent);
  align-items:center;gap:8px;flex-shrink:0}
#spkbar.on{display:flex}
.wave{display:flex;gap:2px;align-items:center}
.wave span{display:block;width:3px;background:var(--accent);border-radius:2px;animation:wv .8s ease-in-out infinite}
.wave span:nth-child(1){height:6px;animation-delay:0s}
.wave span:nth-child(2){height:12px;animation-delay:.1s}
.wave span:nth-child(3){height:8px;animation-delay:.2s}
.wave span:nth-child(4){height:14px;animation-delay:.15s}
.wave span:nth-child(5){height:6px;animation-delay:.05s}
@keyframes wv{0%,100%{transform:scaleY(1)}50%{transform:scaleY(0.3)}}
#stopbtn{margin-left:auto;background:none;border:1px solid var(--accent);color:var(--accent);
  border-radius:5px;font-size:10px;font-family:'DM Mono',monospace;padding:2px 8px;cursor:pointer}

/* Layout */
.layout{display:flex;flex:1;overflow:hidden}

/* Sidebar */
aside{width:210px;background:var(--surface);border-right:1px solid var(--border);
  display:flex;flex-direction:column;padding:14px 10px;gap:4px;flex-shrink:0;overflow-y:auto}
.slabel{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1.5px;
  color:var(--muted);padding:4px 8px 6px;text-transform:uppercase}
.sbtn{background:none;border:1px solid transparent;border-radius:8px;color:var(--muted);
  font-family:'DM Sans',sans-serif;font-size:12.5px;padding:8px 10px;cursor:pointer;
  text-align:left;transition:all .15s;display:flex;align-items:center;gap:8px;width:100%}
.sbtn:hover{background:var(--accent-dim);border-color:#2a4a38;color:var(--text)}
.sbtn.diagram-btn{color:var(--yellow)}
.sbtn.diagram-btn:hover{background:#3d2e1a;border-color:#5a4a1a}
.sdiv{height:1px;background:var(--border);margin:6px 0}

/* Main panels */
main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.panel{display:none;flex:1;flex-direction:column;overflow:hidden}
.panel.active{display:flex}

/* Chat panel */
#chat{flex:1;overflow-y:auto;padding:24px 0;scroll-behavior:smooth}
#chat::-webkit-scrollbar{width:4px}
#chat::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.wrap{max-width:740px;margin:0 auto;padding:0 24px}
.msg{margin-bottom:20px;animation:fadeUp .2s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg.user .bub{background:var(--user-bg);border:1px solid var(--user-border);
  border-radius:16px 16px 4px 16px;padding:12px 16px;margin-left:auto;
  max-width:75%;width:fit-content;font-size:14px;line-height:1.6}
.ai-hdr{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.ai-av{width:26px;height:26px;background:var(--accent-dim);border:1px solid var(--accent);
  border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:13px}
.ai-nm{font-family:'DM Mono',monospace;font-size:11px;color:var(--accent)}
.msg.ai .bub{background:var(--surface2);border:1px solid var(--border);
  border-radius:4px 16px 16px 16px;padding:16px 20px;font-size:14px;
  line-height:1.75;white-space:pre-wrap;word-break:break-word}
.msg.ai .bub.streaming::after{content:'▋';color:var(--accent);
  animation:blink .8s step-end infinite;margin-left:2px}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
.msgbtns{display:flex;gap:6px;margin-top:8px}
.msgbtn{background:none;border:1px solid var(--border);border-radius:6px;
  color:var(--muted);font-size:11px;font-family:'DM Mono',monospace;padding:4px 10px;
  cursor:pointer;display:none;align-items:center;gap:5px;transition:all .15s}
.msgbtn:hover{border-color:var(--accent);color:var(--accent)}
.msgbtn.diag{color:var(--yellow);border-color:#5a4a1a}
.msgbtn.diag:hover{background:#3d2e1a;border-color:var(--yellow)}
.welcome{text-align:center;padding:60px 20px}
.welcome-icon{font-size:48px;margin-bottom:16px}
.welcome h2{font-size:26px;font-weight:400;margin-bottom:8px}
.welcome p{color:var(--muted);font-size:14px;max-width:380px;margin:0 auto;line-height:1.6}

/* Diagram panel */
#diag-panel{flex:1;display:flex;flex-direction:column;overflow:hidden}
.diag-toolbar{display:flex;align-items:center;gap:10px;padding:12px 20px;
  background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0}
.diag-toolbar select{background:var(--surface2);border:1px solid var(--border);color:var(--text);
  border-radius:8px;padding:6px 10px;font-family:'DM Mono',monospace;font-size:12px;outline:none}
.diag-toolbar input{flex:1;background:var(--surface2);border:1px solid var(--border);
  color:var(--text);border-radius:8px;padding:8px 14px;font-family:'DM Sans',sans-serif;
  font-size:13px;outline:none}
.diag-toolbar input:focus{border-color:var(--accent)}
.diag-toolbar input::placeholder{color:var(--muted)}
.template-strip{display:flex;gap:8px;padding:10px 20px;background:var(--bg);
  border-bottom:1px solid var(--border);overflow-x:auto;flex-shrink:0}
.tbtn{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
  color:var(--muted);font-size:11px;font-family:'DM Mono',monospace;padding:7px 10px;
  cursor:pointer;white-space:nowrap;transition:all .15s}
.tbtn:hover{border-color:var(--accent);color:var(--accent2);background:var(--accent-dim)}
.gbtn{background:var(--accent);border:none;border-radius:8px;color:#0d1117;
  font-size:13px;font-weight:500;padding:8px 16px;cursor:pointer;white-space:nowrap;transition:all .15s}
.gbtn:hover{background:var(--accent2)}
.gbtn:disabled{background:var(--border);color:var(--muted);cursor:not-allowed}

.diag-content{flex:1;display:flex;gap:0;overflow:hidden}
.diag-code{width:280px;flex-shrink:0;border-right:1px solid var(--border);display:flex;flex-direction:column}
.diag-code-label{font-family:'DM Mono',monospace;font-size:10px;color:var(--muted);
  padding:8px 14px;border-bottom:1px solid var(--border);letter-spacing:1px}
.diag-code textarea{flex:1;background:var(--surface2);border:none;color:var(--accent2);
  font-family:'DM Mono',monospace;font-size:12px;padding:14px;resize:none;outline:none;line-height:1.6}
.diag-code-btns{display:flex;gap:6px;padding:8px 12px;border-top:1px solid var(--border)}
.cbtn{background:none;border:1px solid var(--border);border-radius:6px;color:var(--muted);
  font-size:11px;font-family:'DM Mono',monospace;padding:4px 10px;cursor:pointer;transition:all .15s}
.cbtn:hover{border-color:var(--accent);color:var(--accent)}

.diag-view{flex:1;overflow:auto;display:flex;align-items:center;justify-content:center;
  padding:30px;position:relative}
#mermaid-output{background:white;border-radius:12px;padding:30px;min-width:300px;
  box-shadow:0 4px 24px rgba(0,0,0,0.4)}
#mermaid-output svg{display:block;margin:auto;max-width:100%;height:auto}
.diag-actions{position:absolute;right:18px;top:14px;display:flex;gap:8px;z-index:2}
.diag-actions .cbtn{background:var(--surface);color:var(--text)}
.diag-placeholder{text-align:center;color:var(--muted)}
.diag-placeholder .pi{font-size:48px;margin-bottom:12px}
.diag-placeholder p{font-size:13px;line-height:1.6}

/* Input bar */
.ibar{padding:14px 24px 18px;background:var(--surface);border-top:1px solid var(--border);flex-shrink:0}
.irow{max-width:740px;margin:0 auto;display:flex;gap:10px;align-items:flex-end}
textarea#inp{flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:12px;
  color:var(--text);font-family:'DM Sans',sans-serif;font-size:14px;padding:12px 16px;
  resize:none;outline:none;min-height:48px;max-height:150px;line-height:1.5;transition:border-color .15s}
textarea#inp:focus{border-color:var(--accent)}
textarea#inp::placeholder{color:var(--muted)}
.sendbtn{background:var(--accent);border:none;border-radius:10px;color:#0d1117;
  font-size:18px;width:48px;height:48px;cursor:pointer;display:flex;
  align-items:center;justify-content:center;flex-shrink:0;transition:all .15s}
.sendbtn:hover{background:var(--accent2)}
.sendbtn:disabled{background:var(--border);color:var(--muted);cursor:not-allowed}
.hint{max-width:740px;margin:5px auto 0;font-size:11px;color:var(--muted);font-family:'DM Mono',monospace}

.diag-err{color:var(--red);font-family:'DM Mono',monospace;font-size:12px;
  padding:16px;background:#1a0a0a;border:1px solid #5a1a1a;border-radius:8px;white-space:pre-wrap}
.spinner{display:inline-block;width:20px;height:20px;border:2px solid var(--border);
  border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-icon">💊</div>
    <div>
      <div class="logo-text">PharmAI</div>
      <div class="logo-sub">PHARMACY STUDENT ASSISTANT</div>
    </div>
  </div>
  <div class="hbtns">
    <span class="badge">llama3.2 · local</span>
    <button class="ibtn on" id="audioBtn" title="Toggle audio">🔊</button>
    <button class="ibtn" id="clearBtn" title="Clear chat">🗑</button>
  </div>
</header>

<div class="tabs">
  <button class="tab active" id="tab-chat">💬 Chat</button>
  <button class="tab" id="tab-diag">📊 Diagrams & Charts</button>
</div>

<div id="status"></div>
<div id="spkbar">
  <div class="wave"><span></span><span></span><span></span><span></span><span></span></div>
  Speaking...
  <button id="stopbtn">■ Stop</button>
</div>

<div class="layout">
  <aside>
    <div class="slabel">Quick Topics</div>
    <button class="sbtn" id="s1">🦠 Antibiotics</button>
    <button class="sbtn" id="s2">📈 Pharmacokinetics</button>
    <button class="sbtn" id="s3">🧮 Dosage Calc</button>
    <button class="sbtn" id="s4">⚠️ Drug Interactions</button>
    <button class="sbtn" id="s5">❤️ Cardio Drugs</button>
    <button class="sbtn" id="s6">💉 Analgesics</button>
    <button class="sbtn" id="s7">📋 Side Effects</button>
    <button class="sbtn" id="s8">🏥 OTC Drugs</button>
    <button class="sbtn" id="s9">🔬 ADME</button>
    <div class="sdiv"></div>
    <div class="slabel">Diagrams</div>
    <button class="sbtn diagram-btn" id="d1">🔄 ADME Flowchart</button>
    <button class="sbtn diagram-btn" id="d2">💊 Drug Mechanism</button>
    <button class="sbtn diagram-btn" id="d3">⚠️ Interaction Chart</button>
    <button class="sbtn diagram-btn" id="d4">🏥 Treatment Flow</button>
    <button class="sbtn diagram-btn" id="d5">📊 Drug Classes</button>
    <div class="sdiv"></div>
    <div class="slabel">Exam Prep</div>
    <button class="sbtn" id="s10">📝 Practice MCQs</button>
    <button class="sbtn" id="s11">📄 Rx Abbreviations</button>
    <button class="sbtn" id="s12">⭐ Must-Know Drugs</button>
  </aside>

  <main>
    <!-- Chat Panel -->
    <div class="panel active" id="panel-chat">
      <div id="chat">
        <div class="wrap">
          <div class="welcome" id="welcome">
            <div class="welcome-icon">💊</div>
            <h2>Welcome to PharmAI</h2>
            <p>Ask about drug mechanisms, interactions, dosages and more — or click <b>Diagrams & Charts</b> to visualize any concept.</p>
          </div>
        </div>
      </div>
      <div class="ibar">
        <div class="irow">
          <textarea id="inp" placeholder="Ask about a drug, mechanism, interaction..." rows="1"></textarea>
          <button class="sendbtn" id="sendBtn">➤</button>
        </div>
        <div class="hint">Enter to send &nbsp;·&nbsp; Shift+Enter for new line</div>
      </div>
    </div>

    <!-- Diagram Panel -->
    <div class="panel" id="panel-diag">
      <div class="diag-toolbar">
        <select id="diagType">
          <option value="flowchart">Flowchart</option>
          <option value="sequence">Sequence</option>
          <option value="graph">Graph / Map</option>
          <option value="pie">Pie Chart</option>
          <option value="timeline">Timeline</option>
          <option value="mindmap">Mind Map</option>
          <option value="class">Class Chart</option>
        </select>
        <input id="diagInput" placeholder="Describe what to visualize e.g. ADME process, beta blocker mechanism..."/>
        <button class="gbtn" id="diagBtn">? Generate</button>
      </div>
      <div class="template-strip" id="templateStrip">
        <button class="tbtn" data-type="flowchart" data-prompt="Create an ADME flowchart with absorption, distribution, metabolism, excretion, and clinical factors">ADME Flow</button>
        <button class="tbtn" data-type="flowchart" data-prompt="Create a stepwise mechanism of action flowchart for beta blockers">MOA Flow</button>
        <button class="tbtn" data-type="graph" data-prompt="Create an interaction map for warfarin with major interacting drug classes and outcomes">Interaction Map</button>
        <button class="tbtn" data-type="pie" data-prompt="Create a pie chart showing common causes of medication non-adherence">Pie Chart</button>
        <button class="tbtn" data-type="timeline" data-prompt="Create a timeline of onset, peak, and duration for insulin types">Timeline</button>
        <button class="tbtn" data-type="mindmap" data-prompt="Create a mind map of antihypertensive drug classes, examples, and key adverse effects">Mind Map</button>
        <button class="tbtn" data-type="class" data-prompt="Create a class chart for analgesics with NSAIDs, opioids, acetaminophen, examples, and cautions">Class Chart</button>
      </div>
      <div class="diag-content">
        <div class="diag-code">
          <div class="diag-code-label">MERMAID CODE</div>
          <textarea id="diagCode" placeholder="Mermaid code will appear here. You can edit it directly..."></textarea>
          <div class="diag-code-btns">
            <button class="cbtn" id="renderBtn">▶ Render</button>
            <button class="cbtn" id="copyBtn">⎘ Copy</button>
            <button class="cbtn" id="sampleBtn">Sample</button>
            <button class="cbtn" id="clearDiagBtn">✕ Clear</button>
          </div>
        </div>
        <div class="diag-view">
          <div class="diag-actions">
            <button class="cbtn" id="downloadSvgBtn">SVG</button>
            <button class="cbtn" id="downloadPngBtn">PNG</button>
          </div>
          <div id="mermaid-output">
            <div class="diag-placeholder">
              <div class="pi">📊</div>
              <p>Describe a concept above and click Generate,<br>or type Mermaid code on the left and click Render.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</div>

<script>
mermaid.initialize({
  startOnLoad: false,
  theme: "default",
  flowchart: {curve: "basis"},
  securityLevel: "loose"
});

var chatHistory = [];
var autoSpeak = true;
var isStreaming = false;
var currentDiagText = "";
var lastRenderedSvg = "";

var sampleDiagrams = {
  flowchart: "flowchart TD\n    A[Patient takes oral drug] --> B[Absorption in gut]\n    B --> C[Distribution in blood]\n    C --> D[Metabolism in liver]\n    D --> E[Excretion by kidney]\n    D --> F[Active or inactive metabolites]",
  sequence: "sequenceDiagram\n    participant Patient\n    participant Pharmacist\n    participant Prescriber\n    Patient->>Pharmacist: Reports dizziness after dose\n    Pharmacist->>Prescriber: Checks interaction and blood pressure\n    Prescriber-->>Pharmacist: Adjusts therapy\n    Pharmacist-->>Patient: Counsels monitoring plan",
  graph: "graph LR\n    A[Warfarin] --> B[NSAIDs]\n    A --> C[Antibiotics]\n    A --> D[Amiodarone]\n    B --> E[Higher bleeding risk]\n    C --> F[INR changes]\n    D --> G[Reduced metabolism]",
  pie: "pie title Medication Non-Adherence Causes\n    \"Forgetfulness\" : 35\n    \"Side effects\" : 25\n    \"Cost\" : 20\n    \"Low health literacy\" : 20",
  timeline: "timeline\n    title Insulin Action Profile\n    Rapid acting : onset 10-20 min : peak 1-3 hr : duration 3-5 hr\n    Short acting : onset 30-60 min : peak 2-4 hr : duration 5-8 hr\n    Long acting : onset 1-2 hr : minimal peak : duration up to 24 hr",
  mindmap: "mindmap\n  root((Antihypertensives))\n    ACE inhibitors\n      Enalapril\n      Dry cough\n    Beta blockers\n      Atenolol\n      Bradycardia\n    Calcium channel blockers\n      Amlodipine\n      Ankle edema",
  class: "classDiagram\n    class Analgesics\n    class NSAIDs\n    class Opioids\n    class Acetaminophen\n    Analgesics <|-- NSAIDs\n    Analgesics <|-- Opioids\n    Analgesics <|-- Acetaminophen\n    NSAIDs : ibuprofen\n    NSAIDs : gastric irritation\n    Opioids : morphine\n    Opioids : respiratory depression"
};

// ── Tab switching ──────────────────────────────────────────────────────────────
document.getElementById("tab-chat").addEventListener("click", function() {
  document.getElementById("tab-chat").classList.add("active");
  document.getElementById("tab-diag").classList.remove("active");
  document.getElementById("panel-chat").classList.add("active");
  document.getElementById("panel-diag").classList.remove("active");
});
document.getElementById("tab-diag").addEventListener("click", function() {
  document.getElementById("tab-diag").classList.add("active");
  document.getElementById("tab-chat").classList.remove("active");
  document.getElementById("panel-diag").classList.add("active");
  document.getElementById("panel-chat").classList.remove("active");
});

// ── Chat shortcuts ─────────────────────────────────────────────────────────────
var shortcuts = {
  s1: "Give a clear overview of antibiotic classes, their mechanisms, and main clinical uses.",
  s2: "Explain the four phases of pharmacokinetics: absorption, distribution, metabolism, and excretion.",
  s3: "Explain how to calculate drug dosages with key formulas and a worked example.",
  s4: "Explain how drug interactions occur and give common clinically important examples.",
  s5: "Summarize the major cardiovascular drug classes, their mechanisms, and clinical uses.",
  s6: "Explain the classes of analgesic drugs, their mechanisms, and when each is used.",
  s7: "How should a pharmacist counsel patients about side effects and adverse drug reactions?",
  s8: "What are the most important over-the-counter drugs a pharmacy student must know?",
  s9: "Explain ADME in pharmacokinetics with clear simple examples.",
  s10: "Give me 5 pharmacy MCQ questions with answers.",
  s11: "List and explain the most common prescription abbreviations used in pharmacy.",
  s12: "What are the most important drug names to memorize for pharmacy exams?"
};
Object.keys(shortcuts).forEach(function(id) {
  var el = document.getElementById(id);
  if (el) el.addEventListener("click", function() {
    switchToChat();
    sendText(shortcuts[id]);
  });
});

// ── Diagram shortcuts ──────────────────────────────────────────────────────────
var diagShortcuts = {
  d1: {type:"flowchart", text:"Show the ADME pharmacokinetics process as a detailed flowchart"},
  d2: {type:"flowchart", text:"Show the mechanism of action of beta blockers step by step"},
  d3: {type:"graph",     text:"Show major drug interaction categories and examples"},
  d4: {type:"flowchart", text:"Show the clinical treatment flowchart for hypertension"},
  d5: {type:"mindmap",   text:"Show major drug classes and their subclasses in pharmacy"}
};
Object.keys(diagShortcuts).forEach(function(id) {
  var el = document.getElementById(id);
  if (el) el.addEventListener("click", function() {
    switchToDiag();
    var s = diagShortcuts[id];
    document.getElementById("diagType").value = s.type;
    document.getElementById("diagInput").value = s.text;
    generateDiagram();
  });
});

function switchToChat() {
  document.getElementById("tab-chat").click();
}
function switchToDiag() {
  document.getElementById("tab-diag").click();
}

// ── Audio ──────────────────────────────────────────────────────────────────────
document.getElementById("audioBtn").addEventListener("click", function() {
  autoSpeak = !autoSpeak;
  this.textContent = autoSpeak ? "🔊" : "🔇";
  this.classList.toggle("on", autoSpeak);
  if (!autoSpeak) stopSpeaking();
});
document.getElementById("stopbtn").addEventListener("click", stopSpeaking);

function stopSpeaking() {
  if (window.speechSynthesis) speechSynthesis.cancel();
  document.getElementById("spkbar").classList.remove("on");
}
function speak(text) {
  if (!autoSpeak || !window.speechSynthesis) return;
  stopSpeaking();
  var clean = text.replace(/[*#`]/g, "").replace(/\n+/g, " ").trim();
  var utt = new SpeechSynthesisUtterance(clean);
  utt.rate = 1.0;
  var voices = speechSynthesis.getVoices();
  var v = voices.find(function(v) {
    return v.lang.startsWith("en") && (v.name.includes("Google") || v.name.includes("Natural") || v.name.includes("Samantha"));
  }) || voices.find(function(v) { return v.lang.startsWith("en"); });
  if (v) utt.voice = v;
  utt.onstart = function() { document.getElementById("spkbar").classList.add("on"); };
  utt.onend = function() { document.getElementById("spkbar").classList.remove("on"); };
  utt.onerror = function() { document.getElementById("spkbar").classList.remove("on"); };
  speechSynthesis.speak(utt);
}

// ── Clear ──────────────────────────────────────────────────────────────────────
document.getElementById("clearBtn").addEventListener("click", function() {
  chatHistory = [];
  stopSpeaking();
  document.getElementById("chat").innerHTML =
    '<div class="wrap"><div class="welcome" id="welcome">' +
    '<div class="welcome-icon">💊</div><h2>Welcome to PharmAI</h2>' +
    '<p>Ask about drug mechanisms, interactions, dosages, and more.</p></div></div>';
});

// ── Status ─────────────────────────────────────────────────────────────────────
function showStatus(msg, type) {
  var bar = document.getElementById("status");
  var c = type === "ok"
    ? {bg:"#1a3d30", border:"#3fb68b", color:"#58d4a4"}
    : {bg:"#3d1a1a", border:"#f85149", color:"#f85149"};
  bar.style.cssText = "display:flex;padding:7px 24px;font-family:'DM Mono',monospace;" +
    "font-size:12px;align-items:center;gap:10px;flex-shrink:0;" +
    "background:" + c.bg + ";border-bottom:1px solid " + c.border + ";color:" + c.color;
  bar.innerHTML = msg;
  if (type === "ok") setTimeout(function() { bar.style.display = "none"; }, 3000);
}

function escHtml(t) {
  return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── Send chat message ──────────────────────────────────────────────────────────
document.getElementById("sendBtn").addEventListener("click", function() {
  sendText(document.getElementById("inp").value.trim());
});
document.getElementById("inp").addEventListener("keydown", function(e) {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!isStreaming) sendText(this.value.trim()); }
});
document.getElementById("inp").addEventListener("input", function() {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 150) + "px";
});

function sendText(text) {
  if (!text || isStreaming) return;
  console.log("[PharmAI] sendText:", text.slice(0,60));

  var inp = document.getElementById("inp");
  inp.value = ""; inp.style.height = "auto";
  isStreaming = true;
  document.getElementById("sendBtn").disabled = true;
  stopSpeaking();

  var welcome = document.getElementById("welcome");
  if (welcome) welcome.remove();

  var chat = document.getElementById("chat");
  var wrap = chat.querySelector(".wrap");
  if (!wrap) { wrap = document.createElement("div"); wrap.className = "wrap"; chat.appendChild(wrap); }

  var userDiv = document.createElement("div");
  userDiv.className = "msg user";
  userDiv.innerHTML = '<div class="bub">' + escHtml(text) + '</div>';
  wrap.appendChild(userDiv);
  chat.scrollTop = chat.scrollHeight;

  var aiDiv = document.createElement("div");
  aiDiv.className = "msg ai";
  aiDiv.innerHTML =
    '<div class="ai-hdr"><div class="ai-av">💊</div><span class="ai-nm">PHARMAI</span></div>' +
    '<div class="bub streaming" id="activebub"></div>' +
    '<div class="msgbtns"><button class="msgbtn" id="activespk">🔊 Speak</button>' +
    '<button class="msgbtn diag" id="activediag">📊 Visualize</button></div>';
  wrap.appendChild(aiDiv);
  chat.scrollTop = chat.scrollHeight;

  var bub = document.getElementById("activebub");
  var fullReply = "";

  fetch("/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({chatHistory: chatHistory, message: text})
  }).then(function(res) {
    chatHistory.push({role:"user", content:text});
    var reader = res.body.getReader();
    var decoder = new TextDecoder();
    var buffer = "";

    function read() {
      reader.read().then(function(result) {
        if (result.done) { finish(fullReply); return; }
        buffer += decoder.decode(result.value, {stream:true});
        var lines = buffer.split("\n");
        buffer = lines.pop();
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i];
          if (!line.startsWith("data: ")) continue;
          var payload = line.slice(6).trim();
          if (payload === "[DONE]") { finish(fullReply); return; }
          try {
            var parsed = JSON.parse(payload);
            if (parsed.error) {
              bub.classList.remove("streaming");
              bub.innerHTML = '<span style="color:var(--red)">' + escHtml(parsed.error) + '</span>';
              done(); return;
            }
            if (parsed.text) {
              fullReply += parsed.text;
              bub.textContent = fullReply;
              chat.scrollTop = chat.scrollHeight;
            }
          } catch(e) {}
        }
        read();
      }).catch(function() { finish(fullReply); });
    }
    read();
  }).catch(function() {
    bub.classList.remove("streaming");
    bub.innerHTML = '<span style="color:var(--red)">Cannot connect. Is python app.py running?</span>';
    done();
  });

  function finish(reply) {
    bub.classList.remove("streaming");
    bub.removeAttribute("id");
    if (reply) chatHistory.push({role:"assistant", content:reply});

    var spk = document.getElementById("activespk");
    var diagBtn2 = document.getElementById("activediag");

    if (spk) {
      spk.removeAttribute("id");
      spk.style.display = "inline-flex";
      (function(r){ spk.addEventListener("click", function() { speak(r); }); })(reply);
    }
    if (diagBtn2) {
      diagBtn2.removeAttribute("id");
      diagBtn2.style.display = "inline-flex";
      (function(r){ diagBtn2.addEventListener("click", function() {
        switchToDiag();
        document.getElementById("diagInput").value = "Visualize: " + r.slice(0,120);
        generateDiagram();
      }); })(reply);
    }
    if (autoSpeak && reply) speak(reply);
    done();
  }

  function done() {
    isStreaming = false;
    document.getElementById("sendBtn").disabled = false;
    document.getElementById("inp").focus();
  }
}

// ── Diagram generation ─────────────────────────────────────────────────────────
document.getElementById("diagBtn").addEventListener("click", generateDiagram);
document.getElementById("renderBtn").addEventListener("click", function() {
  renderMermaid(document.getElementById("diagCode").value);
});
document.getElementById("sampleBtn").addEventListener("click", function() {
  var dtype = document.getElementById("diagType").value;
  var code = sampleDiagrams[dtype] || sampleDiagrams.flowchart;
  document.getElementById("diagCode").value = code;
  renderMermaid(code);
});
document.getElementById("copyBtn").addEventListener("click", function() {
  var code = document.getElementById("diagCode").value;
  navigator.clipboard.writeText(code).then(function() {
    flashButton("copyBtn", "Copied", "Copy");
  });
});
document.getElementById("downloadSvgBtn").addEventListener("click", downloadSvg);
document.getElementById("downloadPngBtn").addEventListener("click", downloadPng);
document.getElementById("clearDiagBtn").addEventListener("click", function() {
  document.getElementById("diagCode").value = "";
  lastRenderedSvg = "";
  document.getElementById("mermaid-output").innerHTML =
    '<div class="diag-placeholder"><div class="pi">??</div>' +
    '<p>Describe a concept above and click Generate,<br>or type Mermaid code on the left and click Render.</p></div>';
});
document.getElementById("diagInput").addEventListener("keydown", function(e) {
  if (e.key === "Enter") generateDiagram();
});
Array.prototype.forEach.call(document.querySelectorAll("#templateStrip .tbtn"), function(btn) {
  btn.addEventListener("click", function() {
    document.getElementById("diagType").value = btn.dataset.type;
    document.getElementById("diagInput").value = btn.dataset.prompt;
    generateDiagram();
  });
});

function flashButton(id, text, original) {
  var btn = document.getElementById(id);
  btn.textContent = text;
  setTimeout(function() { btn.textContent = original; }, 1800);
}

function generateDiagram() {
  var input = document.getElementById("diagInput").value.trim();
  var dtype = document.getElementById("diagType").value;
  if (!input) return;

  var btn = document.getElementById("diagBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';

  document.getElementById("mermaid-output").innerHTML =
    '<div style="text-align:center;color:var(--muted);padding:40px">' +
    '<div class="spinner" style="margin:0 auto 12px"></div><p style="font-size:13px">Generating diagram...</p></div>';

  fetch("/diagram", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({prompt: input, type: dtype})
  }).then(function(r) { return r.json(); }).then(function(data) {
    btn.disabled = false; btn.innerHTML = "? Generate";
    if (data.error) {
      document.getElementById("mermaid-output").innerHTML =
        '<div class="diag-err">Error: ' + escHtml(data.error) + '</div>';
      return;
    }
    var code = cleanMermaid(data.code || "");
    document.getElementById("diagCode").value = code;
    renderMermaid(code);
  }).catch(function(e) {
    btn.disabled = false; btn.innerHTML = "? Generate";
    document.getElementById("mermaid-output").innerHTML =
      '<div class="diag-err">Cannot reach server. Is python app.py running?</div>';
  });
}

function cleanMermaid(code) {
  code = code.replace(/^```[a-zA-Z]*\s*/g, "").replace(/```$/g, "").trim();
  code = code.replace(/\[([^\]]*)\]/g, function(match, label) {
    var safe = label.replace(/[()]/g, "").replace(/\s+/g, " ").trim();
    return "[" + safe + "]";
  });
  if (code.indexOf("sequenceDiagram") === 0) {
    var allowedStarts = [
      "sequenceDiagram", "title", "acc_title", "acc_descr", "autonumber",
      "participant", "actor", "create", "destroy", "activate", "deactivate",
      "note", "Note", "loop", "alt", "else", "opt", "par", "and", "critical",
      "break", "rect", "end", "box", "links", "link", "properties", "details"
    ];
    code = code.split("\n").filter(function(line) {
      var trimmed = line.trim();
      if (!trimmed) return true;
      if (/^[A-Za-z0-9_]+\s*(--?>>?|--x|-x)\s*[A-Za-z0-9_]+\s*:/.test(trimmed)) return true;
      return allowedStarts.some(function(prefix) {
        return trimmed === prefix || trimmed.indexOf(prefix + " ") === 0;
      });
    }).join("\n").trim();
  }
  return code;
}

function renderMermaid(code) {
  code = cleanMermaid(code);
  var codeBox = document.getElementById("diagCode");
  if (codeBox && codeBox.value !== code) codeBox.value = code;
  if (!code.trim()) return;
  var out = document.getElementById("mermaid-output");
  out.innerHTML = '<div id="mermaid-render"></div>';
  lastRenderedSvg = "";
  try {
    mermaid.render("mermaid-render-" + Date.now(), code).then(function(result) {
      lastRenderedSvg = result.svg;
      out.innerHTML = result.svg;
    }).catch(function(e) {
      out.innerHTML = '<div class="diag-err">Diagram error:\n' + escHtml(String(e)) +
        '\n\nTry editing the code on the left and click Render, or click Sample for valid syntax.</div>';
    });
  } catch(e) {
    out.innerHTML = '<div class="diag-err">Render error: ' + escHtml(String(e)) + '</div>';
  }
}

function downloadSvg() {
  if (!lastRenderedSvg) return;
  var blob = new Blob([lastRenderedSvg], {type:"image/svg+xml;charset=utf-8"});
  downloadBlob(blob, "pharma-diagram.svg");
}

function downloadPng() {
  if (!lastRenderedSvg) return;
  var svgBlob = new Blob([lastRenderedSvg], {type:"image/svg+xml;charset=utf-8"});
  var url = URL.createObjectURL(svgBlob);
  var img = new Image();
  img.onload = function() {
    var canvas = document.createElement("canvas");
    canvas.width = img.width * 2;
    canvas.height = img.height * 2;
    var ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(function(blob) {
      downloadBlob(blob, "pharma-diagram.png");
      URL.revokeObjectURL(url);
    });
  };
  img.src = url;
}

function downloadBlob(blob, filename) {
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(function() { URL.revokeObjectURL(a.href); }, 500);
}

// Health check
fetch("/health").then(function(r) {
  if (r.ok) showStatus("✅ Connected — Ollama is running.", "ok");
  else showStatus("⚠️ Ollama error. Run: ollama serve", "error");
}).catch(function() {
  showStatus("❌ Cannot reach server. Run: python app.py", "error");
});

if (window.speechSynthesis) {
  speechSynthesis.addEventListener("voiceschanged", function() { speechSynthesis.getVoices(); });
}
</script>
</body>
</html>"""


def sanitize_mermaid_code(code):
    """Fix common Mermaid output that breaks client-side parsing."""
    cleaned = []
    in_label = False
    for char in code:
        if char == "[":
            in_label = True
            cleaned.append(char)
        elif char == "]":
            in_label = False
            cleaned.append(char)
        elif in_label and char in "()":
            continue
        else:
            cleaned.append(char)
    code = "".join(cleaned).strip()

    if code.startswith("sequenceDiagram"):
        allowed_prefixes = (
            "sequenceDiagram", "title", "acc_title", "acc_descr", "autonumber",
            "participant", "actor", "create", "destroy", "activate", "deactivate",
            "note", "Note", "loop", "alt", "else", "opt", "par", "and", "critical",
            "break", "rect", "end", "box", "links", "link", "properties", "details"
        )
        arrow_tokens = ("->", "-->", "->>", "-->>", "-x", "--x")
        safe_lines = []
        for line in code.splitlines():
            stripped = line.strip()
            if not stripped:
                safe_lines.append(line)
            elif stripped.startswith(allowed_prefixes) or any(token in stripped for token in arrow_tokens):
                safe_lines.append(line)
        code = "\n".join(safe_lines).strip()

    return code

@app.route("/")
def index():
    return HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/health")
def health():
    try:
        ollama.list()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}, 503


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    chat_history = data.get("chatHistory", [])
    user_input = data.get("message", "").strip()
    if not user_input:
        return Response("", status=400)

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + chat_history
        + [{"role": "user", "content": user_input}]
    )

    def generate():
        try:
            stream = ollama.chat(model=MODEL, messages=messages, stream=True)
            for chunk in stream:
                try:
                    text = chunk.message.content
                except AttributeError:
                    try:
                        text = chunk["message"]["content"]
                    except Exception:
                        text = str(chunk)
                if text:
                    yield "data: " + json.dumps({"text": text}) + "\n\n"
        except Exception as e:
            err = str(e).lower()
            if "not found" in err or "no such" in err:
                msg = "Model not found. Run: ollama pull " + MODEL
            elif "connection" in err or "refused" in err:
                msg = "Ollama not running. Open Ollama from taskbar or run: ollama serve"
            else:
                msg = "Error: " + str(e)
            yield "data: " + json.dumps({"error": msg}) + "\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )


@app.route("/diagram", methods=["POST"])
def diagram():
    data = request.get_json(force=True, silent=True) or {}
    prompt = data.get("prompt", "").strip()
    dtype = data.get("type", "flowchart")

    type_hints = {
        "flowchart": (
            "Use flowchart TD syntax with 5 to 9 connected steps. "
            "Use node ids like A, B, C and labels in brackets."
        ),
        "sequence": (
            "Use sequenceDiagram syntax with clear participants and message arrows. "
            "Do not include numbered lists, bullets, or plain explanatory sentences."
        ),
        "graph": (
            "Use graph LR syntax for a relationship map with compact labelled nodes."
        ),
        "pie": (
            "Use pie title syntax with 4 to 6 quoted slices and numeric values."
        ),
        "timeline": (
            "Use timeline syntax with a title and concise events or phases."
        ),
        "mindmap": (
            "Use mindmap syntax with root((Main Concept)) and indented branches."
        ),
        "class": (
            "Use classDiagram syntax with drug classes, examples, and simple relationships."
        ),
    }

    hint = type_hints.get(dtype, type_hints["flowchart"])
    full_prompt = (
        "Generate a Mermaid.js study visual for a pharmacy student about: " + prompt + ". "
        + hint + " "
        "Make it clinically useful but not crowded. Use generic drug names and common brand names where helpful. "
        "Do not use parentheses inside flowchart or graph node labels; use commas or hyphens instead. "
        "Do not include numbered lists, bullets, or explanatory prose outside Mermaid syntax. "
        "Return ONLY the raw Mermaid code. No explanation. No markdown fences. No extra text."
    )


    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": DIAGRAM_PROMPT},
                {"role": "user",   "content": full_prompt}
            ]
        )
        try:
            code = response.message.content
        except AttributeError:
            code = response["message"]["content"]

        # Strip markdown fences if the model adds them anyway
        code = code.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            code = "\n".join(lines).strip()

        valid_starts = (
            "flowchart", "graph", "sequenceDiagram", "pie", "timeline",
            "mindmap", "classDiagram", "stateDiagram", "erDiagram", "journey",
            "gantt", "quadrantChart", "requirementDiagram", "gitGraph"
        )
        if not code.startswith(valid_starts):
            safe_label = prompt[:70].replace("[", "(").replace("]", ")")
            code = "flowchart TD\n    A[" + safe_label + "] --> B[Review and edit generated code]"

        code = sanitize_mermaid_code(code)
        return {"code": code}
    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == "__main__":
    print("PharmAI starting...")
    if not OLLAMA_OK:
        print("ERROR: ollama not installed. Run: pip install ollama")
    else:
        try:
            ollama.list()
            print("Ollama connected")
        except Exception:
            print("WARNING: Ollama not detected. Open Ollama from taskbar.")
    print("Open in browser: http://localhost:5000")
    app.run(debug=False, port=5000, threaded=True)
