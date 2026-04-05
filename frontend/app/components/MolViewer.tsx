"use client";

import { useEffect, useRef } from "react";

interface MolViewerProps {
  sdf: string;
  onClose: () => void;
  smiles: string;
  name: string;
}

export default function MolViewer({
  sdf,
  onClose,
  smiles,
  name,
}: MolViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || !sdf) return;

    let mounted = true;

    import("3dmol").then(($3Dmol) => {
      if (!mounted || !containerRef.current) return;

      containerRef.current.innerHTML = "";
      const viewer = $3Dmol.createViewer(containerRef.current, {
        backgroundColor: "black",
      });
      viewer.addModel(sdf, "sdf");
      viewer.setStyle({}, { stick: { radius: 0.15, colorscheme: "whiteCarbon" } });
      viewer.addStyle({}, { sphere: { scale: 0.25, colorscheme: "whiteCarbon" } });
      viewer.zoomTo();
      viewer.render();
      viewer.spin("y", 0.5);
      viewerRef.current = viewer;
    });

    return () => {
      mounted = false;
    };
  }, [sdf]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl mx-4">
        <div className="border border-white/10 rounded-lg overflow-hidden bg-black">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
            <div>
              <div className="text-base font-medium text-white">
                {name}
              </div>
              <div className="text-xs tracking-[0.2em] uppercase text-neutral-500 mt-1">
                Predicted Structure
              </div>
              <div className="text-xs mt-1 font-mono break-all text-neutral-500">
                {smiles}
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-neutral-500 hover:text-white text-2xl leading-none ml-4"
            >
              &times;
            </button>
          </div>

          {/* 3D Viewer */}
          <div
            ref={containerRef}
            style={{ width: "100%", height: "400px", position: "relative" }}
          />

          {/* Footer */}
          <div className="px-6 py-3 border-t border-white/10 text-xs text-neutral-600">
            Drag to rotate &middot; Scroll to zoom &middot; Right-click to pan
          </div>
        </div>
      </div>
    </div>
  );
}
