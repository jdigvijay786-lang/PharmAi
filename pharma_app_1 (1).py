"""
PharmAI Web — Full Featured Pharmacy Assistant
===============================================
pip install flask ollama youtube-transcript-api pypdf2
ollama pull llama3.2
python pharma_app.py  →  http://localhost:5000
"""
from flask import Flask, request, Response, stream_with_context
import json, re, base64, io

try:
    import ollama
    OLLAMA_OK = True
except ImportError:
    OLLAMA_OK = False

try:
    import PyPDF2
    PDF_OK = True
except ImportError:
    try:
        import pypdf as PyPDF2
        PDF_OK = True
    except ImportError:
        PDF_OK = False

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YT_OK = True
except ImportError:
    YT_OK = False

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
    "You are PharmAI. Generate ONLY raw Mermaid.js diagram code — no explanation, "
    "no markdown fences, no extra text. Start directly with the diagram type keyword. "
    "Keep node labels short. Avoid parentheses and special characters in labels."
)

def ollama_complete(system, user, stream=False):
    return ollama.chat(
        model=MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        stream=stream
    )

def extract_text(chunk):
    try: return chunk.message.content
    except AttributeError:
        try: return chunk["message"]["content"]
        except: return str(chunk)

# ─────────────────────────────── HTML ────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>PharmAI</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
:root{
  --bg:#0d1117;--surface:#161b22;--surface2:#1c2333;--border:#30363d;
  --accent:#3fb68b;--accent2:#58d4a4;--accent-dim:#1a3d30;
  --user-bg:#1a2744;--user-border:#2d4a8a;
  --text:#e6edf3;--muted:#8b949e;--red:#f85149;--yellow:#e3b341;--purple:#a371f7;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* Header */
header{display:flex;align-items:center;justify-content:space-between;padding:10px 20px;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0}
.logo{display:flex;align-items:center;gap:10px}
.logo-icon{width:34px;height:34px;background:var(--accent-dim);border:1.5px solid var(--accent);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:17px}
.logo-text{font-size:19px;font-weight:500;color:var(--accent2)}
.logo-sub{font-size:9px;color:var(--muted);font-family:'DM Mono',monospace}
.hbtns{display:flex;gap:7px;align-items:center}
.badge{font-family:'DM Mono',monospace;font-size:10px;padding:2px 7px;border-radius:20px;border:1px solid var(--border);color:var(--muted)}
.ibtn{background:none;border:1px solid var(--border);color:var(--muted);border-radius:7px;width:32px;height:32px;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;transition:all .15s}
.ibtn:hover{border-color:var(--accent);color:var(--accent)}
.ibtn.on{background:var(--accent-dim);border-color:var(--accent);color:var(--accent2)}

/* Tabs */
.tabs{display:flex;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0;overflow-x:auto}
.tab{padding:9px 16px;font-size:12px;font-family:'DM Mono',monospace;cursor:pointer;color:var(--muted);border-bottom:2px solid transparent;transition:all .15s;display:flex;align-items:center;gap:5px;background:none;border-top:none;border-left:none;border-right:none;white-space:nowrap}
.tab:hover{color:var(--text)}
.tab.active{color:var(--accent2);border-bottom-color:var(--accent)}

/* Status + Speaking */
#status{display:none;padding:6px 20px;font-family:'DM Mono',monospace;font-size:12px;flex-shrink:0}
#spkbar{display:none;background:var(--accent-dim);border-bottom:1px solid var(--accent);padding:5px 20px;font-family:'DM Mono',monospace;font-size:11px;color:var(--accent);align-items:center;gap:8px;flex-shrink:0}
#spkbar.on{display:flex}
.wave{display:flex;gap:2px;align-items:center}
.wave span{display:block;width:3px;background:var(--accent);border-radius:2px;animation:wv .8s ease-in-out infinite}
.wave span:nth-child(1){height:6px}.wave span:nth-child(2){height:12px;animation-delay:.1s}
.wave span:nth-child(3){height:8px;animation-delay:.2s}.wave span:nth-child(4){height:14px;animation-delay:.15s}
.wave span:nth-child(5){height:6px;animation-delay:.05s}
@keyframes wv{0%,100%{transform:scaleY(1)}50%{transform:scaleY(.3)}}
#stopbtn{margin-left:auto;background:none;border:1px solid var(--accent);color:var(--accent);border-radius:5px;font-size:10px;font-family:'DM Mono',monospace;padding:2px 7px;cursor:pointer}

/* Layout */
.layout{display:flex;flex:1;overflow:hidden}

/* Sidebar */
aside{width:200px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:12px 8px;gap:3px;flex-shrink:0;overflow-y:auto}
.slabel{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted);padding:4px 8px 5px;text-transform:uppercase}
.sbtn{background:none;border:1px solid transparent;border-radius:7px;color:var(--muted);font-family:'DM Sans',sans-serif;font-size:12px;padding:7px 9px;cursor:pointer;text-align:left;transition:all .15s;display:flex;align-items:center;gap:7px;width:100%}
.sbtn:hover{background:var(--accent-dim);border-color:#2a4a38;color:var(--text)}
.sbtn.ybtn:hover{background:#1a2a1a;border-color:#2a5a1a}
.sbtn.pbtn{color:var(--purple)}
.sbtn.pbtn:hover{background:#1a1530;border-color:#3a2560}
.sdiv{height:1px;background:var(--border);margin:5px 0}

/* Main panels */
main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.panel{display:none;flex:1;flex-direction:column;overflow:hidden}
.panel.active{display:flex}

/* Chat */
#chat{flex:1;overflow-y:auto;padding:20px 0;scroll-behavior:smooth}
#chat::-webkit-scrollbar{width:4px}
#chat::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.wrap{max-width:720px;margin:0 auto;padding:0 20px}
.msg{margin-bottom:18px;animation:fadeUp .2s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg.user .bub{background:var(--user-bg);border:1px solid var(--user-border);border-radius:14px 14px 4px 14px;padding:11px 15px;margin-left:auto;max-width:75%;width:fit-content;font-size:14px;line-height:1.6}
.ai-hdr{display:flex;align-items:center;gap:7px;margin-bottom:7px}
.ai-av{width:24px;height:24px;background:var(--accent-dim);border:1px solid var(--accent);border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:12px}
.ai-nm{font-family:'DM Mono',monospace;font-size:10px;color:var(--accent)}
.msg.ai .bub{background:var(--surface2);border:1px solid var(--border);border-radius:4px 14px 14px 14px;padding:14px 18px;font-size:14px;line-height:1.75;white-space:pre-wrap;word-break:break-word}
.msg.ai .bub.streaming::after{content:'▋';color:var(--accent);animation:blink .8s step-end infinite;margin-left:2px}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
.msgbtns{display:flex;gap:5px;margin-top:7px;flex-wrap:wrap}
.msgbtn{background:none;border:1px solid var(--border);border-radius:5px;color:var(--muted);font-size:11px;font-family:'DM Mono',monospace;padding:3px 9px;cursor:pointer;display:none;align-items:center;gap:4px;transition:all .15s}
.msgbtn:hover{border-color:var(--accent);color:var(--accent)}
.msgbtn.diag{color:var(--yellow)}
.msgbtn.diag:hover{background:#3d2e1a;border-color:var(--yellow)}
.welcome{text-align:center;padding:50px 20px}
.welcome-icon{font-size:44px;margin-bottom:14px}
.welcome h2{font-size:24px;font-weight:400;margin-bottom:8px}
.welcome p{color:var(--muted);font-size:13px;max-width:380px;margin:0 auto;line-height:1.6}

/* Input bar */
.ibar{padding:12px 20px 16px;background:var(--surface);border-top:1px solid var(--border);flex-shrink:0}
.irow{max-width:720px;margin:0 auto;display:flex;gap:8px;align-items:flex-end}
textarea#inp{flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:11px;color:var(--text);font-family:'DM Sans',sans-serif;font-size:14px;padding:11px 15px;resize:none;outline:none;min-height:46px;max-height:140px;line-height:1.5;transition:border-color .15s}
textarea#inp:focus{border-color:var(--accent)}
textarea#inp::placeholder{color:var(--muted)}
.micbtn{background:none;border:1px solid var(--border);border-radius:9px;color:var(--muted);font-size:17px;width:46px;height:46px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .15s}
.micbtn:hover{border-color:var(--accent);color:var(--accent)}
.micbtn.listening{background:rgba(248,81,73,.15);border-color:var(--red);color:var(--red);animation:pulse .8s ease-in-out infinite}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.08)}}
.sendbtn{background:var(--accent);border:none;border-radius:9px;color:#0d1117;font-size:17px;width:46px;height:46px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .15s}
.sendbtn:hover{background:var(--accent2)}
.sendbtn:disabled{background:var(--border);color:var(--muted);cursor:not-allowed}
.hint{max-width:720px;margin:5px auto 0;font-size:10px;color:var(--muted);font-family:'DM Mono',monospace}

/* Tool panels shared */
.tool-panel{flex:1;display:flex;flex-direction:column;overflow:hidden}
.tool-header{padding:14px 20px;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0}
.tool-header h3{font-size:15px;font-weight:500;margin-bottom:4px}
.tool-header p{font-size:12px;color:var(--muted)}
.tool-body{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:14px}
.tool-body::-webkit-scrollbar{width:4px}
.tool-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.tool-input-row{display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap}
.tool-textarea{flex:1;min-width:200px;background:var(--surface2);border:1px solid var(--border);border-radius:10px;color:var(--text);font-family:'DM Sans',sans-serif;font-size:13px;padding:11px 14px;resize:vertical;outline:none;min-height:90px;transition:border-color .15s}
.tool-textarea:focus{border-color:var(--accent)}
.tool-textarea::placeholder{color:var(--muted)}
.tool-input{flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:10px;color:var(--text);font-family:'DM Sans',sans-serif;font-size:13px;padding:11px 14px;outline:none;transition:border-color .15s}
.tool-input:focus{border-color:var(--accent)}
.tool-input::placeholder{color:var(--muted)}
.gbtn{background:var(--accent);border:none;border-radius:8px;color:#0d1117;font-size:13px;font-weight:500;padding:10px 18px;cursor:pointer;white-space:nowrap;transition:all .15s;flex-shrink:0}
.gbtn:hover{background:var(--accent2)}
.gbtn:disabled{background:var(--border);color:var(--muted);cursor:not-allowed}
.gbtn.purple{background:var(--purple);color:#fff}
.gbtn.purple:hover{background:#b890ff}
.result-box{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:16px 18px;font-size:14px;line-height:1.75;white-space:pre-wrap;word-break:break-word;min-height:60px;display:none}
.result-box.visible{display:block}
.result-actions{display:flex;gap:7px;flex-wrap:wrap}
.abtn{background:none;border:1px solid var(--border);border-radius:6px;color:var(--muted);font-size:11px;font-family:'DM Mono',monospace;padding:4px 10px;cursor:pointer;transition:all .15s}
.abtn:hover{border-color:var(--accent);color:var(--accent)}
.upload-zone{border:2px dashed var(--border);border-radius:10px;padding:28px;text-align:center;cursor:pointer;transition:all .15s;color:var(--muted);font-size:13px}
.upload-zone:hover,.upload-zone.drag{border-color:var(--accent);color:var(--accent);background:var(--accent-dim)}
.upload-zone input{display:none}
.upload-zone .uz-icon{font-size:32px;margin-bottom:8px}

/* Flashcards */
.fc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.fc-card{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:16px;cursor:pointer;transition:all .2s;min-height:130px;display:flex;flex-direction:column;justify-content:space-between;position:relative}
.fc-card:hover{border-color:var(--accent);transform:translateY(-2px)}
.fc-card.flipped .fc-front{display:none}
.fc-card.flipped .fc-back{display:flex}
.fc-front,.fc-back{flex:1;display:flex;flex-direction:column;gap:6px}
.fc-back{display:none;color:var(--accent2)}
.fc-label{font-family:'DM Mono',monospace;font-size:9px;color:var(--muted);letter-spacing:1px;text-transform:uppercase}
.fc-q{font-size:13px;font-weight:500;line-height:1.5}
.fc-a{font-size:13px;line-height:1.5}
.fc-hint{font-size:10px;color:var(--muted);text-align:right;margin-top:6px}

/* Diagram panel */
.diag-toolbar{display:flex;align-items:center;gap:8px;padding:10px 16px;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0;flex-wrap:wrap}
.diag-toolbar select{background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:6px 9px;font-family:'DM Mono',monospace;font-size:12px;outline:none}
.diag-toolbar input{flex:1;min-width:140px;background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:7px;padding:7px 12px;font-family:'DM Sans',sans-serif;font-size:13px;outline:none}
.diag-toolbar input:focus{border-color:var(--accent)}
.diag-toolbar input::placeholder{color:var(--muted)}
.diag-content{flex:1;display:flex;overflow:hidden}
.diag-code{width:260px;flex-shrink:0;border-right:1px solid var(--border);display:flex;flex-direction:column}
.diag-code-label{font-family:'DM Mono',monospace;font-size:9px;color:var(--muted);padding:7px 12px;border-bottom:1px solid var(--border);letter-spacing:1px}
.diag-code textarea{flex:1;background:var(--surface2);border:none;color:var(--accent2);font-family:'DM Mono',monospace;font-size:12px;padding:12px;resize:none;outline:none;line-height:1.6}
.diag-code-btns{display:flex;gap:5px;padding:7px 10px;border-top:1px solid var(--border)}
.cbtn{background:none;border:1px solid var(--border);border-radius:5px;color:var(--muted);font-size:11px;font-family:'DM Mono',monospace;padding:3px 8px;cursor:pointer;transition:all .15s}
.cbtn:hover{border-color:var(--accent);color:var(--accent)}
.diag-view{flex:1;overflow:auto;display:flex;align-items:center;justify-content:center;padding:24px}
#mermaid-output{background:white;border-radius:10px;padding:24px;min-width:260px;box-shadow:0 4px 24px rgba(0,0,0,.4)}
#mermaid-output svg{display:block;margin:auto;max-width:100%}
.diag-placeholder{text-align:center;color:var(--muted)}
.diag-placeholder .pi{font-size:40px;margin-bottom:10px}
.diag-err{color:var(--red);font-family:'DM Mono',monospace;font-size:12px;padding:14px;background:#1a0a0a;border:1px solid #5a1a1a;border-radius:8px;white-space:pre-wrap}
.spinner{display:inline-block;width:18px;height:18px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.loading-txt{color:var(--muted);font-size:13px;display:flex;align-items:center;gap:10px;padding:20px}
.section-title{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:1.5px;color:var(--muted);text-transform:uppercase;margin-bottom:6px}
.mnemonic-box{background:var(--accent-dim);border:1px solid var(--accent);border-radius:10px;padding:18px;font-size:14px;line-height:1.8;white-space:pre-wrap;display:none}
.mnemonic-box.visible{display:block}
.tag{display:inline-block;background:var(--accent-dim);border:1px solid var(--accent);border-radius:5px;font-family:'DM Mono',monospace;font-size:10px;color:var(--accent2);padding:1px 7px;margin:0 2px}
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
  <button class="tab" id="tab-diag">📊 Diagrams</button>
  <button class="tab" id="tab-summary">📝 Summariser</button>
  <button class="tab" id="tab-flash">🃏 Flashcards</button>
  <button class="tab" id="tab-mnem">🧠 Mnemonics</button>
  <button class="tab" id="tab-pdf">📄 PDF</button>
  <button class="tab" id="tab-yt">▶ YouTube</button>
</div>

<div id="status"></div>
<div id="spkbar">
  <div class="wave"><span></span><span></span><span></span><span></span><span></span></div>
  Speaking...
  <button id="stopbtn">■ Stop</button>
</div>

<div class="layout">
  <!-- Sidebar -->
  <aside>
    <div class="slabel">Chat Topics</div>
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
    <button class="sbtn ybtn" id="d1">🔄 ADME Flow</button>
    <button class="sbtn ybtn" id="d2">💊 Drug Mechanism</button>
    <button class="sbtn ybtn" id="d3">⚠️ Interactions</button>
    <button class="sbtn ybtn" id="d4">🏥 Treatment Flow</button>
    <div class="sdiv"></div>
    <div class="slabel">Tools</div>
    <button class="sbtn pbtn" id="q1">📝 Summarise text</button>
    <button class="sbtn pbtn" id="q2">🃏 Make flashcards</button>
    <button class="sbtn pbtn" id="q3">🧠 Make mnemonic</button>
    <button class="sbtn pbtn" id="q4">📝 MCQ Practice</button>
  </aside>

  <main>
    <!-- ── CHAT ── -->
    <div class="panel active" id="panel-chat">
      <div id="chat">
        <div class="wrap">
          <div class="welcome">
            <div class="welcome-icon">💊</div>
            <h2>Welcome to PharmAI</h2>
            <p>Your complete pharmacy study companion. Chat, generate diagrams, summarise notes, make flashcards, mnemonics, and more.</p>
          </div>
        </div>
      </div>
      <div class="ibar">
        <div class="irow">
          <textarea id="inp" placeholder="Ask about a drug, mechanism, interaction..." rows="1"></textarea>
          <button class="micbtn" id="micBtn" title="Click to speak">🎙</button>
          <button class="sendbtn" id="sendBtn">➤</button>
        </div>
        <div class="hint">Enter to send · Shift+Enter new line · 🎙 to speak</div>
      </div>
    </div>

    <!-- ── DIAGRAMS ── -->
    <div class="panel" id="panel-diag">
      <div class="diag-toolbar">
        <select id="diagType">
          <option value="flowchart">Flowchart</option>
          <option value="sequence">Sequence</option>
          <option value="graph">Graph LR</option>
          <option value="pie">Pie Chart</option>
          <option value="timeline">Timeline</option>
        </select>
        <input id="diagInput" placeholder="Describe what to visualize e.g. beta blocker mechanism..."/>
        <button class="gbtn" id="diagBtn">⚡ Generate</button>
      </div>
      <div class="diag-content">
        <div class="diag-code">
          <div class="diag-code-label">MERMAID CODE</div>
          <textarea id="diagCode" placeholder="Generated Mermaid code appears here. Edit and re-render."></textarea>
          <div class="diag-code-btns">
            <button class="cbtn" id="renderBtn">▶ Render</button>
            <button class="cbtn" id="copyDiagBtn">⎘ Copy</button>
            <button class="cbtn" id="clearDiagBtn">✕</button>
          </div>
        </div>
        <div class="diag-view">
          <div id="mermaid-output">
            <div class="diag-placeholder">
              <div class="pi">📊</div>
              <p>Generate or write Mermaid code</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── SUMMARISER ── -->
    <div class="panel" id="panel-summary">
      <div class="tool-panel">
        <div class="tool-header">
          <h3>📝 Text Summariser</h3>
          <p>Paste any pharmacy text — lecture notes, textbook excerpts, drug info — and get a concise summary.</p>
        </div>
        <div class="tool-body">
          <div class="tool-input-row">
            <textarea class="tool-textarea" id="sumInput" placeholder="Paste your text here..." style="min-height:130px"></textarea>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <select id="sumStyle" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:8px 12px;font-size:13px;outline:none">
              <option value="concise">Concise summary</option>
              <option value="bullets">Bullet points</option>
              <option value="detailed">Detailed summary</option>
              <option value="exam">Exam-focused key points</option>
            </select>
            <button class="gbtn" id="sumBtn">📝 Summarise</button>
          </div>
          <div class="section-title">Summary</div>
          <div class="result-box" id="sumResult"></div>
          <div class="result-actions" id="sumActions" style="display:none">
            <button class="abtn" id="sumSpeak">🔊 Speak</button>
            <button class="abtn" id="sumCopy">⎘ Copy</button>
            <button class="abtn" id="sumFlash">🃏 Make Flashcards</button>
            <button class="abtn" id="sumMnem">🧠 Make Mnemonic</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── FLASHCARDS ── -->
    <div class="panel" id="panel-flash">
      <div class="tool-panel">
        <div class="tool-header">
          <h3>🃏 Flashcard Maker</h3>
          <p>Enter a topic or paste text to generate interactive flip flashcards.</p>
        </div>
        <div class="tool-body">
          <div class="tool-input-row">
            <textarea class="tool-textarea" id="flashInput" placeholder="Topic or text e.g. 'beta blockers' or paste notes..."></textarea>
            <div style="display:flex;flex-direction:column;gap:8px">
              <select id="flashCount" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:8px 10px;font-size:13px;outline:none">
                <option value="5">5 cards</option>
                <option value="8" selected>8 cards</option>
                <option value="12">12 cards</option>
                <option value="15">15 cards</option>
              </select>
              <button class="gbtn" id="flashBtn">🃏 Generate</button>
            </div>
          </div>
          <div class="section-title" id="fcTitle" style="display:none">Click a card to reveal the answer</div>
          <div class="fc-grid" id="fcGrid"></div>
        </div>
      </div>
    </div>

    <!-- ── MNEMONICS ── -->
    <div class="panel" id="panel-mnem">
      <div class="tool-panel">
        <div class="tool-header">
          <h3>🧠 Mnemonic Maker</h3>
          <p>Generate memorable mnemonics and memory aids for drug lists, mechanisms, and clinical facts.</p>
        </div>
        <div class="tool-body">
          <div class="tool-input-row">
            <input class="tool-input" id="mnemInput" placeholder="e.g. beta blocker side effects, ADME steps, antibiotic classes..."/>
            <select id="mnemType" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:10px 12px;font-size:13px;outline:none">
              <option value="acronym">Acronym</option>
              <option value="story">Story/rhyme</option>
              <option value="visual">Visual image</option>
              <option value="all">All types</option>
            </select>
            <button class="gbtn purple" id="mnemBtn">🧠 Generate</button>
          </div>
          <div class="section-title">Mnemonic</div>
          <div class="mnemonic-box" id="mnemResult"></div>
          <div class="result-actions" id="mnemActions" style="display:none">
            <button class="abtn" id="mnemSpeak">🔊 Speak</button>
            <button class="abtn" id="mnemCopy">⎘ Copy</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── PDF ── -->
    <div class="panel" id="panel-pdf">
      <div class="tool-panel">
        <div class="tool-header">
          <h3>📄 PDF Summariser</h3>
          <p>Upload a pharmacy PDF — lecture slides, research papers, drug monographs — and get an AI summary.</p>
        </div>
        <div class="tool-body">
          <label class="upload-zone" id="pdfZone">
            <input type="file" id="pdfFile" accept=".pdf"/>
            <div class="uz-icon">📄</div>
            <div>Click to upload or drag a PDF here</div>
            <div style="font-size:11px;margin-top:4px;color:var(--muted)" id="pdfName"></div>
          </label>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <select id="pdfStyle" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:8px 12px;font-size:13px;outline:none">
              <option value="concise">Concise summary</option>
              <option value="bullets">Key bullet points</option>
              <option value="detailed">Detailed summary</option>
              <option value="exam">Exam key points</option>
            </select>
            <button class="gbtn" id="pdfBtn" disabled>📄 Summarise PDF</button>
          </div>
          <div class="section-title">Summary</div>
          <div class="result-box" id="pdfResult"></div>
          <div class="result-actions" id="pdfActions" style="display:none">
            <button class="abtn" id="pdfSpeak">🔊 Speak</button>
            <button class="abtn" id="pdfCopy">⎘ Copy</button>
            <button class="abtn" id="pdfFlash">🃏 Flashcards</button>
            <button class="abtn" id="pdfMnem">🧠 Mnemonic</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── YOUTUBE ── -->
    <div class="panel" id="panel-yt">
      <div class="tool-panel">
        <div class="tool-header">
          <h3>▶ YouTube Summariser</h3>
          <p>Paste a YouTube link for a pharmacy lecture or drug explainer video and get an AI summary.</p>
        </div>
        <div class="tool-body">
          <div class="tool-input-row">
            <input class="tool-input" id="ytUrl" placeholder="https://www.youtube.com/watch?v=..."/>
            <select id="ytStyle" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:10px 12px;font-size:13px;outline:none">
              <option value="concise">Concise</option>
              <option value="bullets">Bullet points</option>
              <option value="detailed">Detailed</option>
              <option value="exam">Exam points</option>
            </select>
            <button class="gbtn" id="ytBtn">▶ Summarise</button>
          </div>
          <div id="ytInfo" style="font-size:12px;color:var(--muted);font-family:'DM Mono',monospace;display:none"></div>
          <div class="section-title">Summary</div>
          <div class="result-box" id="ytResult"></div>
          <div class="result-actions" id="ytActions" style="display:none">
            <button class="abtn" id="ytSpeak">🔊 Speak</button>
            <button class="abtn" id="ytCopy">⎘ Copy</button>
            <button class="abtn" id="ytFlash">🃏 Flashcards</button>
            <button class="abtn" id="ytMnem">🧠 Mnemonic</button>
          </div>
        </div>
      </div>
    </div>

  </main>
</div>

<script>
mermaid.initialize({startOnLoad:false,theme:"default",flowchart:{curve:"basis"},securityLevel:"loose"});

var chatHistory=[], autoSpeak=true, isStreaming=false;

// ── Tab switching ──────────────────────────────────────────────────────────────
var tabs = {
  'tab-chat':'panel-chat','tab-diag':'panel-diag','tab-summary':'panel-summary',
  'tab-flash':'panel-flash','tab-mnem':'panel-mnem','tab-pdf':'panel-pdf','tab-yt':'panel-yt'
};
Object.keys(tabs).forEach(function(tid) {
  document.getElementById(tid).addEventListener('click', function() {
    Object.keys(tabs).forEach(function(t) {
      document.getElementById(t).classList.remove('active');
      document.getElementById(tabs[t]).classList.remove('active');
    });
    document.getElementById(tid).classList.add('active');
    document.getElementById(tabs[tid]).classList.add('active');
  });
});
function goTab(tid){ document.getElementById(tid).click(); }

// ── Chat shortcuts ─────────────────────────────────────────────────────────────
var shortcuts = {
  s1:"Give a clear overview of antibiotic classes, their mechanisms, and main clinical uses.",
  s2:"Explain the four phases of pharmacokinetics: absorption, distribution, metabolism, and excretion.",
  s3:"Explain how to calculate drug dosages with key formulas and a worked example.",
  s4:"Explain how drug interactions occur and give common clinically important examples.",
  s5:"Summarize the major cardiovascular drug classes, their mechanisms, and clinical uses.",
  s6:"Explain the classes of analgesic drugs, their mechanisms, and when each is used.",
  s7:"How should a pharmacist counsel patients about side effects and adverse drug reactions?",
  s8:"What are the most important over-the-counter drugs a pharmacy student must know?",
  s9:"Explain ADME in pharmacokinetics with clear simple examples.",
  q1:function(){ goTab('tab-summary'); },
  q2:function(){ goTab('tab-flash'); },
  q3:function(){ goTab('tab-mnem'); },
  q4:function(){ goTab('tab-chat'); sendText("Give me 5 pharmacy MCQ questions with answers."); }
};
Object.keys(shortcuts).forEach(function(id) {
  var el=document.getElementById(id);
  if(!el) return;
  el.addEventListener('click', function() {
    var s=shortcuts[id];
    if(typeof s==='function'){ s(); } else { goTab('tab-chat'); sendText(s); }
  });
});

// ── Diagram shortcuts ──────────────────────────────────────────────────────────
var diagShortcuts = {
  d1:{type:'flowchart',text:'Show the ADME pharmacokinetics process as a detailed flowchart'},
  d2:{type:'flowchart',text:'Show the mechanism of action of beta blockers step by step'},
  d3:{type:'graph',text:'Show major drug interaction categories and examples'},
  d4:{type:'flowchart',text:'Show the clinical treatment flowchart for hypertension'}
};
Object.keys(diagShortcuts).forEach(function(id) {
  var el=document.getElementById(id);
  if(!el) return;
  el.addEventListener('click', function() {
    goTab('tab-diag');
    var s=diagShortcuts[id];
    document.getElementById('diagType').value=s.type;
    document.getElementById('diagInput').value=s.text;
    generateDiagram();
  });
});

// ── Audio ──────────────────────────────────────────────────────────────────────
document.getElementById('audioBtn').addEventListener('click', function() {
  autoSpeak=!autoSpeak;
  this.textContent=autoSpeak?'🔊':'🔇';
  this.classList.toggle('on',autoSpeak);
  if(!autoSpeak) stopSpeaking();
});
document.getElementById('stopbtn').addEventListener('click', stopSpeaking);
function stopSpeaking(){
  if(window.speechSynthesis) speechSynthesis.cancel();
  document.getElementById('spkbar').classList.remove('on');
}
function speak(text){
  if(!autoSpeak||!window.speechSynthesis) return;
  stopSpeaking();
  var clean=text.replace(/[*#`]/g,'').replace(/\n+/g,' ').trim();
  var utt=new SpeechSynthesisUtterance(clean);
  utt.rate=1.0;
  var voices=speechSynthesis.getVoices();
  var v=voices.find(function(v){return v.lang.startsWith('en')&&(v.name.includes('Google')||v.name.includes('Samantha'));})
    ||voices.find(function(v){return v.lang.startsWith('en');});
  if(v) utt.voice=v;
  utt.onstart=function(){document.getElementById('spkbar').classList.add('on');};
  utt.onend=utt.onerror=function(){document.getElementById('spkbar').classList.remove('on');};
  speechSynthesis.speak(utt);
}

// ── Clear ──────────────────────────────────────────────────────────────────────
document.getElementById('clearBtn').addEventListener('click', function() {
  chatHistory=[];
  stopSpeaking();
  document.getElementById('chat').innerHTML=
    '<div class="wrap"><div class="welcome">'+
    '<div class="welcome-icon">💊</div><h2>Welcome to PharmAI</h2>'+
    '<p>Ask about drug mechanisms, interactions, dosages, and more.</p></div></div>';
});

// ── Status ─────────────────────────────────────────────────────────────────────
function showStatus(msg,type){
  var bar=document.getElementById('status');
  var c=type==='ok'?{bg:'#1a3d30',border:'#3fb68b',color:'#58d4a4'}:{bg:'#3d1a1a',border:'#f85149',color:'#f85149'};
  bar.style.cssText='display:flex;padding:6px 20px;font-family:\'DM Mono\',monospace;font-size:12px;'+
    'align-items:center;gap:10px;flex-shrink:0;background:'+c.bg+';border-bottom:1px solid '+c.border+';color:'+c.color;
  bar.innerHTML=msg;
  if(type==='ok') setTimeout(function(){bar.style.display='none';},3000);
}
function escHtml(t){return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

// ── Loading helpers ────────────────────────────────────────────────────────────
function setLoading(btnId, loading){
  var btn=document.getElementById(btnId);
  if(!btn) return;
  btn.disabled=loading;
  btn._orig=btn._orig||btn.innerHTML;
  btn.innerHTML=loading?'<span class="spinner"></span>':btn._orig;
}
function showResult(boxId, text){
  var box=document.getElementById(boxId);
  box.textContent=text;
  box.classList.add('visible');
}

// ── Copy helper ────────────────────────────────────────────────────────────────
function copyText(text, btn){
  navigator.clipboard.writeText(text).then(function(){
    var orig=btn.textContent;
    btn.textContent='✓ Copied!';
    setTimeout(function(){btn.textContent=orig;},2000);
  });
}

// ── CHAT send ─────────────────────────────────────────────────────────────────
document.getElementById('sendBtn').addEventListener('click',function(){sendText(document.getElementById('inp').value.trim());});
document.getElementById('inp').addEventListener('keydown',function(e){
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();if(!isStreaming)sendText(this.value.trim());}
});
document.getElementById('inp').addEventListener('input',function(){
  this.style.height='auto';
  this.style.height=Math.min(this.scrollHeight,140)+'px';
});

function sendText(text){
  if(!text||isStreaming) return;
  var inp=document.getElementById('inp');
  inp.value=''; inp.style.height='auto';
  isStreaming=true;
  document.getElementById('sendBtn').disabled=true;
  stopSpeaking();

  var chat=document.getElementById('chat');
  var wrap=chat.querySelector('.wrap');
  if(!wrap){wrap=document.createElement('div');wrap.className='wrap';chat.appendChild(wrap);}
  var w=wrap.querySelector('.welcome');
  if(w) w.remove();

  var uDiv=document.createElement('div');
  uDiv.className='msg user';
  uDiv.innerHTML='<div class="bub">'+escHtml(text)+'</div>';
  wrap.appendChild(uDiv);
  chat.scrollTop=chat.scrollHeight;

  var aDiv=document.createElement('div');
  aDiv.className='msg ai';
  aDiv.innerHTML='<div class="ai-hdr"><div class="ai-av">💊</div><span class="ai-nm">PHARMAI</span></div>'+
    '<div class="bub streaming" id="activebub"></div>'+
    '<div class="msgbtns">'+
    '<button class="msgbtn" id="activespk">🔊 Speak</button>'+
    '<button class="msgbtn diag" id="activediag">📊 Visualize</button>'+
    '<button class="msgbtn" id="activeflash">🃏 Flashcards</button>'+
    '<button class="msgbtn" id="activemnem">🧠 Mnemonic</button>'+
    '</div>';
  wrap.appendChild(aDiv);
  chat.scrollTop=chat.scrollHeight;

  var bub=document.getElementById('activebub');
  var fullReply='';
  var finishCalled=false;

  fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({chatHistory:chatHistory,message:text})
  }).then(function(res){
    chatHistory.push({role:'user',content:text});
    var reader=res.body.getReader(),decoder=new TextDecoder(),buffer='';
    function read(){
      reader.read().then(function(result){
        if(result.done){finish(fullReply);return;}
        buffer+=decoder.decode(result.value,{stream:true});
        var lines=buffer.split('\n');
        buffer=lines.pop();
        var done=false;
        for(var i=0;i<lines.length;i++){
          var line=lines[i];
          if(!line.startsWith('data: ')) continue;
          var payload=line.slice(6).trim();
          if(payload==='[DONE]'){done=true;break;}
          try{
            var p=JSON.parse(payload);
            if(p.error){bub.classList.remove('streaming');bub.innerHTML='<span style="color:var(--red)">'+escHtml(p.error)+'</span>';chatDone();return;}
            if(p.text){fullReply+=p.text;bub.textContent=fullReply;chat.scrollTop=chat.scrollHeight;}
          }catch(e){}
        }
        if(done){finish(fullReply);}else{read();}
      }).catch(function(){finish(fullReply);});
    }
    read();
  }).catch(function(){
    bub.classList.remove('streaming');
    bub.innerHTML='<span style="color:var(--red)">Cannot connect. Is python pharma_app.py running?</span>';
    chatDone();
  });

  function finish(reply){
    if(finishCalled) return; finishCalled=true;
    bub.classList.remove('streaming'); bub.removeAttribute('id');
    if(reply) chatHistory.push({role:'assistant',content:reply});

    function showBtn(btnId, handler){
      var btn=document.getElementById(btnId);
      if(btn){btn.removeAttribute('id');btn.style.display='inline-flex';btn.addEventListener('click',handler);}
    }
    showBtn('activespk',function(){speak(reply);});
    showBtn('activediag',function(){
      goTab('tab-diag');
      document.getElementById('diagInput').value='Visualize: '+reply.slice(0,120);
      generateDiagram();
    });
    showBtn('activeflash',function(){
      goTab('tab-flash');
      document.getElementById('flashInput').value=reply.slice(0,800);
      generateFlashcards();
    });
    showBtn('activemnem',function(){
      goTab('tab-mnem');
      document.getElementById('mnemInput').value=reply.slice(0,200);
      generateMnemonic();
    });
    if(autoSpeak&&reply) speak(reply);
    chatDone();
  }
  function chatDone(){
    isStreaming=false;
    document.getElementById('sendBtn').disabled=false;
    document.getElementById('inp').focus();
  }
}

// ── Voice input ────────────────────────────────────────────────────────────────
var SR=window.SpeechRecognition||window.webkitSpeechRecognition;
var micBtn=document.getElementById('micBtn');
var recognition=null, isListening=false;
if(!SR){if(micBtn)micBtn.style.display='none';}
else{
  recognition=new SR();
  recognition.lang='en-US'; recognition.continuous=false; recognition.interimResults=true;
  recognition.onstart=function(){isListening=true;micBtn.classList.add('listening');micBtn.title='Listening... click to stop';document.getElementById('inp').placeholder='Listening...';};
  recognition.onresult=function(e){
    var t='';
    for(var i=e.resultIndex;i<e.results.length;i++) t+=e.results[i][0].transcript;
    document.getElementById('inp').value=t;
    var ta=document.getElementById('inp'); ta.style.height='auto'; ta.style.height=Math.min(ta.scrollHeight,140)+'px';
    if(e.results[e.results.length-1].isFinal){stopListening();if(t.trim())setTimeout(function(){sendText(t.trim());},300);}
  };
  recognition.onerror=function(e){stopListening();if(e.error==='not-allowed')showStatus('❌ Microphone access denied.','error');};
  recognition.onend=function(){stopListening();};
  micBtn.addEventListener('click',function(){isListening?stopListening():startListening();});
}
function startListening(){if(!recognition||isStreaming)return;try{recognition.start();}catch(e){}}
function stopListening(){
  isListening=false;
  if(micBtn){micBtn.classList.remove('listening');micBtn.title='Click to speak';}
  document.getElementById('inp').placeholder='Ask about a drug, mechanism, interaction...';
  try{if(recognition)recognition.stop();}catch(e){}
}

// ── DIAGRAMS ──────────────────────────────────────────────────────────────────
document.getElementById('diagBtn').addEventListener('click',generateDiagram);
document.getElementById('renderBtn').addEventListener('click',function(){renderMermaid(document.getElementById('diagCode').value);});
document.getElementById('copyDiagBtn').addEventListener('click',function(){
  copyText(document.getElementById('diagCode').value,this);
});
document.getElementById('clearDiagBtn').addEventListener('click',function(){
  document.getElementById('diagCode').value='';
  document.getElementById('mermaid-output').innerHTML='<div class="diag-placeholder"><div class="pi">📊</div><p>Generate or write Mermaid code</p></div>';
});
document.getElementById('diagInput').addEventListener('keydown',function(e){if(e.key==='Enter')generateDiagram();});

function generateDiagram(){
  var input=document.getElementById('diagInput').value.trim();
  var dtype=document.getElementById('diagType').value;
  if(!input) return;
  setLoading('diagBtn',true);
  document.getElementById('mermaid-output').innerHTML='<div class="loading-txt"><span class="spinner"></span> Generating diagram...</div>';
  fetch('/diagram',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({prompt:input,type:dtype})
  }).then(function(r){return r.json();}).then(function(data){
    setLoading('diagBtn',false);
    if(data.error){document.getElementById('mermaid-output').innerHTML='<div class="diag-err">'+escHtml(data.error)+'</div>';return;}
    document.getElementById('diagCode').value=data.code||'';
    renderMermaid(data.code||'');
  }).catch(function(){setLoading('diagBtn',false);document.getElementById('mermaid-output').innerHTML='<div class="diag-err">Cannot connect to server.</div>';});
}
function renderMermaid(code){
  if(!code.trim()) return;
  var out=document.getElementById('mermaid-output');
  out.innerHTML='<div id="mermaid-render"></div>';
  mermaid.render('mermaid-render',code).then(function(r){out.innerHTML=r.svg;}).catch(function(e){
    out.innerHTML='<div class="diag-err">Diagram error:\n'+escHtml(String(e))+'</div>';
  });
}

// ── SUMMARISER ────────────────────────────────────────────────────────────────
document.getElementById('sumBtn').addEventListener('click', function(){
  var text=document.getElementById('sumInput').value.trim();
  var style=document.getElementById('sumStyle').value;
  if(!text){showStatus('Paste some text first.','error');return;}
  setLoading('sumBtn',true);
  document.getElementById('sumResult').classList.remove('visible');
  document.getElementById('sumActions').style.display='none';
  fetch('/summarise',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:text,style:style})
  }).then(function(r){return r.json();}).then(function(d){
    setLoading('sumBtn',false);
    if(d.error){showStatus(d.error,'error');return;}
    showResult('sumResult',d.result);
    document.getElementById('sumActions').style.display='flex';
  }).catch(function(){setLoading('sumBtn',false);showStatus('Server error','error');});
});
document.getElementById('sumSpeak').addEventListener('click',function(){speak(document.getElementById('sumResult').textContent);});
document.getElementById('sumCopy').addEventListener('click',function(){copyText(document.getElementById('sumResult').textContent,this);});
document.getElementById('sumFlash').addEventListener('click',function(){
  goTab('tab-flash');
  document.getElementById('flashInput').value=document.getElementById('sumResult').textContent;
  generateFlashcards();
});
document.getElementById('sumMnem').addEventListener('click',function(){
  goTab('tab-mnem');
  document.getElementById('mnemInput').value=document.getElementById('sumResult').textContent.slice(0,200);
  generateMnemonic();
});

// ── FLASHCARDS ────────────────────────────────────────────────────────────────
document.getElementById('flashBtn').addEventListener('click',generateFlashcards);
function generateFlashcards(){
  var text=document.getElementById('flashInput').value.trim();
  var count=document.getElementById('flashCount').value;
  if(!text){showStatus('Enter a topic or text first.','error');return;}
  setLoading('flashBtn',true);
  document.getElementById('fcGrid').innerHTML='<div class="loading-txt"><span class="spinner"></span> Generating flashcards...</div>';
  document.getElementById('fcTitle').style.display='none';
  fetch('/flashcards',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:text,count:parseInt(count)})
  }).then(function(r){return r.json();}).then(function(d){
    setLoading('flashBtn',false);
    if(d.error){document.getElementById('fcGrid').innerHTML='<div style="color:var(--red)">'+escHtml(d.error)+'</div>';return;}
    renderFlashcards(d.cards||[]);
  }).catch(function(){setLoading('flashBtn',false);document.getElementById('fcGrid').innerHTML='<div style="color:var(--red)">Server error</div>';});
}
function renderFlashcards(cards){
  var grid=document.getElementById('fcGrid');
  document.getElementById('fcTitle').style.display='block';
  if(!cards.length){grid.innerHTML='<div style="color:var(--muted)">No flashcards generated.</div>';return;}
  grid.innerHTML='';
  cards.forEach(function(card,i){
    var div=document.createElement('div');
    div.className='fc-card';
    div.innerHTML='<div class="fc-front"><div class="fc-label">Q '+(i+1)+'</div><div class="fc-q">'+escHtml(card.q||'')+'</div><div class="fc-hint">Click to reveal</div></div>'+
      '<div class="fc-back"><div class="fc-label">Answer</div><div class="fc-a">'+escHtml(card.a||'')+'</div><div class="fc-hint">Click to flip back</div></div>';
    div.addEventListener('click',function(){this.classList.toggle('flipped');});
    grid.appendChild(div);
  });
}

// ── MNEMONICS ────────────────────────────────────────────────────────────────
document.getElementById('mnemBtn').addEventListener('click',generateMnemonic);
document.getElementById('mnemInput').addEventListener('keydown',function(e){if(e.key==='Enter')generateMnemonic();});
function generateMnemonic(){
  var text=document.getElementById('mnemInput').value.trim();
  var type=document.getElementById('mnemType').value;
  if(!text){showStatus('Enter a topic first.','error');return;}
  setLoading('mnemBtn',true);
  document.getElementById('mnemResult').classList.remove('visible');
  document.getElementById('mnemActions').style.display='none';
  fetch('/mnemonic',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:text,type:type})
  }).then(function(r){return r.json();}).then(function(d){
    setLoading('mnemBtn',false);
    if(d.error){showStatus(d.error,'error');return;}
    var box=document.getElementById('mnemResult');
    box.textContent=d.result;
    box.classList.add('visible');
    document.getElementById('mnemActions').style.display='flex';
  }).catch(function(){setLoading('mnemBtn',false);showStatus('Server error','error');});
}
document.getElementById('mnemSpeak').addEventListener('click',function(){speak(document.getElementById('mnemResult').textContent);});
document.getElementById('mnemCopy').addEventListener('click',function(){copyText(document.getElementById('mnemResult').textContent,this);});

