/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // GGP Poker 브랜드 컬러
        brand: {
          primary: '#2563eb',    // Blue 600
          secondary: '#1e40af',  // Blue 800
          accent: '#fbbf24',     // Amber 400
        },
        sync: {
          idle: '#6b7280',       // Gray 500
          running: '#3b82f6',    // Blue 500
          success: '#22c55e',    // Green 500
          error: '#ef4444',      // Red 500
        }
      }
    },
  },
  plugins: [],
}
