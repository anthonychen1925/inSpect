"use client";

import { useState, useEffect, useRef } from "react";
import axios from "axios";
import FileUpload from "./components/FileUpload";
import MolViewer from "./components/MolViewer";
import { useTheme } from "./components/ThemeProvider";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Candidate {
  smiles: string;
  name: string;
  score: number;
  rank: number;
  valid: boolean;
  conformer_sdf: string | null;
}

interface PredictResponse {
  candidates: Candidate[];
  modalities_used: string[];
  inference_engine: string;
  warning: string | null;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1]);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function Inline3DViewer({ sdf }: { sdf: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!containerRef.current || !sdf) return;
    let mounted = true;

    const bgColor = theme === "dark" ? "#050505" : "#f0f0f0";
    const colorscheme = theme === "dark" ? "whiteCarbon" : "default";

    import("3dmol").then(($3Dmol) => {
      if (!mounted || !containerRef.current) return;
      containerRef.current.innerHTML = "";
      const viewer = $3Dmol.createViewer(containerRef.current, {
        backgroundColor: bgColor,
      });
      viewer.addModel(sdf, "sdf");
      viewer.setStyle({}, { stick: { radius: 0.15, colorscheme } });
      viewer.addStyle({}, { sphere: { scale: 0.25, colorscheme } });
      viewer.zoomTo();
      viewer.render();
      viewer.spin("y", 0.4);
    });

    return () => { mounted = false; };
  }, [sdf, theme]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "360px", position: "relative", background: "var(--viewer-bg)" }}
    />
  );
}