// ── PDF ───────────────────────────────────────────────────────────────────────
var pdfData=null;
document.getElementById('pdfFile').addEventListener('change',function(){
  var file=this.files[0];
  if(!file) return;
  document.getElementById('pdfName').textContent=file.name+' ('+Math.round(file.size/1024)+' KB)';
  document.getElementById('pdfZone').style.borderColor='var(--accent)';
  var reader=new FileReader();
  reader.onload=function(e){
    pdfData=e.target.result.split(',')[1];
    document.getElementById('pdfBtn').disabled=false;
  };
  reader.readAsDataURL(file);
});
// Drag-drop
var pdfZone=document.getElementById('pdfZone');
['dragover','dragenter'].forEach(function(ev){pdfZone.addEventListener(ev,function(e){e.preventDefault();this.classList.add('drag');});});
['dragleave','drop'].forEach(function(ev){pdfZone.addEventListener(ev,function(e){e.preventDefault();this.classList.remove('drag');});});
pdfZone.addEventListener('drop',function(e){
  var file=e.dataTransfer.files[0];
  if(file&&file.type==='application/pdf'){
    document.getElementById('pdfFile').files=e.dataTransfer.files;
    document.getElementById('pdfFile').dispatchEvent(new Event('change'));
  }
});

document.getElementById('pdfBtn').addEventListener('click',function(){
  if(!pdfData){showStatus('Upload a PDF first.','error');return;}
  var style=document.getElementById('pdfStyle').value;
  setLoading('pdfBtn',true);
  document.getElementById('pdfResult').classList.remove('visible');
  document.getElementById('pdfActions').style.display='none';
  fetch('/pdf',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({pdf:pdfData,style:style})
  }).then(function(r){return r.json();}).then(function(d){
    setLoading('pdfBtn',false);
    if(d.error){showStatus(d.error,'error');return;}
    showResult('pdfResult',d.result);
    document.getElementById('pdfActions').style.display='flex';
  }).catch(function(){setLoading('pdfBtn',false);showStatus('Server error','error');});
});
document.getElementById('pdfSpeak').addEventListener('click',function(){speak(document.getElementById('pdfResult').textContent);});
document.getElementById('pdfCopy').addEventListener('click',function(){copyText(document.getElementById('pdfResult').textContent,this);});
document.getElementById('pdfFlash').addEventListener('click',function(){
  goTab('tab-flash');
  document.getElementById('flashInput').value=document.getElementById('pdfResult').textContent.slice(0,800);
  generateFlashcards();
});
document.getElementById('pdfMnem').addEventListener('click',function(){
  goTab('tab-mnem');
  document.getElementById('mnemInput').value=document.getElementById('pdfResult').textContent.slice(0,200);
  generateMnemonic();
});

