import { ConfigSchema } from "../schema/index.js";

export function emitSchema(): string {
  return JSON.stringify(
    {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      title: "AgentUIConfig",
      ...ConfigSchema,
    },
    null,
    2,
  );
}
