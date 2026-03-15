import type { HieuLucIndex } from '../types';
import { formatDate } from '../api';

export default function HieuLucDetail({ index }: { index: HieuLucIndex }) {
  return (
    <div className="mt-4 border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Hiệu lực chi tiết</h3>

      {index.tom_tat_hieu_luc && (
        <p className="text-sm text-gray-600 italic mb-3">
          {index.tom_tat_hieu_luc}
        </p>
      )}

      {(index.hieu_luc ?? []).length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left p-2 font-medium text-gray-600 border-b">Phạm vi</th>
                <th className="text-left p-2 font-medium text-gray-600 border-b">Từ ngày</th>
                <th className="text-left p-2 font-medium text-gray-600 border-b">Đến ngày</th>
                <th className="text-left p-2 font-medium text-gray-600 border-b">Ghi chú</th>
              </tr>
            </thead>
            <tbody>
              {(index.hieu_luc ?? []).map((entry, i) => (
                <tr key={i} className={entry.den_ngay ? 'bg-red-50' : ''}>
                  <td className="p-2 border-b border-gray-100">{entry.pham_vi}</td>
                  <td className="p-2 border-b border-gray-100">
                    {entry.tu_ngay ? formatDate(entry.tu_ngay) : '—'}
                  </td>
                  <td className="p-2 border-b border-gray-100">
                    {entry.den_ngay ? (
                      formatDate(entry.den_ngay)
                    ) : (
                      <span className="text-green-600 font-medium">Hiện nay</span>
                    )}
                  </td>
                  <td className="p-2 border-b border-gray-100 text-gray-500">
                    {entry.ghi_chu || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(index.van_ban_thay_the ?? []).length > 0 && (
        <div className="mt-3 text-sm">
          <span className="font-medium text-red-700">Thay thế hoàn toàn: </span>
          {(index.van_ban_thay_the ?? []).join(', ')}
        </div>
      )}
      {(index.van_ban_sua_doi ?? []).length > 0 && (
        <div className="mt-1 text-sm">
          <span className="font-medium text-yellow-700">Sửa đổi một phần: </span>
          {(index.van_ban_sua_doi ?? []).join(', ')}
        </div>
      )}
    </div>
  );
}
