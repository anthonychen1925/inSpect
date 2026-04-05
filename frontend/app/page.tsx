"use client";

import { useState, useEffect, useRef } from "react";
import axios from "axios";
import FileUpload from "./components/FileUpload";
import MolViewer from "./components/MolViewer";

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
  warning: string | null;
  demo_mode: boolean;
}

interface DemoMolecule {
  name: string;
  display_name: string;
  formula: string;
  smiles: string;
  mw: number;
  has_nmr: boolean;
  has_ms: boolean;
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

  useEffect(() => {
    if (!containerRef.current || !sdf) return;
    let mounted = true;

    import("3dmol").then(($3Dmol) => {
      if (!mounted || !containerRef.current) return;
      containerRef.current.innerHTML = "";
      const viewer = $3Dmol.createViewer(containerRef.current, {
        backgroundColor: "#050505",
      });
      viewer.addModel(sdf, "sdf");
      viewer.setStyle({}, { stick: { radius: 0.15, colorscheme: "whiteCarbon" } });
      viewer.addStyle({}, { sphere: { scale: 0.25, colorscheme: "whiteCarbon" } });
      viewer.zoomTo();
      viewer.render();
      viewer.spin("y", 0.4);
    });

    return () => { mounted = false; };
  }, [sdf]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "360px", position: "relative" }}
    />
  );
}

