/**
 * The agent's identity mark: a rounded square in the agent color with the
 * agent's initial. Used in the top-bar picker and prefixing every shared-history
 * row so conversation ownership is obvious at a glance.
 */
export function AgentGlyph({
  color,
  name,
  size = 18,
}: {
  color: string;
  name: string;
  size?: number;
}) {
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-[5px] font-semibold text-white"
      style={{
        background: color,
        width: size,
        height: size,
        fontSize: Math.round(size * 0.55),
      }}
    >
      {(name || "?").charAt(0).toUpperCase()}
    </span>
  );
}
