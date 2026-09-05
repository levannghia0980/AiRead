import React from 'react'
import { Settings, Key, CheckCircle, XCircle, Save, Plus, Minus } from 'lucide-react'

interface ModelSettingsPanelProps {
  provider: string
  model: string
  apiKeys: string
  customPrompt: string
  delay: number
  batchSize: number
  startChapter: number | null
  endChapter: number | null
  translationStyle?: string
  enableUnblock?: boolean
  enableErotic?: boolean
  enableLlmExtract?: boolean
  enableNamesDict?: boolean
  enableGgCorrections?: boolean
  forceRetranslate?: boolean
  setSettings: (s: any) => void
  handleTestKey: () => void
  isTestingKey: boolean
  keyTestResult: { success: boolean; message: string } | null
  saveSettingsToEnv: () => Promise<void>
  isSavedToEnv: boolean
  setIsSavedToEnv: (val: boolean) => void
}

const ToggleSwitch: React.FC<{
  label: string
  sublabel?: string
  checked: boolean
  onChange: (val: boolean) => void
  icon?: string
}> = ({ label, sublabel, checked, onChange, icon }) => (
  <button
    type="button"
    onClick={() => onChange(!checked)}
    className={`w-full rounded-xl px-3 py-2 flex items-center justify-between transition-all duration-200 border cursor-pointer ${checked
        ? 'border-emerald-500/50 bg-emerald-950/30 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.15)]'
        : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700'
      }`}
  >
    <div className="flex flex-col text-left pr-2 min-w-0">
      <span className="text-xs font-bold flex items-center gap-1.5 truncate">
        {icon && <span>{icon}</span>}
        {label}
      </span>
      {sublabel && <span className="text-[10px] opacity-75 mt-0.5 font-normal leading-tight">{sublabel}</span>}
    </div>
    <div
      className={`w-9 h-5 rounded-full transition-colors duration-300 relative flex-shrink-0 p-0.5 ${checked ? 'bg-emerald-500' : 'bg-slate-700'
        }`}
    >
      <div
        className={`w-4 h-4 rounded-full bg-white shadow-md transform transition-transform duration-300 ${checked ? 'translate-x-4' : 'translate-x-0'
          }`}
      />
    </div>
  </button>
)

