/** @type {import('tailwindcss').Config} */
// Design system: Scholarly Press (see /DESIGN.md and /tesigo-brandbook.html).
// primary = academic green (NOT blue), gray = warm neutral, serif = Literata.
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Brand accent — academic green #0f6e56 at the 600 step.
        primary: {
          50: '#e8f3ee',
          100: '#c9e3d9',
          200: '#a3d0c0',
          300: '#6fb7a0',
          400: '#3f9b80',
          500: '#1a8064',
          600: '#0f6e56',
          700: '#0a4d3c',
          800: '#083d30',
          900: '#062b22',
        },
        // Warm neutral — remaps Tailwind's cool gray so every existing gray-*
        // utility becomes warm paper/ink without touching component files.
        gray: {
          50: '#f7f5f0',
          100: '#efeadf',
          200: '#e6e1d6',
          300: '#d6d0c2',
          400: '#b3ad9f',
          500: '#8a877f',
          600: '#6b6860',
          700: '#4a4843',
          800: '#302e29',
          900: '#1c1b19',
        },
        secondary: {
          50: '#f7f5f0',
          100: '#efeadf',
          200: '#e6e1d6',
          300: '#d6d0c2',
          400: '#b3ad9f',
          500: '#8a877f',
          600: '#6b6860',
          700: '#4a4843',
          800: '#302e29',
          900: '#1c1b19',
        },
        // Semantic brand tokens (DESIGN.md).
        paper: '#fffdf9',
        ink: '#1c1b19',
        accent: {
          DEFAULT: '#0f6e56',
          deep: '#0a4d3c',
          soft: '#e4f1ea',
        },
      },
      fontFamily: {
        sans: ['Source Sans 3', 'system-ui', 'sans-serif'],
        display: ['Literata', 'Georgia', 'serif'],
        serif: ['Literata', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        paper: '0 1px 2px rgba(28,27,25,.04), 0 8px 24px rgba(28,27,25,.07)',
        'paper-lg': '0 1px 2px rgba(28,27,25,.04), 0 18px 44px rgba(28,27,25,.12)',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