export default function Home() {
  const [nmrFile, setNmrFile] = useState<File | null>(null);
  const [msFile, setMsFile] = useState<File | null>(null);
  const [demoMolecule, setDemoMolecule] = useState<string>("");
  const [demoMolecules, setDemoMolecules] = useState<DemoMolecule[]>([]);

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
      .then(() => {
        setApiStatus("online");
        return axios.get(`${API}/fixtures`);
      })
      .then((res) => setDemoMolecules(res.data.molecules))
      .catch(() => setApiStatus("offline"));
  }, []);

  async function handlePredict() {
    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const body: Record<string, unknown> = {};

      if (demoMolecule) {
        body.demo_molecule = demoMolecule;
      }

      if (nmrFile) body.nmr_csv = await fileToBase64(nmrFile);
      if (msFile) body.ms_csv = await fileToBase64(msFile);

      if (!demoMolecule && !nmrFile && !msFile) {
        setError("Upload at least one spectrum or select a demo molecule.");
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

  function handleDemoSelect(name: string) {
    setDemoMolecule(name === demoMolecule ? "" : name);
    setResults(null);
    setError(null);
  }

  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative px-8 pt-20 pb-16 flex flex-col items-center text-center hero-grid">
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/[0.08] bg-white/[0.02] mb-8">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                apiStatus === "online"
                  ? "bg-emerald-400"
                  : apiStatus === "offline"
                  ? "bg-red-400"
                  : "bg-amber-400 animate-pulse"
              }`}
            />
            <span className="text-[10px] tracking-[0.15em] uppercase text-neutral-500">
              {apiStatus === "online"
                ? "System Online"
                : apiStatus === "offline"
                ? "Backend Offline"
                : "Connecting..."}
            </span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-5">
            <span className="text-white">Spectra</span>
            <span className="text-neutral-600">Struct</span>
          </h1>

          <p className="text-sm text-neutral-500 max-w-lg leading-relaxed">
            Upload NMR or MS spectral data and predict molecular structures
            with 3D conformer visualization.
          </p>
        </div>
      </section>

      <div className="max-w-4xl mx-auto px-8 pb-24">
        {/* Upload Section */}
        <section className="mb-12">
          <div className="flex items-center gap-3 mb-6">
            <div className="text-[10px] tracking-[0.3em] uppercase text-neutral-600 font-medium">
              Upload Spectra
            </div>
            <div className="flex-1 h-px bg-white/[0.06]" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
            <FileUpload label="NMR Spectrum" onFile={setNmrFile} file={nmrFile} />
            <FileUpload label="MS Spectrum" onFile={setMsFile} file={msFile} />
          </div>
        </section>

        {/* Demo Molecules */}
        <section className="mb-12">
          <div className="flex items-center gap-3 mb-6">
            <div className="text-[10px] tracking-[0.3em] uppercase text-neutral-600 font-medium">
              Demo Molecules
            </div>
            <div className="flex-1 h-px bg-white/[0.06]" />
          </div>

          <div className="flex flex-wrap gap-2">
            {demoMolecules.map((mol) => (
              <button
                key={mol.name}
                className={`mol-pill px-3.5 py-2 text-xs border rounded-lg transition-all ${
                  demoMolecule === mol.name
                    ? "active border-white/30 text-white bg-white/[0.06]"
                    : "border-white/[0.06] text-neutral-500 hover:border-white/15 hover:text-neutral-300 hover:bg-white/[0.02]"
                }`}
                onClick={() => handleDemoSelect(mol.name)}
              >
                <span>{mol.display_name}</span>
                {demoMolecule === mol.name && (
                  <span className="ml-2 text-neutral-500 text-[10px]">{mol.formula}</span>
                )}
              </button>
            ))}
          </div>
        </section>

        {/* Predict Button */}
        <div className="flex justify-center mb-16">
          <button
            onClick={handlePredict}
            disabled={loading || apiStatus !== "online"}
            className={`btn-glow px-10 py-3.5 text-sm tracking-[0.2em] uppercase rounded-lg border transition-all ${
              loading
                ? "border-white/[0.06] text-neutral-600 cursor-wait loading-shimmer"
                : apiStatus !== "online"
                ? "border-white/[0.06] text-neutral-700 cursor-not-allowed"
                : "border-white/20 text-white hover:bg-white hover:text-black hover:border-white"
            }`}
          >
            {loading ? "Analyzing..." : "Predict Structure"}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="animate-fade-up mb-8 px-5 py-4 border border-red-500/20 rounded-lg text-sm text-red-400/80 bg-red-500/[0.03]">
            {error}
          </div>
        )}

        {/* Results */}
        {results && results.candidates.length > 0 && (() => {
          const prediction = results.candidates[0];

          return (
            <section className="animate-fade-up">
              <div className="flex items-center gap-3 mb-6">
                <div className="text-[10px] tracking-[0.3em] uppercase text-neutral-600 font-medium">
                  Predicted Structure
                </div>
                <div className="flex-1 h-px bg-white/[0.06]" />
                {results.demo_mode && (
                  <span className="px-2.5 py-1 border border-white/[0.08] rounded text-[9px] tracking-[0.15em] uppercase text-neutral-600 bg-white/[0.02]">
                    Demo
                  </span>
                )}
              </div>

              <div className="result-card border border-white/[0.08] rounded-xl overflow-hidden">
                {/* Molecule header */}
                <div className="px-6 py-5 border-b border-white/[0.06]">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-bold text-white mb-1">
                        {prediction.name}
                      </h2>
                      <div className="flex items-center gap-3">
                        {prediction.valid && (
                          <span className="inline-flex items-center gap-1.5 text-[10px] tracking-wider uppercase text-emerald-400/70">
                            <span className="w-1 h-1 rounded-full bg-emerald-400/70" />
                            RDKit Verified
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-xs text-neutral-600">
                      {results.modalities_used.map((m) => m.toUpperCase()).join(" + ")}
                    </div>
                  </div>
                </div>

                {/* SMILES */}
                <div className="px-6 py-3 border-b border-white/[0.06] bg-white/[0.01]">
                  <code className="text-xs font-mono text-neutral-400 break-all">
                    {prediction.smiles}
                  </code>
                </div>

                {/* Inline 3D Viewer */}
                {prediction.conformer_sdf && (
                  <div className="border-b border-white/[0.06]">
                    <Inline3DViewer sdf={prediction.conformer_sdf} />
                  </div>
                )}

                {/* Footer */}
                <div className="px-6 py-3 flex items-center justify-between">
                  <span className="text-[10px] text-neutral-600 tracking-wide">
                    Drag to rotate · Scroll to zoom
                  </span>
                  {prediction.conformer_sdf && (
                    <button
                      onClick={() => setShowViewer(true)}
                      className="text-[10px] tracking-wider uppercase text-neutral-500 hover:text-white transition-colors"
                    >
                      Expand View
                    </button>
                  )}
                </div>
              </div>
            </section>
          );
        })()}
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