export const ModelSettingsPanel: React.FC<ModelSettingsPanelProps> = ({
  provider,
  model,
  apiKeys,
  customPrompt,
  delay,
  batchSize,
  startChapter,
  endChapter,
  translationStyle: _translationStyle = 'original_only',
  enableUnblock = true,
  enableErotic = false,
  forceRetranslate = false,
  setSettings,
  handleTestKey,
  isTestingKey,
  keyTestResult,
  saveSettingsToEnv,
  isSavedToEnv,
  setIsSavedToEnv
}) => {
  const getModelsForProvider = (prov: string) => {
    switch (prov) {
      case 'gemini':
        return [
          'gemini-3.1-flash-lite',
          'gemini-3.1-flash-lite-preview',
          'gemini-3.5-flash-lite',
          'gemini-3.5-flash'
        ]
      case 'openrouter':
        return [
          'google/gemma-4-26b-a4b-it:free',
          'nvidia/nemotron-3-ultra-550b-a55b:free'
        ]
      case 'openai':
        return ['gpt-4o-mini', 'gpt-4o']
      default:
        return ['default-model']
    }
  }

  const models = getModelsForProvider(provider)

  return (
    <div className="glass-panel rounded-2xl p-4 flex flex-col gap-3 flex-shrink-0">
      <h2 className="text-xs font-bold text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
        <Settings className="w-4 h-4 text-cyber-accent" /> Cấu Hình AI & Model
      </h2>

      {/* Cấu hình Provider & Model */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-cyber-muted block mb-1">Cung Cấp (Provider)</label>
          <select
            value={provider}
            onChange={(e) => {
              const newProv = e.target.value
              const newModels = getModelsForProvider(newProv)
              setSettings({
                provider: newProv,
                model: newModels[0]
              })
            }}
            className="w-full glass-input rounded-xl px-2.5 py-1.5 text-xs text-cyber-text font-semibold bg-slate-900/90 border border-slate-700/60 focus:border-cyber-accent"
          >
            <option value="openrouter">🌐 OpenRouter (Free / Multi-Model)</option>
            <option value="gemini">⚡ Google Gemini (Direct API)</option>
            <option value="openai">🤖 OpenAI</option>
          </select>
        </div>

        <div>
          <label className="text-[10px] text-cyber-muted block mb-1">Mô Hình (Model ID)</label>
          <select
            value={model}
            onChange={(e) => setSettings({ model: e.target.value })}
            className="w-full glass-input rounded-xl px-2.5 py-1.5 text-xs text-cyber-text font-semibold bg-slate-900/90 border border-slate-700/60 focus:border-cyber-accent"
          >
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Kiểu Dịch */}
      <div>
        <label className="text-[10px] font-bold text-cyber-accent block mb-1">
          🎯 Luồng Dịch AI
        </label>
        <div className="w-full glass-input rounded-xl px-2.5 py-1.5 text-xs text-cyber-accent font-semibold bg-slate-900/90 border border-cyber-accent/40 flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <span>🔤 Dịch Tiếng Trung Trực Tiếp</span>
            <span className="text-[10px] font-mono text-cyan-400 font-bold">(RAWT)</span>
          </span>
          <span className="text-[9px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-1.5 py-0.5 rounded font-mono">
            Tối ưu Token & Tốc độ
          </span>
        </div>
      </div>

      {/* API Keys Input */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-[10px] text-cyber-muted flex items-center gap-1">
            <Key className="w-3 h-3 text-cyber-accent" /> Danh Sách API Key (Xuống dòng cho nhiều key)
          </label>
          <div className="flex gap-1.5 flex-wrap justify-end">
            <button
              onClick={handleTestKey}
              disabled={isTestingKey || !apiKeys.trim()}
              className="text-[9px] font-bold px-2 py-0.5 rounded bg-cyber-accent/10 border border-cyber-accent/30 text-cyber-accent hover:bg-cyber-accent/20 transition-all disabled:opacity-40"
            >
              {isTestingKey ? 'Đang test...' : 'Test Key'}
            </button>

            <button
              onClick={async () => {
                await saveSettingsToEnv()
                setIsSavedToEnv(true)
                setTimeout(() => setIsSavedToEnv(false), 3000)
              }}
              className="text-[9px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 transition-all flex items-center gap-1"
            >
              <Save className="w-2.5 h-2.5" /> {isSavedToEnv ? 'Đã Lưu!' : 'Lưu .env'}
            </button>
          </div>
        </div>
        <textarea
          rows={2}
          value={apiKeys}
          onChange={(e) => setSettings({ apiKeys: e.target.value })}
          placeholder="Nhập API Key..."
          className="w-full glass-input rounded-xl p-2 text-[10px] font-mono"
        />

        {keyTestResult && (
          <div className={`mt-1 text-[10px] p-1.5 rounded-lg flex items-center gap-1.5 ${keyTestResult.success
            ? 'bg-emerald-950/40 border border-emerald-500/30 text-emerald-400'
            : 'bg-rose-950/40 border border-rose-500/30 text-rose-400'
            }`}>
            {keyTestResult.success ? <CheckCircle className="w-3 h-3 flex-shrink-0" /> : <XCircle className="w-3 h-3 flex-shrink-0" />}
            <span className="truncate">{keyTestResult.message}</span>
          </div>
        )}
      </div>

      {/* Batch & Delay Config */}
      <div className="grid grid-cols-2 gap-2">
        {/* Gộp Chương (Batch Size) */}
        <div>
          <label className="text-[10px] font-medium text-cyber-muted block mb-1">Gộp Chương (Batch)</label>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setSettings({ batchSize: Math.max(1, Math.round(batchSize || 3) - 1) })}
              className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700/70 text-slate-200 hover:text-white hover:bg-slate-700 active:scale-90 flex items-center justify-center font-bold transition-all shrink-0 shadow-sm"
              title="Giảm 1 chương"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>

            <input
              type="number"
              min={1}
              max={20}
              step={1}
              value={Math.round(batchSize || 3)}
              onChange={(e) => {
                const val = parseInt(e.target.value)
                setSettings({ batchSize: isNaN(val) ? 1 : Math.max(1, Math.min(20, val)) })
              }}
              className="w-full glass-input rounded-xl px-1 py-1.5 text-xs text-center font-bold text-cyber-accent min-w-0"
            />

            <button
              type="button"
              onClick={() => setSettings({ batchSize: Math.min(20, Math.round(batchSize || 3) + 1) })}
              className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700/70 text-slate-200 hover:text-white hover:bg-slate-700 active:scale-90 flex items-center justify-center font-bold transition-all shrink-0 shadow-sm"
              title="Tăng 1 chương"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Delay (Giây) */}
        <div>
          <label className="text-[10px] font-medium text-cyber-muted block mb-1">Delay (Giây)</label>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setSettings({ delay: Math.max(0, Math.round(delay || 0) - 1) })}
              className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700/70 text-slate-200 hover:text-white hover:bg-slate-700 active:scale-90 flex items-center justify-center font-bold transition-all shrink-0 shadow-sm"
              title="Giảm 1 giây"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>

            <input
              type="number"
              min={0}
              max={60}
              step={1}
              value={Math.round(delay || 0)}
              onChange={(e) => {
                const val = parseInt(e.target.value)
                setSettings({ delay: isNaN(val) ? 0 : Math.max(0, Math.min(60, val)) })
              }}
              className="w-full glass-input rounded-xl px-1 py-1.5 text-xs text-center font-bold text-emerald-400 min-w-0"
            />

            <button
              type="button"
              onClick={() => setSettings({ delay: Math.min(60, Math.round(delay || 0) + 1) })}
              className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700/70 text-slate-200 hover:text-white hover:bg-slate-700 active:scale-90 flex items-center justify-center font-bold transition-all shrink-0 shadow-sm"
              title="Tăng 1 giây"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Start / End Chapter Range */}
      <div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-cyber-muted block mb-1">Từ Chương Số</label>
            <input
              type="number"
              placeholder="Tự động tiếp tục"
              value={startChapter ?? ''}
              onChange={(e) => setSettings({ startChapter: e.target.value ? parseInt(e.target.value) : null })}
              className="w-full glass-input rounded-xl px-2.5 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="text-[10px] text-cyber-muted block mb-1">Đến Chương Số</label>
            <input
              type="number"
              placeholder="Đến cuối"
              value={endChapter ?? ''}
              onChange={(e) => setSettings({ endChapter: e.target.value ? parseInt(e.target.value) : null })}
              className="w-full glass-input rounded-xl px-2.5 py-1.5 text-xs"
            />
          </div>
        </div>
        <span className="text-[9px] text-slate-500 italic block mt-1">
          * Để trống Từ Chương = Tự động tiếp tục từ chương chưa dịch
        </span>
      </div>

      {/* Force Retranslate Toggle */}
      <ToggleSwitch
        label="Dịch lại / Ghi đè chương đã dịch"
        sublabel="Mặc định tắt (tự động bỏ qua các chương đã hoàn tất)"
        checked={forceRetranslate}
        onChange={(val) => setSettings({ forceRetranslate: val })}
        icon="🔄"
      />

      {/* 2 Nút gạt độc lập thu nhỏ gọn */}
      <div className="grid grid-cols-2 gap-2">
        <ToggleSwitch
          icon="🔞"
          label="Phong Cách"
          checked={enableErotic}
          onChange={(val) => setSettings({ enableErotic: val })}
        />
        <ToggleSwitch
          icon="🛡️"
          label="Giấu Từ"
          checked={enableUnblock}
          onChange={(val) => setSettings({ enableUnblock: val })}
        />
      </div>

      {/* Custom Prompt Input */}
      <div>
        <label className="text-[10px] text-cyber-muted block mb-1">Prompt Yêu Cầu Tùy Chỉnh</label>
        <textarea
          rows={2}
          value={customPrompt}
          onChange={(e) => setSettings({ customPrompt: e.target.value })}
          placeholder="Nhập yêu cầu bổ sung cho AI (ví dụ: Giữ nguyên xưng hô tiểu thư, thiếu gia)..."
          className="w-full glass-input rounded-xl p-2 text-[10px]"
        />
      </div>
    </div>
  )
}
export default ModelSettingsPanel
