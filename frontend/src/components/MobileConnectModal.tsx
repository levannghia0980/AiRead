import React, { useState, useEffect } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { Smartphone, Copy, Check, X, Wifi, Globe, Laptop, RefreshCw, ShieldAlert, Edit3 } from 'lucide-react'

interface MobileConnectModalProps {
  isOpen: boolean
  onClose: () => void
}

interface AdapterInfo {
  name: string
  ip: string
}

export const MobileConnectModal: React.FC<MobileConnectModalProps> = ({ isOpen, onClose }) => {
  const [networkInfo, setNetworkInfo] = useState<{
    lan_ip: string
    adapters?: AdapterInfo[]
    hostname: string
    ip_url: string
    hostname_url: string
    direct_host_url: string
  } | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedIp, setSelectedIp] = useState<string>('')
  const [isEditingIp, setIsEditingIp] = useState(false)
  const [customIpInput, setCustomIpInput] = useState('')
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'ip' | 'hostname'>('ip')
  const [showFirewallHelp, setShowFirewallHelp] = useState(false)

  const fetchNetwork = () => {
    setLoading(true)
    fetch('/api/settings/network-info')
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          setNetworkInfo(data)
          if (!selectedIp || selectedIp === 'localhost' || selectedIp === '127.0.0.1') {
            const validIp = data.lan_ip && data.lan_ip !== '127.0.0.1' 
              ? data.lan_ip 
              : (data.adapters && data.adapters[0]?.ip) || window.location.hostname
            setSelectedIp(validIp)
            setCustomIpInput(validIp)
          }
        }
      })
      .catch(err => {
        console.error('Failed to fetch network info', err)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (isOpen) {
      fetchNetwork()
    }
  }, [isOpen])

  if (!isOpen) return null

  const effectiveIp = selectedIp && selectedIp !== 'localhost' && selectedIp !== '127.0.0.1'
    ? selectedIp
    : (networkInfo?.lan_ip && networkInfo.lan_ip !== '127.0.0.1' ? networkInfo.lan_ip : '192.168.1.x')

  const currentUrl = activeTab === 'ip' 
    ? `http://${effectiveIp}:8000`
    : (networkInfo?.hostname_url || `http://${networkInfo?.hostname?.toLowerCase() || 'airead'}.local:8000`)

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey(null), 2000)
  }

  const handleSaveCustomIp = () => {
    if (customIpInput.trim()) {
      setSelectedIp(customIpInput.trim())
      setIsEditingIp(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fade-in">
      <div className="bg-[#0b101e] border border-cyan-500/40 rounded-2xl w-full max-w-md p-5 shadow-2xl relative text-slate-200 max-h-[95vh] overflow-y-auto custom-scrollbar">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-xl border border-slate-700/60 hover:bg-slate-800 text-slate-400 hover:text-white transition-all"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3 mb-3">
          <div className="p-2.5 bg-gradient-to-tr from-cyan-500 to-blue-600 rounded-xl shadow-lg shadow-cyan-500/20 text-white">
            <Smartphone className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-bold text-base text-slate-100 flex items-center gap-2">
              Kết Nối Điện Thoại
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                Cùng Mạng LAN/Wi-Fi
              </span>
            </h2>
            <p className="text-xs text-slate-400">Quét mã QR để mở giao diện đọc truyện trên điện thoại</p>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex gap-2 p-1 bg-slate-900/80 rounded-xl border border-slate-800 mb-3">
          <button
            onClick={() => setActiveTab('ip')}
            className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'ip'
                ? 'bg-cyan-500 text-slate-950 shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Wifi className="w-3.5 h-3.5" />
            <span>Địa Chỉ IP Wi-Fi/LAN</span>
          </button>

          <button
            onClick={() => setActiveTab('hostname')}
            className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'hostname'
                ? 'bg-purple-500 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Laptop className="w-3.5 h-3.5" />
            <span>Link Cố Định (mDNS)</span>
          </button>
        </div>

        {/* IP Selector / Custom Input if Multiple Adapters */}
        {activeTab === 'ip' && (
          <div className="mb-3 p-2.5 bg-slate-900/60 rounded-xl border border-slate-800 text-xs">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5">
                <Wifi className="w-3 h-3 text-cyan-400" />
                IP Máy Tính Trong Mạng:
              </span>
              <button 
                onClick={fetchNetwork}
                disabled={loading}
                className="text-[10px] text-cyan-400 hover:underline flex items-center gap-1"
                title="Làm mới IP"
              >
                <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                Làm mới
              </button>
            </div>

            {isEditingIp ? (
              <div className="flex gap-1.5 mt-1">
                <input
                  type="text"
                  value={customIpInput}
                  onChange={(e) => setCustomIpInput(e.target.value)}
                  placeholder="Ví dụ: 192.168.1.100"
                  className="flex-1 px-2.5 py-1 text-xs bg-slate-950 border border-cyan-500/50 rounded-lg text-cyan-300 font-mono focus:outline-none"
                />
                <button
                  onClick={handleSaveCustomIp}
                  className="px-2.5 py-1 bg-cyan-500 text-slate-950 text-xs font-bold rounded-lg"
                >
                  Xong
                </button>
                <button
                  onClick={() => setIsEditingIp(false)}
                  className="px-2 py-1 bg-slate-800 text-slate-400 text-xs rounded-lg"
                >
                  Hủy
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-cyan-300 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-500/30">
                    {effectiveIp}
                  </span>
                  {networkInfo?.adapters && networkInfo.adapters.length > 1 && (
                    <select
                      value={selectedIp}
                      onChange={(e) => setSelectedIp(e.target.value)}
                      className="bg-slate-800 text-slate-300 text-[11px] px-2 py-0.5 rounded border border-slate-700 focus:outline-none"
                    >
                      {networkInfo.adapters.map((ad, idx) => (
                        <option key={idx} value={ad.ip}>
                          {ad.name}: {ad.ip}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <button
                  onClick={() => {
                    setCustomIpInput(effectiveIp)
                    setIsEditingIp(true)
                  }}
                  className="text-[11px] text-slate-400 hover:text-cyan-300 flex items-center gap-1 p-1"
                  title="Sửa IP thủ công nếu cần"
                >
                  <Edit3 className="w-3 h-3" />
                  Sửa
                </button>
              </div>
            )}
          </div>
        )}

        {/* QR Code Container */}
        <div className="flex flex-col items-center justify-center p-3 bg-slate-950/80 rounded-xl border border-slate-800/80 mb-3">
          <div className="p-2.5 bg-white rounded-xl shadow-xl">
            <QRCodeSVG
              value={currentUrl}
              size={170}
              level="M"
              includeMargin={false}
            />
          </div>
          <p className="text-[11px] text-slate-400 mt-2 text-center">
            Dùng <b>Camera</b> hoặc <b>Zalo</b> trên điện thoại để quét mã mở ngay
          </p>
        </div>

        {/* Link Details & 1-Click Copy */}
        <div className="space-y-1.5 mb-3">
          <div className="flex items-center justify-between p-2 bg-slate-900/60 rounded-xl border border-slate-800 text-xs">
            <div className="min-w-0 flex-1 mr-2">
              <span className="text-[10px] text-slate-500 block">Đường dẫn {activeTab === 'ip' ? 'IP LAN' : 'Cố Định'}:</span>
              <span className="font-mono font-bold text-cyan-400 truncate block">
                {currentUrl}
              </span>
            </div>
            <button
              onClick={() => handleCopy(currentUrl, 'main')}
              className="px-2.5 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 font-bold text-xs flex items-center gap-1 border border-cyan-500/40 transition-all flex-shrink-0"
            >
              {copiedKey === 'main' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copiedKey === 'main' ? 'Đã chép' : 'Sao chép'}</span>
            </button>
          </div>

          {networkInfo?.hostname_url && activeTab === 'ip' && (
            <div className="flex items-center justify-between p-2 bg-slate-900/40 rounded-xl border border-slate-800/60 text-xs">
              <div className="min-w-0 flex-1 mr-2">
                <span className="text-[10px] text-slate-500 block">Link tên máy tính (mDNS):</span>
                <span className="font-mono text-purple-300 truncate block">
                  {networkInfo.hostname_url}
                </span>
              </div>
              <button
                onClick={() => handleCopy(networkInfo.hostname_url, 'host')}
                className="px-2.5 py-1 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 text-xs flex items-center gap-1 border border-purple-500/40 transition-all flex-shrink-0"
              >
                {copiedKey === 'host' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedKey === 'host' ? 'Đã chép' : 'Sao chép'}</span>
              </button>
            </div>
          )}
        </div>

        {/* Troubleshooting & Notes */}
        <div className="space-y-2">
          <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-[11px] text-blue-300 flex items-start gap-2">
            <Globe className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-cyan-400" />
            <span>
              <b>Lưu ý:</b> Điện thoại và máy tính cần bắt chung một mạng Wi-Fi / Router. Bạn có thể lưu link này vào Bookmark trên trình duyệt điện thoại để mở lại bất cứ lúc nào!
            </span>
          </div>

          <button
            onClick={() => setShowFirewallHelp(!showFirewallHelp)}
            className="w-full text-left p-2 rounded-xl bg-slate-900/80 hover:bg-slate-800/80 border border-amber-500/30 text-amber-300 text-[11px] flex items-center justify-between transition-all"
          >
            <span className="flex items-center gap-1.5 font-medium">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
              Điện thoại báo không thể kết nối hoặc tải mãi?
            </span>
            <span className="text-[10px] text-amber-400 underline">
              {showFirewallHelp ? 'Thu gọn' : 'Xem cách sửa'}
            </span>
          </button>

          {showFirewallHelp && (
            <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-[11px] text-slate-300 space-y-1.5">
              <p className="font-semibold text-amber-300">3 Nguyên nhân thường gặp:</p>
              <ol className="list-decimal list-inside space-y-1 text-slate-300">
                <li>
                  <b>Tường lửa Windows (Firewall):</b> Windows có thể đang chặn cổng 8000. Bạn hãy tìm <b>Windows Defender Firewall</b> &gt; Cho phép ứng dụng hoặc tắt tạm thời mạng Private.
                </li>
                <li>
                  <b>Cách ly Wi-Fi (AP Isolation):</b> Một số router Wi-Fi chặn các thiết bị thấy nhau. Hãy thử tắt 4G/5G trên điện thoại và bật đúng mạng Wi-Fi của nhà.
                </li>
                <li>
                  <b>Nhập trực tiếp IP:</b> Mở Safari / Chrome trên điện thoại gõ: <code className="text-cyan-300 bg-slate-900 px-1 py-0.5 rounded font-mono">{currentUrl}</code>
                </li>
              </ol>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
export default MobileConnectModal

