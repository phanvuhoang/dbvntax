import { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!password || password.length < 6) {
      setError('Mật khẩu phải có ít nhất 6 ký tự');
      return;
    }
    if (password !== confirm) {
      setError('Mật khẩu xác nhận không khớp');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi xảy ra');
      setSuccess(data.message || 'Đặt mật khẩu mới thành công!');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="bg-white p-8 rounded-xl shadow-lg text-center">
          <p className="text-red-600 mb-4">Link không hợp lệ.</p>
          <button onClick={() => navigate('/')} className="px-4 py-2 bg-primary text-white rounded hover:bg-primary-dark transition text-sm">
            Về trang chủ
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-xl shadow-lg w-[380px]">
        <h1 className="text-lg font-bold text-primary text-center mb-6">Đặt mật khẩu mới</h1>

        {success ? (
          <div className="text-center">
            <p className="text-green-600 text-sm mb-4">{success}</p>
            <button onClick={() => navigate('/')} className="px-4 py-2 bg-primary text-white rounded hover:bg-primary-dark transition text-sm">
              Đăng nhập
            </button>
          </div>
        ) : (
          <>
            <div className="mb-3">
              <label className="block text-xs font-semibold text-gray-500 mb-1">Mật khẩu mới</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none"
                placeholder="••••••"
                autoFocus
              />
            </div>
            <div className="mb-3">
              <label className="block text-xs font-semibold text-gray-500 mb-1">Xác nhận mật khẩu</label>
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none"
                placeholder="••••••"
                onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit(); }}
              />
            </div>
            {error && <p className="text-red-600 text-xs mb-3">{error}</p>}
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full px-4 py-2 bg-primary text-white rounded text-sm font-medium hover:bg-primary-dark transition disabled:opacity-50"
            >
              {loading ? 'Đang xử lý...' : 'Đặt mật khẩu mới'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
