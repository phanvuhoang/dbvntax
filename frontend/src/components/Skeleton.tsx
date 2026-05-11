interface SkeletonCardProps {
  count?: number;
}

function SkeletonLine({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-gray-200 animate-pulse rounded ${className}`} />
  );
}

function SkeletonDocCard() {
  return (
    <div className="px-3 py-3 border-b border-gray-100 space-y-2">
      <div className="flex justify-between items-start gap-2">
        <SkeletonLine className="h-4 w-28" />
        <SkeletonLine className="h-4 w-10" />
      </div>
      <SkeletonLine className="h-3.5 w-full" />
      <SkeletonLine className="h-3.5 w-4/5" />
      <div className="flex gap-2 mt-1.5">
        <SkeletonLine className="h-3 w-16" />
        <SkeletonLine className="h-3 w-12" />
        <SkeletonLine className="h-3 w-14" />
      </div>
    </div>
  );
}

export default function SkeletonCards({ count = 6 }: SkeletonCardProps) {
  return (
    <div>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonDocCard key={i} />
      ))}
    </div>
  );
}
