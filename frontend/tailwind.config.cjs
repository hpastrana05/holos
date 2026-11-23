module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#10131c",
        glow: "#22223b",
        "tile-glass": "rgba(255, 255, 255, .065)",
        "panel-glass": "rgba(255, 255, 255, .035)",
        "chart-hover": "rgba(255, 255, 255, .055)",
        panel: "#1a2030",
        control: "#141a27",
        ink: "#f2f4fb",
        muted: "#aeb8cd",
        edge: "#353e52",
        brand: "#b7a7ff",
        health: "#ff93b4",
        finance: "#78e2c0",
        nutrition: "#ffc478",
        calendar: "#9aaeff",
        house: "#79dafa",
        chat: "#d7a5ff",
        danger: "#ff9f9f",
      },
      borderRadius: { control: "12px", card: "20px", tile: "26px" },
      boxShadow: { glass: "0 12px 30px rgba(5, 8, 17, .22), inset 0 1px rgba(255, 255, 255, .035)" },
    },
  },
};
