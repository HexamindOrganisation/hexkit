import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const distDir = resolve(root, "dist");
mkdirSync(distDir, { recursive: true });

const copies = [
  { src: resolve(root, "src/styles.css"), dst: resolve(distDir, "style.css") },
  { src: resolve(root, "src/shadcn.css"), dst: resolve(distDir, "shadcn.css") },
  {
    src: resolve(root, "tailwind.preset.cjs"),
    dst: resolve(distDir, "tailwind.preset.cjs"),
  },
];

for (const { src, dst } of copies) {
  copyFileSync(src, dst);
  process.stdout.write(`copied ${src} -> ${dst}\n`);
}
