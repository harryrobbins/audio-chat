/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'govuk-blue': '#1d70b8',
        'govuk-black': '#0b0c0c',
        'govuk-grey-1': '#333333',
        'govuk-grey-2': '#6f777b',
        'govuk-grey-3': '#b1b4b6',
        'govuk-grey-4': '#f3f2f1',
        'govuk-white': '#ffffff',
        'govuk-green': '#00703c',
        'govuk-red': '#d4351c',
        'govuk-yellow': '#ffdd00',
      },
      fontFamily: {
        'govuk': ['GDS Transport', 'arial', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
