#!/usr/bin/env node
import process from "node:process";
import { emitSchema } from "./emit-schema.js";
import { validateFile, formatDiagnostic } from "./validate.js";

function main(): void {
  const [, , cmd, ...rest] = process.argv;

  if (!cmd || cmd === "--help" || cmd === "-h") {
    usage();
    process.exit(cmd ? 0 : 1);
  }

  if (cmd === "emit-schema") {
    process.stdout.write(emitSchema() + "\n");
    return;
  }

  if (cmd === "validate") {
    const file = rest[0];
    if (!file) {
      console.error("validate: expected a config file path");
      process.exit(2);
    }
    const res = validateFile(file);
    for (const d of res.diagnostics) {
      const line = formatDiagnostic(d);
      if (d.severity === "error") console.error(line);
      else console.warn(line);
    }
    if (res.ok) {
      console.log(`✓ ${file} is valid`);
      process.exit(0);
    }
    process.exit(1);
  }

  console.error(`Unknown command: ${cmd}`);
  usage();
  process.exit(2);
}

function usage(): void {
  const text = `agent-ui — YAML-driven React UI for AI agents

Usage:
  agent-ui emit-schema            Print the JSON Schema for the config
  agent-ui validate <file.yaml>   Validate a YAML config; exits non-zero on errors
`;
  process.stdout.write(text);
}

main();
