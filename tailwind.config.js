/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        vps: {
          dark: '#0f172a',
          card: '#1e293b',
          border: '#334155',
          primary: '#38bdf8',
          secondary: '#818cf8',
          accent: '#facc15',
        }
      }
    },
  },
  plugins: [],
}
