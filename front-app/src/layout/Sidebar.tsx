import { NavLink } from "react-router-dom";
import {
  Bot,
  KeyRound,
  Monitor,
  Moon,
  Settings,
  Sparkles,
  Sun,
} from "lucide-react";
import { useTheme, type Theme } from "../state/theme.js";

interface NavItem {
  to: string;
  label: string;
  icon: typeof Bot;
}

const ITEMS: NavItem[] = [
  { to: "/", label: "Agents", icon: Bot },
  { to: "/secrets", label: "Secrets", icon: KeyRound },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar(): JSX.Element {
  return (
    <aside className="hidden h-full w-60 shrink-0 flex-col border-r border-border bg-card/40 backdrop-blur supports-[backdrop-filter]:bg-card/30 md:flex">
      <Brand />
      <nav className="flex-1 px-2 py-2">
        <SectionLabel>Navigate</SectionLabel>
        <ul className="space-y-0.5">
          {ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  [
                    "group flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                    isActive
                      ? "bg-secondary/80 text-secondary-foreground"
                      : "text-muted-foreground hover:bg-secondary/40 hover:text-foreground",
                  ].join(" ")
                }
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <Footer />
    </aside>
  );
}

function Brand(): JSX.Element {
  return (
    <div className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-4">
      <span className="grid h-7 w-7 place-items-center rounded-md bg-primary/15 text-primary ring-1 ring-inset ring-primary/30">
        <Sparkles className="h-4 w-4" />
      </span>
      <div className="leading-tight">
        <div className="text-sm font-semibold tracking-tight">
          Agents Console
        </div>
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          v0
        </div>
      </div>
    </div>
  );
}

function Footer(): JSX.Element {
  return (
    <div className="border-t border-border p-2">
      <ThemeToggle />
    </div>
  );
}

function ThemeToggle(): JSX.Element {
  const { theme, cycle } = useTheme();
  const config: Record<Theme, { icon: typeof Sun; label: string }> = {
    light: { icon: Sun, label: "Light" },
    dark: { icon: Moon, label: "Dark" },
    system: { icon: Monitor, label: "System" },
  };
  const Icon = config[theme].icon;
  return (
    <button
      type="button"
      onClick={cycle}
      title={`Theme: ${config[theme].label} (click to cycle)`}
      className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary/40 hover:text-foreground"
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span>{config[theme].label}</span>
    </button>
  );
}

function SectionLabel({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div className="px-2.5 pb-1.5 pt-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
      {children}
    </div>
  );
}
