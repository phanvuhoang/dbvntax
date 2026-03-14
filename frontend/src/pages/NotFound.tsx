import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-4">
      <span className="text-6xl">404</span>
      <p className="text-lg">Trang không tồn tại</p>
      <Link
        to="/"
        className="px-4 py-2 bg-primary text-white text-sm rounded hover:bg-primary-dark transition"
      >
        Về trang chủ
      </Link>
    </div>
  );
}
