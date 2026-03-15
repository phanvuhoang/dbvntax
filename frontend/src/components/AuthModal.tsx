import { useState } from 'react';

interface Props {
  open: boolean;
  onClose: () => void;
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string, ho_ten: string) => Promise<void>;
}

export default function AuthModal({ open, onClose, onLogin, onRegister }: Props) {
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [hoTen, setHoTen] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const handleSubmit = async () => {
    if (!email) return;
    if (mode !== 'forgot' && !password) return;
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await onLogin(email, password);
        setEmail(''); setPassword(''); setHoTen('');
        onClose();
      } else if (mode === 'register') {
        await onRegister(email, password, hoTen);
        setEmail(''); setPassword(''); setHoTen('');
        onClose();
      } else {
        const res = await fetch('/api/auth/forgot-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        });
        if (!res.ok) throw new Error('Lỗi xảy ra');
        setSuccess('Nếu email tồn tại, bạn sẽ nhận được link đặt lại mật khẩu. Vui lòng kiểm tra hộp thư.');
      }
    } catch (e: any) {
      setError(e.message || 'Lỗi xảy ra');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (m: 'login' | 'register' | 'forgot') => {
    setMode(m);
    setError('');
    setSuccess('');
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={onClose}>
      <div
        className="bg-white rounded-xl p-7 w-[380px] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit(); if (e.key === 'Escape') onClose(); }}
      >
        <h2 className="text-lg font-bold text-primary text-center mb-4">
          {mode === 'login' ? 'Đăng nhập' : mode === 'register' ? 'Đăng ký' : 'Quên mật khẩu'}
        </h2>

        {mode !== 'forgot' && (
          <div className="flex justify-center gap-6 mb-4">
            <button
              onClick={() => switchMode('login')}
              className={`text-sm pb-1 border-b-2 transition ${mode === 'login' ? 'text-primary border-primary font-semibold' : 'text-gray-400 border-transparent'}`}
            >
              Đăng nhập
            </button>
            <button
              onClick={() => switchMode('register')}
              className={`text-sm pb-1 border-b-2 transition ${mode === 'register' ? 'text-primary border-primary font-semibold' : 'text-gray-400 border-transparent'}`}
            >
              Đăng ký
            </button>
          </div>
        )}

        {mode === 'register' && (
          <div className="mb-3">
            <label className="block text-xs font-semibold text-gray-500 mb-1">Họ tên</label>
            <input
              value={hoTen}
              onChange={(e) => setHoTen(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none"
              placeholder="Nguyễn Văn A"
            />
          </div>
        )}
        <div className="mb-3">
          <label className="block text-xs font-semibold text-gray-500 mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none"
            placeholder="email@example.com"
            autoFocus
          />
        </div>
        {mode !== 'forgot' && (
          <div className="mb-3">
            <label className="block text-xs font-semibold text-gray-500 mb-1">Mật khẩu</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none"
              placeholder="••••••"
            />
          </div>
        )}

        {error && <p className="text-red-600 text-xs mb-3">{error}</p>}
        {success && <p className="text-green-600 text-xs mb-3">{success}</p>}

        <div className="flex gap-2 mt-4">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-300 rounded text-sm text-gray-600 hover:border-primary hover:text-primary transition"
          >
            Hủy
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-4 py-2 bg-primary text-white rounded text-sm font-medium hover:bg-primary-dark transition disabled:opacity-50"
          >
            {loading ? 'Đang xử lý...' : (
              mode === 'login' ? 'Đăng nhập' : mode === 'register' ? 'Đăng ký' : 'Gửi email'
            )}
          </button>
        </div>

        {mode === 'login' && (
          <button
            onClick={() => switchMode('forgot')}
            className="block mx-auto mt-3 text-xs text-gray-400 hover:text-primary transition"
          >
            Quên mật khẩu?
          </button>
        )}
        {mode === 'forgot' && (
          <button
            onClick={() => switchMode('login')}
            className="block mx-auto mt-3 text-xs text-gray-400 hover:text-primary transition"
          >
            ← Quay lại đăng nhập
          </button>
        )}
      </div>
    </div>
  );
}
