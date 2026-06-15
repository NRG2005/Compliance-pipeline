# Builds C3_C6_Detectors_Guide.pdf  — phone-friendly explanation of the C3 & C6 folders.
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Preformatted, HRFlowable, KeepTogether)

OUT = r"D:\Bank-Project\Compliance-pipeline\C3_C6_Detectors_Guide.pdf"

styles = getSampleStyleSheet()
H = colors.HexColor
NAVY = H("#1F3A5F")
BLUE = H("#2E6DB4")
GREY = H("#444444")
LIGHT = H("#EEF2F7")
CODEBG = H("#F4F4F4")

title = ParagraphStyle("title", parent=styles["Title"], fontSize=22, textColor=NAVY,
                       spaceAfter=4, leading=26)
subtitle = ParagraphStyle("subtitle", parent=styles["Normal"], fontSize=11,
                          textColor=GREY, spaceAfter=14, leading=15)
h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, textColor=NAVY,
                    spaceBefore=16, spaceAfter=6, leading=20)
h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12.5, textColor=BLUE,
                    spaceBefore=10, spaceAfter=3, leading=15)
body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10.5, leading=15,
                      spaceAfter=6, textColor=H("#1A1A1A"))
bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=3)
code = ParagraphStyle("code", parent=styles["Code"], fontSize=8.7, leading=11,
                      textColor=H("#102A43"))
note = ParagraphStyle("note", parent=body, fontSize=10.5, leading=15,
                      textColor=H("#7A3E00"))

def P(t, s=body): return Paragraph(t, s)
def B(t): return Paragraph("&bull;&nbsp; " + t, bullet)
def hr(): return HRFlowable(width="100%", thickness=0.6, color=H("#C9D6E5"),
                            spaceBefore=8, spaceAfter=8)

