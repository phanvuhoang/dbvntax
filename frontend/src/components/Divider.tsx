interface Props {
  onResize: (delta: number) => void;
}

export default function Divider({ onResize }: Props) {
  const onMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    let lastX = e.clientX;
    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - lastX;
      lastX = ev.clientX;
      onResize(dx);
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };

  return (
    <div
      onMouseDown={onMouseDown}
      className="w-1 cursor-col-resize bg-gray-200 hover:bg-primary flex-shrink-0 transition-colors"
    />
  );
}