// ── YOUTUBE ───────────────────────────────────────────────────────────────────
document.getElementById('ytBtn').addEventListener('click',function(){
  var url=document.getElementById('ytUrl').value.trim();
  var style=document.getElementById('ytStyle').value;
  if(!url){showStatus('Paste a YouTube URL first.','error');return;}
  setLoading('ytBtn',true);
  document.getElementById('ytResult').classList.remove('visible');
  document.getElementById('ytActions').style.display='none';
  document.getElementById('ytInfo').style.display='none';
  fetch('/youtube',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({url:url,style:style})
  }).then(function(r){return r.json();}).then(function(d){
    setLoading('ytBtn',false);
    if(d.error){showStatus(d.error,'error');return;}
    if(d.info){var inf=document.getElementById('ytInfo');inf.textContent=d.info;inf.style.display='block';}
    showResult('ytResult',d.result);
    document.getElementById('ytActions').style.display='flex';
  }).catch(function(){setLoading('ytBtn',false);showStatus('Server error','error');});
});
document.getElementById('ytUrl').addEventListener('keydown',function(e){if(e.key==='Enter')document.getElementById('ytBtn').click();});
document.getElementById('ytSpeak').addEventListener('click',function(){speak(document.getElementById('ytResult').textContent);});
document.getElementById('ytCopy').addEventListener('click',function(){copyText(document.getElementById('ytResult').textContent,this);});
document.getElementById('ytFlash').addEventListener('click',function(){
  goTab('tab-flash');
  document.getElementById('flashInput').value=document.getElementById('ytResult').textContent.slice(0,800);
  generateFlashcards();
});
document.getElementById('ytMnem').addEventListener('click',function(){
  goTab('tab-mnem');
  document.getElementById('mnemInput').value=document.getElementById('ytResult').textContent.slice(0,200);
  generateMnemonic();
});

