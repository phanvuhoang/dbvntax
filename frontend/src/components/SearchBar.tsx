import { useRef, useEffect } from 'react';

interface Props {
  value: string;
  onChange: (val: string) => void;
}

export default function SearchBar({ value, onChange }: Props) {
  const ref = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    ref.current?.focus();
  }, []);

  const handleChange = (v: string) => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => onChange(v), 300);
  };

  return (
    <div className="relative">
      <input
        ref={ref}
        type="text"
        defaultValue={value}
        placeholder='Tìm kiếm văn bản thuế... (+TNDN "chi phí được trừ")'
        className="w-full px-4 py-2.5 pl-10 border border-gray-300 rounded-full text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition"
        onChange={(e) => handleChange(e.target.value.trim())}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            clearTimeout(timerRef.current);
            onChange((e.target as HTMLInputElement).value.trim());
          }
        }}
      />
      <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    </div>
  );
}
