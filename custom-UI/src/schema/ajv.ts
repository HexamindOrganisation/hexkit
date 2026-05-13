import Ajv, { type ValidateFunction } from "ajv";
import addFormats from "ajv-formats";

const ajv = new Ajv({
  strict: false,
  allErrors: true,
  useDefaults: true,
  removeAdditional: true,
});
addFormats(ajv);

export function compileSchema<T = unknown>(schema: object): ValidateFunction<T> {
  return ajv.compile<T>(schema);
}

export { ajv };
