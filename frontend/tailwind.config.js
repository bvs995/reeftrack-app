/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        marine: {
          950: '#020617', // Slate-950 ultra oscuro abisal
          900: '#0f172a', // Slate-900 base náutica
          850: '#141f36', // Slate-850 intermedio
          800: '#1e293b', // Slate-800 paneles
          700: '#334155', // Slate-700 bordes y separadores
          600: '#475569',
        },
        cyan: {
          neon: '#00f2fe',
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
        },
        emerald: {
          neon: '#00ff9d',
          400: '#34d399',
          500: '#10b981',
        },
        coral: {
          neon: '#ff3366',
          400: '#fb7185',
          500: '#f43f5e',
        }
      },
      boxShadow: {
        'neon-cyan': '0 0 20px -3px rgba(6, 182, 212, 0.45)',
        'neon-cyan-lg': '0 0 35px -5px rgba(6, 182, 212, 0.65)',
        'neon-emerald': '0 0 20px -3px rgba(16, 185, 129, 0.45)',
        'neon-coral': '0 0 20px -3px rgba(244, 63, 94, 0.45)',
      },
      minHeight: {
        'touch': '48px',
        'touch-lg': '56px',
      }
    },
  },
  plugins: [],
}
