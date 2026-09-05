/**@type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        wolfpack: {
          DEFAULT: '#f97316',
          dark: '#1e1b3a',
        },
      },
    },
  },
  plugins: [],
}