export default function Home() {
  const [nmrFile, setNmrFile] = useState<File | null>(null);
  const [msFile, setMsFile] = useState<File | null>(null);
  const [irFile, setIrFile] = useState<File | null>(null);

  const [results, setResults] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showViewer, setShowViewer] = useState(false);

  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">(
    "checking"
  );

  useEffect(() => {
    axios
      .get(`${API}/health`)
      .then(() => setApiStatus("online"))
      .catch(() => setApiStatus("offline"));
  }, []);

  async function handlePredict() {
    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const body: Record<string, unknown> = {};

      if (nmrFile) body.nmr_csv = await fileToBase64(nmrFile);
      if (msFile) body.ms_csv = await fileToBase64(msFile);
      if (irFile) body.ir_csv = await fileToBase64(irFile);

      if (!nmrFile && !msFile && !irFile) {
        setError("Upload at least one spectrum CSV (NMR, MS, and/or IR). IR alone is not sufficient.");
        setLoading(false);
        return;
      }

      const res = await axios.post<PredictResponse>(`${API}/predict`, body);
      setResults(res.data);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || err.message);
      } else {
        setError("Prediction failed");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative px-8 pt-20 pb-16 flex flex-col items-center text-center hero-grid">
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[var(--border)] bg-[var(--card-bg)] mb-8">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                apiStatus === "online"
                  ? "bg-emerald-400"
                  : apiStatus === "offline"
                  ? "bg-red-400"
                  : "bg-amber-400 animate-pulse"
              }`}
            />
            <span className="text-[10px] tracking-[0.15em] uppercase" style={{ color: "var(--text-muted)" }}>
              {apiStatus === "online"
                ? "System Online"
                : apiStatus === "offline"
                ? "Backend Offline"
                : "Connecting..."}
            </span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-5">
            <span style={{ color: "var(--text-primary)" }}>Spectra</span>
            <span style={{ color: "var(--text-muted)" }}>Struct</span>
          </h1>

          <p className="text-sm max-w-lg leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            Upload NMR and/or MS spectral CSVs (two columns + header). Predictions are computed from
            your files against the reference library; optional IR is accepted for future scoring.
          </p>
        </div>
      </section>

      <div className="max-w-4xl mx-auto px-8 pb-24">
        {/* Upload Section */}
        <section className="mb-12">
          <div className="flex items-center gap-3 mb-6">
            <div className="text-[10px] tracking-[0.3em] uppercase font-medium" style={{ color: "var(--text-muted)" }}>
              Upload Spectra
            </div>
            <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
            <FileUpload label="NMR Spectrum" onFile={setNmrFile} file={nmrFile} />
            <FileUpload label="MS Spectrum" onFile={setMsFile} file={msFile} />
            <FileUpload label="IR Spectrum (optional)" onFile={setIrFile} file={irFile} />
          </div>
        </section>

        {/* Predict Button */}
        <div className="flex justify-center mb-16">
          <button
            onClick={handlePredict}
            disabled={loading || apiStatus !== "online"}
            className={`btn-glow px-10 py-3.5 text-sm tracking-[0.2em] uppercase rounded-lg border transition-all ${
              loading ? "cursor-wait loading-shimmer" : ""
            }`}
            style={{
              borderColor: loading || apiStatus !== "online" ? "var(--border)" : "var(--border-strong)",
              color: loading || apiStatus !== "online" ? "var(--text-muted)" : "var(--text-primary)",
              cursor: apiStatus !== "online" && !loading ? "not-allowed" : undefined,
            }}
            onMouseEnter={(e) => {
              if (!loading && apiStatus === "online") {
                e.currentTarget.style.background = "var(--btn-hover-bg)";
                e.currentTarget.style.color = "var(--btn-hover-text)";
                e.currentTarget.style.borderColor = "var(--btn-hover-bg)";
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = loading || apiStatus !== "online" ? "var(--text-muted)" : "var(--text-primary)";
              e.currentTarget.style.borderColor = loading || apiStatus !== "online" ? "var(--border)" : "var(--border-strong)";
            }}
          >
            {loading ? "Analyzing..." : "Predict Structure"}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="animate-fade-up mb-8 px-5 py-4 rounded-lg text-sm" style={{
            border: "1px solid var(--error)",
            color: "var(--error)",
            opacity: 0.8,
            background: "var(--card-bg)",
          }}>
            {error}
          </div>
        )}

        {/* Results */}
        {results && results.candidates.length > 0 && (
          <section className="animate-fade-up">
            <div className="flex items-center gap-3 mb-6">
              <div className="text-[10px] tracking-[0.3em] uppercase font-medium" style={{ color: "var(--text-muted)" }}>
                Top {results.candidates.length} Candidates
              </div>
              <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                {results.modalities_used.map((m) => m.toUpperCase()).join(" + ")}
              </div>
              <span
                className="px-2.5 py-1 rounded text-[9px] tracking-[0.12em] uppercase max-w-[14rem] truncate"
                style={{
                  border: "1px solid var(--border)",
                  color: "var(--text-muted)",
                  background: "var(--card-bg)",
                }}
                title={results.inference_engine}
              >
                {results.inference_engine.replace(/_/g, " ")}
              </span>
            </div>
            {results.warning && (
              <p className="text-xs mb-6 leading-relaxed" style={{ color: "var(--text-muted)" }}>
                {results.warning}
              </p>
            )}

            {/* Top prediction with 3D viewer */}
            {(() => {
              const prediction = results.candidates[0];
              return (
                <div className="result-card rounded-xl overflow-hidden mb-6" style={{ border: "1px solid var(--border)" }}>
                  <div className="px-6 py-5" style={{ borderBottom: "1px solid var(--border)" }}>
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-3 mb-1">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded" style={{ background: "var(--hover-bg)", color: "var(--text-muted)" }}>#1</span>
                          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                            {prediction.name}
                          </h2>
                        </div>
                        <div className="flex items-center gap-3">
                          {prediction.valid && (
                            <span className="inline-flex items-center gap-1.5 text-[10px] tracking-wider uppercase" style={{ color: "var(--success)" }}>
                              <span className="w-1 h-1 rounded-full" style={{ background: "var(--success)" }} />
                              RDKit Verified
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
                          {(prediction.score * 100).toFixed(1)}%
                        </div>
                        <div className="text-[10px] tracking-wider uppercase" style={{ color: "var(--text-muted)" }}>
                          Confidence
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="px-6 py-3" style={{ borderBottom: "1px solid var(--border)", background: "var(--card-bg)" }}>
                    <code className="text-xs font-mono break-all" style={{ color: "var(--text-secondary)" }}>
                      {prediction.smiles}
                    </code>
                  </div>

                  {prediction.conformer_sdf && (
                    <div style={{ borderBottom: "1px solid var(--border)" }}>
                      <Inline3DViewer sdf={prediction.conformer_sdf} />
                    </div>
                  )}

                  <div className="px-6 py-3 flex items-center justify-between">
                    <span className="text-[10px] tracking-wide" style={{ color: "var(--text-muted)" }}>
                      Drag to rotate · Scroll to zoom
                    </span>
                    {prediction.conformer_sdf && (
                      <button
                        onClick={() => setShowViewer(true)}
                        className="text-[10px] tracking-wider uppercase transition-colors"
                        style={{ color: "var(--text-secondary)" }}
                        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; }}
                      >
                        Expand View
                      </button>
                    )}
                  </div>
                </div>
              );
            })()}

            {/* Remaining candidates list */}
            {results.candidates.length > 1 && (
              <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
                {results.candidates.slice(1).map((candidate) => (
                  <div
                    key={candidate.rank}
                    className="px-6 py-4 flex items-center justify-between transition-colors"
                    style={{
                      borderBottom: "1px solid var(--border)",
                      cursor: candidate.conformer_sdf ? "pointer" : "default",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--hover-bg)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    onClick={() => {
                      if (candidate.conformer_sdf) {
                        setResults({
                          ...results,
                          candidates: [candidate, ...results.candidates.filter((c) => c.rank !== candidate.rank)],
                        });
                      }
                    }}
                  >
                    <div className="flex items-center gap-4 min-w-0">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded shrink-0" style={{ background: "var(--hover-bg)", color: "var(--text-muted)" }}>
                        #{candidate.rank}
                      </span>
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>
                          {candidate.name}
                        </div>
                        <code className="text-[11px] font-mono truncate block" style={{ color: "var(--text-muted)" }}>
                          {candidate.smiles}
                        </code>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 shrink-0 ml-4">
                      {candidate.valid && (
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--success)" }} />
                      )}
                      <div className="text-right">
                        <div className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                          {(candidate.score * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </div>

      {/* Full-screen 3D Viewer modal */}
      {showViewer && results?.candidates[0]?.conformer_sdf && (
        <MolViewer
          sdf={results.candidates[0].conformer_sdf}
          smiles={results.candidates[0].smiles}
          name={results.candidates[0].name}
          onClose={() => setShowViewer(false)}
        />
      )}
    </div>
  );
}
