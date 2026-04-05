"use client";

import { useEffect, useRef } from "react";

interface MolViewer3DProps {
  sdf: string;
  name: string;
  smiles: string;
  formula?: string;
}

export default function MolViewer3D({
  sdf,
  name,
  smiles,
  formula,
}: MolViewer3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);

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
      viewer.setStyle(
        {},
        { stick: { radius: 0.15, colorscheme: "whiteCarbon" } }
      );
      viewer.addStyle(
        {},
        { sphere: { scale: 0.25, colorscheme: "whiteCarbon" } }
      );
      viewer.zoomTo();
      viewer.render();
      viewer.spin("y", 0.5);
    });

    return () => {
      mounted = false;
    };
  }, [sdf]);

  return (
    <div className="border border-white/10 rounded-lg overflow-hidden bg-black">
      {/* Info bar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
        <div>
          <div className="text-xl font-bold text-white">{name}</div>
          {formula && (
            <div className="text-xs text-neutral-500 mt-0.5 font-mono">
              {formula}
            </div>
          )}
        </div>
        <div className="text-[10px] tracking-wider uppercase text-neutral-500">
          Top Match
        </div>
      </div>

      {/* 3D viewer */}
      <div
        ref={containerRef}
        style={{ width: "100%", height: "400px", position: "relative" }}
      />

      {/* Footer with SMILES */}
      <div className="px-6 py-3 border-t border-white/10 flex items-center justify-between">
        <div className="text-xs font-mono text-neutral-600 break-all pr-4">
          {smiles}
        </div>
        <div className="text-[10px] text-neutral-600 shrink-0">
          Drag to rotate &middot; Scroll to zoom
        </div>
      </div>
    </div>
  );
}
