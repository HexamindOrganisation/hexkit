const path = require("node:path");

/** @type {import("tailwindcss").Config} */
module.exports = {
  presets: [require(path.resolve(__dirname, "../../tailwind.preset.cjs"))],
  content: [
    path.resolve(__dirname, "./**/*.{ts,tsx,html}"),
    path.resolve(__dirname, "../../src/**/*.{ts,tsx}"),
  ],
};
