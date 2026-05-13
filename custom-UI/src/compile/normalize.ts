import type { Page } from "../schema/page.js";
import type { ResolvedConfig, ResolvedWidget } from "./resolve.js";

/** Stage 4: pure defaults / shape normalization on the resolved config. */
export function normalize(resolved: ResolvedConfig): ResolvedConfig {
  const page: Page = {
    ...resolved.page,
    main_menu: resolved.page.main_menu ?? [],
  };
  const widgets: ResolvedWidget[] = resolved.widgets.map((w) => ({
    ...w,
    position: w.position ?? {},
  }));
  return {
    page,
    widgets,
    unknownWidgets: resolved.unknownWidgets,
    diagnostics: resolved.diagnostics,
  };
}
