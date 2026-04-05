"use client";

import { useCallback, useState, useRef } from "react";

interface FileUploadProps {
  label: string;
  accept?: string;
  onFile: (file: File | null) => void;
  file: File | null;
}

export default function FileUpload({
  label,
  accept = ".csv,.jpg,.jpeg,.png",
  onFile,
  file,
}: FileUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) onFile(f);
    },
    [onFile]
  );

  return (
    <div
      className={`drop-zone rounded-xl p-8 text-center cursor-pointer transition-all ${
        dragOver ? "drag-over" : ""
      } ${file ? "border-white/20 bg-white/[0.03]" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0] || null;
          onFile(f);
        }}
      />

      <div className="text-[10px] tracking-[0.2em] uppercase text-neutral-500 mb-3">
        {label}
      </div>

      {file ? (
        <div className="flex items-center justify-center gap-3">
          <span className="text-sm text-white/90">{file.name}</span>
          <button
            className="text-neutral-600 hover:text-white text-xs transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              onFile(null);
            }}
          >
            remove
          </button>
        </div>
      ) : (
        <div className="text-xs text-neutral-600">
          Drop CSV or image, or click to browse
        </div>
      )}
    </div>
  );
}
