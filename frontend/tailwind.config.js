/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Sentinel AI design system — deep slate professional theme
        slate: {
          950: '#0a0f1a',
          925: '#0d1424',
          900: '#0f172a',
          850: '#131d35',
          800: '#1e293b',
          750: '#243044',
          700: '#334155',
          600: '#475569',
          500: '#64748b',
          400: '#94a3b8',
          300: '#cbd5e1',
          200: '#e2e8f0',
          100: '#f1f5f9',
        },
        // Semantic risk colors
        risk: {
          critical: '#ef4444',   // red-500
          high: '#f97316',       // orange-500
          medium: '#eab308',     // yellow-500
          low: '#22c55e',        // green-500
          none: '#64748b',       // slate-500
        },
        // Priority colors
        priority: {
          immediate: '#ef4444',
          'short-term': '#f97316',
          'medium-term': '#eab308',
          monitor: '#22c55e',
        },
        // Data type colors
        datatype: {
          observed: '#3b82f6',    // blue-500
          derived: '#8b5cf6',     // violet-500
          estimated: '#f59e0b',   // amber-500
          simulated: '#06b6d4',   // cyan-500
          recommendation: '#10b981', // emerald-500
        },
        // Accent
        accent: {
          blue: '#3b82f6',
          teal: '#14b8a6',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        '2xs': '0.625rem',
        xs: '0.75rem',
        sm: '0.8125rem',
        base: '0.875rem',
        lg: '1rem',
        xl: '1.125rem',
        '2xl': '1.25rem',
        '3xl': '1.5rem',
        '4xl': '1.875rem',
      },
    },
  },
  plugins: [],
}
