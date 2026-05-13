export interface ActionDispatcher {
  invoke(action: string, args?: unknown): Promise<unknown>;
  subscribe?(
    action: string,
    args: unknown,
    onData: (d: unknown) => void,
    onError?: (e: unknown) => void,
  ): () => void;
  has?(action: string): boolean;
}

/** A no-op dispatcher useful for tests and default fallbacks. */
export const nullDispatcher: ActionDispatcher = {
  async invoke() {
    return undefined;
  },
  has() {
    return false;
  },
};
