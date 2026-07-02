/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark-blue / navy brand ramp, matching the STK logo (replaces the
        // former orange). Every `brand-*` class recolors from here.
        brand: {
          50: '#eef4fb',
          100: '#d8e6f5',
          200: '#b3cbe9',
          300: '#7fa6d6',
          400: '#4f7db8',
          500: '#2f5c94',
          600: '#1e4373',
          700: '#163356',
          800: '#112843',
          900: '#0c1c30',
        }
      }
    },
  },
  plugins: [],
}