// ── Health check ──────────────────────────────────────────────────────────────
fetch('/health').then(function(r){
  if(r.ok) showStatus('✅ Connected — Ollama is running.','ok');
  else showStatus('⚠️ Ollama error. Run: ollama serve','error');
}).catch(function(){showStatus('❌ Cannot reach server. Run: python pharma_app.py','error');});

if(window.speechSynthesis) speechSynthesis.addEventListener('voiceschanged',function(){speechSynthesis.getVoices();});
</script>
</body>
</html>"""


# ─────────────────────────────── ROUTES ──────────────────────────────────────

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
    user_input   = data.get("message", "").strip()
    if not user_input:
        return Response("", status=400)
    messages = ([{"role":"system","content":SYSTEM_PROMPT}]
                + chat_history
                + [{"role":"user","content":user_input}])
    def generate():
        try:
            stream = ollama.chat(model=MODEL, messages=messages, stream=True)
            for chunk in stream:
                t = extract_text(chunk)
                if t: yield "data: " + json.dumps({"text":t}) + "\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"
        yield "data: [DONE]\n\n"
    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering":"no","Cache-Control":"no-cache"})

@app.route("/diagram", methods=["POST"])
def diagram():
    data   = request.get_json(force=True, silent=True) or {}
    prompt = data.get("prompt","").strip()
    dtype  = data.get("type","flowchart")
    hints  = {"flowchart":"Use flowchart TD syntax.","sequence":"Use sequenceDiagram syntax.",
              "graph":"Use graph LR syntax.","pie":"Use pie chart syntax.","timeline":"Use timeline syntax."}
    full   = ("Generate a Mermaid.js diagram for pharmacy students about: " + prompt
              + ". " + hints.get(dtype,"Use flowchart TD.") + " Return ONLY raw Mermaid code.")
    try:
        resp = ollama_complete(DIAGRAM_PROMPT, full)
        code = extract_text(resp)
        code = code.strip()
        if code.startswith("```"):
            code = "\n".join(l for l in code.split("\n") if not l.strip().startswith("```")).strip()
        return {"code": code}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/summarise", methods=["POST"])
def summarise():
    data  = request.get_json(force=True, silent=True) or {}
    text  = data.get("text","").strip()
    style = data.get("style","concise")
    if not text:
        return {"error":"No text provided"}, 400
    style_prompts = {
        "concise":  "Write a concise 3-5 sentence summary.",
        "bullets":  "Summarise as clear bullet points, each starting with a dash.",
        "detailed": "Write a detailed paragraph summary covering all key points.",
        "exam":     "Extract the most important exam-relevant facts as numbered points."
    }
    prompt = ("You are a pharmacy education assistant. "
              + style_prompts.get(style,"Summarise concisely.")
              + " Focus on pharmacy-relevant information.\n\nText:\n" + text[:4000])
    try:
        resp   = ollama_complete(SYSTEM_PROMPT, prompt)
        result = extract_text(resp)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/flashcards", methods=["POST"])
def flashcards():
    data  = request.get_json(force=True, silent=True) or {}
    text  = data.get("text","").strip()
    count = min(int(data.get("count",8)), 20)
    if not text:
        return {"error":"No text provided"}, 400
    prompt = (f"You are a pharmacy flashcard maker. Create exactly {count} flashcards from this text. "
              "Return ONLY a JSON array like: [{\"q\":\"question\",\"a\":\"answer\"},...] "
              "No explanation, no markdown, just the raw JSON array.\n\nText:\n" + text[:3000])
    try:
        resp = ollama_complete(SYSTEM_PROMPT, prompt)
        raw  = extract_text(resp).strip()
        raw  = re.sub(r'^```[a-z]*\n?','',raw); raw = re.sub(r'\n?```$','',raw)
        start = raw.find('['); end = raw.rfind(']')
        if start != -1 and end != -1:
            cards = json.loads(raw[start:end+1])
        else:
            cards = json.loads(raw)
        return {"cards": cards}
    except Exception as e:
        return {"error": "Could not parse flashcards: " + str(e)}, 500

@app.route("/mnemonic", methods=["POST"])
def mnemonic():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text","").strip()
    mtype = data.get("type","acronym")
    if not text:
        return {"error":"No text provided"}, 400
    type_prompts = {
        "acronym": "Create a memorable ACRONYM mnemonic.",
        "story":   "Create a memorable rhyme or short story mnemonic.",
        "visual":  "Describe a vivid visual memory palace image.",
        "all":     "Create an acronym, a rhyme, and a visual memory image."
    }
    prompt = ("You are a pharmacy memory expert. "
              + type_prompts.get(mtype,"Create a memorable mnemonic.")
              + " Make it easy to remember for pharmacy students. Be creative and clear.\n\nTopic: " + text)
    try:
        resp   = ollama_complete(SYSTEM_PROMPT, prompt)
        result = extract_text(resp)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/pdf", methods=["POST"])
def pdf():
    if not PDF_OK:
        return {"error": "PyPDF2 not installed. Run: pip install PyPDF2"}, 500
    data  = request.get_json(force=True, silent=True) or {}
    b64   = data.get("pdf","")
    style = data.get("style","concise")
    if not b64:
        return {"error":"No PDF data"}, 400
    try:
        pdf_bytes = base64.b64decode(b64)
        reader    = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text      = ""
        for page in reader.pages[:20]:  # max 20 pages
            text += page.extract_text() or ""
        if not text.strip():
            return {"error":"Could not extract text from PDF. It may be scanned/image-based."}, 400
        style_prompts = {
            "concise":  "Write a concise 3-5 sentence summary.",
            "bullets":  "Summarise as clear bullet points.",
            "detailed": "Write a detailed summary covering all key points.",
            "exam":     "Extract the most important exam-relevant facts as numbered points."
        }
        prompt = ("Pharmacy PDF document content:\n" + text[:4000]
                  + "\n\nTask: " + style_prompts.get(style,"Summarise concisely."))
        resp   = ollama_complete(SYSTEM_PROMPT, prompt)
        result = extract_text(resp)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/youtube", methods=["POST"])
def youtube():
    if not YT_OK:
        return {"error": "youtube-transcript-api not installed. Run: pip install youtube-transcript-api"}, 500
    data  = request.get_json(force=True, silent=True) or {}
    url   = data.get("url","").strip()
    style = data.get("style","concise")
    if not url:
        return {"error":"No URL provided"}, 400
    # Extract video ID
    vid = None
    patterns = [r'v=([a-zA-Z0-9_-]{11})', r'youtu\.be/([a-zA-Z0-9_-]{11})',
                r'embed/([a-zA-Z0-9_-]{11})', r'shorts/([a-zA-Z0-9_-]{11})']
    for pat in patterns:
        m = re.search(pat, url)
        if m: vid = m.group(1); break
    if not vid:
        return {"error":"Could not find a valid YouTube video ID in that URL."}, 400
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(vid, languages=['en','en-US','en-GB'])
        transcript = " ".join(t['text'] for t in transcript_list)
        if not transcript.strip():
            return {"error":"No transcript found for this video."}, 400
        style_prompts = {
            "concise":  "Write a concise 3-5 sentence summary.",
            "bullets":  "Summarise as clear bullet points.",
            "detailed": "Write a detailed summary covering all key points.",
            "exam":     "Extract the most important exam-relevant pharmacy facts as numbered points."
        }
        prompt = ("YouTube pharmacy video transcript:\n" + transcript[:4000]
                  + "\n\nTask: " + style_prompts.get(style,"Summarise concisely."))
        resp   = ollama_complete(SYSTEM_PROMPT, prompt)
        result = extract_text(resp)
        info   = f"Video ID: {vid} · Transcript: {len(transcript_list)} segments"
        return {"result": result, "info": info}
    except Exception as e:
        err = str(e)
        if "no element" in err.lower() or "transcript" in err.lower():
            return {"error":"No English transcript available for this video. Try a different video."}, 400
        return {"error": err}, 500

if __name__ == "__main__":
    print("=" * 52)
    print("  💊  PharmAI — Full Featured")
    print("=" * 52)
    if not OLLAMA_OK:
        print("  ❌ ollama not installed → pip install ollama")
    else:
        try: ollama.list(); print("  ✅ Ollama connected")
        except: print("  ⚠️  Ollama not running → ollama serve")
    print(f"  📄 PDF support: {'✅' if PDF_OK else '❌ pip install PyPDF2'}")
    print(f"  ▶  YouTube support: {'✅' if YT_OK else '❌ pip install youtube-transcript-api'}")
    print("  🌐 Open: http://localhost:5000")
    print("=" * 52)
    app.run(debug=False, port=5000, threaded=True)
