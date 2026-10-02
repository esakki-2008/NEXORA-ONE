/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#07111f",
        panel: "#0d1b2b",
        line: "#20334a",
        cyan: "#5de4ff",
        signal: "#8ba9ff"
      }
    }
  },
  plugins: []
};
