**This “Intelligence Document Processing Pipeline” demo is a great swap-in: it keeps the MOSA/plug-and-play story but drops the video burden.
Below is a concrete plan that slots straight into our 25-min Linchpin briefing and fits the 9-day clock.**

---

## 1 What the Audience Will See (Live Clip #2 replacement)

| Pane                  | Live Content (20 s clip)                                                                       | Under-the-hood Genesis events                                        |
| --------------------- | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| **Doc In-Tray**       | 4 sample PDFs + 1 JPEG in Arabic/Hebrew/English                                                | Interface posts **`DocumentReceived`** topic                         |
| **Service Tiles**     | Status lights: AWS Textract → Google Translate → Azure Text Analytics → OpenAI Threat Synth    | Each service publishes **`ProcessingStatus`** + `FunctionCapability` |
| **Fusion Trace**      | Streaming JSON showing entities, locations, timestamps as they’re appended                     | **`IntelFusionAgent`** publishes incremental **`IntelRecord`**       |
| **Priority Brief**    | Auto-generated bullet summary animating from draft → final (“HVT planning IED drop at 0400 Z”) | OpenAI/Claude call invoked via Genesis tool schema                   |
| **Event Log (small)** | DDS discovery + `ChainEvent` messages scrolling                                                | Proves zero-config plumbing                                          |

*Clip narrates itself: “Textract digitises handwritten note → Translate converts Hebrew to English → Text Analytics extracts ‘IED’, ‘0400Z’, ‘Route 7’ → Threat Synth scores 90/100.”*

---

## 2 Minimal Architecture

```
CapturedDocs (Interface) ─┬─► AWS Textract Service (GenesisRPCService)
                           │
                           ├─► Google Translate Service (GenesisRPCService)
                           │
                           ├─► Azure TextAnalytics Service (GenesisRPCService)
                           │
                           └─► IntelFusionAgent (OpenAIGenesisAgent)
                                   │  calls OpenAI/Claude via @genesis_tool
                                   ▼
                             ThreatAssessment Topic
                                   │
                                   ▼
                              Web UI Dashboard
```

* Every service exposes **one tool** (`extract_text`, `translate_text`, `analyze_text`) and also emits a DDS **`DocFragment`** message when it finishes a stage.
* **IntelFusionAgent** listens for `DocFragment`s, merges them in memory, and when enough signals accumulate, calls its internal `@genesis_tool threat_synth()` (wrapper around OpenAI/Claude) to produce the final brief.
* Web dashboard subscribes only to `DocFragment` & `ThreatAssessment`, so there is zero direct coupling to vendor APIs.

---

## 3 Data & “Document” Strategy

| Stage        | Asset Prep (≤ 1 day)                 | Service Runtime Behaviour |
| ------------ | ------------------------------------ | ------------------------- |
| **Raw Docs** | - 2 handwritten PNGs (Hebrew/Arabic) |                           |

* 2 scanned PDFs (mixed tables/maps)
* 1 plain-text SIGINT log | Interface publishes each file path & doc ID to DDS |
  \| **Textract Output** | Run AWS Textract **offline** once; cache JSON tokens + key-value pairs | Service streams JSON tokens in 3-4 chunks to simulate pagination |
  \| **Translate Output** | Run Google Cloud Translate offline on each chunk | Service publishes translated text & language confidence |
  \| **Text Analytics** | Feed translated text into Azure Text Analytics offline → entities JSON | Service publishes entity list & sentiment |
  \| **Threat Synth** | Pre-run OpenAI/Claude on full intel bundle; cache response | Agent still calls API at demo time but falls back to cached answer if no key |

> *Because everything is cached, “live” means **streaming cached JSON at 5-10 Hz**—no external latency or API-quota risk.*

---

## 4 Slide-Deck Adjustments (changes only)

| Old Slide          | New Content                                                                                  |
| ------------------ | -------------------------------------------------------------------------------------------- |
| 6 (Architecture)   | Replace sensor diagram with **Document Pipeline** graphic                                    |
| 7 (Scenario Comic) | 4 frames: *Bag raid* → Docs digitised → Entities flagged → Actionable brief                  |
| 8 (Live Clip ①)    | **unchanged** – still “5-second service onboarding” (show Textract service auto-discovering) |
| 9 (Live Clip ②)    | New dashboard clip described above                                                           |
| 10 (Before/After)  | Hours-long manual triage → 4-min auto-pipeline                                               |
| Speaker notes      | Emphasise analyst bottleneck, multilingual pain-point, MOSA vendor mix                       |

Everything else (pain slide, Genesis one-pager, Linchpin alignment, call-to-action) stays intact.

---

## 5 Nine-Day Micro-Schedule (document variant)

| Day     | Deliverable                                                                       | Owner |
| ------- | --------------------------------------------------------------------------------- | ----- |
| **1**   | Gather 5 sample docs; run Textract/Translate/Text Analytics; store JSON per docID | Hila  |
| **1-2** | Define `DocFragment`, `IntelRecord`, `ThreatAssessment` IDL                       | Jason |
| **2**   | Build **`TextractService`** (streams cached tokens)                               | Hila  |
| **3**   | Build **`TranslateService`** (streams cached translations)                        | Hila  |
| **3**   | Build **`TextAnalyticsService`** (streams entities)                               | Hila  |
| **3-4** | Build **`IntelFusionAgent`** (stateful, cached OpenAI fallback)                   | Jason |
| **4**   | `CapturedDocsInterface` (CLI drop-folder watcher + WebSocket bridge)              | Jason |
| **5**   | Vue/Tailwind dashboard – four panes + brief panel                                 | Hila  |
| **6**   | Record Clip ① (launch Textract service) & Clip ② (dashboard live)                 | Jason |
| **7**   | Insert new graphics, adjust speaker notes                                         | Jason |
| **8**   | Dry-run with Paul                                                                 | Team  |
| **9**   | Buffer / polish                                                                   | —     |

---

## 6 Why This Still Nails Linchpin’s Objectives

| Linchpin Need                     | Demo Proof Point                                                                                          |
| --------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Multi-vendor interoperability** | Textract (AWS) + Translate (Google) + Text Analytics (Azure) + OpenAI = 4 vendors auto-discovered via DDS |
| **Speed & accuracy**              | 100 pp/day analyst backlog → 4 min automated brief                                                        |
| **MOSA compliance**               | Each vendor module is a **GenesisRPCService**; drop-in replacements validated live                        |
| **LLM-agnostic**                  | Swap Claude for GPT or local LLM by editing one line in `IntelFusionAgent`                                |
| **Observability**                 | `ChainEvent` trace shown in log pane; replayable later                                                    |

---

### Quick Decision Check

*If we thumbs-up this track today, I’ll stub the Gen-IDL tonight and Hila can start caching Textract output tomorrow morning.*

Let me know if you want any tweaks or have different document languages/contents in mind!
