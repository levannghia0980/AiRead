import React from 'react'
import {
  BookOpen,
  Library as LibIcon,
  FileText,
  Headphones,
  Sun,
  Moon
} from 'lucide-react'

interface NavbarProps {
  activeTab: 'translate' | 'glossary' | 'library' | 'audio'
  setActiveTab: (tab: 'translate' | 'glossary' | 'library' | 'audio') => void
  selectedNovelTitle?: string
  isRunning?: boolean
  theme?: 'dark' | 'light'
  toggleTheme?: () => void
}

export const Navbar: React.FC<NavbarProps> = React.memo(({
  activeTab,
  setActiveTab,
  selectedNovelTitle,
  isRunning,
  theme = 'dark',
  toggleTheme
}) => {
  return (
    <>
      {/* Top Navbar Header */}
      <header className="fixed top-0 left-0 right-0 z-50 h-16 bg-[#070A13]/95 border-b border-slate-900 transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          {/* Brand Logo */}
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-gradient-to-tr from-cyber-accent to-purple-600 rounded-xl shadow-lg shadow-cyber-accent/20">
              <BookOpen className="w-5 h-5 md:w-6 md:h-6 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-base md:text-lg text-slate-100 flex items-center gap-2">
                AiRead <span className="text-[10px] md:text-xs px-2 py-0.5 rounded-full bg-cyber-accent/20 text-cyber-accent border border-cyber-accent/30">v2.5 Pro</span>
              </h1>
              <p className="text-[9px] md:text-[10px] text-cyber-muted hidden xs:block">Hệ thống dịch thuật & Audio AI</p>
            </div>
          </div>

          {/* Desktop Center Tabs Navigation */}
          <nav className="hidden md:flex items-center space-x-1 bg-cyber-dark/60 p-1.5 rounded-xl border border-cyber-border">
            <button
              onClick={() => setActiveTab('translate')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'translate'
                  ? 'bg-cyber-accent text-white shadow-lg shadow-cyber-accent/30 font-bold'
                  : 'text-cyber-muted hover:text-slate-200 hover:bg-cyber-card/50'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              <span>Dịch Thuật</span>
              {isRunning && (
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping ml-1" />
              )}
            </button>

            <button
              onClick={() => setActiveTab('library')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'library'
                  ? 'bg-cyber-accent text-white shadow-lg shadow-cyber-accent/30 font-bold'
                  : 'text-cyber-muted hover:text-slate-200 hover:bg-cyber-card/50'
              }`}
            >
              <LibIcon className="w-4 h-4" />
              <span>Thư Viện</span>
            </button>

            <button
              onClick={() => setActiveTab('audio')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'audio'
                  ? 'bg-cyber-accent text-white shadow-lg shadow-cyber-accent/30 font-bold'
                  : 'text-cyber-muted hover:text-slate-200 hover:bg-cyber-card/50'
              }`}
            >
              <Headphones className="w-4 h-4" />
              <span>Audio Studio</span>
            </button>

            <button
              onClick={() => setActiveTab('glossary')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'glossary'
                  ? 'bg-cyber-accent text-white shadow-lg shadow-cyber-accent/30 font-bold'
                  : 'text-cyber-muted hover:text-slate-200 hover:bg-cyber-card/50'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Từ Điển</span>
            </button>

          </nav>

          {/* Right Status & Theme Toggle */}
          <div className="flex items-center space-x-3">
            {/* Theme Switcher Button */}
            {toggleTheme && (
              <button
                onClick={toggleTheme}
                className={`px-3 py-1.5 rounded-xl border transition-all flex items-center gap-1.5 text-xs font-bold ${
                  theme === 'light'
                    ? 'bg-[#f4ecd8] border-[#d8c7a1] text-[#b45309] hover:bg-[#ede4ce] shadow-sm'
                    : 'bg-slate-900/90 border-cyber-border text-amber-400 hover:bg-slate-800'
                }`}
                title={theme === 'light' ? 'Chuyển sang Giao diện Tối (Cyber Dark)' : 'Chuyển sang Giao diện Sáng (Giấy Đọc Truyện)'}
              >
                {theme === 'light' ? (
                  <>
                    <Sun className="w-4 h-4 text-amber-700" />
                    <span className="hidden sm:inline text-amber-900 font-bold">Giấy Sáng</span>
                  </>
                ) : (
                  <>
                    <Moon className="w-4 h-4 text-amber-400" />
                    <span className="hidden sm:inline text-slate-300">Giao diện Tối</span>
                  </>
                )}
              </button>
            )}

            {selectedNovelTitle ? (
              <div className="text-right">
                <span className="text-[9px] text-cyber-muted block">Truyện đang chọn:</span>
                <span className="text-xs font-bold text-cyber-accent truncate max-w-[100px] sm:max-w-[160px] block">
                  {selectedNovelTitle}
                </span>
              </div>
            ) : (
              <div className="text-right hidden sm:block">
                <span className="text-[10px] text-cyber-muted block">Trạng thái:</span>
                <span className="text-xs font-medium text-emerald-400">Sẵn sàng</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Mobile Fixed Bottom Navigation Bar (Dành riêng cho màn hình Điện thoại) */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-[#070A13]/98 border-t border-slate-800/90 py-1 px-2 flex items-center justify-around shadow-2xl backdrop-blur-lg">
        <button
          onClick={() => setActiveTab('translate')}
          className={`flex flex-col items-center py-1 px-3 rounded-xl transition-all ${
            activeTab === 'translate'
              ? 'text-cyber-accent font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <div className="relative">
            <BookOpen className="w-5 h-5 mb-0.5" />
            {isRunning && (
              <span className="absolute -top-0.5 -right-1 w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            )}
          </div>
          <span className="text-[10px]">Dịch Thuật</span>
        </button>

        <button
          onClick={() => setActiveTab('library')}
          className={`flex flex-col items-center py-1 px-3 rounded-xl transition-all ${
            activeTab === 'library'
              ? 'text-cyber-accent font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <LibIcon className="w-5 h-5 mb-0.5" />
          <span className="text-[10px]">Thư Viện</span>
        </button>

        <button
          onClick={() => setActiveTab('audio')}
          className={`flex flex-col items-center py-1 px-3 rounded-xl transition-all ${
            activeTab === 'audio'
              ? 'text-cyber-accent font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Headphones className="w-5 h-5 mb-0.5" />
          <span className="text-[10px]">Audio</span>
        </button>

        <button
          onClick={() => setActiveTab('glossary')}
          className={`flex flex-col items-center py-1 px-3 rounded-xl transition-all ${
            activeTab === 'glossary'
              ? 'text-cyber-accent font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileText className="w-5 h-5 mb-0.5" />
          <span className="text-[10px]">Từ Điển</span>
        </button>

      </div>
    </>
  )
})
export default Navbar