def codeblock(txt):
    p = Preformatted(txt, code)
    t = Table([[p]], colWidths=[165*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CODEBG),
        ("BOX", (0,0), (-1,-1), 0.5, H("#D0D7DE")),
        ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    return t

def table(rows, widths, header=True):
    data = [[Paragraph(c, ParagraphStyle("c", parent=body, fontSize=9.3, leading=12)) for c in r] for r in rows]
    t = Table(data, colWidths=widths)
    st = [("GRID",(0,0),(-1,-1),0.5,H("#C9D6E5")),
          ("VALIGN",(0,0),(-1,-1),"TOP"),
          ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
          ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
          ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, LIGHT])]
    if header:
        st += [("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),colors.white)]
        data[0] = [Paragraph("<b>%s</b>" % c, ParagraphStyle("hd",parent=body,fontSize=9.3,
                   leading=12,textColor=colors.white)) for c in rows[0]]
        t = Table(data, colWidths=widths); t.setStyle(TableStyle(st))
    else:
        t.setStyle(TableStyle(st))
    return t

S = []
S.append(P("Understanding C3 &amp; C6", title))
S.append(P("Your two detectors in the L2 Transaction Monitor &mdash; what every file does and why. "
           "Written for the Microsoft demo.", subtitle))
S.append(hr())

# Shared design
S.append(P("The shared idea behind both folders", h1))
S.append(P("Each detector is built like an assembly line of 4 jobs:", body))
S.append(codeblock(
"1. MEASURE    -> turn raw data into plain facts (no decisions)\n"
"2. RULES      -> a deterministic 'rulebook' brain scores the facts (baseline)\n"
"3. AI         -> a Phi-4-mini brain sees the SAME facts and adds CONTEXT\n"
"4. FRONT DOOR -> __init__.py ties it together, offers one clean function"))
S.append(P("<b>Why this split?</b>", body))
S.append(B("Measuring separately means both brains see <b>identical facts</b> &mdash; so comparing their "
           "scores is a <b>fair fight</b> (this is what makes the F1 numbers honest)."))
S.append(B("Two brains let you <b>prove the AI beats plain rules</b> (the project's whole thesis)."))
S.append(B("One front door means the rest of the pipeline just calls one function and ignores the internals."))

# C3
S.append(hr())
S.append(P("C3 &mdash; Graph / Network Flow", h1))
S.append(P("<b>What it catches:</b> laundering hidden in the <b>connections between accounts</b> &mdash; "
           "<b>mule accounts</b> (money funnels in, sweeps out) and <b>layering loops</b> (money goes around "
           "and returns to itself). Weight in L2 = <b>0.17</b>.", body))

S.append(P("graph_builder.py &mdash; builds the map of money movement", h2))
S.append(B("Defines <b>TxGraph</b>: a directed graph (arrows: who paid whom) over a <b>72-hour window</b>."))
S.append(B("<b>shared_attribute(a,b)</b> decides if two accounts are secretly the same person: "
           "same device ID -> same bank branch (IFSC prefix) -> same surname. This is what makes a 'loop' detectable."))
S.append(B("<b>Why:</b> build the map once, reuse it for both pattern checks &mdash; no double work."))

S.append(P("patterns.py &mdash; measures the two suspicious shapes (no decisions)", h2))
S.append(B("<b>fan_in_out_features()</b> = the mule shape: many tiny credits (under Rs 5,000) from different "
           "senders in a 2-hour burst, then one big transfer sweeping &gt;80% out within 30 minutes."))
S.append(B("<b>round_trip_features()</b> = the layering shape: a breadth-first search up to 4 hops to find "
           "money that returns to a same-identity account with most of its value preserved."))
S.append(B("<b>Why measure only:</b> so both brains downstream get identical raw measurements."))

S.append(P("detector.py &mdash; the deterministic 'rulebook' brain (baseline)", h2))
S.append(B("Fires only when strict thresholds are all met; returns a label (1 = suspicious, 0 = normal)."))
S.append(B("<b>Why:</b> it is the <b>baseline to beat</b>. Deliberately context-blind &mdash; it cannot tell a "
           "real mule from a legit payroll/merchant account. Fixing that blind spot is the AI's job."))

S.append(P("slm_classifier.py &mdash; the Phi-4-mini 'context' brain  [KEY FILE]", h2))
S.append(B("Asks Phi-4-mini: is this a real mule/layering, or a legitimate business pattern?"))
S.append(B("<b>The grounding trick (your core contribution):</b> it computes two booleans &mdash; mule_sweep and "
           "layering_loop &mdash; itself, and tells the model 'these are the ONLY things that matter', with "
           "worked examples (registered merchant + sweep = NORMAL)."))
S.append(B("<b>reference_reasoner()</b> = transparent backup using the same rules, never peeks at the answer; "
           "used as the offline fallback if Ollama is down."))
S.append(B("<b>Why:</b> lifts C3 from rules-only F1 <b>0.722 -&gt; 0.914</b>."))

S.append(P("thresholds.py &mdash; all policy numbers in one place", h2))
S.append(B("72h window; fan-in (&gt;=5 distinct credits under Rs 5,000, sweep &gt;80% in 30 min); round-trip "
           "(&lt;=3 hops to fire); fire threshold 0.50; plus citations (PMLA s.3, RBI FRM EWS, MuleHunter.AI)."))
S.append(B("<b>Why a separate file:</b> a regulation change is a number edit here &mdash; no code change."))

S.append(P("__init__.py &mdash; the front door (3 ways to call C3)", h2))
S.append(B("<b>run_c3(case, mode)</b> -> full result dict (deterministic / slm / both)."))
S.append(B("<b>analyze_graph_network_flow()</b> -> async float version for L2's main.py."))
S.append(B("<b>evaluate_row(row, dl)</b> -> the adapter the unified pipeline orchestrator calls."))

# C6
S.append(hr())
S.append(P("C6 &mdash; Geo-Anomaly", h1))
S.append(P("<b>What it catches:</b> someone logging in from a <b>new device / new country / impossible "
           "location</b> and draining an account &mdash; i.e. <b>account takeover</b>. Weight in L2 = <b>0.10</b>.", body))

S.append(P("features.py &mdash; measures the location/device signals (no decisions)", h2))
S.append(B("New / rare location; foreign / FATF high-risk country."))
S.append(B("<b>Impossible travel</b> &mdash; uses the <b>Haversine formula</b> to get distance from the last "
           "transaction, divides by time = implied speed. Mumbai -&gt; London in 10 minutes = faster than a jet "
           "= impossible = takeover."))
S.append(B("New device; balance drain (&gt;=80% of balance); odd hour (1-5 AM)."))
S.append(B("<b>Why:</b> one shared fact-sheet both brains consume."))

S.append(P("detector.py &mdash; the deterministic 'rulebook' brain (baseline)", h2))
S.append(B("Combines the signals with <b>noisy-OR</b>: P = 1 - (1-s1) x (1-s2) x ... &mdash; a clean way to "
           "merge independent risk signals into one 0-1 score. Fires at &gt;= 0.50."))
S.append(B("<b>Why:</b> the baseline; context-blind (cannot tell an NRE account's normal foreign transfer from fraud)."))

S.append(P("slm_classifier.py &mdash; the Phi-4-mini 'context' brain  [KEY FILE]", h2))
S.append(B("Grounded on <b>4 triggers</b>: new_device, impossible_travel, fatf_high_risk, foreign_unexpected."))
S.append(B("The smart part: explicitly told to <b>IGNORE</b> amount size / balance-drain / odd-hour on their own "
           "&mdash; those only matter WITH a trigger. (A huge payment from your own phone at 3 AM is normal; "
           "the same from a new device is not.)"))
S.append(B("<b>_foreign_unexpected()</b> knows NRE/NRO and frequent travellers legitimately transact abroad, "
           "so it will not flag them."))
S.append(B("<b>Why:</b> lifts C6 from rules-only F1 <b>0.732 -&gt; 0.919</b>."))

S.append(P("thresholds.py &mdash; all policy numbers", h2))
S.append(B("Signal weights (impossible-travel 0.95 = strongest); 900 km/h speed cap; 80% balance-drain; "
           "odd-hour window; the FATF country list {KP, IR, MM, SY, AF, YE}; fire threshold 0.50."))

S.append(P("__init__.py &mdash; the front door", h2))
S.append(B("<b>run_c6(transaction, account_history, mode)</b> -> full result dict."))
S.append(B("<b>check_geo_anomaly()</b> -> async float for main.py. (The orchestrator path calls detector.predict "
           "directly, with the travel-profile gate living in the orchestrator.)"))

# The honest detail
S.append(hr())
S.append(P("Important: the two paths (know this for the demo)", h1))
S.append(P("There are two paths, and they use different brains:", body))
S.append(table([
    ["Path", "Which brain runs", "Where the number comes from"],
    ["Standalone C3/C6 evaluation", "Phi-4-mini (the AI brain)",
     "C3 F1 0.914, C6 F1 0.919 (vs ~0.72 rules) &mdash; proves AI beats rules"],
    ["Whole-L2 pipeline (run_l2.py)", "the deterministic brain (evaluate_row / detector.predict)",
     "part of the F1 0.988 whole-layer number"],
], widths=[42*mm, 50*mm, 73*mm]))
S.append(Spacer(1,6))
S.append(P("<b>So when you run the full pipeline, C3/C6 use their deterministic rules &mdash; not Phi-4.</b> "
           "The Phi-4 intelligence is proven in the separate C3/C6 evaluation (the 0.914/0.919 numbers).", note))
S.append(P("<b>Why built that way:</b> the integrated pipeline runs deterministically so it is fast and needs no "
           "Ollama running (every transaction would otherwise wait ~5s for the model). Phi-4 mode is the "
           "'smart mode' you switch on (USE_MOCK=False) to show it beats the baseline.", body))
S.append(P("<b>If asked 'is the AI actually used?'</b> &mdash; honest answer: each detector has a fast rule-based "
           "mode and a Phi-4 contextual mode. The integrated 2,000-transaction run uses the fast rules for speed "
           "and offline reproducibility; the Phi-4 mode is separately benchmarked at F1 0.914/0.919, proving the "
           "AI adds ~0.19 F1 over rules, and it is a config flip to route the pipeline through it.", body))

# Why smart
S.append(hr())
S.append(P("Why C3 &amp; C6 are the 'smart' detectors", h1))
S.append(P("These are the two detectors where <b>context changes everything</b>:", body))
S.append(B("A sweep is a <b>mule</b> &mdash; unless it is a registered merchant (then it is normal settlement)."))
S.append(B("A foreign login is <b>fraud</b> &mdash; unless it is an NRE account (then it is expected)."))
S.append(P("Plain rules cannot make those calls without drowning in false alarms. That is exactly why these two "
           "got the Phi-4 treatment &mdash; and the grounding technique (compute the triggers, hand them to the "
           "model) is what made a tiny 3.8B model reach F1 &gt;= 0.91.", body))

# Q&A
S.append(hr())
S.append(P("Quick demo Q&amp;A for your part", h1))
qa = [
    ("What is the difference between detector.py and slm_classifier.py?",
     "Same input, two brains: detector.py is fixed rules (baseline); slm_classifier.py is Phi-4 adding context. "
     "Fair comparison because they share features.py / patterns.py."),
    ("How does C3 find a loop?",
     "It builds a 72h money graph, does a breadth-first search up to 4 hops, and flags a return to a same-identity "
     "account (device / IFSC / surname) with high value preserved."),
    ("How does C6 know travel is impossible?",
     "Haversine distance divided by time = implied speed; over 900 km/h is faster than a jet -> impossible."),
    ("Why does the AI beat the rules?",
     "Context: merchant vs mule, NRE vs domestic. Rules cannot tell them apart; the grounded SLM can. "
     "Proven: +0.19 F1 on both."),
    ("Did you cheat the F1?",
     "No &mdash; the reference reasoner and the SLM never see the label; both brains share identical measured features."),
]
for q,a in qa:
    S.append(P("<b>Q: %s</b>" % q, body))
    S.append(P("A: %s" % a, ParagraphStyle("a", parent=body, leftIndent=10, textColor=GREY, spaceAfter=8)))

S.append(hr())
S.append(P("One-line summary: C3 and C6 each measure facts once, then run them through two brains &mdash; a fast "
           "rulebook (baseline) and a grounded Phi-4-mini (context). The AI mode is benchmarked at F1 0.914 / 0.919 "
           "(vs ~0.72 rules); the integrated pipeline uses the fast rules and can be switched to Phi-4 with one flag.",
           ParagraphStyle("sum", parent=body, fontSize=10, textColor=NAVY)))

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(H("#8A98A8"))
    canvas.drawString(20*mm, 12*mm, "Compliance Pipeline  -  C3 & C6 Detectors Guide")
    canvas.drawRightString(190*mm, 12*mm, "Page %d" % doc.page)
    canvas.restoreState()

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=18*mm, bottomMargin=18*mm,
                        title="C3 & C6 Detectors Guide", author="Compliance Pipeline")
doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("WROTE", OUT)
