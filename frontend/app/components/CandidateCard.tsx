"use client";

interface Candidate {
  smiles: string;
  name: string;
  score: number;
  rank: number;
  valid: boolean;
  conformer_sdf: string | null;
}

interface CandidateCardProps {
  candidate: Candidate;
  onClick: () => void;
  isCorrect?: boolean;
}

export default function CandidateCard({
  candidate,
  onClick,
  isCorrect,
}: CandidateCardProps) {
  return (
    <div
      className={`group border rounded-lg p-4 cursor-pointer transition-all hover:border-white/30 hover:bg-white/[0.02] ${
        isCorrect
          ? "border-white/20 bg-white/[0.03]"
          : "border-white/5 bg-transparent"
      }`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold text-white/20 group-hover:text-white/40 transition-colors">
            {candidate.rank}
          </span>
          <div>
            <div className="text-sm text-neutral-200 font-medium leading-tight">
              {candidate.name}
            </div>
            <div className="flex items-center gap-2 mt-1">
              {candidate.valid ? (
                <span className="text-[10px] tracking-wider uppercase text-green-500/70">
                  Valid
                </span>
              ) : (
                <span className="text-[10px] tracking-wider uppercase text-red-500/70">
                  Invalid
                </span>
              )}
              {candidate.conformer_sdf && (
                <span className="text-[10px] tracking-wider uppercase text-blue-400/70">
                  3D
                </span>
              )}
            </div>
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
