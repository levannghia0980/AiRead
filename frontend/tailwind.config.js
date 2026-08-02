/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cyber: {
          bg: "#0B0F19",
          card: "rgba(17, 25, 40, 0.75)",
          border: "rgba(255, 255, 255, 0.08)",
          accent: "#00E5FF", // Neon Cyan
          purple: "#9E00FF", // Neon Purple
          pink: "#FF007F",   // Neon Pink
          success: "#00FF66", // Neon Green
          danger: "#FF3366",  // Neon Red
          text: "#E2E8F0",
          muted: "#94A3B8"
        }
      },
      backdropBlur: {
        xs: "2px",
      },
      animation: {
        'glow-pulse': 'glowPulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out forwards',
      },
      keyframes: {
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 5px rgba(0, 229, 255, 0.2), 0 0 15px rgba(0, 229, 255, 0.1)' },
          '50%': { boxShadow: '0 0 15px rgba(0, 229, 255, 0.5), 0 0 30px rgba(0, 229, 255, 0.2)' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        }
      }
    },
  },
  plugins: [],
}
