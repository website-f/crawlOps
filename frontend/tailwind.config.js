/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#fcfcfb',
        plane: '#f9f9f7',
        ink: '#0b0b0b',
        inksec: '#52514e',
        muted: '#898781',
        grid: '#e1e0d9',
        // single locked accent for the whole product — the blue already used ~38×
        // across the app, promoted to a token so everything stays consistent
        // (and stray purples get pulled back to it). One accent, Meltwater-clean.
        accent: {
          DEFAULT: '#2a78d6',
          soft: '#eaf2fb',
          ink: '#1f5aa8',
        },
        danger: '#d64545',
        positive: '#0a7d0a',
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      boxShadow: {
        // shadows tinted to the warm neutral background — never pure black
        card: '0 1px 2px rgba(28,26,20,0.04), 0 1px 1px rgba(28,26,20,0.03)',
        raise: '0 2px 8px rgba(28,26,20,0.06), 0 1px 2px rgba(28,26,20,0.04)',
        float: '0 12px 32px -8px rgba(28,26,20,0.18), 0 4px 10px -4px rgba(28,26,20,0.10)',
      },
      keyframes: {
        fade: { from: { opacity: 0 }, to: { opacity: 1 } },
        pop: {
          from: { opacity: 0, transform: 'translateY(6px) scale(0.98)' },
          to: { opacity: 1, transform: 'translateY(0) scale(1)' },
        },
        slidein: {
          from: { opacity: 0, transform: 'translateX(12px)' },
          to: { opacity: 1, transform: 'translateX(0)' },
        },
        drawerin: {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(0)' },
        },
        canvasin: {
          from: { transform: 'translateX(100%)' },
          to: { transform: 'translateX(0)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
    },
  },
  plugins: [],
}
